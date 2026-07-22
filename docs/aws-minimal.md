# InsightFlow — Minimal AWS Deployment Plan

> **Status:** Analysis / planning only. No application code changes in this phase.  
> **Track:** Minimal AWS (Phase A) — complete this first; Terraform, Prometheus/Grafana, Bedrock, and async pipelines come later.

This document describes the **smallest useful AWS footprint** for InsightFlow so you can honestly say the app is deployed on AWS with object storage, containers, logging, and HTTPS — without rewriting the Streamlit app or adopting a full microservices design.

---

## What you have today (local)

```
CSV Upload → Analyzer → Stats/Charts → TF-IDF RAG → Ollama (local) → AI Insights/Q&A → PDF
```

Everything runs in-process in Streamlit. Uploaded CSVs, charts, and PDFs are ephemeral (session / local disk). The LLM depends on a **local Ollama daemon**.

---

## Goal of Minimal AWS

Ship a **portfolio-ready cloud demo** with the least new infrastructure:

| Outcome | How |
|---------|-----|
| App runs on AWS | Streamlit container on **App Runner** or **ECS Fargate** |
| Files persist | **S3** for CSVs / PDFs / chart images (when wired later) |
| Ops visibility | **CloudWatch** Logs (+ basic metrics/alarms) |
| Secure public URL | **ALB** (if ECS) or App Runner HTTPS + optional **Route 53** + **ACM** |
| Images versioned | **ECR** for the Docker image |

**Out of scope for this phase:** Terraform, Prometheus/Grafana, Bedrock, Lambda/Step Functions, Cognito, RDS, OpenSearch, EKS, SageMaker.

---

## Recommended minimal architecture

```
User (browser)
      │
      ▼
HTTPS (ACM cert) ─── App Runner  OR  ALB → ECS Fargate
      │                      │
      │                      ▼
      │               Streamlit container (ECR image)
      │                      │
      ├──────────────────────┼──► S3 (uploads, PDFs, charts)   [Phase A target]
      │                      │
      └──────────────────────┴──► CloudWatch Logs / Metrics

Ollama options (pick one for Minimal):
  A) Keep Ollama on a small EC2 in the same VPC (app talks to it privately)
  B) Run insights/Q&A only when Ollama is reachable; document local-AI fallback
  C) Defer cloud LLM to Phase B (Bedrock) — Minimal can still demo upload/analyze/charts/PDF
```

### Why this shape?

- Matches the current **monolith Streamlit** design — no forced rewrite.
- Uses standard AWS building blocks recruiters recognize.
- Leaves a clean upgrade path to Terraform, Bedrock, and observability later.

---

## Services to include (Minimal only)

| AWS service | Role for InsightFlow | Difficulty |
|-------------|----------------------|------------|
| **Amazon S3** | Store uploaded CSVs, generated PDFs, chart PNGs | Easy |
| **Amazon ECR** | Docker image registry for the Streamlit app | Easy |
| **AWS App Runner** *or* **ECS Fargate** | Run the Streamlit container without managing servers | Easy–medium |
| **Application Load Balancer (ALB)** | HTTPS, health checks (mainly if using ECS) | Easy–medium |
| **Amazon CloudWatch Logs** | App logs, errors, RAG/LLM failure traces | Easy |
| **CloudWatch Metrics + Alarms** | Request count, latency, error rate; optional “Ollama down” | Easy |
| **AWS IAM** | Least-privilege role: app → S3, logs, (optional) EC2/Ollama network | Easy |
| **AWS Certificate Manager (ACM)** | Free TLS certificates | Easy |
| **Amazon Route 53** | Optional custom domain | Easy |
| **Amazon EC2** (optional) | Host Ollama if you want AI insights in the cloud without Bedrock yet | Easy–medium |
| **AWS Secrets Manager** | Optional; useful if you add API keys / DB later | Easy |

### App Runner vs ECS Fargate (Minimal choice)

| | **App Runner** | **ECS Fargate** |
|--|----------------|-----------------|
| Setup | Fewer knobs; good first deploy | More control; closer to “real” production patterns |
| Networking to private Ollama EC2 | Harder / limited VPC options depending on setup | Natural (same VPC, security groups) |
| Resume story | “Deployed containerized Streamlit on AWS” | “ECS, ALB, IAM, VPC-aware deploy” |
| **Suggestion** | Use App Runner if Ollama stays local or AI is deferred | Prefer **ECS Fargate** if Ollama will live on EC2 in a VPC |

For InsightFlow, **ECS Fargate + S3 + CloudWatch (+ optional EC2 for Ollama)** is the stronger Minimal story if you want cloud AI soon. **App Runner + S3 + CloudWatch** is fine if the first milestone is “app online + files in S3.”

---

## The Ollama constraint (honest Minimal guidance)

Ollama expects a **daemon on a machine**, not a pure serverless API.

| Approach | Fits Minimal? | Notes |
|----------|---------------|-------|
| **EC2 + Ollama** next to ECS | Yes | Small instance in private subnet; Streamlit calls `http://ollama:11434` |
| **Bedrock** instead of Ollama | Phase B | Best long-term managed LLM; not required for Minimal deploy |
| **Local Ollama only** while app is on AWS | Weak demo | Charts/stats/PDF work; AI features fail unless tunnel/VPN |
| **SageMaker endpoints** | No | Overkill for this app |

**Practical Minimal recommendation:** Deploy Streamlit + S3 + CloudWatch first. Document Ollama as either (1) EC2 sidecar in the same VPC, or (2) Phase B Bedrock swap. Do not block Phase A on rewriting `utils/llm.py`.

---

## What “done” looks like for Minimal AWS

You can claim this when the following are true:

1. Streamlit image builds and is pushed to **ECR**.
2. Container runs on **App Runner or ECS Fargate** with a public HTTPS URL.
3. At least one **S3 bucket** exists for artifacts (even if app wiring is thin at first).
4. Application stdout/stderr (or structured logs) appear in **CloudWatch Logs**.
5. Optional: one CloudWatch **alarm** on 5xx / unhealthy target / high error rate.
6. README (or this doc’s “Deploy notes”) explains how to open the URL and where files land in S3.
7. **No** Terraform / Prometheus / Grafana / Cognito / Step Functions required yet.

Portfolio one-liner:

> Deployed InsightFlow on AWS using a containerized Streamlit app (ECS Fargate / App Runner), S3 for artifacts, CloudWatch for logs/metrics, and HTTPS.

---

## Suggested implementation order (still no code in this doc)

When you choose to implement Phase A, keep changes isolated:

1. **Dockerfile** for `data-analyst-agent` (new file; do not change analyzer/RAG logic).
2. **ECR** repository + image push.
3. **S3** bucket + IAM role for the task/service (`s3:PutObject` / `GetObject` on that bucket only).
4. **ECS Fargate** service (or App Runner) listening on Streamlit port `8501`.
5. **ALB + ACM** (ECS path) or App Runner managed HTTPS.
6. **CloudWatch** log group wired to the container.
7. Optional **EC2** Ollama + security group allowing only the app SG on port `11434`.
8. Thin S3 helpers (new module) for upload/PDF persistence — avoid scattering AWS calls through `app.py` until needed.

Keep existing modules (`analyzer.py`, `charts.py`, `rag.py`, `llm.py`, `pdf_report.py`) behavior-compatible so local `streamlit run app.py` still works.

---

## What to defer (next tracks)

After Minimal is complete, revisit in order:

| Phase | Track | Adds |
|-------|--------|------|
| **B** | Cloud AI | Bedrock *or* documented EC2 Ollama; IAM for model invoke |
| **C** | IaC | Terraform modules for S3, ECR, ECS/ALB, IAM, log groups |
| **D** | Observability | Prometheus metrics + Grafana (or AMP + Managed Grafana) alongside CloudWatch |
| **E** | Medium product | Cognito, RDS/DynamoDB history, SQS / Step Functions async PDF pipeline |

See the comparison below so Phase A stays intentionally small.

### Minimal vs later options

| Idea | In Minimal? | Verdict |
|------|-------------|---------|
| S3 + ECS/App Runner + CloudWatch | **Yes** | High fit, simple |
| ALB + ACM + Route 53 | Optional yes | HTTPS / custom domain |
| EC2 Ollama | Optional | Keep local LLM story on AWS |
| Bedrock | Later | High fit for real cloud AI |
| Terraform | Later | High fit once deploy is stable |
| Prometheus + Grafana | Later | Good SRE story; medium effort |
| Step Functions + Lambda | Later | Good medium project; more moving parts |
| EKS / SageMaker | No | Usually overkill for Streamlit-only |

---

## Cost & ops expectations (rough)

- **App Runner / Fargate:** pay while the service runs (scale-to-zero options vary; Fargate typically billed for running tasks).
- **S3:** cheap for portfolio-scale CSVs/PDFs.
- **CloudWatch:** logs storage + optional custom metrics; start with logs only if budgeting tightly.
- **EC2 for Ollama:** usually the largest ongoing cost if always-on; stop the instance when not demoing.
- **ACM / Route 53:** cert free; hosted zone has a small monthly cost.

Minimal tip: use a single region, one small Fargate task (or App Runner), one S3 bucket, and stop Ollama EC2 when idle.

---

## Security checklist (Minimal)

- Public ALB/App Runner only exposes Streamlit; no open SSH to Ollama EC2 from `0.0.0.0/0`.
- Task role: S3 bucket access only — no `AdministratorAccess`.
- Prefer private subnet for Ollama EC2; egress only as needed for model pulls.
- Do not commit AWS keys; use IAM roles for the running task.
- If you add Secrets Manager later, load secrets at runtime — never bake into the image.

---

## Resume / interview talking points

- Containerized a Streamlit analytics app and deployed it on **ECS Fargate / App Runner**.
- Used **S3** for durable uploads and generated reports.
- Centralized logs in **CloudWatch**; basic health/error alarms.
- Explained the **Ollama vs managed LLM** tradeoff and why Minimal keeps the app shape intact.
- Clear roadmap: Terraform → Bedrock or EC2 Ollama → Prometheus/Grafana.

---

## Decision log

| Date | Decision |
|------|----------|
| 2026-07-22 | Start with **Minimal AWS** only (this document). |
| — | Defer Terraform, Prometheus/Grafana, Bedrock, Cognito, Step Functions until Minimal is complete. |

When Phase A is implemented, update this file with the actual service names (cluster, bucket, URL) and mark checklist items done — still prefer new files over invasive edits to core analysis code.
