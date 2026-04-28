from functools import wraps
from fastapi import HTTPException, status, Depends
from typing import Callable, Optional
from src.infrastructure.security.tenant.context import get_tenant_context

def require_permission(permission: str):
    """
    Decorator: Endpoint için gerekli yetkiyi kontrol eder
    SOLID: Open/Closed - Yeni permission'lar kolay eklenebilir
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = get_tenant_context()
            
            # Super admin her şeyi yapabilir
            if ctx.role == "super_admin":
                return await func(*args, **kwargs)
            
            # Wildcard permission check
            if f"{permission.split(':')[0]}:*" in ctx.permissions:
                return await func(*args, **kwargs)
            
            # Specific permission check
            if permission not in ctx.permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {permission}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(*allowed_roles: str):
    """
    Decorator: Sadece belirli roller erişebilir
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = get_tenant_context()
            
            if ctx.role not in allowed_roles and ctx.role != "super_admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient role. Allowed: {', '.join(allowed_roles)}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def check_tenant_status():
    """
    Dependency: Tenant'ın aktif olup olmadığını kontrol eder
    """
    def checker():
        ctx = get_tenant_context()
        
        if ctx.deployment_type == "cloud" and ctx.status in ("suspended", "canceled", "past_due"):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Account {ctx.status}. Please update billing or contact support."
            )
        
        return ctx
    return Depends(checker)