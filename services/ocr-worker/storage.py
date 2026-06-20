"""
Storage client for OCR Worker.
"""
import json
import aioboto3
import structlog
from config import settings

logger = structlog.get_logger()


class StorageClient:
    _session = None

    @classmethod
    async def init(cls):
        cls._session = aioboto3.Session()
        logger.info("storage.session_initialized")

    @classmethod
    def _get_client_args(cls) -> dict:
        args = {
            "service_name": "s3",
            "aws_access_key_id": settings.MINIO_ACCESS_KEY,
            "aws_secret_access_key": settings.MINIO_SECRET_KEY,
            "use_ssl": settings.MINIO_USE_SSL,
        }
        if settings.STORAGE_PROVIDER == "minio":
            endpoint = settings.MINIO_ENDPOINT
            if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
                endpoint = f"http://{endpoint}"
            args["endpoint_url"] = endpoint
        return args

    @classmethod
    async def upload(
        cls,
        bucket: str,
        key: str,
        content: bytes,
        content_type: str,
        metadata: dict = None,
    ):
        if metadata is None:
            metadata = {}
        async with cls._session.client(**cls._get_client_args()) as s3:
            await s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                Metadata=metadata,
            )

    @classmethod
    async def download(cls, bucket: str, key: str) -> bytes:
        async with cls._session.client(**cls._get_client_args()) as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()

    @classmethod
    async def upload_json(cls, bucket: str, key: str, data: dict):
        content = json.dumps(data).encode("utf-8")
        await cls.upload(
            bucket=bucket,
            key=key,
            content=content,
            content_type="application/json",
        )
