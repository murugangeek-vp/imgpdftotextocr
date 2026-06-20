"""MongoDB async client for Result Service."""
import motor.motor_asyncio
from config import settings

_client = None
_db = None


class Database:
    @classmethod
    async def connect(cls):
        global _client, _db
        _client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URI)
        _db = _client[settings.MONGODB_DB]

    @classmethod
    async def disconnect(cls):
        if _client:
            _client.close()

    @classmethod
    def get_db(cls):
        return _db
