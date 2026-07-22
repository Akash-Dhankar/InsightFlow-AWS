#!/usr/bin/env bash
# Build the InsightFlow Streamlit image and push it to ECR.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="${ROOT_DIR}/data-analyst-agent"

PROJECT_NAME="${PROJECT_NAME:-insightflow}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-minimal}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need aws
need docker

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-app"

echo "==> Ensuring ECR repository exists (via stack or create-on-demand)"
if ! aws ecr describe-repositories --repository-names "${PROJECT_NAME}-app" --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "ECR repo ${PROJECT_NAME}-app not found. Deploy the CloudFormation stack first (./deploy.sh), or create the repo manually."
  exit 1
fi

echo "==> Logging in to ECR (${AWS_REGION})"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "==> Building image ${ECR_URI}:${IMAGE_TAG}"
docker build -t "${PROJECT_NAME}-app:${IMAGE_TAG}" -t "${ECR_URI}:${IMAGE_TAG}" "${APP_DIR}"

echo "==> Pushing ${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:${IMAGE_TAG}"

echo "==> Done. Image: ${ECR_URI}:${IMAGE_TAG}"
echo "    If the ECS service is already running, force a new deployment:"
echo "    aws ecs update-service --cluster ${PROJECT_NAME}-cluster --service ${PROJECT_NAME}-service --force-new-deployment --region ${AWS_REGION}"
