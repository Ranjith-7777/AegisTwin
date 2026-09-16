# Research Contributions

AegisArena combines several established ideas from cloud security and
resilience engineering into one working, measurable system. The
contribution is the *integration and evaluation methodology*, not a claim
that any single technique here is individually novel research.

## 1. Digital-twin-driven cyber-resilience evaluation

Rather than reasoning about attack impact in the abstract, AegisArena
maintains a live digital twin (graph of synthetic assets and relationships)
that both the Red Agent and Blue agents actually act against. Impact,
blast radius, and response outcomes are read off the twin's real state
after each step, not asserted by a report generator.

## 2. Graph-based exposure / blast-radius reasoning

Attack paths, affected-asset sets, and blast radius are computed from the
topology graph itself (reachability and relationship traversal), not from a
static severity table. This lets the system answer "what does this
specific incident actually threaten" rather than a generic "this technique
is usually bad" rating.

## 3. Counterfactual defensive simulation ("what-if")

Before a response is executed, its effect is simulated against the digital
twin (Response Planner + Impact Simulation Agent) and shown as a
counterfactual overlay distinct from observed reality. A response is
evaluated on paper before it is ever applied.

## 4. Policy-constrained multi-agent response

The Blue side is not a single model making a single decision. It is six
deterministic agents in a fixed pipeline — plan, simulate impact, check
safety policy, route for approval or autonomous execution, execute
synthetically, verify — each producing an auditable, persisted
`AgentDecision`. The Safety Governor and policy layer can block or demote a
plan regardless of how good its raw score looks.

## 5. Independent post-action verification

Execution is not assumed to have worked. A separate Verification Agent
checks both the security effect and operational health afterward, and
triggers rollback automatically if verification fails. Success is measured,
not declared.

## 6. Reproducible multi-baseline resilience evaluation

The same scenario/seed is run under four isolated defence baselines —
NO_ACTIVE_DEFENCE, RULE_BASED, ML_ASSISTED, AGENTIC — so the value of the
full agentic pipeline is measured against real alternatives, not against a
strawman. Baseline isolation is deliberate: non-agentic baselines create
zero `AgentDecisionRecord`s by design, so a comparison can't be accidentally
contaminated by agentic reasoning leaking into a "simpler" baseline.

## 7. Quantified resilience: ARS and MCI

- **Aegis Resilience Score (ARS)** = `100 × (0.20·A + 0.35·W + 0.25·M +
  0.20·R)`, where A = Threat Awareness, W = Withstand/Containment, M =
  Mission Preservation, R = Verified Recovery. ARS is deterministic and
  strategy-neutral — it does not know or care which baseline produced the
  run it is scoring. It is **not** a probability.
- **Mission Continuity Index (MCI)** is the trapezoidal area under the
  criticality-weighted Mission Health curve over the experiment's duration
  (critical=4, high=3, medium=2, low=1), summarizing how much of the
  mission stayed available, not just whether it eventually recovered.

## What this project does not claim

This is not a claim of formal, peer-reviewed research novelty. It is a
working demonstration that these ideas can be implemented together,
measured consistently, and produce a resilience signal that changes
meaningfully across defence strategies — see
`docs/final/LIMITATIONS_AND_FUTURE_WORK.md` for what is explicitly *not*
proven yet (e.g. sensitivity to the canonical seeds, the single-chokepoint
topology characteristic).
