"""
Shared models to break circular imports
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
import uuid

class ActionStatus(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    PENDING_APPROVAL = "PENDING_APPROVAL"

@dataclass
class InterceptActionCommand:
    agent_name: str
    action_type: str
    payload: Dict[str, Any]
    tenant_id: str
    user_id: str
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class InterceptActionResult:
    action_id: str
    status: ActionStatus
    risk_score: float
    message: Optional[str] = None
    policy_violations: List[str] = field(default_factory=list)