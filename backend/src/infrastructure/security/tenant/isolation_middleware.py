"""
SOLID: Single Responsibility
Tenant isolation middleware with WebSocket support
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from src.infrastructure.security.auth.jwt_handler import JWTHandler
# ✅ Doğru import: tenant_context_var artık public
from src.infrastructure.security.tenant.context import (
    TenantContext, 
    tenant_context_var,
    set_tenant_context,
    reset_tenant_context
)
import logging

logger = logging.getLogger(__name__)

class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Multi-tenant isolation via JWT token
    ✅ WebSocket connections are bypassed (auth handled in Socket.IO layer)
    """
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # ✅ WebSocket bağlantılarını bypass et (Socket.IO kendi auth'unu yapar)
        if scope["type"] == "websocket":
            return await self.app(scope, receive, send)
        
        # HTTP istekleri için devam et
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        request = Request(scope, receive=receive)

        public_paths = [
            "/api/v1/auth/login",
            "/api/v1/auth/register", 
            "/api/v1/auth/refresh",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/ws",  # WebSocket mount path
        ]

        request_path = request.url.path.split("?")[0]
        if any(request_path == pub or request_path.startswith(pub + "/") for pub in public_paths):
            return await self.app(scope, receive, send)
        
        # ✅ Socket.IO internal path'leri de bypass et
        if request_path.startswith("/socket.io") or request_path.startswith("/ws/socket.io"):
            return await self.app(scope, receive, send)
        
        # ✅ Swagger/docs endpoint'lerini bypass et (opsiyonel)
        if request.url.path in ["/docs", "/redoc", "/openapi.json", "/health"]:
            return await self.app(scope, receive, send)
        
        # Authorization header'ını al
        auth_header = request.headers.get("authorization")
        
        if not auth_header or not auth_header.lower().startswith("bearer "):
            logger.warning(f"❌ No valid Bearer token: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication token"
            )
        
        # Token'ı extract et
        token = auth_header[7:].strip()
        
        # Token'ı doğrula
        try:
            payload = JWTHandler.verify_token(token, "access")
        except ValueError as e:
            logger.warning(f"❌ Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
        
        # Tenant context oluştur
        tenant_context = TenantContext(
            user_id=payload["sub"],
            tenant_id=payload["tenant_id"],
            tenant_slug=payload.get("tenant_slug"),
            schema_name=f"tenant_{payload.get('tenant_slug', 'default')}",
            role=payload.get("role", "viewer"),
            permissions=payload.get("permissions", []),
            deployment_type=payload.get("deployment_type", "cloud")
        )
        
        # Context'i request'e ekle
        request.state.tenant_context = tenant_context
        
        # Global context variable'a set et (async-safe)
        token_var = tenant_context_var.set(tenant_context)
        
        try:
            return await self.app(scope, receive, send)
        finally:
            tenant_context_var.reset(token_var)

    async def create_tenant_schema(self, schema_name: str):
        """Create PostgreSQL schema for new tenant + base tables - context-independent"""
        session = await self._get_session()
        try:
            # Explicit schema name, no context dependency
            await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            await session.execute(text(f"""
                SET search_path TO {schema_name};
                -- ... existing table creation SQL ...
            """))
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()