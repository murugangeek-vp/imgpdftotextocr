# ============================================================
# OCR Platform — Developer Makefile
# Usage: make <target>
# ============================================================

.PHONY: help dev down build test lint proto clean k3d-up k3d-down

help:
	@echo "OCR Platform — Available Commands"
	@echo "-----------------------------------"
	@echo "  make dev          Start full local stack (Docker Compose)"
	@echo "  make down         Stop all local services"
	@echo "  make build        Build all Docker images"
	@echo "  make test         Run all tests (unit + integration)"
	@echo "  make lint         Run linters (Bandit, Semgrep, Trivy)"
	@echo "  make proto        Compile all .proto files"
	@echo "  make k3d-up       Start local k3d Kubernetes cluster"
	@echo "  make k3d-down     Destroy local k3d cluster"
	@echo "  make clean        Remove all build artifacts and volumes"
	@echo "  make minio-setup  Create MinIO buckets"
	@echo "  make keycloak-setup Setup Keycloak realm"
	@echo "  make logs svc=<name>  Tail logs for a service"

# ── Local Dev ────────────────────────────────────────────────
dev:
	docker compose up -d
	@echo "✅ Stack is up. Web UI: http://localhost:3000"
	@echo "   Admin:   http://localhost:8501"
	@echo "   Kong:    http://localhost:8080"
	@echo "   Grafana: http://localhost:3001"
	@echo "   Langfuse:http://localhost:3002"

down:
	docker compose down

restart svc:
	docker compose restart $(svc)

logs:
	docker compose logs -f $(svc)

build:
	docker compose build --parallel

# ── Testing ──────────────────────────────────────────────────
test:
	docker compose -f docker-compose.test.yml up --abort-on-container-exit --exit-code-from test-runner

test-unit:
	cd services && python -m pytest */tests/unit/ -v --tb=short

test-integration:
	docker compose -f docker-compose.test.yml run --rm test-runner pytest tests/integration/ -v

test-load:
	k6 run tests/load/ocr-pipeline.js --vus 100 --duration 60s

# ── Code Quality ─────────────────────────────────────────────
lint:
	bandit -r services/ -ll -x services/*/tests
	semgrep --config=auto services/
	trivy fs . --severity HIGH,CRITICAL

# ── Proto Compilation ────────────────────────────────────────
proto:
	@echo "Compiling .proto files..."
	for svc in auth quota ocr result; do \
		python -m grpc_tools.protoc \
			-I shared/proto \
			--python_out=shared/proto/gen \
			--grpc_python_out=shared/proto/gen \
			shared/proto/$${svc}.proto; \
	done
	@echo "✅ Proto files compiled"

# ── MinIO Setup ──────────────────────────────────────────────
minio-setup:
	bash infrastructure/local/minio-setup.sh

# ── Keycloak Setup ───────────────────────────────────────────
keycloak-setup:
	bash infrastructure/local/keycloak-setup.sh

# ── k3d Local Kubernetes ─────────────────────────────────────
k3d-up:
	k3d cluster create ocr-platform --config infrastructure/local/k3d-config.yaml
	kubectl apply -f k8s/local/

k3d-down:
	k3d cluster delete ocr-platform

# ── Cleanup ──────────────────────────────────────────────────
clean:
	docker compose down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
