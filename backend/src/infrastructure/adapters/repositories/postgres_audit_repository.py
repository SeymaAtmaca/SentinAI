from typing import Optional, Dict, Any
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.domain.repositories.IAuditRepository import IAuditRepository

class PostgresAuditRepository(IAuditRepository):
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
    
    async def log_action(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        payload: Dict[str, Any]
    ) -> None:
        async with self.SessionLocal() as session:
            await session.execute(text("SET search_path TO public"))
            
            # Dict'i JSON string'e çevir
            payload_json = json.dumps(payload, default=str)
            
            # Named parameters + CAST ile JSONB
            query = text("""
                INSERT INTO audit_logs (tenant_id, user_id, action, resource_type, resource_id, payload)
                VALUES (:tenant_id, :user_id, :action, :resource_type, :resource_id, CAST(:payload AS JSONB))
            """)
            
            await session.execute(query, {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "payload": payload_json
            })
            await session.commit()