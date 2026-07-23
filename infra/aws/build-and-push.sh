#!/usr/bin/env bash
# Build the InsightFlow Streamlit image and push it to ECR.
#
# Prerequisites: CloudFormation stack already created (ECR repo exists),
# Docker daemon running, AWS credentials configured.
#
# Usage:
#   ./infra/aws/build-and-push.sh
#   PROJECT_NAME=insightflow AWS_REGION=us-east-1 IMAGE_TAG=latest ./infra/aws/build-and-push.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="${ROOT_DIR}/data-analyst-agent"

PROJECT_NAME="${PROJECT_NAME:-insightflow}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ECR_REPO_NAME="${PROJECT_NAME}-app"

log() { printf '%s\n' "$*"; }
err() { printf 'ERROR: %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

need aws
need docker

if [[ ! -f "${APP_DIR}/Dockerfile" ]]; then
  die "Dockerfile not found at ${APP_DIR}/Dockerfile"
fi

if ! docker info >/dev/null 2>&1; then
  die "Docker daemon is not running. Start Docker Desktop / dockerd, then retry."
fi

export AWS_DEFAULT_REGION="${AWS_REGION}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "AWS credentials not configured. Run: aws configure"

ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

log "==> Ensuring ECR repository exists: ${ECR_REPO_NAME}"
if ! aws ecr describe-repositories \
  --repository-names "${ECR_REPO_NAME}" \
  --region "${AWS_REGION}" >/dev/null 2>&1; then
  die "ECR repo '${ECR_REPO_NAME}' not found in ${AWS_REGION}. Run Phase 1 first: ./infra/aws/deploy.sh (or create the CloudFormation stack)."
fi

log "==> Logging in to ECR (${AWS_REGION})"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}" \
  || die "ECR docker login failed."

log "==> Building image ${ECR_URI}:${IMAGE_TAG}"
docker build \
  -t "${PROJECT_NAME}-app:${IMAGE_TAG}" \
  -t "${ECR_URI}:${IMAGE_TAG}" \
  "${APP_DIR}" \
  || die "docker build failed."

log "==> Pushing ${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:${IMAGE_TAG}" \
  || die "docker push failed."

log "==> Confirming image is visible in ECR"
DIGEST="$(aws ecr describe-images \
  --repository-name "${ECR_REPO_NAME}" \
  --image-ids "imageTag=${IMAGE_TAG}" \
  --region "${AWS_REGION}" \
  --query 'imageDetails[0].imageDigest' \
  --output text 2>/dev/null || true)"

if [[ -z "${DIGEST}" || "${DIGEST}" == "None" ]]; then
  die "Push appeared to succeed but ${ECR_REPO_NAME}:${IMAGE_TAG} is not queryable in ECR yet."
fi

log "==> Done. Image: ${ECR_URI}:${IMAGE_TAG}"
log "    Digest: ${DIGEST}"
