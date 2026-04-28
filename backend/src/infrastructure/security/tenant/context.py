import contextvars
from dataclasses import dataclass
from typing import Optional

@dataclass
class TenantContext:
    """
    Thread-safe tenant context holder
    Her request için izole edilmiş tenant bilgisi
    """
    tenant_id: str
    tenant_slug: str
    schema_name: str
    user_id: str
    role: str
    permissions: list[str]
    deployment_type: str = "cloud"

# Context variable for async-safe storage
_tenant_ctx: contextvars.ContextVar[Optional[TenantContext]] = contextvars.ContextVar(
    "tenant_ctx", default=None
)

def get_tenant_context() -> TenantContext:
    """Mevcut request'in tenant context'ini al"""
    ctx = _tenant_ctx.get()
    if ctx is None:
        raise RuntimeError("Tenant context not set. Middleware not executed.")
    return ctx

def set_tenant_context(ctx: TenantContext) -> contextvars.Token:
    """Tenant context'i ayarla ve token döndür (reset için)"""
    return _tenant_ctx.set(ctx)

def reset_tenant_context(token: contextvars.Token):
    """Context'i eski haline döndür"""
    _tenant_ctx.reset(token)