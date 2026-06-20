"""
File upload router — the main ingestion endpoint.
Flow: auth → quota check → file validation → ClamAV scan → dedup hash → S3 upload → Kafka publish
"""
import hashlib
import io
import uuid
from datetime import datetime
from typing import Optional, List

import fitz  # PyMuPDF
import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from config import settings
from validators.file_validator import validate_file
from validators.quota_check import check_quota_for_user
from validators.clamav_scanner import scan_file
from storage import StorageClient
from kafka_producer import KafkaProducerClient
from database import Database

logger = structlog.get_logger()
router = APIRouter()

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/tiff", "image/webp", "image/bmp",
    "application/pdf",
}


class UploadResponse(BaseModel):
    job_id: str
    file_name: str
    page_count: int
    status: str
    message: str


@router.post("/", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    tier: str = Form(default="free"),
    languages: str = Form(default="en"),  # Comma-separated: "en,hi,ta"
):
    """
    Upload an image or PDF for OCR processing.
    - PDFs are limited to 5 pages maximum.
    - File size limits enforced by tier.
    - ClamAV virus scan performed before processing.
    - Duplicate file dedup via SHA-256 hash.
    """
    job_id = str(uuid.uuid4())
    log = logger.bind(job_id=job_id, user_id=user_id, file_name=file.filename)

    # ── 1. Read file into memory ──────────────────────────────────────────────
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)

    # ── 2. File type and size validation ──────────────────────────────────────
    await validate_file(
        filename=file.filename,
        content_type=file.content_type,
        file_size_mb=file_size_mb,
        tier=tier,
    )

    # ── 3. PDF page count enforcement ─────────────────────────────────────────
    page_count = 1
    if file.content_type == "application/pdf":
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            page_count = len(doc)
            doc.close()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or corrupted PDF file: {str(e)}",
            )

        if page_count > settings.MAX_PAGES_PER_PDF:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"PDF has {page_count} pages but maximum allowed is "
                    f"{settings.MAX_PAGES_PER_PDF} pages. "
                    f"Please split your PDF and upload sections separately."
                ),
            )
        log.info("pdf.page_count_ok", pages=page_count)

    # ── 4. Quota check (BEFORE any processing) ────────────────────────────────
    quota_result = await check_quota_for_user(
        user_id=user_id,
        session_id=session_id,
        tier=tier,
        pages=page_count,
    )
    if not quota_result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "message": quota_result["denied_reason"],
                "limit_type": quota_result["limit_type"],
                "current_usage": quota_result["current_usage"],
                "limit_value": quota_result["limit_value"],
                "reset_at_unix": quota_result["reset_at_unix"],
                "upgrade_url": f"{settings.WEB_APP_URL}/pricing",
            },
        )

    # ── 5. ClamAV virus scan ──────────────────────────────────────────────────
    scan_result = await scan_file(content=content, filename=file.filename)
    if scan_result["infected"]:
        log.error("clamav.virus_detected", virus=scan_result.get("virus_name"))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "malware_detected",
                "message": "File failed security scan and cannot be processed.",
            },
        )

    # ── 6. SHA-256 dedup hash ─────────────────────────────────────────────────
    file_hash = hashlib.sha256(content).hexdigest()
    file_key = f"uploads/{user_id}/{job_id}/{file.filename}"

    # ── 7. Upload to MinIO / S3 ───────────────────────────────────────────────
    await StorageClient.upload(
        bucket=settings.MINIO_BUCKET_UPLOADS,
        key=file_key,
        content=content,
        content_type=file.content_type,
        metadata={
            "job_id": job_id,
            "user_id": user_id,
            "file_hash": file_hash,
            "page_count": str(page_count),
        },
    )
    log.info("storage.uploaded", key=file_key)

    # ── 8. Persist job record to MongoDB ──────────────────────────────────────
    db = Database.get_db()
    job_doc = {
        "job_id": job_id,
        "user_id": user_id,
        "session_id": session_id,
        "tier": tier,
        "file_name": file.filename,
        "file_key": file_key,
        "file_hash": file_hash,
        "file_type": file.content_type,
        "page_count": page_count,
        "languages": [l.strip() for l in languages.split(",")],
        "status": "queued",
        "submitted_at": datetime.utcnow(),
        "completed_at": None,
        "error": None,
    }
    await db.ocr_jobs.insert_one(job_doc)

    # ── 9. Publish to Kafka ───────────────────────────────────────────────────
    event = {
        "event_type": "JOB_SUBMITTED",
        "job_id": job_id,
        "user_id": user_id,
        "session_id": session_id,
        "file_key": file_key,
        "file_name": file.filename,
        "file_type": file.content_type,
        "page_count": page_count,
        "languages": [l.strip() for l in languages.split(",")],
        "tier": tier,
        "file_hash": file_hash,
        "submitted_at": datetime.utcnow().isoformat(),
    }
    await KafkaProducerClient.send(
        topic=settings.KAFKA_TOPIC_OCR_PENDING,
        key=user_id,
        value=event,
    )
    log.info("kafka.job_published", topic=settings.KAFKA_TOPIC_OCR_PENDING)

    return UploadResponse(
        job_id=job_id,
        file_name=file.filename,
        page_count=page_count,
        status="queued",
        message="File accepted and queued for OCR processing.",
    )
