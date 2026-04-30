"""
SOLID: Open/Closed & Interface Segregation
RBAC permission guards for endpoint protection
"""

from functools import wraps
from enum import Enum
from typing import Callable, Optional, Set
from fastapi import HTTPException, status, Depends
from src.infrastructure.security.tenant.context import get_tenant_context

# ================= PERMISSION ENUM =================
class Permission(str, Enum):
    """
    Granular permissions - ISP (Interface Segregation) compliant
    Format: "resource:action" (e.g., "model:read", "approval:approve")
    """
    # Model Management
    MODEL_READ = "model:read"
    MODEL_CREATE = "model:create"
    MODEL_UPDATE = "model:update"
    MODEL_DELETE = "model:delete"
    MODEL_DEPLOY = "model:deploy"
    
    # Approval Workflow
    APPROVAL_REQUEST = "approval:request"
    APPROVAL_APPROVE = "approval:approve"
    APPROVAL_REJECT = "approval:reject"
    APPROVAL_DEFER = "approval:defer"
    
    # Drift & Monitoring
    DRIFT_READ = "drift:read"
    METRICS_READ = "metrics:read"
    ALERTS_MANAGE = "alerts:manage"
    
    # System & Tenant Management
    TENANT_MANAGE = "tenant:manage"
    USER_MANAGE = "user:manage"
    POLICY_MANAGE = "policy:manage"
    
    # Audit & Compliance
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    
    # Billing (Enterprise)
    BILLING_READ = "billing:read"
    BILLING_MANAGE = "billing:manage"

# ================= ROLE-PERMISSION MATRIX =================
ROLE_PERMISSIONS: dict[str, Set[Permission]] = {
    "super_admin": set(Permission),  # Tüm yetkiler
    
    "tenant_admin": {
        Permission.MODEL_READ,
        Permission.MODEL_CREATE,
        Permission.MODEL_UPDATE,
        Permission.MODEL_DELETE,
        Permission.MODEL_DEPLOY,
        Permission.APPROVAL_REQUEST,
        Permission.APPROVAL_APPROVE,
        Permission.APPROVAL_REJECT,
        Permission.DRIFT_READ,
        Permission.METRICS_READ,
        Permission.ALERTS_MANAGE,
        Permission.USER_MANAGE,
        Permission.POLICY_MANAGE,
        Permission.AUDIT_READ,
        Permission.BILLING_READ,
    },
    
    "member": {
        Permission.MODEL_READ,
        Permission.MODEL_CREATE,
        Permission.APPROVAL_REQUEST,
        Permission.DRIFT_READ,
        Permission.METRICS_READ,
        Permission.AUDIT_READ,
    },
    
    "viewer": {
        Permission.MODEL_READ,
        Permission.DRIFT_READ,
        Permission.METRICS_READ,
        Permission.AUDIT_READ,
    },
    
    "auditor": {
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.MODEL_READ,
        Permission.DRIFT_READ,
    },
}

# ================= RBAC GUARDS =================

def require_permission(required_permission: Permission):
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
            
            user_permissions = ROLE_PERMISSIONS.get(ctx.role, set())
            
            # Wildcard permission check (örn: "model:*" → tüm model yetkileri)
            resource = required_permission.value.split(":")[0]
            if f"{resource}:*" in user_permissions:
                return await func(*args, **kwargs)
            
            # Specific permission check
            if required_permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {required_permission.value}"
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