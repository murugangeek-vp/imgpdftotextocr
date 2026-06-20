# Production Deployment Guide

This guide details the step-by-step process of transitioning the Event-Driven OCR Platform from a local development stack to a production cloud environment on **AWS (Amazon Web Services)**.

---

## 🏗️ Production Architecture Map

In production, local mock components are replaced with managed cloud infrastructure for high availability, security, and durability:

| Local Component | Production AWS Managed Service | Purpose |
| :--- | :--- | :--- |
| **Keycloak (dev-mem)** | **AWS Cognito User Pools** | Secure tenant user IAM and JWT distribution |
| **MinIO Storage** | **Amazon S3** | Durable object store with KMS AES-256 encryption |
| **Apache Kafka** | **Amazon MSK (Managed Streaming for Kafka)** | Managed multi-AZ event broker |
| **MongoDB** | **Amazon DocumentDB (MongoDB compatible)** | Highly available document database |
| **Redis** | **Amazon ElastiCache for Redis** | High-performance distributed cache for quotas |
| **Docker Compose** | **Amazon ECS (Fargate) / EKS** | Auto-scaled container orchestration |
| **Kong API Gateway** | **AWS Application Load Balancer (ALB)** | Public routing and TLS termination |
| **Triton Mock** | **AWS ECS on GPU Nodes (g5.xlarge Spot)** | Triton inference engine auto-scaled on demand |

---

## 📋 Step-by-Step Deployment Execution

### Step 1: Storage Layer Setup (Amazon S3)

1.  Create two distinct, private S3 buckets:
    *   `ocr-uploads-prod`: Raw uploads (lifecycle rule to expire files after 24 hours).
    *   `ocr-results-prod`: Final processed JSON results.
2.  Enable **Default Encryption** with AWS KMS keys.
3.  Block all public access and configure CORS to allow requests from your production web domain.

### Step 2: Event Streaming Layer (Amazon MSK)

1.  Provision an **Amazon MSK Cluster** in 3 Availability Zones.
2.  Enable TLS client-broker communication.
3.  Create the required topics:
    *   `ocr.jobs.pending` (10 partitions, compaction disabled)
    *   `ocr.jobs.completed` (5 partitions)
    *   `ocr.jobs.failed` (5 partitions)
    *   `quota.alerts` (3 partitions)

### Step 3: Identity Management (AWS Cognito)

1.  Provision an **AWS Cognito User Pool** with hosted UI enabled.
2.  Configure custom scopes:
    *   `ocr-api/read`
    *   `ocr-api/write`
3.  Add App Clients for:
    *   Next.js Frontend (Authorization Code Grant with PKCE)
    *   Machine Clients (Client Credentials Grant)

### Step 4: Database Layer (Amazon DocumentDB & ElastiCache)

1.  **DocumentDB Cluster:**
    *   Deploy with 1 writer and 2 read replicas.
    *   Create collections: `ocr_jobs`, `api_keys`, `users`.
2.  **ElastiCache Redis:**
    *   Launch cluster with Multi-AZ enabled.
    *   Set Redis AUTH to secure communication.

### Step 5: Container Deployment (Amazon ECS on AWS Fargate & EC2 Spot)

1.  **CPU Services (Fargate):**
    *   Deploy `auth-service`, `ingestion-service`, `quota-service`, `result-service`, `notification-service`, `chat-service`, and `admin-service` to AWS Fargate.
    *   Set up Application Load Balancers for traffic ingress.
2.  **OCR Worker Pool (EC2 Spot):**
    *   Deploy `ocr-worker` as an ECS service backed by ASG (Auto Scaling Group).
    *   Use KEDA (Kubernetes Event-driven Autoscaling) or ECS Target Tracking scaling policy on Kafka lag metrics (`ocr.jobs.pending`).
3.  **Triton GPU Inference (EC2 Spot):**
    *   Deploy the official NVIDIA Triton container on GPU-optimized Spot instances (`g5.xlarge` with TensorRT runtime).

---

## 🔒 Security Best Practices

1.  **IAM Roles (Least Privilege):** No hardcoded credentials. All ECS tasks must utilize task-specific IAM roles (e.g. access to specific S3 buckets and Cognito).
2.  **VPC Isolation:** Keep databases, cache, and Triton in private subnets with NAT gateways. Only the Application Load Balancer and CloudFront distribution should accept external internet traffic.
3.  **WAF Protection:** Attach AWS WAF to CloudFront to prevent common SQL injection, XSS, and DDoS attacks.
