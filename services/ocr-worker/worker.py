"""
OCR Worker — Main Kafka Consumer Loop
Consumes OCR jobs from Kafka, runs the full pipeline:
  Download → Split PDF → Preprocess → Triton Inference → Post-process → Publish Result
"""
import asyncio
import json
import signal
import sys

import structlog
from kafka import KafkaConsumer

from config import settings
from pipeline.pdf_splitter import PDFSplitter
from pipeline.preprocessor import ImagePreprocessor
from pipeline.triton_client import TritonOCRClient
from pipeline.postprocessor import OCRPostProcessor
from result_publisher import ResultPublisher
from storage import StorageClient
from quota_incrementer import increment_quota

logger = structlog.get_logger()

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("ocr_worker.shutdown_signal", signal=signum)
    running = False


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


async def process_job(event: dict):
    job_id = event["job_id"]
    user_id = event["user_id"]
    log = logger.bind(job_id=job_id, user_id=user_id)

    try:
        log.info("ocr_worker.job_started")

        # ── 1. Download file from MinIO/S3 ───────────────────────────────────
        content = await StorageClient.download(
            bucket=settings.MINIO_BUCKET_UPLOADS,
            key=event["file_key"],
        )
        log.info("ocr_worker.file_downloaded", key=event["file_key"])

        # ── 2. Split PDF into page images ─────────────────────────────────────
        if event["file_type"] == "application/pdf":
            page_images = PDFSplitter.split(content)
        else:
            page_images = [content]

        log.info("ocr_worker.pages_split", count=len(page_images))

        # ── 3. Preprocess each page (deskew, binarize, denoise) ───────────────
        preprocessed = [ImagePreprocessor.preprocess(img) for img in page_images]

        # ── 4. Run Triton inference ───────────────────────────────────────────
        triton = TritonOCRClient()
        raw_results = await triton.infer_batch(preprocessed, languages=event.get("languages", ["en"]))
        log.info("ocr_worker.inference_done")

        # ── 5. Post-process: layout parsing + spell check ─────────────────────
        postprocessor = OCRPostProcessor(languages=event.get("languages", ["en"]))
        page_results = postprocessor.process(raw_results)

        # ── 6. Save result to MinIO/S3 ────────────────────────────────────────
        result_key = f"results/{user_id}/{job_id}/result.json"
        result_payload = {
            "job_id": job_id,
            "user_id": user_id,
            "pages": page_results,
            "page_count": len(page_results),
        }
        await StorageClient.upload_json(
            bucket=settings.MINIO_BUCKET_RESULTS,
            key=result_key,
            data=result_payload,
        )

        # ── 7. Publish completion event ───────────────────────────────────────
        await ResultPublisher.publish_success(
            job_id=job_id,
            user_id=user_id,
            session_id=event["session_id"],
            page_results=page_results,
            result_key=result_key,
        )

        # ── 8. Increment quota counters ───────────────────────────────────────
        await increment_quota(
            user_id=user_id,
            session_id=event["session_id"],
            tier=event["tier"],
            pages=len(page_results),
        )

        log.info("ocr_worker.job_completed", pages=len(page_results))

    except Exception as e:
        log.error("ocr_worker.job_failed", error=str(e), exc_info=True)
        await ResultPublisher.publish_failure(
            job_id=job_id,
            user_id=user_id,
            error=str(e),
        )


def main():
    logger.info("ocr_worker.starting", concurrency=settings.WORKER_CONCURRENCY)

    consumer = KafkaConsumer(
        settings.KAFKA_TOPIC_OCR_PENDING,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        max_poll_records=10,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(StorageClient.init())

    logger.info("ocr_worker.listening", topic=settings.KAFKA_TOPIC_OCR_PENDING)

    while running:
        try:
            msg_pack = consumer.poll(timeout_ms=1000)
            for tp, messages in msg_pack.items():
                for msg in messages:
                    event = msg.value
                    loop.run_until_complete(process_job(event))
                    consumer.commit()
        except Exception as e:
            logger.error("ocr_worker.poll_error", error=str(e))

    consumer.close()
    loop.close()
    logger.info("ocr_worker.stopped")


if __name__ == "__main__":
    main()
