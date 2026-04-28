from fastapi import Request, HTTPException, status
from jose import JWTError
from src.infrastructure.security.auth.jwt_handler import JWTHandler
from src.infrastructure.security.tenant.context import TenantContext, set_tenant_context, reset_tenant_context
from src.infrastructure.config.settings import settings

class TenantIsolationMiddleware:
    """
    SOLID: Single Responsibility
    Her request'te tenant izolasyonunu sağlar
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        request = Request(scope, receive=receive)
        
        # Skip auth for public endpoints
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await self.app(scope, receive, send)
        
        # Skip auth for login/register
        if request.url.path.startswith("/api/v1/auth"):
            return await self.app(scope, receive, send)
        
        # Extract and verify token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        try:
            token = auth_header.split(" ")[1]
            payload = JWTHandler.verify_token(token, "access")
            
            # Build tenant context
            tenant_ctx = TenantContext(
                tenant_id=payload["tenant_id"],
                tenant_slug=payload.get("tenant_slug", ""),
                schema_name=f"tenant_{payload.get('tenant_slug', '')}",
                user_id=payload["sub"],
                role=payload["role"],
                permissions=payload.get("permissions", []),
                deployment_type=payload.get("deployment_type", "cloud")
            )
            
            # Set context for this request
            token_ctx = set_tenant_context(tenant_ctx)
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        except KeyError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token missing required claim: {e}"
            )
        
        try:
            # Execute request with tenant context
            return await self.app(scope, receive, send)
        finally:
            # Always reset context after request
            reset_tenant_context(token_ctx)