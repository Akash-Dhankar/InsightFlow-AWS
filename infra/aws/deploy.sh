#!/usr/bin/env bash
# Deploy InsightFlow Minimal AWS stack (S3, ECR, ECS Fargate, ALB, CloudWatch).
#
# Usage:
#   ./infra/aws/deploy.sh
#   AWS_REGION=us-east-1 CERTIFICATE_ARN=arn:aws:acm:... ./infra/aws/deploy.sh
#
# Prerequisites: aws CLI, docker, credentials with rights to create the stack resources.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CFN_TEMPLATE="${ROOT_DIR}/infra/aws/cloudformation.yaml"
BUILD_SCRIPT="${ROOT_DIR}/infra/aws/build-and-push.sh"

PROJECT_NAME="${PROJECT_NAME:-insightflow}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-minimal}"
DESIRED_COUNT="${DESIRED_COUNT:-1}"
TASK_CPU="${TASK_CPU:-512}"
TASK_MEMORY="${TASK_MEMORY:-1024}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"
CERTIFICATE_ARN="${CERTIFICATE_ARN:-}"
SKIP_BUILD="${SKIP_BUILD:-0}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need aws
need docker

export AWS_DEFAULT_REGION="${AWS_REGION}"

echo "==> Using account $(aws sts get-caller-identity --query Account --output text) in ${AWS_REGION}"

echo "==> Resolving default VPC and public subnets"
VPC_ID="$(aws ec2 describe-vpcs \
  --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' \
  --output text)"

if [[ -z "${VPC_ID}" || "${VPC_ID}" == "None" ]]; then
  echo "No default VPC found. Create a default VPC or edit this script to pass VpcId/subnets." >&2
  exit 1
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
  echo "Need at least 2 subnets in VPC ${VPC_ID} for an internet-facing ALB." >&2
  exit 1
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
  echo "Could not find subnets in two different AZs." >&2
  exit 1
fi

SUBNET_CSV="$(IFS=,; echo "${SELECTED_SUBNETS[*]}")"
echo "    VPC=${VPC_ID}"
echo "    Subnets=${SUBNET_CSV}"

echo "==> Deploying CloudFormation stack ${STACK_NAME}"
aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${CFN_TEMPLATE}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    "ProjectName=${PROJECT_NAME}" \
    "VpcId=${VPC_ID}" \
    "PublicSubnetIds=${SUBNET_CSV}" \
    "ImageTag=${IMAGE_TAG}" \
    "DesiredCount=${DESIRED_COUNT}" \
    "TaskCpu=${TASK_CPU}" \
    "TaskMemory=${TASK_MEMORY}" \
    "OllamaBaseUrl=${OLLAMA_BASE_URL}" \
    "OllamaModel=${OLLAMA_MODEL}" \
    "CertificateArn=${CERTIFICATE_ARN}" \
  --no-fail-on-empty-changeset

if [[ "${SKIP_BUILD}" != "1" ]]; then
  echo "==> Building and pushing container image"
  PROJECT_NAME="${PROJECT_NAME}" AWS_REGION="${AWS_REGION}" IMAGE_TAG="${IMAGE_TAG}" \
    bash "${BUILD_SCRIPT}"

  echo "==> Forcing ECS service to pull the new image"
  aws ecs update-service \
    --cluster "${PROJECT_NAME}-cluster" \
    --service "${PROJECT_NAME}-service" \
    --force-new-deployment \
    --region "${AWS_REGION}" >/dev/null
fi

echo "==> Stack outputs"
aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' \
  --output table

APP_URL="$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='AppUrl'].OutputValue" \
  --output text)"

echo
echo "InsightFlow Minimal AWS deploy finished."
echo "Open: ${APP_URL}"
echo "Logs: /ecs/${PROJECT_NAME} in CloudWatch"
echo "Note: AI Insights need a reachable Ollama (set OLLAMA_BASE_URL) or Phase B Bedrock."
