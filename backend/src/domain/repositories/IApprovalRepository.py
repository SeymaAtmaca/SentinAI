"""
SOLID: Dependency Inversion Principle
Approval workflow interface - Domain layer
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class IApprovalRepository(ABC):
    @abstractmethod
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
        """
        Onay isteği oluştur
        Returns: approval_request_id
        """
        pass