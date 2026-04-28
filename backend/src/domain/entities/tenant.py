from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

@dataclass
class Tenant:
    """
    SOLID: Single Responsibility
    Tenant entity - sadece veri yapısı ve basit business logic
    """
    
    # === REQUIRED FIELDS (No defaults)  ===
    slug: str                    # URL identifier: "abc-company"
    name: str                    # Company name: "ABC Corp"
    schema_name: str            # DB schema: "tenant_abc_company"
    
    # === OPTIONAL FIELDS (With defaults)  ===
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: str = "trial"        # trial, active, past_due, suspended, canceled
    deployment_type: str = "cloud"  # cloud, on_premise
    stripe_customer_id: Optional[str] = None
    subscription_plan: Optional[str] = None
    subscription_status: Optional[str] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    def is_active(self) -> bool:
        """Tenant aktif mi?"""
        return self.status == "active"
    
    def is_suspended(self) -> bool:
        """Tenant dondurulmuş mu?"""
        return self.status in ("suspended", "canceled", "past_due")
    
    def get_schema_name(self) -> str:
        """PostgreSQL schema adını döndür"""
        return self.schema_name