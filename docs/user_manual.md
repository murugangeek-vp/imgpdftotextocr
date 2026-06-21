# 📖 OCR Platform User Manual

Welcome to the **Enterprise-Grade Event-Driven OCR Platform** User Manual. This guide provides comprehensive instructions for developers, system administrators, and users to deploy, integrate, and operate the platform.

---

## 🚀 Quick Navigation

1. [Local Development (Docker Compose)](#-local-development-docker-compose)
2. [Local Kubernetes Deployment (Minikube)](#%EF%B8%8F-local-kubernetes-deployment-minikube)
3. [End-User Guide (Next.js Web UI)](#-end-user-guide-nextjs-web-ui)
4. [Admin & Configuration Dashboard](#-admin--configuration-dashboard)
5. [API Integration & Developer Reference](#-api-integration--developer-reference)
6. [Troubleshooting & FAQ](#-troubleshooting--faq)

---

## 💻 Local Development (Docker Compose)

The easiest way to run the entire OCR Platform stack locally for development or demonstration is using Docker Compose.

### Prerequisites
* **Docker Desktop** (with Compose v2+)
* **Python 3.11** (for local CLI utility scripting)
* **Make** (optional, but simplifies command execution)

### Initial Launch Steps
1. **Prepare Environment File:**
   Copy the template file to configure your local setup:
   ```bash
   cp .env.local.template .env.local
   ```
   To enable primary OpenAI GPT-4o routing, add your `OPENAI_API_KEY` to the `.env.local` file. If left blank, requests will automatically fallback to the local Ollama instance.

2. **Boot the Stack:**
   Launch the entire set of microservices and dependencies:
   ```bash
   make dev
   # Alternative: docker compose up -d
   ```

3. **Check Service Health:**
   Ensure all container health checks pass:
   ```bash
   docker compose ps
   ```

4. **Verify Interfaces:**
   Once running, you can access the local dashboards on the following ports:
   * **Web Portal:** `http://localhost:3000`
   * **Kong API Gateway:** `http://localhost:8080`
   * **Admin Console:** `http://localhost:8501`
   * **Keycloak IAM:** `http://localhost:8088`
   * **Langfuse Tracer:** `http://localhost:3002`

---

## ☸️ Local Kubernetes Deployment (Minikube)

For testing Kubernetes configurations, scaling logic, and routing boundaries before EKS deployment, you can deploy the stack directly in **Minikube**.

### 1. Minikube Initialization
Start Minikube with sufficient resources (minimum 4 CPUs, 8GB RAM, and ingress enabled):
```bash
minikube start --cpus=4 --memory=8192
minikube addons enable ingress
```

### 2. Connect Docker Daemon
Point your terminal to Minikube's Docker daemon so that Docker images built locally are immediately available in your Kubernetes cluster without needing an external registry:
```bash
# On Linux/macOS:
eval $(minikube docker-env)

# On Windows (PowerShell):
& minikube -p minikube docker-env | Invoke-Expression
```

### 3. Build Container Images
Build the microservices under the local Minikube environment:
```bash
docker build -t ocr/auth-service:latest ./services/auth-service
docker build -t ocr/ingestion-service:latest ./services/ingestion-service
docker build -t ocr/quota-service:latest ./services/quota-service
docker build -t ocr/ocr-worker:latest ./services/ocr-worker
docker build -t ocr/result-service:latest ./services/result-service
docker build -t ocr/notification-service:latest ./services/notification-service
docker build -t ocr/chat-service:latest ./services/chat-service
docker build -t ocr/admin-service:latest ./services/admin-service
docker build -t ocr/web-app:latest ./services/web-app
```

### 4. Apply Kubernetes Manifests
Apply the configuration manifests from `infrastructure/k8s` in order:

```bash
# 1. Create Namespace
kubectl apply -f infrastructure/k8s/namespace.yaml

# 2. Configure RBAC Roles and ServiceAccounts
kubectl apply -f infrastructure/k8s/rbac.yaml

# 3. Create Secrets and ConfigMaps
kubectl apply -f infrastructure/k8s/configmap.yaml
# Copy secret template, replace placeholders with actual credentials, and apply:
kubectl apply -f infrastructure/k8s/secret.template.yaml

# 4. Apply Network Policy Constraints
kubectl apply -f infrastructure/k8s/network-policies.yaml

# 5. Launch all microservice deployments and cluster services
kubectl apply -f infrastructure/k8s/deployments.yaml

# 6. Apply Ingress Rules & autoscaling limits
kubectl apply -f infrastructure/k8s/ingress.yaml
kubectl apply -f infrastructure/k8s/keda-scaledobject.yaml
```

### 5. Access the Local Cluster
To expose the cluster ingress on your local machine, open a terminal window and run:
```bash
minikube tunnel
```
Add `ocr.local` to your local `/etc/hosts` file (or `C:\Windows\System32\drivers\etc\hosts` on Windows) mapping to `127.0.0.1`. You can then navigate to `http://ocr.local/` in your browser.

---

## 🖥️ End-User Guide (Next.js Web UI)

The Next.js customer portal (`http://localhost:3000`) provides a visual dashboard to manage documents, track usage quota, and perform OCR operations.

### 📤 Uploading Documents
1. **File Dropzone:** Click or drag-and-drop a file (PDF, PNG, JPG, or WebP) into the central container.
2. **Quota Checks:**
   * **Size Limit:** The frontend verifies file size before sending (`10MB` for Free Tier, `50MB` for Basic, `100MB` for Pro).
   * **Page Limit:** Standard user policies restrict PDF files to **5 pages**. Multi-page PDFs are automatically validated on ingestion.
3. **Language Selection:** Choose from English, Hindi, or any of the 22 scheduled Indian languages. This configures the post-processing spell checker and LayoutLM context.
4. **Antivirus Processing:** Upon uploading, the server passes the file to ClamAV. Infected files are blocked instantly with an error code.

### 📋 Processing Monitor & Result Viewer
* **Real-time Progress:** The upload generates a `job_id` and establishes a Server-Sent Events (SSE) connection to `notification-service`. You can watch the real-time pipeline steps: `queued` ➔ `preprocessing` ➔ `inference` ➔ `postprocessing` ➔ `completed`.
* **Side-by-Side Panel:** Once completed, the left pane displays the document image with detected bounding boxes, and the right pane shows the extracted, corrected text.
* **Copy/Export:** Copy the plain text output or download the structured JSON format containing text coordinates, confidence values, and page details.

### 💬 Document AI Chat (RAG)
* **Contextual Conversations:** Ask questions based on the document text. The chatbot searches the extracted text pages using RAG.
* **Model Tags:** At the bottom of each chat response, a label shows which LLM generated the text (e.g. `GPT-4o` or `Llama-3.2`) so you can track resource usage.

---

## ⚙️ Admin & Configuration Dashboard

The Admin Dashboard is built with **Streamlit** (`http://localhost:8501`) and is reserved for administrative tasks and real-time environment management.

### 1. Dynamic Tier Controls
Administrators can edit the page limits, daily quotas, file sizes, and data retention windows for user tiers without restarting any backend containers:
* **Free:** 5 pages/day, 10MB file limit, 24-hour retention.
* **Basic:** 100 pages/day, 50MB file limit, 30-day retention.
* **Pro:** Unlimited pages/day, 100MB file limit, 90-day retention.

Saving updates writes them directly to MongoDB, triggering a Redis cache eviction. All services fetch the fresh limits on their next transaction.

### 2. Ingestion Audits
* **Audit Trail:** View the processing log of all files, including username, file hashes, page count, Triton processing latency, confidence scores, and malware scan status.
* **Storage Actions:** Force-purge expired files from MinIO/S3 or clear cached duplicate task hashes to allow reprocessing.

---

## 🔌 API Integration & Developer Reference

Developers can bypass the frontend and query the platform endpoints through the API Gateway at port `8080`.

### 1. Ingest File (Multipart POST)
Upload a document to the processing queue.

```bash
curl -X POST "http://localhost:8080/ingestion-service/api/v1/upload/" \
  -F "file=@/path/to/invoice.pdf" \
  -F "user_id=dev-developer" \
  -F "session_id=manual-test-01" \
  -F "tier=pro" \
  -F "languages=en,hi"
```

**Success Response (202 Accepted):**
```json
{
  "job_id": "b3e0c06a-ff55-4929-8736-226ea19bcf82",
  "file_name": "invoice.pdf",
  "page_count": 1,
  "status": "queued",
  "message": "File accepted and queued for OCR processing."
}
```

### 2. Listen to Job Progress (Server-Sent Events)
Establish a stream connection to watch processing stages.

```bash
curl -N "http://localhost:8080/api/v1/jobs/b3e0c06a-ff55-4929-8736-226ea19bcf82/stream"
```

**Stream Outputs:**
```text
data: {"status": "queued", "progress_percentage": 0}
data: {"status": "preprocessing", "progress_percentage": 25}
data: {"status": "inference", "progress_percentage": 60}
data: {"status": "postprocessing", "progress_percentage": 85}
data: {"status": "completed", "progress_percentage": 100}
```

### 3. Retrieve Extraction Details (GET)
Fetch the final OCR text content and layout structures.

```bash
curl -X GET "http://localhost:8080/result-service/api/v1/results/b3e0c06a-ff55-4929-8736-226ea19bcf82"
```

---

## 🔧 Troubleshooting & FAQ

### Q1: The web portal says my PDF exceeded the page limit, but it is only 4 pages.
Verify your pricing tier profile. The maximum page limit for the `Free` tier is **5 pages**. Make sure you are authenticated with the correct tier settings. Also check if the document contains corrupt page catalog definitions, causing the PDF reader to misread the page count.

### Q2: Kafka connections are failing during startup.
Ensure you let the containers boot fully. The event stream brokers take ~30 seconds to initialize, perform health checks, and claim leader election. Run `docker compose logs kafka` to check broker availability.

### Q3: My file is rejected due to a scan error.
The `ingestion-service` passes all incoming files to ClamAV. If the ClamAV daemon is busy or booting, or if your file fails the virus scan signature database check, the server will block the upload. Check `docker compose logs clamav` to ensure the virus definitions are loaded.

### Q4: KEDA isn't scaling the ocr-worker deployment.
Ensure KEDA is running in your Kubernetes namespace. Check KEDA operator logs:
```bash
kubectl logs -n keda deployment/keda-operator
```
Ensure the scaler target has access to the Kafka service address and is listening to the target topic (`ocr.jobs.pending`). Run `kubectl describe scaledobject ocr-worker-scaler` to check the trigger metrics.
