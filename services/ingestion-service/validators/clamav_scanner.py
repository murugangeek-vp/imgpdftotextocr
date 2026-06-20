"""
ClamAV virus scanner integration.
Scans every uploaded file before any processing begins.
"""
import asyncio
import clamd
import structlog

from config import settings

logger = structlog.get_logger()


async def scan_file(content: bytes, filename: str) -> dict:
    """
    Scan file content with ClamAV daemon.
    Returns: {infected: bool, virus_name: str | None}
    """
    try:
        # Run in thread pool (clamd is synchronous)
        result = await asyncio.get_event_loop().run_in_executor(
            None, _scan_sync, content, filename
        )
        return result
    except Exception as e:
        logger.error("clamav.scan_error", error=str(e), filename=filename)
        # Fail-safe: if ClamAV is unavailable in dev, log and allow
        # In production, this should be a hard failure
        if settings.APP_ENV == "production":
            raise RuntimeError(f"ClamAV unavailable: {e}")
        logger.warning("clamav.skipping_in_dev", filename=filename)
        return {"infected": False, "virus_name": None}


def _scan_sync(content: bytes, filename: str) -> dict:
    cd = clamd.ClamdNetworkSocket(host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT)
    result = cd.instream(content)
    status, virus_name = result.get("stream", ("OK", None))
    infected = status == "FOUND"
    if infected:
        logger.error("clamav.virus_found", virus=virus_name, filename=filename)
    return {"infected": infected, "virus_name": virus_name}
