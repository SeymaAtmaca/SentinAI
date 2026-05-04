"""
Approval Workflow Endpoints
Human-in-the-Loop approval system
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
from src.infrastructure.messaging.websocket_manager import websocket_manager

from src.infrastructure.security.tenant.context import get_tenant_context, TenantContext
from src.infrastructure.security.rbac.guards import require_permission, Permission
from src.infrastructure.config.settings import settings
from src.infrastructure.adapters.repositories.postgres_approval_repository import PostgresApprovalRepository
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

router = APIRouter(prefix="/approvals", tags=["Approvals"])

# ================= REQUEST/RESPONSE MODELS =================

class ApprovalResponse(BaseModel):
    id: str
    action_id: str
    tenant_id: str
    requested_by: str
    action_type: str
    payload: Dict[str, Any]
    risk_score: float
    risk_factors: list
    status: str
    comments: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None

class ApproveRequest(BaseModel):
    comments: Optional[str] = Field(None, max_length=500)

class RejectRequest(BaseModel):
    comments: Optional[str] = Field(..., max_length=500, description="Rejection reason is required")

# ================= HELPER =================

def get_db_session():
    """Database session factory"""
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ================= ENDPOINTS =================


@router.get("/", response_model=list[ApprovalResponse])
@require_permission(Permission.APPROVAL_REQUEST)
async def list_approvals(
    status_filter: Optional[str] = "pending",
    limit: int = 50,
    ctx: TenantContext = Depends(get_tenant_context)
):
    """Pending/processed approvals listesi"""
    SessionLocal = get_db_session()
    async with SessionLocal() as session:
        await session.execute(text("SET search_path TO public"))
        
        # ✅ FIX: status_filter NULL ise farklı query, değilse farklı query
        # Bu, PostgreSQL'in parametre tipini belirlemesini sağlar
        if status_filter is None:
            query = text("""
                SELECT id, action_id, tenant_id, requested_by, action_type, 
                       payload, risk_score, risk_factors, status, comments,
                       created_at, decided_at
                FROM approvals
                WHERE tenant_id = :tenant_id
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            params = {"tenant_id": ctx.tenant_id, "limit": limit}
        else:
            query = text("""
                SELECT id, action_id, tenant_id, requested_by, action_type, 
                       payload, risk_score, risk_factors, status, comments,
                       created_at, decided_at
                FROM approvals
                WHERE tenant_id = :tenant_id
                AND status = :status_filter
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            params = {
                "tenant_id": ctx.tenant_id, 
                "status_filter": status_filter, 
                "limit": limit
            }
        
        result = await session.execute(query, params)
        rows = result.fetchall()
        
        return [
            ApprovalResponse(
                id=str(row[0]),
                action_id=str(row[1]),
                tenant_id=str(row[2]),
                requested_by=str(row[3]),
                action_type=row[4],
                payload=row[5],
                risk_score=float(row[6]),
                risk_factors=row[7] or [],
                status=row[8],
                comments=row[9],
                created_at=row[10],
                decided_at=row[11]
            )
            for row in rows
        ]
    
@router.get("/{approval_id}", response_model=ApprovalResponse)
@require_permission(Permission.APPROVAL_REQUEST)
async def get_approval(
    approval_id: str,
    ctx: TenantContext = Depends(get_tenant_context)
):
    """Single approval details"""
    SessionLocal = get_db_session()
    async with SessionLocal() as session:
        await session.execute(text("SET search_path TO public"))
        
        query = text("""
            SELECT id, action_id, tenant_id, requested_by, action_type, 
                   payload, risk_score, risk_factors, status, comments,
                   created_at, decided_at
            FROM approvals
            WHERE id = :id AND tenant_id = :tenant_id
        """)
        
        result = await session.execute(query, {
            "id": approval_id,
            "tenant_id": ctx.tenant_id
        })
        
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Approval not found")
        
        return ApprovalResponse(
            id=str(row[0]),
            action_id=str(row[1]),
            tenant_id=str(row[2]),
            requested_by=str(row[3]),
            action_type=row[4],
            payload=row[5],
            risk_score=float(row[6]),
            risk_factors=row[7] or [],
            status=row[8],
            comments=row[9],
            created_at=row[10],
            decided_at=row[11]
        )

@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
@require_permission(Permission.APPROVAL_APPROVE)
async def approve_request(
    approval_id: str,
    request: ApproveRequest,
    background_tasks: BackgroundTasks,
    ctx: TenantContext = Depends(get_tenant_context)
):
    """
    Approval request'i onayla
    Multi-level approval varsa bir sonraki seviyeye geçir
    """
    SessionLocal = get_db_session()
    async with SessionLocal() as session:
        await session.execute(text("SET search_path TO public"))
        
        # 1. Update approval status
        update_query = text("""
            UPDATE approvals
            SET status = 'approved',
                comments = :comments,
                decided_at = NOW(),
                decided_by = :decided_by
            WHERE id = :id AND tenant_id = :tenant_id AND status = 'pending'
            RETURNING id, action_id, action_type, payload
        """)
        
        result = await session.execute(update_query, {
            "id": approval_id,
            "tenant_id": ctx.tenant_id,
            "comments": request.comments,
            "decided_by": ctx.user_id
        })
        
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=400,
                detail="Approval not found or already processed"
            )
        
        await session.commit()

        background_tasks.add_task(
            websocket_manager.notify_approval_updated,
            tenant_id=ctx.tenant_id,
            approval={
                "id": approval_id,
                "action_type": row[2],  # action_type from RETURNING clause
                "status": "approved",
                "decided_at": datetime.now().isoformat()
            }
        )
        
        # 2. Background task: Execute the original action
        # TODO: Action execution logic (AI agent'a callback)
        background_tasks.add_task(
            execute_approved_action,
            action_id=str(row[1]),
            action_type=row[2],
            payload=row[3]
        )
        
        # 3. WebSocket notification (TODO)
        background_tasks.add_task(
            send_approval_notification,
            approval_id=approval_id,
            status="approved"
        )
        
        # Return updated approval
        return await get_approval(approval_id, ctx)

@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
@require_permission(Permission.APPROVAL_REJECT)
async def reject_request(
    approval_id: str,
    request: RejectRequest,
    ctx: TenantContext = Depends(get_tenant_context)
):
    """Approval request'i reddet"""
    SessionLocal = get_db_session()
    async with SessionLocal() as session:
        await session.execute(text("SET search_path TO public"))
        
        update_query = text("""
            UPDATE approvals
            SET status = 'rejected',
                comments = :comments,
                decided_at = NOW(),
                decided_by = :decided_by
            WHERE id = :id AND tenant_id = :tenant_id AND status = 'pending'
            RETURNING id
        """)
        
        result = await session.execute(update_query, {
            "id": approval_id,
            "tenant_id": ctx.tenant_id,
            "comments": request.comments,
            "decided_by": ctx.user_id
        })
        
        if not result.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Approval not found or already processed"
            )
        
        await session.commit()
        
        # WebSocket notification (TODO)
        # background_tasks.add_task(...)
        
        return await get_approval(approval_id, ctx)

# ================= BACKGROUND TASKS =================

async def execute_approved_action(action_id: str, action_type: str, payload: Dict[str, Any]):
    """
    Onaylanan aksiyonu gerçekleştir
    TODO: AI agent callback veya event publishing
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"✅ Executing approved action: {action_id} ({action_type})")
    # Implementation: Kafka event publish veya AI agent'a webhook

async def send_approval_notification(approval_id: str, status: str):
    """
    WebSocket ile real-time notification gönder
    TODO: WebSocket manager entegrasyonu
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔔 Approval {approval_id} {status}")