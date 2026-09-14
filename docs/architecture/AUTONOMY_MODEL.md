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
   is a fixed catalogue property (`response_playbook_service.py`) that
   autonomy mode cannot override. Exactly **two** of the 10 playbooks
   carry this tier:
   - `increase-synthetic-monitoring` — an `annotate_node` operation with
     zero real connectivity change (observe-only).
   - `quarantine-synthetic-ingress-edge` (Phase 4 final correction pass)
     — a genuine `remove_edge` operation. See "The one autonomous
     containment action" below.

   Every other playbook that removes or restricts a real relationship
   (`block-synthetic-route`, `isolate-synthetic-endpoint`,
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

**Consequence, verified by test**
(`tests/test_workflow_coordinator.py::
test_autonomous_mode_still_requires_approval_for_an_analyst_tier_candidate`):
`block-synthetic-route` has real, evidenced security value but its
catalogue tier is `analyst_approval` — creating an orchestration for it
directly still routes to `awaiting_analyst_approval` even in `AUTONOMOUS`
mode, regardless of how it ranks against other candidates.

## The one autonomous containment action

`quarantine-synthetic-ingress-edge` (`edge_restriction`, `remove_edge`)
is the one playbook in the catalogue that is both `automatic_candidate`
tier **and** performs a genuine connectivity change — removing one
evidenced, anomalous external-to-internal ingress relationship (the
specific route an attacker was observed entering through). It is
deliberately narrow:

- **Scope**: only ever targets a single relationship whose source is an
  `external_client` asset and whose edge is itself in this run's
  `anomalous_observed_edge_ids` (see the target-generation rule in
  `response_service.analyze()`) — never an interior lateral-movement
  edge, never a user/identity, never a database/object store.
- **Why it is containment, not observation**: it is a real `remove_edge`
  mutation, evaluated by the same what-if engine as every other
  edge-restriction playbook. For the reference staged-compromise
  incident it shows `attack_paths: 1 -> 0`,
  `critical_targets_reachable: 1 -> 0`, `security_gain: 34.5` — a real,
  measured reduction in reachable attack paths, not merely improved
  telemetry.
- **Why it is safe to automate**: `default_operational_impact = "low"`,
  `default_blast_radius = "single_relationship"`, `reversibility =
  "reversible"` — all three catalogue-declared properties a human
  reviewer set, matching exactly the bound POL-003/004/005 enforce.
  Cutting off a source the system has already flagged anomalous carries
  low genuine operational cost (no legitimate traffic is known to depend
  on it), and the action is fully reversible via the existing rollback
  path.
- **Policy still gates it, unconditionally**: POL-006 still blocks
  automatic execution if this playbook were ever pointed at a critical
  database/object store target (it structurally never is, since its only
  `supported_target_types` is `relationship`, but the policy check runs
  regardless — see `tests/test_policy_engine.py::
  test_the_containment_playbook_cannot_target_a_critical_datastore_automatically`).
  Autonomy mode can never bypass this.

The one demonstrable end-to-end autonomous self-healing loop
(`tests/test_workflow_coordinator.py::
test_autonomous_self_healing_performs_real_containment_end_to_end`)
drives this entirely through `WorkflowCoordinator.run()` - no manual
recommendation selection - and shows: candidate ranking (this playbook
wins on Response Utility Score for a real evidenced ingress edge) →
automatic policy approval → automatic routing → synthetic execution →
independent post-execution verification → `verified`, with zero human
approval records created. `increase-synthetic-monitoring` remains
policy-eligible for automation too, but it is never described as
"self-healing" anywhere in this codebase - it has no containment effect.

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
