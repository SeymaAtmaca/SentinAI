"""
Guardian Gateway: AI Agent Action Interception
PDF Reference: "Human-in-the-Loop Approval System Architecture"
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
import uuid
import logging

from src.infrastructure.security.tenant.context import get_tenant_context, TenantContext
from src.infrastructure.security.rbac.guards import require_permission, Permission
from src.infrastructure.config.settings import settings

# Use case ve modeller
from src.application.use_cases.intercept_action.models import InterceptActionCommand, InterceptActionResult, ActionStatus
from src.application.use_cases.intercept_action.policy_engine import PolicyEngine

# Repository interface'leri
from src.domain.repositories.IAuditRepository import IAuditRepository
from src.domain.repositories.IApprovalRepository import IApprovalRepository

# Repository implementasyonları (Manuel injection için)
from src.infrastructure.adapters.repositories.postgres_audit_repository import PostgresAuditRepository
from src.infrastructure.adapters.repositories.postgres_approval_repository import PostgresApprovalRepository

# Use case (Manuel injection için)
from src.application.use_cases.intercept_action.intercept_action_use_case import InterceptActionUseCase
from src.infrastructure.messaging.websocket_manager import websocket_manager

router = APIRouter(prefix="/guard", tags=["Guardian"])
logger = logging.getLogger(__name__)

# ================= REQUEST/RESPONSE MODELS =================

class InterceptActionRequest(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=100)
    action_type: str = Field(..., pattern=r'^[a-z_]+$')
    payload: Dict[str, Any] = Field(...)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('payload')
    def validate_payload_size(cls, v):
        import json
        if len(json.dumps(v)) > 100 * 1024:
            raise ValueError('Payload too large (max 100KB)')
        return v

class InterceptActionResponse(BaseModel):
    action_id: str
    status: str
    risk_score: float
    message: Optional[str] = None
    approval_url: Optional[str] = None

# ================= ENDPOINTS =================

@router.post("/intercept", response_model=InterceptActionResponse)
@require_permission(Permission.APPROVAL_REQUEST)
async def intercept_action(
    request: InterceptActionRequest,
    background_tasks: BackgroundTasks,
    ctx: TenantContext = Depends(get_tenant_context)
):
    """
    AI ajanının aksiyonunu intercept eder, risk analizi yapar,
    gerekirse human approval'a yönlendirir.
    """
    
    # --- MANUEL DEPENDENCY INJECTION (Development için) ---
    # Repository instances oluştur
    audit_repo: IAuditRepository = PostgresAuditRepository(settings.DATABASE_URL)
    approval_repo: IApprovalRepository = PostgresApprovalRepository(settings.DATABASE_URL)
    
    # Policy Engine ve Use Case oluştur
    policy_engine = PolicyEngine()
    use_case = InterceptActionUseCase(
        audit_repo=audit_repo,
        approval_repo=approval_repo,
        policy_engine=policy_engine
    )
    # -------------------------------------------------------
    
    # 1. Command oluştur
    command = InterceptActionCommand(
        agent_name=request.agent_name,
        action_type=request.action_type,
        payload=request.payload,
        metadata=request.metadata,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id
    )
    
    # 2. Use case'i çalıştır
    result: InterceptActionResult = await use_case.execute(command)
    
    # 3. Eğer PENDING_APPROVAL ise, WebSocket notification (simülasyon)
    if result.status == ActionStatus.PENDING_APPROVAL:
        background_tasks.add_task(
            websocket_manager.notify_approval_created,
            tenant_id=ctx.tenant_id,
            approval={
                "id": result.action_id,
                "action_type": request.action_type,
                "risk_score": result.risk_score,
                "created_at": datetime.now().isoformat()
            }
    )
    elif result.status == ActionStatus.BLOCKED:
        background_tasks.add_task(
            websocket_manager.notify_high_risk_blocked,
            tenant_id=ctx.tenant_id,
            action={
                "action_id": result.action_id,
                "action_type": request.action_type,
                "risk_score": result.risk_score
            }
        )
    
    # 4. Response oluştur
    response = InterceptActionResponse(
        action_id=result.action_id,
        status=result.status.value,
        risk_score=result.risk_score,
        message=result.message
    )
    
    if result.status == ActionStatus.PENDING_APPROVAL:
        response.approval_url = f"/api/v1/approvals/{result.action_id}"
    
    return response

# ================= HELPERS =================

async def send_approval_notification(tenant_id: str, action_id: str, risk_score: float):
    """
    WebSocket üzerinden approval notification gönder
    TODO: WebSocket manager entegrasyonu
    """
    logger.info(
        f"🔔 Approval notification: tenant={tenant_id}, action={action_id}, risk={risk_score}"
    )