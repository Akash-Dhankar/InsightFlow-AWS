# InsightFlow — Minimal AWS deploy guide (Phase A)

This guide deploys InsightFlow with:

- **ECR** — Streamlit Docker image  
- **ECS Fargate** — runs the container  
- **ALB** — public HTTP (optional HTTPS via ACM)  
- **S3** — CSVs, PDFs, chart PNGs  
- **CloudWatch Logs** + unhealthy-host **alarm**  
- **IAM** — least-privilege task role for S3  

Terraform, Prometheus/Grafana, Bedrock, and Cognito are **not** in this phase.

---

## How deploy ordering works (important)

`./infra/aws/deploy.sh` uses a **3-phase** order so CloudFormation never waits on a missing image:

| Phase | What happens |
|-------|----------------|
| **1** | CloudFormation creates/updates infra with **`DesiredCount=0`** → stack reaches `CREATE_COMPLETE` / `UPDATE_COMPLETE` without pulling from ECR |
| **2** | Docker image is built and pushed to ECR; script verifies the tag exists |
| **3** | ECS desired count is set to **1**, force-new-deployment runs, script waits until the service is stable |

This avoids `CannotPullContainerError` during stack creation.

---

## Prerequisites

- AWS account + credentials (`aws configure` or env vars)
- [Docker](https://docs.docker.com/get-docker/) running
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- A **default VPC** with subnets in at least two AZs (common for new accounts)

Optional:

- ACM certificate ARN in the same region for HTTPS
- Ollama on EC2 (or local) reachable from the task — otherwise charts/stats/PDF still work; AI Insights show offline

---

## Quick deploy

From the **repo root** on your laptop:

```bash
chmod +x infra/aws/deploy.sh infra/aws/build-and-push.sh infra/aws/destroy.sh

export AWS_REGION=us-east-1
# Optional:
# export CERTIFICATE_ARN=arn:aws:acm:us-east-1:123456789012:certificate/...
# export OLLAMA_BASE_URL=http://10.0.1.20:11434

./infra/aws/deploy.sh
```

When it finishes, open the printed **AppUrl**.

### If a previous deploy is stuck / rolled back

```bash
# Delete failed stack (empties S3 first), then redeploy
FORCE_CLEAN=1 ./infra/aws/deploy.sh
```

Or tear down fully:

```bash
./infra/aws/destroy.sh
./infra/aws/deploy.sh
```

---

## Local container smoke test (no AWS)

```bash
docker compose up --build
```

Then open http://localhost:8501  

Without `INSIGHTFLOW_S3_BUCKET`, the app keeps session-only uploads/downloads.

---

## Rebuild / update only the image

```bash
export AWS_REGION=us-east-1
./infra/aws/build-and-push.sh

aws ecs update-service \
  --cluster insightflow-cluster \
  --service insightflow-service \
  --force-new-deployment \
  --desired-count 1 \
  --region "$AWS_REGION"

aws ecs wait services-stable \
  --cluster insightflow-cluster \
  --services insightflow-service \
  --region "$AWS_REGION"
```

Or simply re-run `./infra/aws/deploy.sh` (idempotent).

---

## Environment variables (app)

| Variable | Default | Purpose |
|----------|---------|---------|
| `INSIGHTFLOW_S3_BUCKET` | _(empty = S3 off)_ | Artifact bucket |
| `INSIGHTFLOW_S3_PREFIX` | `insightflow` | Key prefix |
| `AWS_DEFAULT_REGION` | `us-east-1` | S3 / AWS SDK region |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model name |
| `INSIGHTFLOW_LOG_LEVEL` | `INFO` | Stdout logs → CloudWatch |

On ECS these are set by CloudFormation (bucket + region + Ollama URL).

### Deploy script knobs

| Variable | Default | Purpose |
|----------|---------|---------|
| `AWS_REGION` | `us-east-1` | Deploy region |
| `RUNTIME_DESIRED_COUNT` | `1` | Tasks after image push |
| `SKIP_BUILD` | `0` | Skip docker build/push |
| `FORCE_CLEAN` | `0` | Delete healthy stack before recreate |
| `ECS_STABLE_TIMEOUT_SECONDS` | `900` | Max wait for ECS stability |

---

## S3 layout

```
s3://<bucket>/insightflow/
  uploads/YYYY/MM/DD/<timestamp>_<file>.csv
  reports/YYYY/MM/DD/<timestamp>_insightflow_report_....pdf
  charts/YYYY/MM/DD/<timestamp>_histogram_....png
```

---

## HTTPS and custom domain

1. Request/validate a certificate in **ACM** (same region as the stack).  
2. Redeploy with `CERTIFICATE_ARN=arn:aws:acm:...`.  
3. Point Route 53 (or any DNS) at the ALB DNS name.  

With a certificate, both HTTP (80) and HTTPS (443) forward to the app.

---

## Ollama on AWS (optional Minimal add-on)

1. Launch a small EC2 in the **same VPC**.  
2. Install Ollama and pull `qwen2.5:3b`.  
3. Security group: allow TCP `11434` **only** from the ECS service security group.  
4. Redeploy with `OLLAMA_BASE_URL=http://<private-ip>:11434`.  

Or defer LLM to Phase B (**Bedrock**).

---

## Verify “done” checklist

- [ ] Stack `insightflow-minimal` is `CREATE_COMPLETE` / `UPDATE_COMPLETE`  
- [ ] Image exists in ECR `insightflow-app:latest`  
- [ ] ECS service desired/running = 1 and stable  
- [ ] ALB URL loads Streamlit  
- [ ] Upload a CSV → object under `insightflow/uploads/`  
- [ ] Generate PDF → object under `insightflow/reports/`  
- [ ] Logs in CloudWatch group `/ecs/insightflow`  

---

## Tear down

```bash
./infra/aws/destroy.sh
```

This empties the versioned S3 bucket, then deletes the CloudFormation stack (ECR images are cleared via `EmptyOnDelete`).

---

## Cost notes

Stop billing for Fargate when not demoing:

```bash
aws ecs update-service \
  --cluster insightflow-cluster \
  --service insightflow-service \
  --desired-count 0 \
  --region "$AWS_REGION"
```
