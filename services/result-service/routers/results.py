"""
Results API Router
"""
from fastapi import APIRouter, HTTPException, status
from database import Database

router = APIRouter()


@router.get("/{job_id}")
async def get_job_result(job_id: str):
    """Retrieve the status and extracted text details of an OCR job."""
    db = Database.get_db()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not connected",
        )

    job = await db.ocr_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OCR job not found",
        )

    return job


@router.get("/user/{user_id}")
async def list_user_jobs(user_id: str):
    """List historical OCR jobs submitted by a specific user."""
    db = Database.get_db()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not connected",
        )

    # Return up to 50 most recent jobs
    cursor = db.ocr_jobs.find({"user_id": user_id}, {"_id": 0}).sort(
        "submitted_at", -1
    )
    jobs = await cursor.to_list(length=50)
    return jobs
