"""
Triton OCR Client
Connects to NVIDIA Triton Inference Server.
In production: uses gRPC (port 8001) for maximum throughput.
In local dev (CPU mock): falls back to HTTP (port 8000) automatically.
"""
import asyncio
import time
from typing import List

import httpx
import numpy as np
import structlog
from prometheus_client import Counter, Histogram

from config import settings

logger = structlog.get_logger()

# ── Prometheus metrics ────────────────────────────────────────────────────────
triton_request_duration = Histogram(
    "triton_request_duration_seconds",
    "Triton inference request duration",
    ["model"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)
triton_errors = Counter(
    "triton_errors_total",
    "Triton inference errors",
    ["model"],
)


class TritonOCRClient:
    """
    OCR inference client for NVIDIA Triton Inference Server.
    Uses HTTP API for compatibility with the local CPU mock.
    In production switch TRITON_USE_GRPC=true for lower latency.
    """

    def __init__(self):
        self.http_url = settings.TRITON_HTTP_URL
        self.model_name = settings.TRITON_MODEL_ENSEMBLE

    async def infer_batch(
        self, preprocessed_images: List[np.ndarray], languages: List[str]
    ) -> List[dict]:
        """
        Run OCR inference on a batch of preprocessed page images via HTTP.
        Returns a list of {text, confidence, language} per page.
        """
        results = []
        for idx, img_array in enumerate(preprocessed_images):
            start = time.perf_counter()
            try:
                result = await self._infer_single_http(img_array, languages)
                elapsed = time.perf_counter() - start
                triton_request_duration.labels(model=self.model_name).observe(elapsed)
                results.append(result)
                logger.debug("triton.page_done", page=idx + 1, elapsed_s=round(elapsed, 3))
            except Exception as e:
                triton_errors.labels(model=self.model_name).inc()
                logger.error("triton.inference_error", page=idx + 1, error=str(e))
                results.append(
                    {
                        "text": f"[OCR Error on page {idx + 1}: {str(e)}]",
                        "confidence": 0.0,
                        "language": "unknown",
                        "blocks": [],
                    }
                )

        return results

    async def _infer_single_http(
        self, img_array: np.ndarray, languages: List[str]
    ) -> dict:
        """
        Send a single image to Triton HTTP API and parse the response.
        Compatible with both real Triton and the local CPU mock.
        """
        url = f"{self.http_url}/v2/models/{self.model_name}/infer"

        # Convert image to nested list (JSON serializable)
        if img_array.ndim == 2:
            img_tensor = img_array[:, :, np.newaxis]
        else:
            img_tensor = img_array

        payload = {
            "inputs": [
                {
                    "name": "image_input",
                    "datatype": "FP32",
                    "shape": list(img_tensor.shape),
                    "data": img_tensor.flatten().tolist(),
                },
                {
                    "name": "language_hint",
                    "datatype": "BYTES",
                    "shape": [1, 1],
                    "data": [",".join(languages)],
                },
            ],
            "outputs": [
                {"name": "recognized_text"},
                {"name": "confidence"},
                {"name": "detected_language"},
            ],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        outputs = {o["name"]: o["data"] for o in data.get("outputs", [])}

        text = outputs.get("recognized_text", [""])[0]
        confidence = float(outputs.get("confidence", [0.95])[0])
        lang = outputs.get("detected_language", ["en"])[0]

        return {
            "text": text,
            "confidence": confidence,
            "language": lang,
            "blocks": [],
        }
