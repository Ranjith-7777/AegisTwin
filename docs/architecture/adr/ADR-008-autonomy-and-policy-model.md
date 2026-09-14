# ADR-008: Autonomy as a Dual-Gate (Playbook Tier + Policy), Not a Mode-Overrides-Tier Model

## Status
Accepted — Phase 4.

## Context

Phase 4 required 4 autonomy levels (OBSERVE, RECOMMEND, APPROVAL_REQUIRED,
AUTONOMOUS) where AUTONOMOUS "may auto-execute ONLY policy-eligible
actions," explicitly warning that autonomy must never mean "execute
everything." The existing Phase 3 catalogue
(`response_playbook_service.py`) already assigns each of its 9 playbooks
a fixed `approval_tier` (`automatic_candidate`, `analyst_approval`,
`administrator_approval`, or `prohibited`) reflecting a human catalogue
author's judgment of that specific action's risk. A lightweight
policy-as-code layer (see ADR-... none prior; this is the first policy
engine in the codebase) was also required, deliberately not OPA.

## Decision

Automatic execution requires **two independent gates to both agree**,
neither able to unilaterally authorize it:

1. The playbook's own catalogue `approval_tier` must already be
   `automatic_candidate` — a fixed property autonomy mode cannot
   override.
2. `policy_service.evaluate_response_policies()` must return
   `overall_pass = True` for POL-003 (reversibility), POL-004 (impact),
   POL-005 (blast radius), and POL-006 (critical data-store isolation) —
   all evaluated only when `autonomy_mode == "autonomous"`.

Both `SafetyGovernorAgent` and `ApprovalRouterAgent` independently
re-check this combination rather than one agent trusting the other's
gate — see `AUTONOMY_MODEL.md`. The policy catalogue itself is 7 plain
Python functions (`policy_service.py`) returning typed
`PolicyEvaluation` results, not a rules DSL or an external engine.

## Alternatives considered

1. **Let AUTONOMOUS mode bypass a playbook's own tier for any
   policy-passing action.** Rejected as the primary failure mode the
   phase spec warns against: a playbook's tier already encodes a human
   judgment about that specific action's blast radius and
   reversibility risk (e.g. `quarantine-synthetic-application` is
   `administrator_approval` specifically because it is `high` impact and
   `service`-scoped even though it is reversible) — a generic policy
   threshold check alone cannot substitute for that per-action review.
2. **Introduce OPA/Gatekeeper (or a similar dedicated policy engine) for
   Phase 4.** Rejected per the phase's own explicit instruction and
   escalation list — this is a modular monolith with 7 simple policies;
   a dedicated engine and its operational overhead (a sidecar process,
   a policy bundle format, a new failure mode for policy evaluation
   itself) would be disproportionate. Revisit only if the policy count
   or complexity grows enough to need composable rule authoring by
   non-engineers.
3. **Make policy evaluation return a single boolean.** Rejected per the
   phase's explicit requirement that every policy decision report
   policy_id/name/result/reason — a single boolean would hide exactly
   the information a professor-facing UI and an auditor need.

## Consequences

- Positive: raising autonomy mode can only ever *unlock* automation for
  actions the catalogue authors already judged safe to automate (tier =
  `automatic_candidate`) and that pass every automation-specific policy
  — it can never make a previously-gated action fully automatic on its
  own.
- Positive: policy evaluation is pure, synchronous, and in-process — no
  new deployment topology, no new latency source, and trivially
  unit-testable (`tests/test_policy_engine.py`).
- Negative: today's catalogue has exactly one `automatic_candidate`
  playbook (`increase-synthetic-monitoring`, itself a zero-connectivity-
  change observation action), so the demonstrable "genuine autonomous
  self-healing" scenario is necessarily an evidence-gathering action,
  not a containment action. This is accepted and documented (see
  `AUTONOMY_MODEL.md`) as the honest, safe consequence of the design,
  not worked around by loosening the gate.

## Future reconsideration trigger

Revisit the playbook-tier gate if a future phase's catalogue introduces
additional genuinely low-risk, reversible, single-resource-scoped
containment actions that a human reviewer judges safe to pre-tier as
`automatic_candidate` — the dual-gate model already supports that
without any change to `policy_service.py` or the agents.
