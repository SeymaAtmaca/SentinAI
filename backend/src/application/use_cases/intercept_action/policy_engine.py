"""
SOLID: Open/Closed Principle
Configurable policy engine for risk assessment
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
from enum import Enum
import re

from .models import InterceptActionCommand, ActionStatus
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.application.use_cases.intercept_action.intercept_action_use_case import InterceptActionCommand


@dataclass
class PolicyRule:
    """Single policy rule configuration"""
    name: str
    condition: str  # Simple expression: "amount > 50000"
    risk_weight: float  # 0.0 - 1.0
    action: str  # "add_risk", "block", "require_approval"
    description: str = ""

@dataclass
class PolicyConfig:
    """Policy engine configuration"""
    rules: List[PolicyRule] = field(default_factory=list)
    risk_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "low": 0.3,
        "medium": 0.6,
        "high": 0.8
    })
    auto_block_threshold: float = 0.9
    auto_approve_threshold: float = 0.2

class PolicyEngine:
    def __init__(self, config: PolicyConfig = None):
        self.config = config or self._default_config()
    
    def _default_config(self) -> PolicyConfig:
        return PolicyConfig(rules=[
            PolicyRule("high_value_payment", "action_type == 'payment' and payload.get('amount', 0) > 50000", 0.5, "require_approval", "Payments >50K"),
            PolicyRule("very_high_payment", "action_type == 'payment' and payload.get('amount', 0) > 250000", 0.4, "block", "Payments >250K"),
            PolicyRule("pii_detected", "any(k in payload for k in ['tc_no', 'ssn', 'credit_card'])", 0.3, "add_risk", "PII found"),
            PolicyRule("model_deploy", "action_type in ['model_deploy', 'model_delete']", 0.4, "require_approval", "Model changes"),
        ])
    
    def calculate_risk(self, cmd: InterceptActionCommand) -> Tuple[float, List[str]]:
        score, factors = 0.0, []
        for rule in self.config.rules:
            if self._eval(rule.condition, cmd):
                score += rule.risk_weight
                factors.append(rule.name)
        return min(score, 1.0), factors
    
    def evaluate_policies(self, cmd: InterceptActionCommand, risk_score: float) -> Tuple[List[str], ActionStatus]:
        violations = []
        for rule in self.config.rules:
            if rule.action == "block" and self._eval(rule.condition, cmd):
                violations.append(rule.name)
        if violations: return violations, ActionStatus.BLOCKED
        
        for rule in self.config.rules:
            if rule.action == "require_approval" and self._eval(rule.condition, cmd):
                violations.append(rule.name)
                
        if risk_score >= self.config.auto_block_threshold: return violations or ["high_risk"], ActionStatus.BLOCKED
        if risk_score >= self.config.risk_thresholds["medium"] or violations: return violations, ActionStatus.PENDING_APPROVAL
        return [], ActionStatus.ALLOWED

    def _eval(self, condition: str, cmd: InterceptActionCommand) -> bool:
        try:
            return bool(eval(condition, {"__builtins__": {}}, {
                "action_type": cmd.action_type, "payload": cmd.payload, 
                "agent_name": cmd.agent_name, "metadata": cmd.metadata or {}
            }))
        except: return False
        """
        Evaluate a simple policy condition
        
        Supported: comparisons, logical ops, dict access
        Example: "action_type == 'payment' and payload.get('amount', 0) > 50000"
        """
        # Safe eval context
        context = {
            "action_type": cmd.action_type,
            "payload": cmd.payload,
            "agent_name": cmd.agent_name,
            "metadata": cmd.metadata or {}
        }
        
        try:
            # Simple safe eval (production'da daha güvenli parser kullanılmalı)
            return bool(eval(condition, {"__builtins__": {}}, context))
        except Exception:
            return False  # Fail-safe: condition error = no match