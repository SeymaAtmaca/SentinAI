"""
SOLID: Single Responsibility
Policy Engine core logic for action interception
"""

from dataclasses import field
from typing import Optional, Dict, Any, List
import uuid
import json

# ✅ 1. Veri sınıflarını models.py'den çekiyoruz (Duplicate kaldırıldı)
from .models import InterceptActionCommand, InterceptActionResult, ActionStatus
from .policy_engine import PolicyEngine

# ✅ 2. Repository interface'lerini import ediyoruz
from src.domain.repositories.IAuditRepository import IAuditRepository
from src.domain.repositories.IApprovalRepository import IApprovalRepository

# ================= USE CASE =================

class InterceptActionUseCase:
    """
    Main use case for intercepting and evaluating AI agent actions
    
    Flow:
    1. Calculate risk score (Policy Engine)
    2. Evaluate policies
    3. Make decision (ALLOW/BLOCK/PENDING)
    4. Log to audit trail
    5. Create approval request if needed
    """
    
    def __init__(
        self,
        audit_repo: IAuditRepository,
        approval_repo: IApprovalRepository,
        policy_engine: PolicyEngine
    ):
        self.audit_repo = audit_repo
        self.approval_repo = approval_repo
        self.policy_engine = policy_engine
    
    async def execute(self, cmd: InterceptActionCommand) -> InterceptActionResult:
        """Execute the interception workflow"""
        
        # 1. Risk scoring
        risk_score, risk_factors = self.policy_engine.calculate_risk(cmd)
        
        # 2. Policy evaluation
        violations, decision = self.policy_engine.evaluate_policies(cmd, risk_score)
        
        # 3. Generate action ID
        action_id = str(uuid.uuid4())
        
        # 4. Audit logging (immutable)
        await self.audit_repo.log_action(
            tenant_id=cmd.tenant_id,
            user_id=cmd.user_id,
            action=f"action_intercept:{cmd.action_type}",
            resource_type="ai_agent",
            resource_id=None,
            payload={
                "agent_name": cmd.agent_name,
                "payload_summary": self._summarize_payload(cmd.payload),
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "violations": violations,
                "decision": decision.value
            }
        )
        
        # 5. If PENDING, create approval request
        if decision == ActionStatus.PENDING_APPROVAL:
            await self.approval_repo.create_approval_request(
                action_id=action_id,
                tenant_id=cmd.tenant_id,
                requested_by=cmd.user_id,
                action_type=cmd.action_type,
                payload=cmd.payload,
                risk_score=risk_score,
                risk_factors=risk_factors
            )
        
        # 6. Build result message
        message = self._build_message(decision, risk_score, violations)
        
        return InterceptActionResult(
            action_id=action_id,
            status=decision,
            risk_score=risk_score,
            message=message,
            policy_violations=violations
        )
    
    def _summarize_payload(self, payload: Dict[str, Any], max_length: int = 500) -> str:
        """Create a safe summary of payload for logging"""
        summary = json.dumps(payload, default=str)[:max_length]
        return summary + "..." if len(summary) == max_length else summary
    
    def _build_message(self, decision: ActionStatus, risk_score: float, violations: List[str]) -> Optional[str]:
        """Build human-readable message based on decision"""
        if decision == ActionStatus.ALLOWED:
            return f"Action approved (risk: {risk_score:.2f})"
        elif decision == ActionStatus.BLOCKED:
            return f"Action blocked: {', '.join(violations)}" if violations else "Action blocked due to high risk"
        else:  # PENDING_APPROVAL
            return f"Action requires approval (risk: {risk_score:.2f})"