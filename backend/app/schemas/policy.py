"""Phase 4 policy-as-code: a small, declarative, inspectable set of rules
governing Blue Agent decisions. Deliberately NOT OPA/Gatekeeper - this is a
modular monolith and these policies are simple enough that a dedicated
policy engine would be disproportionate. See
docs/architecture/POLICY_ENGINE.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

PolicyResult = Literal["pass", "fail", "not_applicable"]


class PolicyDefinition(BaseModel):
    policy_id: str
    name: str
    purpose: str
    applies_to: str
    decision_effect: str
    enabled: bool
    synthetic: Literal[True] = True


class PolicyEvaluation(BaseModel):
    policy_id: str
    policy_name: str
    result: PolicyResult
    reason: str
    synthetic: Literal[True] = True


class PolicyEvaluationResult(BaseModel):
    evaluations: list[PolicyEvaluation]
    overall_pass: bool
    failed_policy_ids: list[str]
    synthetic: Literal[True] = True
