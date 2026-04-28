from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import uuid

class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    MEMBER = "member"
    VIEWER = "viewer"
    AUDITOR = "auditor"

@dataclass
class User:
    """
    SOLID: Single Responsibility
    User entity - sadece veri yapısı ve basit business logic
    """
    
    # === REQUIRED FIELDS (No defaults) ===
    tenant_id: uuid.UUID
    email: str
    password_hash: str
    role: Role
    
    # === OPTIONAL FIELDS (With defaults) ===
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    
    def has_permission(self, permission: str) -> bool:
        """Role-based permission check"""
        PERMISSIONS = {
            Role.SUPER_ADMIN: {"*"},
            Role.TENANT_ADMIN: {"model:*", "approval:*", "audit:read"},
            Role.MEMBER: {"model:read", "model:create", "audit:read"},
            Role.VIEWER: {"model:read", "audit:read"},
            Role.AUDITOR: {"audit:read", "audit:export"},
        }
        user_perms = PERMISSIONS.get(self.role, set())
        return "*" in user_perms or permission in user_perms