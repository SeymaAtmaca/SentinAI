"""
SOLID: Dependency Inversion Principle
Audit logging interface - Domain layer
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class IAuditRepository(ABC):
    @abstractmethod
    async def log_action(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        payload: Dict[str, Any]
    ) -> None:
        """Immutable audit log kaydı oluştur"""
        pass