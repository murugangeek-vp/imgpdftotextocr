# API Gateway Contract Reference

This document maps all public REST endpoints exposed through the API Gateway (Kong) at port `8080` (or Application Load Balancer in production) to their target microservices.

---

## 🚪 Summary of Exposed Routes

Public host url: `http://localhost:8080`

| Public Routing Path | Target Microservice | Allowed Methods | Description |
| :--- | :--- | :--- | :--- |
| `/ingestion-service/api/v1/upload/` | `ingestion-service` | `POST` | Upload and queue an image or PDF for OCR |
| `/ingestion-service/api/v1/presigned/` | `ingestion-service` | `POST` | Request a direct upload presigned URL |
| `/quota-service/api/v1/quota/usage` | `quota-service` | `POST` | Get remaining daily/weekly usage slots |
| `/result-service/api/v1/results/{id}`| `result-service` | `GET` | Get final OCR text & layout data |
| `/chat-service/api/v1/chat/` | `chat-service` | `POST` | Query LLM on processed document text |
| `/api/v1/jobs/{id}/stream` | `notification-service` | `GET` | Real-time job status notifications (SSE) |

---

## 📋 Endpoint Specifications

### 1. File Ingestion & Queue Upload
*   **Path:** `POST /ingestion-service/api/v1/upload/`
*   **Headers:** `Content-Type: multipart/form-data`
*   **Form Parameters:**
    *   `file` (file binary, required): Target image or PDF.
    *   `user_id` (string, required): Active user identifier.
    *   `session_id` (string, required): Current tracking session ID.
    *   `tier` (string, optional, default: `"free"`): Current pricing plan level.
    *   `languages` (string, optional, default: `"en"`): Comma-separated language codes.
*   **Successful Response (202 Accepted):**
    ```json
    {
      "job_id": "a38b4ea9-eff8-4d11-9951-64e6f1882121",
      "file_name": "invoice.png",
      "page_count": 1,
      "status": "queued",
      "message": "File accepted and queued for OCR processing."
    }
    ```

### 2. Quota Check
*   **Path:** `POST /quota-service/api/v1/quota/usage`
*   **Payload (JSON):**
    ```json
    {
      "user_id": "dev-user-id",
      "session_id": "sess-dev",
      "tier": "free"
    }
    ```
*   **Successful Response (200 OK):**
    ```json
    {
      "allowed": true,
      "limits": {
        "pages_per_session": 5,
        "pages_per_day": 5,
        "pages_per_week": 20,
        "pages_per_month": 50,
        "max_file_size_mb": 10,
        "max_pages_per_pdf": 5
      },
      "usage": {
        "pages_today": 1,
        "pages_this_week": 1,
        "pages_this_month": 1
      }
    }
    ```

### 3. Retrieve OCR Results
*   **Path:** `GET /result-service/api/v1/results/{job_id}`
*   **Successful Response (200 OK):**
    ```json
    {
      "job_id": "a38b4ea9-eff8-4d11-9951-64e6f1882121",
      "user_id": "dev-user-id",
      "file_name": "invoice.png",
      "page_count": 1,
      "languages": ["en"],
      "status": "completed",
      "confidence": 0.92,
      "model_used": "ocr_ensemble",
      "pages": [
        {
          "page_number": 1,
          "text": "Extracted text here...",
          "layout_json": "{}",
          "confidence": 0.92,
          "language": "en"
        }
      ]
    }
    ```

### 4. AI Document Assistant Chat
*   **Path:** `POST /chat-service/api/v1/chat/`
*   **Payload (JSON):**
    ```json
    {
      "job_id": "a38b4ea9-eff8-4d11-9951-64e6f1882121",
      "user_id": "dev-user-id",
      "tier": "free",
      "messages": [
        {
          "role": "user",
          "content": "Summarize this invoice."
        }
      ],
      "ocr_context": "Raw OCR content of the document..."
    }
    ```
*   **Successful Response (200 OK):**
    ```json
    {
      "message": "Here is the summary of the invoice...",
      "model_used": "llama3.2:1b",
      "provider": "ollama"
    }
    ```
