"""
Auth Service — gRPC Servicer Implementation
"""
import grpc
import httpx
from jose import jwt
import structlog
from shared.proto.gen import auth_pb2, auth_pb2_grpc
from config import settings
from database import Database

logger = structlog.get_logger()
_jwks = None


async def fetch_jwks():
    global _jwks
    if _jwks is not None:
        return _jwks
    url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            _jwks = resp.json()
            return _jwks
    except Exception as e:
        logger.warning("auth.fetch_jwks_unreachable", error=str(e), url=url)
        return None


async def validate_jwt_token(token: str) -> dict:
    jwks = await fetch_jwks()
    try:
        if jwks:
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=settings.KEYCLOAK_CLIENT_ID,
                options={"verify_aud": False},
            )
        else:
            # Fallback for local development when Keycloak is offline
            payload = jwt.get_unverified_claims(token)
            logger.warning("auth.token_unverified_fallback", token=token[:15])

        user_id = payload.get("sub", "")
        email = payload.get("email", "")
        roles = payload.get("realm_access", {}).get("roles", [])
        
        # Determine tier
        tier = "free"
        if "pro" in roles:
            tier = "pro"
        elif "basic" in roles:
            tier = "basic"

        return {
            "valid": True,
            "user_id": user_id,
            "email": email,
            "tier": tier,
            "roles": roles,
            "exp": payload.get("exp", 0),
            "iat": payload.get("iat", 0),
            "error": "",
        }
    except Exception as e:
        logger.error("auth.token_invalid", error=str(e))
        # If the token is manually generated dummy token for local dev, let's decode it as HS256 using SECRET_KEY
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            return {
                "valid": True,
                "user_id": payload.get("user_id", "dev-user-id"),
                "email": payload.get("email", "dev@example.com"),
                "tier": payload.get("tier", "free"),
                "roles": payload.get("roles", ["user"]),
                "exp": payload.get("exp", 0),
                "iat": payload.get("iat", 0),
                "error": "",
            }
        except Exception:
            return {"valid": False, "error": str(e)}


async def validate_api_key_db(api_key: str) -> dict:
    db = Database.get_db()
    if db is None:
        # If database is offline, let's allow a fallback dev api key in local mode
        if settings.APP_ENV == "local" and api_key == "dev-api-key-12345":
            return {
                "valid": True,
                "user_id": "dev-user-id",
                "email": "dev@example.com",
                "tier": "pro",
                "roles": ["user", "pro"],
                "exp": 0,
                "iat": 0,
                "error": "",
            }
        return {"valid": False, "error": "Database not connected"}

    key_doc = await db.api_keys.find_one({"api_key": api_key, "active": True})
    if not key_doc:
        # Fallback for easy dev
        if settings.APP_ENV == "local" and api_key == "dev-api-key-12345":
            return {
                "valid": True,
                "user_id": "dev-user-id",
                "email": "dev@example.com",
                "tier": "pro",
                "roles": ["user", "pro"],
                "exp": 0,
                "iat": 0,
                "error": "",
            }
        return {"valid": False, "error": "Invalid or inactive API key"}

    return {
        "valid": True,
        "user_id": key_doc["user_id"],
        "email": key_doc["email"],
        "tier": key_doc.get("tier", "free"),
        "roles": key_doc.get("roles", ["user"]),
        "exp": 0,
        "iat": 0,
        "error": "",
    }


class AuthServiceServicer(auth_pb2_grpc.AuthServiceServicer):

    async def ValidateToken(self, request, context):
        logger.info("grpc.validate_token")
        res = await validate_jwt_token(request.token)
        if not res["valid"]:
            return auth_pb2.ValidateTokenResponse(
                valid=False,
                error=res["error"],
            )

        payload = auth_pb2.TokenPayload(
            user_id=res["user_id"],
            email=res["email"],
            tier=res["tier"],
            roles=res["roles"],
            exp=res["exp"],
            iat=res["iat"],
        )
        return auth_pb2.ValidateTokenResponse(valid=True, payload=payload)

    async def ValidateApiKey(self, request, context):
        logger.info("grpc.validate_api_key")
        res = await validate_api_key_db(request.api_key)
        if not res["valid"]:
            return auth_pb2.ValidateApiKeyResponse(
                valid=False,
                error=res["error"],
            )

        payload = auth_pb2.TokenPayload(
            user_id=res["user_id"],
            email=res["email"],
            tier=res["tier"],
            roles=res["roles"],
            exp=res["exp"],
            iat=res["iat"],
        )
        return auth_pb2.ValidateApiKeyResponse(valid=True, payload=payload)


async def start_grpc_server(host: str, port: int):
    server = grpc.aio.server()
    auth_pb2_grpc.add_AuthServiceServicer_to_server(
        AuthServiceServicer(), server
    )
    server.add_insecure_port(f"{host}:{port}")
    logger.info("grpc.auth_server_starting", host=host, port=port)
    await server.start()
    return server
