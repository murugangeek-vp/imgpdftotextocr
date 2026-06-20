# Platform Architecture & Component Guide

This document describes the design patterns, event flows, and technical choices that power the highly scalable OCR platform.

---

## 🏗️ Design Philosophy

The platform is designed around three core principles:
1.  **Decoupled & Event-Driven:** Network-bound API services (Ingestion) are isolated from CPU/GPU-bound processing workers (OCR Workers) via **Apache Kafka** event queues.
2.  **SLA-Driven Scaling:** Computing quotas are enforced at the gateway and ingestion layers before heavy file transfers or GPU inference begin.
3.  **Unified Host Gateway:** Client applications query all services through the single public port `8080` (Kong Gateway), simplifying CORS, network proxying, and client configuration.

---

## 🔄 End-to-End Data Flow

```
[ Client UI ]
     │  1. Upload document (POST)
     ▼
[ Ingestion Service ]
     │  2. Validate size & format
     │  3. Consult redis for quota
     │  4. Run ClamAV scanner
     │  5. Save file to uploads/ private bucket (MinIO)
     │  6. Insert "queued" status to MongoDB
     │  7. Publish event to "ocr.jobs.pending" topic
     ▼
[ Apache Kafka ]
     │
     ├───────────► [ OCR Worker Pool ]
     │                 │  8. Download file from bucket
     │                 │  9. Split PDF / preprocess images
     │                 │  10. Dispatch batches to Triton Inference Server
     │                 │  11. Post-process LayoutLM & spelling corrections
     │                 │  12. Save result JSON to results/ bucket (MinIO)
     │                 │  13. Publish event to "ocr.jobs.completed" / "failed"
     │                 ▼
     └───────────► [ Result Service ]
                       │  14. Update MongoDB status to "completed"
                       ▼
                   [ Notification Service ]
                       │  15. Deliver SSE (Server-Sent Event) to Client
                       ▼
                  [ Client UI ]
                       │  16. Request result JSON (GET) and render
```

---

## ⚡ Key Microservices

### Ingestion Service (8002)
FastAPI application that acts as the entrypoint for user files. Enforces security scans, parses PDFs for page counts, checks quota limits, uploads raw documents to MinIO/S3, persists metadata to MongoDB, and registers tasks in Kafka.

### Quota Service (8003)
Enforces rate-limits based on user pricing tiers (Free, Basic, Professional). Keeps tracking counters in Redis for lightning-fast increments and rollbacks (e.g. daily, weekly, monthly limits). Tier definitions are read dynamically from MongoDB and cached with a 60-second TTL.

### OCR Worker Pool
Async Python consumers scaled horizontally based on KEDA queue metrics. They fetch images, split multi-page PDFs locally, perform binarization/denoising, make gRPC inference queries to Triton, apply spell checking, and publish final JSON payloads.

### Triton Inference Server (9700)
Maintains deep learning models in memory:
*   `ocr_detection`: PaddleOCR model running in an ONNX runtime.
*   `ocr_recognition`: TrOCR Transformer model optimized as a TensorRT engine.
*   `ocr_ensemble`: A Business Logic Script (BLS) combining detection and recognition into a single pipeline request.

### Chat Service (8006)
Provides RAG (Retrieval-Augmented Generation) chat over the processed document text. Uses LangChain to parse OCR context, routes queries to OpenAI GPT-4o or Ollama Llama 3.2 based on cost and complexity, and uploads trace logs directly to Langfuse.
