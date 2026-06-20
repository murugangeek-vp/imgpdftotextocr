"""
Triton CPU Mock Server
Simulates NVIDIA Triton Inference Server for local development (no GPU needed).
Implements the same HTTP /v2 API surface and returns synthetic OCR text results.
Runs on ports 8000 (HTTP), 8001 (HTTP/gRPC mock), 8002 (metrics).
"""
import random
import json
import time
import asyncio
from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import make_asgi_app, Counter, Histogram
import uvicorn

app = FastAPI(title="Triton CPU Mock", version="2.0.0")

# ── Prometheus metrics (mirrors real Triton) ──────────────────────────────────
infer_count = Counter("nv_inference_count", "Inference count", ["model"])
infer_duration = Histogram("nv_inference_duration_us", "Inference duration µs", ["model"])


# ── Sample texts for realistic-looking OCR mock output ───────────────────────
SAMPLE_TEXTS = [
    "Invoice No: INV-2024-00123\nDate: 20 June 2024\nTotal Amount: ₹45,680.00\nGST (18%): ₹8,222.40",
    "The quick brown fox jumps over the lazy dog. This is a sample OCR extracted text from a scanned document.",
    "नमस्ते दुनिया। यह एक परीक्षण पाठ है। OCR प्रणाली हिंदी भाषा को सही ढंग से पहचान सकती है।",
    "Dear Customer,\nThank you for your order #ORD-789456.\nYour package will be delivered by 25 June 2024.",
    "CERTIFICATE OF COMPLETION\nThis is to certify that John Doe has successfully completed\nAdvanced Python Programming Course - Grade: A+",
    "PRESCRIPTION\nPatient: Ravi Kumar | Age: 45\nTab Metformin 500mg - 1-0-1\nTab Atorvastatin 10mg - 0-0-1",
    "வணக்கம்! இது ஒரு தமிழ் OCR சோதனை உரை. கணினி தமிழ் எழுத்துக்களை சரியாக அடையாளம் காண்கிறது.",
    "CONTRACT AGREEMENT\nThis agreement is made between Party A and Party B\non the 20th day of June 2024.",
]

LANGUAGES = ["en", "hi", "ta", "te", "ml", "kn", "bn", "mr", "gu", "pa"]


def get_sample_ocr_result():
    text = random.choice(SAMPLE_TEXTS)
    confidence = round(random.uniform(0.87, 0.99), 3)
    lang = random.choice(LANGUAGES[:3])  # bias toward common languages
    return text, confidence, lang


# ── Triton v2 API ─────────────────────────────────────────────────────────────

@app.get("/v2/health/ready")
async def health_ready():
    return {"ready": True}


@app.get("/v2/health/live")
async def health_live():
    return {"live": True}


@app.get("/v2")
async def server_metadata():
    return {
        "name": "triton",
        "version": "2.40.0",
        "extensions": ["classification", "sequence", "model_repository", "schedule_policy", "model_configuration", "system_shared_memory", "cuda_shared_memory", "binary_tensor_data", "parameters", "statistics", "trace", "logging"],
    }


@app.get("/v2/models/{model_name}")
async def model_metadata(model_name: str):
    return {
        "name": model_name,
        "versions": ["1"],
        "platform": "cpu_mock",
        "inputs": [{"name": "image_input", "datatype": "FP32", "shape": [-1, 640, 640, 1]}],
        "outputs": [
            {"name": "recognized_text", "datatype": "BYTES", "shape": [-1, 1]},
            {"name": "confidence", "datatype": "FP32", "shape": [-1, 1]},
            {"name": "detected_language", "datatype": "BYTES", "shape": [-1, 1]},
        ],
    }


@app.get("/v2/models/{model_name}/ready")
async def model_ready(model_name: str):
    return {"ready": True}


@app.post("/v2/models/{model_name}/infer")
async def model_infer(model_name: str):
    """Mock inference — returns realistic fake OCR output."""
    start = time.time()

    # Simulate GPU inference time (50-300ms)
    await asyncio.sleep(random.uniform(0.05, 0.3))

    text, confidence, lang = get_sample_ocr_result()

    elapsed_us = (time.time() - start) * 1_000_000
    infer_count.labels(model=model_name).inc()
    infer_duration.labels(model=model_name).observe(elapsed_us)

    return {
        "model_name": model_name,
        "model_version": "1",
        "outputs": [
            {
                "name": "recognized_text",
                "datatype": "BYTES",
                "shape": [1, 1],
                "data": [text],
            },
            {
                "name": "confidence",
                "datatype": "FP32",
                "shape": [1, 1],
                "data": [confidence],
            },
            {
                "name": "detected_language",
                "datatype": "BYTES",
                "shape": [1, 1],
                "data": [lang],
            },
        ],
    }


# ── Prometheus metrics endpoint ───────────────────────────────────────────────
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
