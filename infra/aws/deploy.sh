#!/usr/bin/env bash
# Deploy InsightFlow Minimal AWS (ordered, idempotent).
#
# Phase 1 — CloudFormation with DesiredCount=0 (no image pull required)
# Phase 2 — Build & push Docker image to ECR
# Phase 3 — Scale ECS to DesiredCount=1, force deploy, wait until stable
#
# Usage (from repo root):
#   ./infra/aws/deploy.sh
#   AWS_REGION=us-east-1 ./infra/aws/deploy.sh
#
# Optional:
#   CERTIFICATE_ARN=arn:aws:acm:... ./infra/aws/deploy.sh
#   OLLAMA_BASE_URL=http://10.0.1.20:11434 ./infra/aws/deploy.sh
#   SKIP_BUILD=1 ./infra/aws/deploy.sh          # infra only (still scales if image exists)
#   FORCE_CLEAN=1 ./infra/aws/deploy.sh         # delete failed/rollback stack first
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CFN_TEMPLATE="${ROOT_DIR}/infra/aws/cloudformation.yaml"
BUILD_SCRIPT="${ROOT_DIR}/infra/aws/build-and-push.sh"

PROJECT_NAME="${PROJECT_NAME:-insightflow}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-minimal}"
RUNTIME_DESIRED_COUNT="${RUNTIME_DESIRED_COUNT:-1}"
TASK_CPU="${TASK_CPU:-512}"
TASK_MEMORY="${TASK_MEMORY:-1024}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"
CERTIFICATE_ARN="${CERTIFICATE_ARN:-}"
SKIP_BUILD="${SKIP_BUILD:-0}"
FORCE_CLEAN="${FORCE_CLEAN:-0}"
ECS_STABLE_TIMEOUT_SECONDS="${ECS_STABLE_TIMEOUT_SECONDS:-900}"

CLUSTER_NAME="${PROJECT_NAME}-cluster"
SERVICE_NAME="${PROJECT_NAME}-service"
ECR_REPO_NAME="${PROJECT_NAME}-app"

log()  { printf '%s\n' "$*"; }
err()  { printf 'ERROR: %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

stack_status() {
  aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "DOES_NOT_EXIST"
}

stack_output() {
  local key="$1"
  aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue" \
    --output text 2>/dev/null || true
}

empty_s3_bucket() {
  local bucket="$1"
  [[ -z "${bucket}" || "${bucket}" == "None" ]] && return 0

  if ! aws s3api head-bucket --bucket "${bucket}" --region "${AWS_REGION}" 2>/dev/null; then
    log "    S3 bucket ${bucket} not found (already gone)."
    return 0
  fi

  log "    Emptying s3://${bucket} (including versions)..."
  # Delete current objects
  aws s3 rm "s3://${bucket}" --recursive --region "${AWS_REGION}" >/dev/null || true

  # Delete versioned objects / delete markers if versioning is enabled
  local versions
  versions="$(aws s3api list-object-versions \
    --bucket "${bucket}" \
    --region "${AWS_REGION}" \
    --output json 2>/dev/null || echo '{}')"

  python3 - "${bucket}" "${AWS_REGION}" <<'PY' || true
import json, subprocess, sys
bucket, region = sys.argv[1], sys.argv[2]
raw = subprocess.check_output(
    ["aws", "s3api", "list-object-versions", "--bucket", bucket, "--region", region, "--output", "json"],
    text=True,
)
data = json.loads(raw or "{}")
objects = []
for v in data.get("Versions") or []:
    objects.append({"Key": v["Key"], "VersionId": v["VersionId"]})
for m in data.get("DeleteMarkers") or []:
    objects.append({"Key": m["Key"], "VersionId": m["VersionId"]})
for i in range(0, len(objects), 1000):
    chunk = objects[i:i + 1000]
    payload = json.dumps({"Objects": chunk, "Quiet": True})
    subprocess.run(
        ["aws", "s3api", "delete-objects", "--bucket", bucket, "--region", region, "--delete", payload],
        check=False,
    )
PY
}

wait_stack_deleted() {
  log "    Waiting for stack ${STACK_NAME} to finish deleting..."
  aws cloudformation wait stack-delete-complete \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    || die "Timed out / failed waiting for stack delete. Check CloudFormation events."
}

delete_stack_cleanly() {
  log "==> Cleaning previous stack ${STACK_NAME}"
  local bucket
  bucket="$(stack_output S3BucketName)"
  if [[ -z "${bucket}" || "${bucket}" == "None" ]]; then
    # Fallback to deterministic name if outputs unavailable
    local account
    account="$(aws sts get-caller-identity --query Account --output text)"
    bucket="${PROJECT_NAME}-artifacts-${account}-${AWS_REGION}"
  fi
  empty_s3_bucket "${bucket}"

  aws cloudformation delete-stack \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}"
  wait_stack_deleted
}

recover_failed_stack_if_needed() {
  local status
  status="$(stack_status)"
  case "${status}" in
    DOES_NOT_EXIST)
      return 0
      ;;
    CREATE_COMPLETE|UPDATE_COMPLETE|UPDATE_ROLLBACK_COMPLETE)
      if [[ "${FORCE_CLEAN}" == "1" ]]; then
        delete_stack_cleanly
      fi
      return 0
      ;;
    ROLLBACK_COMPLETE|CREATE_FAILED|ROLLBACK_FAILED|DELETE_FAILED|UPDATE_ROLLBACK_FAILED|UPDATE_FAILED)
      err "Stack ${STACK_NAME} is in ${status}."
      log "Deleting it so deploy can recreate cleanly..."
      delete_stack_cleanly
      return 0
      ;;
    *_IN_PROGRESS)
      die "Stack ${STACK_NAME} is currently ${status}. Wait for it to finish, then re-run ./infra/aws/deploy.sh"
      ;;
    *)
      die "Unsupported stack status ${status}. Inspect in CloudFormation console, then set FORCE_CLEAN=1 to recreate."
      ;;
  esac
}

wait_stack_ready() {
  local status
  status="$(stack_status)"
  case "${status}" in
    CREATE_COMPLETE|UPDATE_COMPLETE)
      log "    Stack status: ${status}"
      return 0
      ;;
    *)
      die "Stack ${STACK_NAME} finished deploy but status is ${status} (expected CREATE_COMPLETE or UPDATE_COMPLETE). Check CloudFormation events."
      ;;
  esac
}

verify_ecr_image() {
  log "==> Verifying ECR image ${ECR_REPO_NAME}:${IMAGE_TAG}"
  if ! aws ecr describe-images \
    --repository-name "${ECR_REPO_NAME}" \
    --image-ids "imageTag=${IMAGE_TAG}" \
    --region "${AWS_REGION}" \
    --query 'imageDetails[0].imageDigest' \
    --output text >/dev/null; then
    die "Image ${ECR_REPO_NAME}:${IMAGE_TAG} not found in ECR. Phase 2 build/push must succeed before scaling ECS."
  fi
  local digest
  digest="$(aws ecr describe-images \
    --repository-name "${ECR_REPO_NAME}" \
    --image-ids "imageTag=${IMAGE_TAG}" \
    --region "${AWS_REGION}" \
    --query 'imageDetails[0].imageDigest' \
    --output text)"
  log "    Found image digest: ${digest}"
}

scale_and_wait_ecs() {
  log "==> Phase 3: Scaling ECS service to ${RUNTIME_DESIRED_COUNT} and waiting for stability"
  aws ecs update-service \
    --cluster "${CLUSTER_NAME}" \
    --service "${SERVICE_NAME}" \
    --desired-count "${RUNTIME_DESIRED_COUNT}" \
    --force-new-deployment \
    --region "${AWS_REGION}" \
    --query 'service.{status:status,desired:desiredCount,running:runningCount}' \
    --output table >/dev/null \
    || die "Failed to update ECS service ${SERVICE_NAME}"

  log "    Waiting up to ${ECS_STABLE_TIMEOUT_SECONDS}s for service to become stable..."
  local start now desired running pending primary_status
  start="$(date +%s)"

  while true; do
    now="$(date +%s)"
    if (( now - start > ECS_STABLE_TIMEOUT_SECONDS )); then
      err "Timed out waiting for ECS service stability."
      aws ecs describe-services \
        --cluster "${CLUSTER_NAME}" \
        --services "${SERVICE_NAME}" \
        --region "${AWS_REGION}" \
        --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,events:events[:5]}' \
        --output json >&2 || true
      die "ECS service did not become stable. Check stopped tasks for CannotPullContainerError / health check failures."
    fi

    desired="$(aws ecs describe-services \
      --cluster "${CLUSTER_NAME}" \
      --services "${SERVICE_NAME}" \
      --region "${AWS_REGION}" \
      --query 'services[0].desiredCount' \
      --output text)"
    running="$(aws ecs describe-services \
      --cluster "${CLUSTER_NAME}" \
      --services "${SERVICE_NAME}" \
      --region "${AWS_REGION}" \
      --query 'services[0].runningCount' \
      --output text)"
    pending="$(aws ecs describe-services \
      --cluster "${CLUSTER_NAME}" \
      --services "${SERVICE_NAME}" \
      --region "${AWS_REGION}" \
      --query 'services[0].pendingCount' \
      --output text)"
    primary_status="$(aws ecs describe-services \
      --cluster "${CLUSTER_NAME}" \
      --services "${SERVICE_NAME}" \
      --region "${AWS_REGION}" \
      --query 'services[0].deployments[?status==`PRIMARY`].rolloutState | [0]' \
      --output text 2>/dev/null || echo "UNKNOWN")"

    log "    desired=${desired} running=${running} pending=${pending} rollout=${primary_status}"

    if [[ "${primary_status}" == "FAILED" ]]; then
      die "ECS PRIMARY deployment rollout FAILED (circuit breaker). Inspect service events and stopped tasks."
    fi

    if [[ "${desired}" == "${RUNTIME_DESIRED_COUNT}" \
       && "${running}" == "${RUNTIME_DESIRED_COUNT}" \
       && "${pending}" == "0" \
       && "${primary_status}" == "COMPLETED" ]]; then
      log "    ECS service is stable."
      return 0
    fi

    # Older accounts / API shapes may omit rolloutState; fall back to count-only + waiter once.
    if [[ "${desired}" == "${RUNTIME_DESIRED_COUNT}" \
       && "${running}" == "${RUNTIME_DESIRED_COUNT}" \
       && "${pending}" == "0" ]] \
       && { [[ "${primary_status}" == "None" ]] || [[ "${primary_status}" == "null" ]] || [[ "${primary_status}" == "UNKNOWN" ]]; }; then
      if aws ecs wait services-stable \
        --cluster "${CLUSTER_NAME}" \
        --services "${SERVICE_NAME}" \
        --region "${AWS_REGION}"; then
        log "    ECS service is stable (waiter confirmed)."
        return 0
      fi
      die "ECS waiter reported the service is not stable. Check service events and stopped tasks."
    fi

    sleep 15
  done
}

# ─── main ───────────────────────────────────────────────────────────────────
need aws
need docker
need python3

if ! docker info >/dev/null 2>&1; then
  die "Docker daemon is not running. Start Docker Desktop / dockerd, then retry."
fi

if [[ ! -f "${CFN_TEMPLATE}" ]]; then
  die "CloudFormation template not found: ${CFN_TEMPLATE}"
fi

export AWS_DEFAULT_REGION="${AWS_REGION}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "AWS credentials not configured. Run: aws configure"
log "==> Account ${ACCOUNT_ID} | region ${AWS_REGION} | stack ${STACK_NAME}"

recover_failed_stack_if_needed

log "==> Resolving default VPC and public subnets"
VPC_ID="$(aws ec2 describe-vpcs \
  --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' \
  --output text)"

if [[ -z "${VPC_ID}" || "${VPC_ID}" == "None" ]]; then
  die "No default VPC found. Create a default VPC in the EC2/VPC console, then retry."
fi

mapfile -t SUBNET_IDS < <(aws ec2 describe-subnets \
  --filters Name=vpc-id,Values="${VPC_ID}" Name=default-for-az,Values=true \
  --query 'Subnets[].SubnetId' \
  --output text | tr '\t' '\n' | sed '/^$/d')

if [[ "${#SUBNET_IDS[@]}" -lt 2 ]]; then
  mapfile -t SUBNET_IDS < <(aws ec2 describe-subnets \
    --filters Name=vpc-id,Values="${VPC_ID}" \
    --query 'Subnets[].SubnetId' \
    --output text | tr '\t' '\n' | sed '/^$/d')
fi

if [[ "${#SUBNET_IDS[@]}" -lt 2 ]]; then
  die "Need at least 2 subnets in VPC ${VPC_ID} for an internet-facing ALB."
fi

declare -A SEEN_AZ
SELECTED_SUBNETS=()
while IFS=$'\t' read -r subnet_id az; do
  [[ -n "${SEEN_AZ[$az]:-}" ]] && continue
  SEEN_AZ[$az]=1
  SELECTED_SUBNETS+=("${subnet_id}")
  [[ "${#SELECTED_SUBNETS[@]}" -eq 2 ]] && break
done < <(aws ec2 describe-subnets \
  --subnet-ids "${SUBNET_IDS[@]}" \
  --query 'Subnets[].[SubnetId,AvailabilityZone]' \
  --output text)

if [[ "${#SELECTED_SUBNETS[@]}" -lt 2 ]]; then
  die "Could not find subnets in two different AZs."
fi

SUBNET_CSV="$(IFS=,; echo "${SELECTED_SUBNETS[*]}")"
log "    VPC=${VPC_ID}"
log "    Subnets=${SUBNET_CSV}"

# ─── Phase 1 ────────────────────────────────────────────────────────────────
log "==> Phase 1: Deploying CloudFormation with DesiredCount=0"
aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${CFN_TEMPLATE}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    "ProjectName=${PROJECT_NAME}" \
    "VpcId=${VPC_ID}" \
    "PublicSubnetIds=${SUBNET_CSV}" \
    "ImageTag=${IMAGE_TAG}" \
    "DesiredCount=0" \
    "TaskCpu=${TASK_CPU}" \
    "TaskMemory=${TASK_MEMORY}" \
    "OllamaBaseUrl=${OLLAMA_BASE_URL}" \
    "OllamaModel=${OLLAMA_MODEL}" \
    "CertificateArn=${CERTIFICATE_ARN}" \
  --no-fail-on-empty-changeset \
  || die "CloudFormation deploy failed. Check stack events for ${STACK_NAME}."

wait_stack_ready
log "    Phase 1 complete (infra up, no tasks running)."

# ─── Phase 2 ────────────────────────────────────────────────────────────────
if [[ "${SKIP_BUILD}" != "1" ]]; then
  log "==> Phase 2: Building and pushing Docker image to ECR"
  PROJECT_NAME="${PROJECT_NAME}" \
  AWS_REGION="${AWS_REGION}" \
  IMAGE_TAG="${IMAGE_TAG}" \
    bash "${BUILD_SCRIPT}" \
    || die "Docker build/push failed."
else
  log "==> Phase 2: SKIP_BUILD=1 — skipping docker build/push"
fi

verify_ecr_image

# ─── Phase 3 ────────────────────────────────────────────────────────────────
scale_and_wait_ecs

log "==> Stack outputs"
aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' \
  --output table

APP_URL="$(stack_output AppUrl)"
BUCKET="$(stack_output S3BucketName)"

log ""
log "InsightFlow Minimal AWS deploy finished."
log "Open:  ${APP_URL}"
log "S3:    s3://${BUCKET}/insightflow/"
log "Logs:  CloudWatch log group /ecs/${PROJECT_NAME}"
log "Note:  AI Insights need a reachable Ollama (OLLAMA_BASE_URL) or Phase B Bedrock."
log ""
log "To tear down later: ./infra/aws/destroy.sh"
