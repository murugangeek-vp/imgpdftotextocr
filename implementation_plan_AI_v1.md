# Enterprise-Grade OCR Platform — APPROVED Implementation Plan

> **Status: ✅ APPROVED — Implementation in progress**

---

## Finalized Decisions

| Decision | Choice |
|----------|--------|
| OCR Engine | Self-hosted TrOCR + PaddleOCR via NVIDIA Triton |
| LLM | OpenAI GPT-4o (primary) + Ollama Llama 3.2:1b (fallback) with smart model routing |
| Tier Config | Dynamically configurable via DB (hot-reload, no restart/redeploy required) |
| Auth (Dev/Local) | Self-hosted Keycloak |
| Auth (Production) | AWS Cognito |
| Payment | Stripe (global) + Razorpay (India) — both |
| Public UI | Next.js (React) — production-grade |
| Admin UI | Streamlit — internal dashboard only |
| Indian Languages | All 22 scheduled languages (Phase 1) |
| Ingestion Service | Python (FastAPI) |
| LLM Observability | Langfuse (Docker locally, EC2 in production) |
| GPU (Prod) | AWS g5.xlarge Spot (~$0.40/hr), max 10 nodes |
| Data Policy | User-informed in UI; AES-256 at rest, TLS 1.3 in transit |

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         PUBLIC INTERNET                                   │
│  [Next.js Web App]  [Mobile API Clients]  [Third-party REST Clients]     │
└────────────────────┬────────────────────────────────────────────────────┘
                     │ HTTPS / WebSocket / SSE
                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│              EDGE (AWS CloudFront + WAF / Nginx locally)                  │
│     DDoS Protection │ TLS Termination │ Geo-blocking │ Bot Defense       │
└────────────────────┬────────────────────────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│              API GATEWAY (Kong)                                           │
│   JWT Auth │ Rate Limiting │ Request Routing │ CORS │ Throttling         │
└──┬──────────┬──────────┬──────────┬─────────────────────────────────────┘
   │          │          │          │
   ▼          ▼          ▼          ▼
[auth]   [ingestion]  [result]   [chat]      ← FastAPI microservices
   │          │          │          │          (gRPC inter-service)
   ▼          │          ▼          ▼
[Keycloak/   │       [MongoDB]  [OpenAI GPT-4o]
 Cognito]    │                  [Ollama Llama3.2:1b]
             │                  [Langfuse Tracer]
             ▼
      [quota-service] ← Redis (per session/day/week/month counters)
             │
             ▼ (if quota OK)
      [MinIO / S3]  ← presigned URL direct upload
             │
             ▼
      [notification-service] ← SSE real-time status to browser
             │
      ┌──────┴───────────────────────────────────────┐
      │           Apache Kafka                       │
      │  Topics: ocr.jobs.pending                    │
      │          ocr.jobs.completed                  │
      │          ocr.jobs.failed                     │
      │          quota.alerts                        │
      └──────────────────┬───────────────────────────┘
                         │
                         ▼
      ┌──────────────────────────────────────────────┐
      │       OCR Worker Pool (KEDA auto-scaled)     │
      │                                              │
      │  [PDF Splitter (PyMuPDF, CPU)]               │
      │       ↓                                      │
      │  [Preprocessor (OpenCV: deskew, binarize)]   │
      │       ↓                                      │
      │  [Redis Hash Dedup check]                    │
      │       ↓ (cache miss)                         │
      │  [Triton gRPC Client]                        │
      │       ↓                                      │
      │  [Post-processor: LayoutLM + spell-check]    │
      │       ↓                                      │
      │  [Result Publisher → Kafka → result-service] │
      └──────────────────────────────────────────────┘
                         │
                         ▼
      ┌──────────────────────────────────────────────┐
      │   NVIDIA Triton Inference Server (GPU)       │
      │   ├── ocr_detection (PaddleOCR → ONNX)      │
      │   ├── ocr_recognition (TrOCR → TensorRT)    │
      │   └── ocr_ensemble (BLS pipeline)            │
      └──────────────────────────────────────────────┘
                         │
      ┌──────────────────────────────────────────────┐
      │          OBSERVABILITY STACK                 │
      │  Langfuse │ RAGAS │ Prometheus │ Grafana     │
      │  Jaeger (traces) │ ELK (logs)               │
      └──────────────────────────────────────────────┘
```

---

## Dynamic Tier Configuration

Tier limits are stored in MongoDB `tier_configs` collection and cached in Redis with a 60-second TTL.
**No server restart or redeployment required** — update the DB record and all services pick it up within 60 seconds.

```json
[
  {
    "tier": "free",
    "version": 1,
    "limits": {
      "pages_per_session": 5,
      "pages_per_day": 5,
      "pages_per_week": 20,
      "pages_per_month": 50,
      "max_file_size_mb": 10,
      "max_pages_per_pdf": 5,
      "concurrent_sessions": 1,
      "result_retention_hours": 24
    }
  },
  {
    "tier": "basic",
    "version": 1,
    "limits": {
      "pages_per_session": 20,
      "pages_per_day": 100,
      "pages_per_week": 500,
      "pages_per_month": 2000,
      "max_file_size_mb": 50,
      "max_pages_per_pdf": 5,
      "concurrent_sessions": 5,
      "result_retention_days": 30
    }
  },
  {
    "tier": "pro",
    "version": 1,
    "limits": {
      "pages_per_session": -1,
      "pages_per_day": -1,
      "pages_per_week": -1,
      "pages_per_month": -1,
      "max_file_size_mb": 100,
      "max_pages_per_pdf": 5,
      "concurrent_sessions": 20,
      "result_retention_days": 90
    }
  }
]
```

---

## LLM Smart Model Routing

```
User Chat Request
      │
      ▼
[model-router]
      ├── If: OpenAI API healthy + user is paid tier → GPT-4o
      ├── If: OpenAI API rate-limited / error → Ollama Llama 3.2:1b (fallback)
      ├── If: user is free tier + low complexity → Ollama Llama 3.2:1b (cost saving)
      └── All calls traced in Langfuse with model tag
```

---

## Project File Structure

```
imgpdftotextocr/
├── .env.local                          # Local env (gitignored)
├── .env.production.template            # Production env template
├── docker-compose.yml                  # Full local stack
├── docker-compose.override.yml         # Dev hot-reload overrides
├── Makefile                            # make dev, make test, make build
│
├── services/
│   ├── auth-service/                   # FastAPI + Keycloak/Cognito
│   ├── ingestion-service/              # FastAPI + MinIO/S3 presigned
│   ├── quota-service/                  # FastAPI + Redis counters
│   ├── ocr-worker/                     # Async Kafka consumer + Triton
│   ├── triton-server/                  # NVIDIA Triton + models
│   ├── result-service/                 # FastAPI + MongoDB
│   ├── notification-service/           # FastAPI SSE
│   ├── chat-service/                   # FastAPI + LangChain + routing
│   ├── admin-service/                  # Streamlit dashboard
│   └── web-app/                        # Next.js public UI
│
├── shared/
│   ├── proto/                          # .proto gRPC contracts
│   ├── models/                         # Shared Pydantic schemas
│   └── kafka/                          # Topic definitions
│
├── observability/
│   ├── langfuse/
│   ├── prometheus/
│   ├── grafana/dashboards/
│   └── jaeger/
│
├── k8s/
│   ├── local/                          # k3d manifests
│   └── production/                     # EKS manifests + Helm
│
├── infrastructure/
│   ├── local/k3d-config.yaml
│   └── aws/terraform/
│
├── docs/
│   ├── architecture/
│   ├── deployment/
│   ├── security/
│   └── governance/dos-and-donts.md
│
└── tests/
    ├── unit/
    ├── integration/
    ├── load/                           # k6 scripts
    └── security/                       # OWASP ZAP
```

---

## Implementation Phases

### Phase 1 — Foundation & Local Dev (Weeks 1–3)
- Monorepo scaffolding + Docker Compose full stack
- Shared proto files (gRPC contracts)
- Auth service + Keycloak (local) / Cognito (prod)
- Quota service with Redis + dynamic tier config from MongoDB
- Ingestion service (MinIO presigned URLs, file validation, 5-page PDF limit)
- MongoDB schemas + result service
- Notification service (SSE)

### Phase 2 — OCR Pipeline (Weeks 4–6)
- Kafka topics + producer/consumer
- OCR worker: PDF splitter + OpenCV preprocessor
- Triton server (CPU mock for dev, GPU for prod)
- PaddleOCR → ONNX, TrOCR → TensorRT
- Ensemble BLS pipeline
- Post-processor: LayoutLM + BERT spell check (all 22 Indian languages)

### Phase 3 — Chat & LLM Layer (Weeks 7–8)
- Chat service + LangChain + smart model router
- OpenAI GPT-4o + Ollama Llama 3.2:1b fallback
- Langfuse tracing + RAGAS nightly evaluation

### Phase 4 — UI (Weeks 9–10)
- Next.js public web app (upload, result viewer, chat, quota indicator)
- Data sovereignty notice in UI (clear user-facing policy)
- Stripe + Razorpay payment integration
- Streamlit admin dashboard

### Phase 5 — Security & Hardening (Weeks 11–12)
- ClamAV file scanning
- Kubernetes NetworkPolicy (deny-all default)
- TLS everywhere (cert-manager)
- OWASP ZAP + Trivy + Bandit + Semgrep in CI

### Phase 6 — AWS Production Deployment (Weeks 13–15)
- Terraform: EKS, MSK, S3, ElastiCache, DocumentDB, Cognito
- Helm charts + KEDA autoscaling
- S3 lifecycle rules (auto-delete per retention window)
- CloudFront + WAF + billing alerts
- GitHub Actions CI/CD

### Phase 7 — Load Testing & Go-Live (Week 16)
- k6: 1000 concurrent users, 10K pages/hour
- Chaos engineering (kill Triton pod, verify KEDA recovery)
- DR drill
- Documentation finalization

---

## AWS Cost & Deployment Notes

> GPU Node: `g5.xlarge` (NVIDIA A10G)
> On-Demand: ~$1.006/hr | Spot: ~$0.40/hr
> Max nodes (KEDA): 10 → Peak cost: ~$4/hr Spot
> Scale-to-zero at night: ~$0/hr idle
> **Set AWS Budget Alert at $200/month before go-live**
> Keep EKS cluster, MSK, S3 in same AWS Region (e.g., ap-south-1 for India latency)

---

## Governance & Dos/Don'ts

### ✅ Dos
- Enforce quota **before** queuing any job (fail fast at API layer)
- Use presigned URLs — never proxy uploads through app servers
- SHA-256 hash every file → check Redis dedup cache before GPU inference
- Store secrets in AWS Secrets Manager (prod) / Docker secrets (local)
- Pin all Docker image digests in production
- ClamAV scan every upload before processing
- Enable MongoDB point-in-time recovery
- Set KEDA `minReplicaCount: 0` — scale to zero when idle
- Display data sovereignty notice on upload UI (retention window, encryption)
- Hot-reload tier configs from MongoDB (60s cache TTL)

### ❌ Don'ts
- Never log file contents, PII, or API keys
- Never allow PDFs > 5 pages — reject at ingestion with clear error message
- Never skip quota check in any code path (even internal APIs)
- Never expose MongoDB, Redis, or Kafka publicly
- Never store raw files beyond the user's retention window
- Never run Triton as root
- Never hardcode credentials in source or Dockerfiles
- Never process S3 events without verifying metadata signature
- Never deploy untested model quantization without accuracy benchmark
