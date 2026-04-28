from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

@dataclass
class AuditLog:
    """
    Immutable audit log entity
    SOLID: Single Responsibility
    """
    
    # === REQUIRED FIELDS (No defaults)  ===
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    action: str                  # "login", "model_create", "approval_grant"
    
    # === OPTIONAL FIELDS (With defaults) ===
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    resource_type: Optional[str] = None
    resource_id: Optional[uuid.UUID] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Immutable: No update/delete methods (compliance için)