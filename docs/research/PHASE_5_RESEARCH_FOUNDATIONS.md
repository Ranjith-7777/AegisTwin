# Phase 5 Research Foundations

Conceptual grounding for Phase 5's evaluation methodology (PM spec
Section 99). For each system/framework below: what conceptual idea
AegisArena borrows, and where AegisArena's actual implementation differs.
None of the formulas described elsewhere in `docs/evaluation/` are claimed
to originate from, or be used by, any of the systems named here.

## NIST SP 800-160 Volume 2 — cyber resiliency

**Borrowed idea:** the anticipate/withstand/recover/adapt framing of
resilience as a lifecycle, not a single point-in-time security posture.
AegisArena's Mission Continuity Index is explicitly a time-integral — it
scores the whole recovery trajectory, not just the end state — which is a
direct methodological echo of "withstand" (does health stay high during
the incident) and "recover" (does health return to baseline, and how fast)
as separate concerns.

**Where AegisArena differs:** NIST SP 800-160 Volume 2 is a general
engineering framework for real systems and does not define AegisArena's
specific scoring formulas. The Aegis Resilience Score's four pillars
(Threat Awareness, Withstand/Containment, Mission Preservation, Verified
Recovery), their weights, and the trapezoidal-AUC MCI calculation are
AegisArena's own design (`resilience_score_service.py`,
`mission_continuity_service.py`), built for this synthetic cyber-range's
own available evidence (Attack Graph/Blast Radius what-if recomputation,
mission-relevant resource health), not derived from or reproducing any
formula in the NIST document.

## NIST measurement-guidance principles

**Borrowed idea:** meaningful measures (metrics tied to an actual decision
or outcome, not vanity counters), repeatability (the same input produces
the same output), honest treatment of uncertainty (N/A is a real answer,
not a forced default), and comparison only between genuinely comparable
things. Phase 5 operationalizes each of these directly:
`metrics_service.py`'s `Metric` wrapper makes applicability explicit
everywhere; `experiment_service.py`'s canonical constants make every
experiment reproducible; `comparison_service.check_fairness` refuses to
present a comparison as "paired" when the underlying conditions differ;
`aggregation_service.py` deliberately omits any significance-testing code
given its small (5-seed) canonical sample size rather than manufacturing a
false sense of statistical confidence.

**Where AegisArena differs:** these are general good-measurement
principles, not a specific formula or scoring system — AegisArena applies
the principles, not a borrowed calculation.

## Autonomous cyber-defence evaluation literature (general trend, not a specific citation)

**Borrowed idea:** a broad and growing trend in autonomous-defence research
toward separating Measures of Performance (did the mechanism execute
correctly) from Measures of Effectiveness (did the outcome actually matter)
rather than collapsing evaluation into a single scalar reward, and toward
avoiding evaluating an autonomous defender purely by whether a human judge
found the demo convincing. `METRICS_CATALOGUE.md`'s explicit MOP/MOE split
follows this general direction.

**Where AegisArena differs:** no specific paper, author, or year is cited
here because none is being verified as the source of AegisArena's own
metric definitions — this is described as a general research trend
AegisArena's structure is consistent with, not a reproduction of a named
study's methodology.

## Quantitative resilience / area-under-curve thinking

**Borrowed idea:** representing a system's health as a curve over time and
scoring the area under it is a well-established general technique for
capturing "how much and how long", not just "did it eventually recover".
AegisArena's MCI applies exactly this idea to a Mission Health curve.

**Where AegisArena differs:** the specific curve construction (event-driven
timepoints tied to real experiment stage transitions, rather than fixed-
interval sampling — see ADR-012) and the exact healthy/unhealthy
per-resource definition (simultaneously not-exposed AND still-connected,
criticality-weighted, no partial credit) are AegisArena's own design
choices for this codebase's specific evidence sources, not copied from any
external AUC-based resilience metric.

## CybORG / CAGE Challenge

**Borrowed idea:** a simulated network environment with a red/blue
adversarial loop, used as a controlled testbed for evaluating autonomous
defensive agents — conceptually the same shape as AegisArena's Digital
Twin + synthetic attack scenario + defence-strategy comparison.

**Where AegisArena differs:** CybORG/CAGE's own scoring (typically a single
cumulative reward signal tuned for reinforcement-learning competition) is
not used here. AegisArena's four-pillar ARS and separate MCI are a
different, deliberately decomposed scoring design intended for human-
readable evaluation reporting rather than RL training signal.

## CyberBattleSim

**Borrowed idea:** an abstracted, graph-based network representation for
reasoning about attacker lateral movement and reachability — conceptually
close to AegisArena's own Attack Graph/Blast Radius what-if evidence
(`what_if_evidence_service.py`).

**Where AegisArena differs:** AegisArena's Attack Graph/Blast Radius
implementation, and the way its before/after evidence feeds `attack_path_
reduction`/`blast_radius_reduction`/`critical_exposure_reduction`, is this
codebase's own service, not CyberBattleSim's engine or scoring.

## MITRE CALDERA

**Borrowed idea:** an operator framework for running structured adversary
emulation (technique-tagged attack steps) against a target environment,
which is the same general shape as AegisArena's scenario catalogue tagging
attack steps with severity and technique metadata for ground-truth
detection scoring.

**Where AegisArena differs:** CALDERA is a real-world adversary-emulation
tool operating against real or virtualized infrastructure; AegisArena's
scenarios are fully synthetic telemetry generation
(`event_generator.py`/`scenario_service.py`) with no live execution against
real systems, and detection/response scoring is computed against
AegisArena's own ground-truth step labels, not CALDERA's operation logs.

## Microsoft Defender for Cloud / Google Security Command Center / AWS Security Hub

**Borrowed idea:** these commercial Cloud Security Posture Management/
detection platforms establish the general vocabulary AegisArena's
synthetic telemetry and detection pipeline echo — anomaly scoring,
incident correlation, severity-tagged findings, and (for the more mature
platforms) automated remediation playbooks comparable in spirit to
AegisArena's response playbooks.

**Where AegisArena differs:** none of these platforms' actual detection
models, scoring algorithms, or proprietary risk-scoring formulas are used,
reproduced, or benchmarked against here — AegisArena is a fully synthetic
research/demo environment, and its detection/response pipeline is built
independently for this project.

## SOAR platforms (Security Orchestration, Automation and Response)

**Borrowed idea:** the general orchestration pattern of "detect → correlate
→ recommend/select a response playbook → execute → verify → roll back on
failure", which is precisely the Phase 4 Blue-agent loop Phase 5 evaluates.

**Where AegisArena differs:** AegisArena's playbooks, policy engine, and
verification/rollback logic are this project's own implementation
(`response_playbook_service.py`, `policy_service.py`,
`orchestration_service.py` — see `docs/architecture/POLICY_ENGINE.md` and
`VERIFICATION_AND_ROLLBACK.md`), not integrations with or reproductions of
any commercial SOAR product's engine.

## Statement

AegisArena's Aegis Resilience Score and Mission Continuity Index are
original formulas designed for this project, not reproductions of any
cited system's proprietary scoring.
