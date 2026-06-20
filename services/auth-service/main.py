"""
Auth Service — Main FastAPI Application
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import structlog
from fastapi import FastAPI, APIRouter, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from pydantic import BaseModel
from prometheus_client import make_asgi_app

from config import settings
from database import Database
from grpc_server import start_grpc_server

logger = structlog.get_logger()
router = APIRouter()


class TokenGenerateRequest(BaseModel):
    user_id: str = "dev-user-id"
    email: str = "dev@example.com"
    tier: str = "free"  # "free" | "basic" | "pro"
    roles: list = ["user"]


class TokenGenerateResponse(BaseModel):
    token: str
    expire_at_unix: int


@router.post("/token", response_model=TokenGenerateResponse)
async def generate_dev_token(req: TokenGenerateRequest):
    """
    Generate a signed JWT token for development purposes.
    Signed using the SECRET_KEY with HS256.
    """
    if settings.APP_ENV != "local":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token generation endpoint only available in local dev environment",
        )

    expire = datetime.utcnow() + timedelta(hours=24)
    payload = {
        "sub": req.user_id,
        "user_id": req.user_id,
        "email": req.email,
        "tier": req.tier,
        "roles": req.roles,
        "realm_access": {"roles": req.roles + [req.tier]},
        "exp": int(expire.timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
    }
    try:
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        return TokenGenerateResponse(
            token=token,
            expire_at_unix=int(expire.timestamp()),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate JWT: {str(e)}",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("auth_service.startup", env=settings.APP_ENV)
    await Database.connect()

    # Start gRPC Server
    grpc_server = await start_grpc_server("0.0.0.0", settings.AUTH_SERVICE_GRPC_PORT)

    yield

    await grpc_server.stop(grace=5)
    await Database.disconnect()
    logger.info("auth_service.shutdown")


app = FastAPI(
    title="Auth Service",
    description="JWT Token validation and API key authentication gateway service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "auth-service"}


app.include_router(router, prefix="/api/v1/auth", tags=["auth"])
