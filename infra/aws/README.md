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

## Prerequisites

- AWS account + credentials (`aws configure` or env vars)
- [Docker](https://docs.docker.com/get-docker/)
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- A **default VPC** with subnets in at least two AZs (common for new accounts)

Optional:

- ACM certificate ARN in the same region for HTTPS
- Ollama on EC2 (or local) reachable from the task — otherwise charts/stats/PDF still work; AI Insights show offline

---

## Quick deploy

From the repo root:

```bash
chmod +x infra/aws/deploy.sh infra/aws/build-and-push.sh

# Optional env
export AWS_REGION=us-east-1
# export CERTIFICATE_ARN=arn:aws:acm:us-east-1:123456789012:certificate/...
# export OLLAMA_BASE_URL=http://10.0.1.20:11434

./infra/aws/deploy.sh
```

The script will:

1. Detect the default VPC + two public subnets  
2. Deploy `infra/aws/cloudformation.yaml`  
3. Build `data-analyst-agent/Dockerfile` and push to ECR  
4. Force a new ECS deployment  
5. Print the ALB URL and other outputs  

Open the **AppUrl** from the stack outputs (HTTP on port 80).

---

## Local container smoke test (no AWS)

```bash
docker compose up --build
```

Then open http://localhost:8501  

To exercise S3 from the local container:

```bash
export INSIGHTFLOW_S3_BUCKET=your-bucket-name
export AWS_DEFAULT_REGION=us-east-1
# ensure AWS credentials are available
docker compose up --build
```

Without `INSIGHTFLOW_S3_BUCKET`, the app behaves exactly as before (session-only uploads/downloads).

---

## Rebuild / update only the image

```bash
export AWS_REGION=us-east-1
./infra/aws/build-and-push.sh

aws ecs update-service \
  --cluster insightflow-cluster \
  --service insightflow-service \
  --force-new-deployment \
  --region "$AWS_REGION"
```

---

## Environment variables (app)

| Variable | Default | Purpose |
|----------|---------|---------|
| `INSIGHTFLOW_S3_BUCKET` | _(empty = S3 off)_ | Artifact bucket |
| `INSIGHTFLOW_S3_PREFIX` | `insightflow` | Key prefix |
| `AWS_DEFAULT_REGION` | `us-east-1` | S3 / AWS SDK region |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model name |
| `INSIGHTFLOW_LOG_LEVEL` | `INFO` | Stdout logs → CloudWatch |

On ECS these are set by CloudFormation (bucket + region + Ollama URL).

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

With a certificate, both HTTP (80) and HTTPS (443) forward to the app. Point DNS at the ALB when you add a custom domain.

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
- [ ] Image exists in ECR `insightflow-app`  
- [ ] ALB URL loads Streamlit  
- [ ] Upload a CSV → object appears under `insightflow/uploads/` when S3 is enabled  
- [ ] Generate PDF → object under `insightflow/reports/`  
- [ ] Logs appear in CloudWatch group `/ecs/insightflow`  
- [ ] Alarm `insightflow-unhealthy-hosts` exists  

---

## Tear down

```bash
# Empty the artifact bucket first (Retain policy keeps the bucket on stack delete)
aws s3 rm "s3://insightflow-artifacts-<account>-<region>" --recursive

aws cloudformation delete-stack --stack-name insightflow-minimal --region "$AWS_REGION"
```

Delete the ECR images if you no longer need them.

---

## Cost notes

Stop or set `DesiredCount=0` when not demoing. Ollama on always-on EC2 is usually the largest optional cost; S3 + CloudWatch Logs are small at portfolio scale.
