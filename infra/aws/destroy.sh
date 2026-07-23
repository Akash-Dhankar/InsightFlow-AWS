#!/usr/bin/env bash
# Tear down InsightFlow Minimal AWS stack cleanly (idempotent).
#
# Empties the versioned S3 artifact bucket, then deletes the CloudFormation stack.
# ECR images are removed automatically when EmptyOnDelete=true on the repository.
#
# Usage:
#   ./infra/aws/destroy.sh
#   AWS_REGION=us-east-1 ./infra/aws/destroy.sh
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-insightflow}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-minimal}"

log() { printf '%s\n' "$*"; }
err() { printf 'ERROR: %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

need aws
need python3

export AWS_DEFAULT_REGION="${AWS_REGION}"

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
  aws s3 rm "s3://${bucket}" --recursive --region "${AWS_REGION}" >/dev/null || true

  python3 - "${bucket}" "${AWS_REGION}" <<'PY'
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
    if not chunk:
        continue
    payload = json.dumps({"Objects": chunk, "Quiet": True})
    subprocess.run(
        ["aws", "s3api", "delete-objects", "--bucket", bucket, "--region", region, "--delete", payload],
        check=False,
    )
PY
}

STATUS="$(stack_status)"
if [[ "${STATUS}" == "DOES_NOT_EXIST" ]]; then
  log "Stack ${STACK_NAME} does not exist. Nothing to delete."
  exit 0
fi

log "==> Destroying stack ${STACK_NAME} (status=${STATUS}) in ${AWS_REGION}"

BUCKET="$(stack_output S3BucketName)"
if [[ -z "${BUCKET}" || "${BUCKET}" == "None" ]]; then
  ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
  BUCKET="${PROJECT_NAME}-artifacts-${ACCOUNT_ID}-${AWS_REGION}"
fi
empty_s3_bucket "${BUCKET}"

log "==> Deleting CloudFormation stack"
aws cloudformation delete-stack \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}"

log "==> Waiting for delete to complete..."
aws cloudformation wait stack-delete-complete \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  || die "Stack delete did not complete cleanly. Check CloudFormation events."

log "Stack ${STACK_NAME} deleted."
