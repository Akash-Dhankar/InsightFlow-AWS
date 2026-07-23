# InsightFlow — Minimal AWS Deployment Plan

> **Status:** Phase A **implemented** in-repo (container + S3 wiring + CloudFormation).  
> Deploy to your AWS account with `./infra/aws/deploy.sh` (see [infra/aws/README.md](../infra/aws/README.md)).  
> **Out of scope still:** Terraform, Prometheus/Grafana, Bedrock, Cognito, Step Functions.

This document describes the **smallest useful AWS footprint** for InsightFlow and how it maps to what is now in the repository.

---

## What you have today

```
CSV Upload → Analyzer → Stats/Charts → TF-IDF RAG → Ollama → AI Insights/Q&A → PDF
                                    ↘ (optional) S3 artifacts
                                    ↘ CloudWatch via container stdout
```

Local `streamlit run app.py` still works unchanged when `INSIGHTFLOW_S3_BUCKET` is unset.

---

## Phase A architecture (implemented)

```
User (browser)
      │
      ▼
ALB (HTTP; optional HTTPS via ACM)
      │
      ▼
ECS Fargate ← ECR image (Streamlit)
      │
      ├──► S3 (uploads / reports / charts)
      └──► CloudWatch Logs (+ unhealthy-host alarm)

Ollama: optional via OLLAMA_BASE_URL (EC2 later, or Phase B Bedrock)
```

---

## Repo artifacts for Phase A

| Path | Role |
|------|------|
| `data-analyst-agent/Dockerfile` | Container image for Streamlit |
| `data-analyst-agent/.streamlit/config.toml` | Headless / `0.0.0.0` config |
| `data-analyst-agent/utils/s3_storage.py` | Optional S3 uploads |
| `data-analyst-agent/utils/app_logging.py` | Stdout logging for CloudWatch |
| `infra/aws/cloudformation.yaml` | S3, ECR, ECS (DesiredCount=0), ALB, IAM, Logs, alarm |
| `infra/aws/deploy.sh` | Ordered 3-phase deploy: CFN → image push → scale ECS |
| `infra/aws/build-and-push.sh` | Build/push image only |
| `infra/aws/destroy.sh` | Empty S3 + delete stack |
| `infra/aws/README.md` | Step-by-step deploy guide |
| `docker-compose.yml` | Local container smoke test |

---

## Services included

| AWS service | Role | In template? |
|-------------|------|--------------|
| Amazon S3 | CSVs, PDFs, chart PNGs | Yes |
| Amazon ECR | App image | Yes |
| ECS Fargate | Run Streamlit | Yes |
| ALB | Public access + health checks | Yes |
| CloudWatch Logs | Container logs | Yes |
| CloudWatch Alarm | Unhealthy host count | Yes |
| IAM | Execution + task roles (S3) | Yes |
| ACM | Optional HTTPS | Parameter |
| Route 53 | Custom domain | Manual DNS → ALB |
| EC2 Ollama | Optional LLM host | Documented; not in template |

---

## Definition of done (checklist)

1. Streamlit image builds (`Dockerfile` / `docker compose build`).
2. CloudFormation completes with **DesiredCount=0** (no image pull required).
3. Image pushed to **ECR**, then ECS scaled to **1** and becomes stable.
4. Container reachable via **ALB**.
5. **S3** bucket receives uploads/reports when the app runs on AWS.
6. Logs appear in **CloudWatch** `/ecs/insightflow`.
7. Unhealthy-host **alarm** exists.
8. Deploy/teardown documented in `infra/aws/README.md` (`deploy.sh` / `destroy.sh`).

---

## Ollama note

Phase A does **not** require Ollama in AWS. Upload → analyze → charts → PDF work without it. AI Insights/Q&A need `OLLAMA_BASE_URL` pointing at a reachable Ollama, or Phase B **Bedrock**.

---

## Next phases (not started)

| Phase | Track |
|-------|--------|
| **B** | Bedrock or EC2 Ollama |
| **C** | Terraform modules (replace/augment CFN) |
| **D** | Prometheus + Grafana |
| **E** | Cognito, RDS, Step Functions |

---

## Decision log

| Date | Decision |
|------|----------|
| 2026-07-22 | Start with Minimal AWS planning doc. |
| 2026-07-22 | Implement Phase A: Docker + S3 helpers + CloudFormation + deploy scripts. |
