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
tenant_context_var: contextvars.ContextVar[Optional[TenantContext]] = contextvars.ContextVar(
    "tenant_context", default=None
)

def get_tenant_context() -> TenantContext:
    """Mevcut request'in tenant context'ini al"""
    ctx = tenant_context_var.get()
    if ctx is None:
        raise RuntimeError("Tenant context not set. Middleware not executed.")
    return ctx

def set_tenant_context(ctx: TenantContext) -> contextvars.Token:
    """Tenant context'i ayarla ve token döndür (reset için)"""
    return tenant_context_var.set(ctx)

def reset_tenant_context(token: contextvars.Token):
    """Context'i eski haline döndür"""
    tenant_context_var.reset(token)