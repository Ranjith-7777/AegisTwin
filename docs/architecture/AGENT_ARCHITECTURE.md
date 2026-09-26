# Agent Architecture

AegisArena has exactly **7 functional agents** — 1 Red-side, 6 Blue-side.
This is the load-bearing fact of Phase 4 and it is enforced in code, not
just described here: `tests/test_agent_registry.py` asserts the registry
returns exactly 7 agents split 1 red / 6 blue, and that no analytical
subsystem id ever collides with an agent id.

An **agent**, for this codebase, is a component that makes an
independent decision that changes what happens next in the response
pipeline (select, permit/block, route, execute, verify). An
**analytical subsystem** only ever produces evidence that an agent
consumes — it never itself decides anything. This distinction is not
cosmetic: it is why Isolation Forest, incident correlation, MITRE
mapping, the Attack Graph and Blast Radius are never counted as agents
anywhere in this system, in code or in the UI.

## The 7 agents

| # | Agent | Side | Implementation | Version |
|---|---|---|---|---|
| 1 | Synthetic Red Agent / Scenario Engine | Red | Deterministic scenario/event generator (`app/services/event_generator.py`, `app/services/scenario_service.py`) | `aegisarena-scenario-engine-v1` |
| 2 | Response Planner Agent | Blue | Multi-candidate ranking (`app/services/orchestration_agents.py::ResponsePlannerAgent`, enriched by `app/services/blue_planning_service.py`) | `deterministic-resilience-agent-v2` |
| 3 | Impact Simulation Agent | Blue | Simulation-currency validation (`ImpactSimulationAgent`) | `deterministic-resilience-agent-v2` |
| 4 | Safety Governor Agent | Blue | Policy-as-code evaluation (`SafetyGovernorAgent` + `app/services/policy_service.py`) | `deterministic-resilience-agent-v2` |
| 5 | Approval Router Agent | Blue | Autonomy-aware routing (`ApprovalRouterAgent`) | `deterministic-resilience-agent-v2` |
| 6 | Synthetic Execution Agent | Blue | Synthetic-state mutation (`SyntheticExecutionAgent`) | `deterministic-resilience-agent-v2` |
| 7 | Verification Agent | Blue | Dual security/operational verification (`VerificationAgent`) | `deterministic-resilience-agent-v2` |

Agents 2-7 are implemented in `app/services/orchestration_agents.py` and
share one version string, `AGENT_VERSION` — see "Versioning" below. Agent
1 has its own version because it is a wholly separate implementation
(the Red scenario/event generator, not part of `orchestration_agents.py`).

The registry (`app/services/agent_registry_service.py::registry()`,
served at `GET /api/v1/agents`) returns every agent's id, display name,
side, role, description, implementation type, version, declared
input/decision/output types, and `next_agent` — the exact handoff order
below. This is a **static description of real code**, not a
configuration a user edits; it exists so the professor-facing UI (and
this document) can never drift from what `orchestration_agents.py`
actually does.

## Analytical subsystems (never agents)

| Subsystem | What it produces | Consumed by |
|---|---|---|
| Telemetry | Deterministic synthetic event stream | Response Planner |
| Detection (Isolation Forest) | An anomaly score/classification per event | Response Planner |
| Incident Correlation | Incident candidates grouped from anomalous evidence | Response Planner |
| MITRE ATT&CK Mapping | Local technique IDs for observed evidence | Response Planner |
| Attack Graph | Ranked, deterministic attack paths | Response Planner, Impact Simulation |
| Blast Radius | Deterministic reachability estimate | Response Planner, Impact Simulation |
| Prediction | Next-stage progression hypotheses | Response Planner |

None of these seven ever independently decides a response, an approval,
an execution, or a verification outcome. They are queried *by* an
agent (chiefly the Response Planner, via `blue_planning_service.py`,
and the Impact Simulation Agent, via the existing Phase 3
`response_service.py` simulation) as evidence inputs. The registry
endpoint returns them in a separate `analytical_subsystems` array from
`agents`, and the professor-facing Agent Workflow UI
(`frontend/src/pages/blueAgent/AgentWorkflowPage.tsx`) renders them in a
visually distinct, explicitly labeled "Analytical subsystems (not
agents)" section between the Red and Blue agent cards.

## The Workflow Coordinator is not an 8th agent

`app/services/workflow_coordinator_service.py::WorkflowCoordinator` exists
to sequence one call each into `blue_planning_service.compare()` →
`orchestration_service.create()` → (AUTONOMOUS mode, and only when the
Approval Router already routed the plan to automatic) `execute()` →
`verify()`. It makes **no independent security, policy, approval,
execution, or verification decision of its own** — every decision is
still made by the 6 Blue agents and the policy engine it calls, in
exactly the sequence a human operator driving the API step by step
would produce. It is documented, tested (`tests/test_workflow_coordinator.py`),
and displayed (where surfaced in the UI) as "Workflow Coordinator," never
as an agent, and the registry endpoint does not list it.

## Handoff order (the pipeline)

```
Response Planner Agent
    -> Impact Simulation Agent
        -> Safety Governor Agent
            -> Approval Router Agent
                -> Synthetic Execution Agent
                    -> Verification Agent
```

Each agent's `AgentResult.next_agent` names the next hop; a `None`
next_agent means the pipeline stopped there (e.g. the Impact Simulation
Agent found a stale simulation, or the Safety Governor blocked the
plan). `agent_registry_service.trace_for_orchestration()` reconstructs
this exact real sequence from persisted `AgentDecisionRecord` rows for
one orchestration — it never fabricates a trace, and honestly reports
`stopped_reason` when the real pipeline did not reach a terminal state
(see `GET /api/v1/agents/orchestrations/{id}/trace`).

**All 6 Blue agents persist a real `AgentDecisionRecord`, including
Verification.** An earlier draft of `orchestration_service.verify()`
persisted a `ResponseVerificationRecord` and an audit event but never
called `_decision()` for the Verification Agent — the same mechanism
Response Planner, Impact Simulation, Safety Governor, Approval Router
and Synthetic Execution already used. This meant a complete orchestration's
trace only ever showed 5 of the 6 Blue agents. Fixed: `verify()` now
calls `self._decision()` with the Verification Agent's real decision
(`decision_type="verification"`, `decision` is the verification status,
`next_agent=None`), so `tests/test_agent_registry.py::
test_complete_orchestration_trace_shows_the_exact_six_blue_agent_order`
asserts the exact 6-agent order by ID, not a weaker "first is planner /
last status is reached" proxy.

## Versioning

`AGENT_VERSION` moved from `deterministic-simulation-agent-v1` (Phase 3)
to `deterministic-resilience-agent-v2` (Phase 4). What actually changed
between v1 and v2:

- `SafetyGovernorAgent` now calls `policy_service.evaluate_response_policies()`
  (POL-001..POL-006) instead of re-implementing autonomous-eligibility
  checks inline, and reports which policy IDs blocked a plan.
- `SafetyGovernorAgent` and `ApprovalRouterAgent` are now autonomy-mode
  aware: RECOMMEND and APPROVAL_REQUIRED never auto-execute regardless of
  playbook tier; AUTONOMOUS auto-executes only when the tier is
  `automatic_candidate` **and** every applicable policy passed.
- `VerificationAgent` now checks security effect AND operational health
  independently (see `docs/architecture/VERIFICATION_AND_ROLLBACK.md`)
  instead of treating "a mutation occurred" as success.

The planner/impact-simulation/execution agent *contracts* (what they
take in, what they hand off) and the orchestration state machine are
unchanged from v1 — this is a behavioral upgrade to 3 of the 6 agents,
not a new architecture.

## Where this is enforced, not just documented

- `tests/test_agent_registry.py` — exact-7 proof, Red/Blue split proof,
  analytical-subsystem-exclusion proof, trace-ordering proof, a 404 (not
  a fabricated trace) for an unknown orchestration.
- `tests/test_workflow_coordinator.py` — the Coordinator never bypasses
  a real agent decision, for all 4 autonomy modes.
- `frontend/src/pages/blueAgent/AgentWorkflowPage.tsx` — the
  professor-facing view described above.
