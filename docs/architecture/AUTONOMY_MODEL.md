# Autonomy Model

Four autonomy modes, one persisted singleton
(`AutonomyConfigRecord`, `id="singleton"`, analogous to the existing
`SystemState` singleton pattern), default `RECOMMEND`. See
`app/schemas/autonomy.py` and `app/services/autonomy_service.py`.

| Mode | Behavior |
|---|---|
| `OBSERVE` | Detection/evidence only — no response plan is generated. `WorkflowCoordinator.run()` returns immediately with `orchestration: null`. |
| `RECOMMEND` | Candidate plans are generated and ranked (`blue_planning_service.compare()`), never automatically orchestrated or executed. |
| `APPROVAL_REQUIRED` | A plan is generated, validated, and an orchestration is created — but execution always requires an explicit analyst/administrator approval decision, regardless of playbook tier. |
| `AUTONOMOUS` | Eligible low-impact, reversible, policy-passing actions may execute automatically. **This never means "execute everything"** — see below. |

Raising the mode to `AUTONOMOUS` requires an explicit `confirm: true` on
`PUT /api/v1/autonomy` (`AutonomyConfigUpdate.confirm`); the API returns
`422 AUTONOMY_CONFIRMATION_REQUIRED` otherwise. The frontend
(`VerificationPage.tsx`'s `AutonomyControl`) surfaces this as a visible
inline confirmation panel naming the consequence, not a native
`confirm()` dialog — a deliberate, non-hidden safety confirmation per the
Phase 4 spec, not a dramatic warning.

## AUTONOMOUS never means "execute everything"

Automatic execution requires **all** of the following, enforced across
two independent gates that must both agree:

1. **The playbook's own catalogue tier is `automatic_candidate`.** This
   is a fixed, Phase-3 catalogue property (`response_playbook_service.py`)
   that autonomy mode cannot override. In the current 9-playbook
   catalogue, exactly **one** playbook — `increase-synthetic-monitoring`
   (an `annotate_node` operation with zero real connectivity change) —
   carries this tier. Every playbook that removes or restricts a real
   relationship (`block-synthetic-route`, `isolate-synthetic-endpoint`,
   `quarantine-synthetic-application`, `protect-sensitive-synthetic-database`,
   etc.) requires `analyst_approval` or `administrator_approval` no
   matter what autonomy mode is active.
2. **Every applicable policy passes** (`policy_service.evaluate_response_policies()`,
   POL-003 through POL-006 — see `POLICY_ENGINE.md`): the action must be
   reversible, within the operational-impact and blast-radius limits for
   automation, and not targeting a high/critical database or object
   store unless the playbook already requires administrator approval.

Both `SafetyGovernorAgent` and `ApprovalRouterAgent`
(`app/services/orchestration_agents.py`) check this independently — the
Safety Governor computes `automatic_approved` only when both conditions
hold, and the Approval Router separately re-checks
`autonomy_mode == "autonomous" and tier == "automatic_candidate" and
policy_pass` before returning the `"automatic"` decision. Neither agent
trusts the other's gate alone.

**Consequence, verified by test** (`tests/test_workflow_coordinator.py::
test_autonomous_mode_still_requires_approval_for_real_containment`): in
a real staged-compromise incident, the highest-ranked candidate by
Response Utility Score is `block-synthetic-route` (real security value,
`analyst_approval` tier) — even in `AUTONOMOUS` mode, this correctly
still routes to `awaiting_analyst_approval`. The one demonstrable
end-to-end autonomous self-healing loop
(`test_autonomous_self_healing_for_the_one_automation_eligible_playbook`)
uses the one playbook the catalogue and policy engine jointly permit to
run without a human, and shows create → automatic approval → execute →
verify completing with zero human intervention.

## Why this design (not "AUTONOMOUS overrides everything")

An earlier, simpler design considered letting `AUTONOMOUS` mode bypass a
playbook's own approval tier for any policy-passing action. Rejected:
that would let mode selection alone make a high-impact, hard-to-reverse
action (e.g. quarantining a Kubernetes pod, `administrator_approval`
tier) execute without a human ever having reviewed *that specific
playbook's* risk profile — exactly the "AUTONOMOUS means execute
everything" failure mode the Phase 4 spec explicitly prohibits. Gating
on both the playbook's fixed tier and the policy result means autonomy
mode can only ever *unlock* automation for actions the catalogue authors
already judged safe to automate, never override that judgment.

## Persistence and events

`autonomy_service.set_mode()` publishes `EventType.AUTONOMY_DECISION`
with `AutonomyDecisionPayload(autonomy_mode, recommendation_id="n/a",
decision=f"mode_changed:{previous}->{new}", reason=...)` for every mode
change, and commits the new mode to `autonomy_config` immediately —
there is no pending/staged mode state. `autonomy_service.require_mode()`
is the single read path every Phase 4 service uses; it never
independently re-derives or caches the mode.
