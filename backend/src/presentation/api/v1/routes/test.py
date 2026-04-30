"""
Test endpoints for auth & tenant isolation verification
Sadece development için - production'da kaldırılacak
"""

from src.infrastructure.security.tenant.context import get_tenant_context, TenantContext
from fastapi import APIRouter, Depends, HTTPException, status
from src.infrastructure.security.tenant.context import get_tenant_context, TenantContext
from src.infrastructure.security.rbac.guards import require_permission, Permission

router = APIRouter(prefix="/test", tags=["Test - Dev Only"])

@router.get("/me")
async def get_current_user(ctx: TenantContext = Depends(get_tenant_context)):
    """
    Mevcut tenant context'ini döndür
    Auth middleware'inin çalıştığını test etmek için
    """
    return {
        "user_id": ctx.user_id,
        "tenant_id": ctx.tenant_id,
        "tenant_slug": ctx.tenant_slug,
        "schema_name": ctx.schema_name,
        "role": ctx.role,
        "permissions": ctx.permissions,
        "deployment_type": ctx.deployment_type
    }

@router.get("/protected")
@require_permission(Permission.MODEL_READ)
async def protected_endpoint(ctx: TenantContext = Depends(get_tenant_context)):
    """
    RBAC guard'ı ile korunan endpoint
    Sadece 'model:read' yetkisi olanlar erişebilir
    """
    return {
        "message": "✓ Access granted!",
        "tenant": ctx.tenant_slug,
        "role": ctx.role
    }

@router.get("/admin-only")
@require_permission(Permission.TENANT_MANAGE)
async def admin_only_endpoint(ctx: TenantContext = Depends(get_tenant_context)):
    """
    Sadece tenant_admin ve super_admin erişebilir
    """
    return {
        "message": "✓ Admin access granted!",
        "tenant": ctx.tenant_slug,
        "note": "This endpoint requires TENANT_MANAGE permission"
    }