# Enterprise-Grade Event-Driven OCR Platform

An enterprise-grade, highly scalable, decoupled, event-driven OCR (Optical Character Recognition) platform. It extracts printed and handwritten text from images and PDFs in real-time, supporting global scripts and all **22 scheduled Indian languages** via a self-hosted pipeline.

---

## 🚀 Key Features

*   **Self-Hosted Deep Learning Pipeline:** PaddleOCR (detection) + TrOCR (recognition) running on a self-hosted **NVIDIA Triton Inference Server** with CPU mock mode for local dev.
*   **Decoupled Async Architecture:** Ingestion and processing are fully decoupled using **Apache Kafka** to handle peak traffic.
*   **Dynamic Tier & Cost Control:** Quota and size limits are hot-reloadable on the fly from MongoDB / Redis cache with zero service downtime.
*   **Smart LLM Assistant Router:** Cost-effective LLM routing between **OpenAI GPT-4o** (for paid tier/complex requests) and local **Ollama Llama 3.2:1b** (for free tier/fallback).
*   **End-to-End LLM Observability:** Full request tracing, latency tracking, and analysis integrated with **Langfuse**.
*   **Anti-Virus Scanning:** Immediate malware checks on file upload using **ClamAV** daemon before storing files.
*   **Secure Storage:** Multi-region private bucket upload (MinIO locally / Amazon S3 in prod) with client-side direct uploads via presigned URLs and AES-256 at-rest encryption.

---

## 📐 System Architecture

The platform follows a decoupled microservices design, routing all public client traffic through an API gateway:

```
                      ┌─────────────────────────────────┐
                      │          PUBLIC INTERNET        │
                      │  [Next.js App]  [REST Client]   │
                      └────────────────┬────────────────┘
                                       │ HTTPS / SSE
                                       ▼
                      ┌─────────────────────────────────┐
                      │       API GATEWAY (Kong)        │
                      │       Edge Port Mapping         │
                      └────────────────┬────────────────┘
                                       │
         ┌───────────────┬─────────────┼───────────────┬──────────────┐
         ▼               ▼             ▼               ▼              ▼
  [auth-service] [ingestion-service] [result-service] [chat-service] [notification-service]
     (8001)           (8002)         (8004)          (8006)           (8005)
       │               │               │               │               │
       ▼               ▼               ▼               ▼               ▼
  [Keycloak]     [MinIO Storage]   [MongoDB]      [Smart Router]    [Kafka SSE]
   (8088)            (9000)      (ocrplatform)       ├── GPT-4o        (9092)
                                                     └── Llama3.2
                                                     └── Langfuse
                                                           (3002)
```

---

## 🔌 API & Port Reference Table

All services run inside a dedicated Docker bridge network. For host system access, the edge gateway and service dashboards map to the following ports:

| Service / Dashboard | Internal Port | Host Port | Description |
| :--- | :--- | :--- | :--- |
| **Edge Gateway (Kong)** | `8000` | **`8080`** | Primary public REST API entrypoint |
| **Next.js Web UI** | `3000` | **`3000`** | Main customer portal and OCR workspace |
| **Admin Dashboard** | `8501` | **`8501`** | Streamlit internal system dashboard |
| **Keycloak IAM** | `8080` | **`8088`** | Identity Provider (master & ocr realms) |
| **Langfuse Observability**| `3000` | **`3002`** | LLM Tracer dashboard |
| **MinIO Console** | `9001` | **`9001`** | Object storage manager console |
| **ClamAV Antivirus** | `3310` | **`3310`** | Malware scanner engine |
| **Triton Inference** | `8000` | **`9700`** | Deep learning HTTP server mock |
| **Grafana Metrics** | `3000` | **`3001`** | System metrics visualization dashboard |
| **Jaeger UI** | `16686` | **`16686`**| Distributed tracing visualization |

---

## 🛠️ Local Development Setup

### Prerequisites

Ensure you have the following installed on your machine:
*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Compose v2+)
*   [Python 3.11](https://www.python.org/downloads/)
*   `make` utility (optional, commands can be run directly)

### Initial Run & Launch

1.  **Configure Environment Variables:**
    Create a local configuration file `.env.local` based on the template:
    ```bash
    cp .env.local.template .env.local
    ```
    *Note: Add your `OPENAI_API_KEY` to `.env.local` to enable primary GPT-4o assistant routing.*

2.  **Start Infrastructure & Services:**
    Launch the full Docker stack:
    ```bash
    make dev
    # or run: docker compose up -d
    ```
    This command downloads dependencies, compiles protobuf files, initializes the Kafka topics and MinIO buckets, and brings up the services.

3.  **Confirm Service Status:**
    To verify all services are active and healthy:
    ```bash
    docker compose ps
    ```

---

## ⚙️ Dynamic Tier Configurations

System limits can be adjusted dynamically in the database with **zero service restarts**. The configs are stored in the MongoDB `tier_configs` collection and cached in Redis with a 60-second TTL.

Example document for the **Free Tier**:
```json
{
  "tier": "free",
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
}
```

---

## 🕵️‍♂️ Monitoring & Observability

1.  **Langfuse (LLM Tracing):**
    Open `http://localhost:3002/` in your browser. Click **Sign Up** to create your local administrator account and inspect traces.
2.  **Metrics (Prometheus & Grafana):**
    Grafana dashboard is available at `http://localhost:3001/` (default login `admin` / `admin`).
3.  **Jaeger (Traces):**
    Open `http://localhost:16686/` to trace internal microservice requests.

---

## 🧪 Testing

Run quality checks and tests on the services:
```bash
# Run unit tests locally
make test-unit

# Run full integration tests inside Docker
make test-integration
```
