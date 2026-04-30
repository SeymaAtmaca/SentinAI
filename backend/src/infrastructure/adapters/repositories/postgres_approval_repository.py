from typing import Dict, Any, List
import json
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.domain.repositories.IApprovalRepository import IApprovalRepository

class PostgresApprovalRepository(IApprovalRepository):
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
    
    async def create_approval_request(
        self,
        action_id: str,
        tenant_id: str,
        requested_by: str,
        action_type: str,
        payload: Dict[str, Any],
        risk_score: float,
        risk_factors: List[str]
    ) -> str:
        approval_id = str(uuid.uuid4())
        async with self.SessionLocal() as session:
            await session.execute(text("SET search_path TO public"))
            
            # Dict ve List'leri JSON string'e çevir
            payload_json = json.dumps(payload, default=str)
            risk_factors_json = json.dumps(risk_factors)
            
            # Named parameters + CAST ile JSONB
            query = text("""
                INSERT INTO approvals (
                    id, action_id, tenant_id, requested_by, action_type, 
                    payload, risk_score, risk_factors, status
                )
                VALUES (
                    :id, :action_id, :tenant_id, :requested_by, :action_type,
                    CAST(:payload AS JSONB), :risk_score, CAST(:risk_factors AS JSONB), :status
                )
                RETURNING id
            """)
            
            result = await session.execute(query, {
                "id": approval_id,
                "action_id": action_id,
                "tenant_id": tenant_id,
                "requested_by": requested_by,
                "action_type": action_type,
                "payload": payload_json,
                "risk_score": risk_score,
                "risk_factors": risk_factors_json,
                "status": "pending"
            })
            await session.commit()
            return approval_id