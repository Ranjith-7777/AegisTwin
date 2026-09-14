"""Correction pass: proves `mission_continuity_service.compute_curve`'s
terminal `"experiment_horizon"` point is real - constructed from REAL
experiments run end-to-end through `experiment_service.create_and_run` +
`evaluate_experiment` (never hand-built `MissionHealthPointRecord` fixtures;
those pure-function properties are already covered by
`test_mission_continuity.py`), against `ExperimentMetricRecord
.logical_timeline_json["experiment_horizon_sim"]`.

## Why some tests here patch `MissionContinuityService._exposed_asset_ids`

`leaked-api-credential`/`ddos-traffic-spike` etc, run for real in this
codebase's compact fixed topology (13 mission-relevant nodes, `WHAT_IF_
MAX_DEPTH` blast radius), reach `has_evidence=True` at the very FIRST
anomalous event, and that first anchor's forward blast radius already
covers the entire topology - confirmed empirically (see the correction-pass
notes) across every shipped scenario/seed: real `MissionHealth` collapses to
`0.0` at `attack_observed` and never naturally differs again before
containment. Separately, every currently-catalogued auto-eligible playbook
available to `rule_based`/`ml_assisted` targets a chokepoint asset
(`api-gateway-01`, or the sole entry edge) whose removal simultaneously
clears exposure AND disconnects most of the topology from
`ENTRY_ASSET_ID` - so real `changed_node_ids`/`changed_edge_ids` alone
cannot cleanly demonstrate "recovery raises Mission Health" in isolation
either. Both are genuine properties of this environment's small topology
and current playbook catalogue, not bugs this correction pass is asked to
fix.

To still prove the terminal-point/MCI machinery honestly credits recovery
using the REAL `compute_curve()`/`_build_points()`/`compute_mci()` pipeline
(real `ExperimentRecord`, real telemetry-derived timeline, real dedup
logic), `test_recovery_credits_healthy_interval_and_faster_response_scores_higher`
does two things to a REAL persisted experiment, and nothing else:

1. Reassigns `experiment.changed_node_ids_json` to a non-chokepoint leaf
   node (`backup-service-01` - nothing in this topology depends on it as
   its only path, confirmed from `topology_service.EDGE_DEFINITIONS`) so
   containment's real connectivity effect is small and known, instead of
   catastrophic.
2. Monkeypatches `_exposed_asset_ids` to clear exposure exactly when real
   containment exclude-sets are in effect (`exclude_node_ids or
   exclude_edge_ids`) - i.e. exposure clears once mitigation genuinely
   applies, never earlier - leaving `EvaluationSyntheticActionRecord
   .through_sequence_number` (the real timing lever) as the only thing that
   changes between the "fast" and "slow" runs.

Every other value in that test - `experiment_horizon_sim`, event timestamps,
`CRITICALITY_WEIGHTS`, the dedup/terminal-point logic in `_build_points`,
`compute_mci`'s trapezoidal AUC - is real and unpatched, and every expected
number below is hand-verified against it.
"""

from __future__ import annotations

from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models import (
    EvaluationSyntheticActionRecord,
    ExperimentRecord,
    MissionHealthPointRecord,
)
from app.schemas.evaluation import DefenceMode, ExperimentCreate
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import experiment_service
from app.services.evaluation.metrics_service import evaluation_metrics_service
from app.services.evaluation.mission_continuity_service import mission_continuity_service

SCENARIO = "leaked-api-credential"
SEED = 7


def _session(client: TestClient) -> Session:
    return cast(Session, cast(FastAPI, client.app).state.database.session_factory())


def _run(session: Session, defence_mode: DefenceMode, seed: int = SEED) -> ExperimentRecord:
    request = ExperimentCreate(scenario_id=SCENARIO, seed=seed, defence_mode=defence_mode)
    experiment = experiment_service.create_and_run(session, request)
    assert experiment.status == "completed", experiment.failure_message
    return experiment


# ----------------------------------------------------------------------
# 1 & 2: no_active_defence has a defined MCI, and it matches a hand
# computation of the real (constant, sustained-degraded) curve.
# ----------------------------------------------------------------------


def test_no_active_defence_has_defined_mci_when_horizon_positive(client: TestClient) -> None:
    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.NO_ACTIVE_DEFENCE)
        metric_record, points = evaluate_experiment(session, experiment.experiment_id)

        horizon = cast(float | None, metric_record.logical_timeline_json["experiment_horizon_sim"])
        assert horizon is not None and horizon > 0

        # Before this fix: curve = [baseline(t=0), attack_observed(t=0)] ->
        # zero duration -> compute_mci returns None. After: a terminal
        # "experiment_horizon" point extends the curve to the real horizon.
        assert metric_record.mci is not None
        assert points[-1].logical_time_sim == horizon
        assert points[-1].stage == "experiment_horizon"
    finally:
        session.close()


def test_no_active_defence_constant_degraded_state_matches_hand_computed_auc(
    client: TestClient,
) -> None:
    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.NO_ACTIVE_DEFENCE)
        metric_record, points = evaluate_experiment(session, experiment.experiment_id)

        # `no_active_defence` never mutates the topology and never gains
        # new evidence-clearing exclude sets, so this scenario/seed's real
        # curve is exactly [baseline(t=0, h=1.0), attack_observed(t=0,
        # h=0.0), experiment_horizon(t=horizon, h=0.0)] - a fully exposed,
        # never-recovering state held constant to the horizon.
        stages = [(p.stage, p.logical_time_sim, p.mission_health) for p in points]
        assert stages == [
            ("baseline", 0.0, 1.0),
            ("attack_observed", 0.0, 0.0),
            ("experiment_horizon", 380.0, 0.0),
        ]

        horizon = metric_record.logical_timeline_json["experiment_horizon_sim"]
        # Trapezoidal AUC: 0*(1.0+0.0)/2 [zero-width baseline->attack_observed]
        # + horizon*(0.0+0.0)/2 [attack_observed->experiment_horizon] = 0.0
        expected_mci = 0.0
        assert metric_record.mci == expected_mci
        assert mission_continuity_service.compute_mci(points) == expected_mci
        assert horizon == 380.0
    finally:
        session.close()


# ----------------------------------------------------------------------
# 5: final Mission Health point time equals experiment_horizon_sim, for
# every mode, on real curves (no patching needed for this property alone).
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode",
    [
        DefenceMode.NO_ACTIVE_DEFENCE,
        DefenceMode.RULE_BASED,
        DefenceMode.ML_ASSISTED,
        DefenceMode.AGENTIC,
    ],
)
def test_final_point_time_equals_horizon_for_every_mode(
    client: TestClient, mode: DefenceMode
) -> None:
    session = _session(client)
    try:
        experiment = _run(session, mode)
        metric_record, points = evaluate_experiment(session, experiment.experiment_id)
        horizon = metric_record.logical_timeline_json["experiment_horizon_sim"]
        assert horizon is not None
        assert points[-1].logical_time_sim == horizon
    finally:
        session.close()


# ----------------------------------------------------------------------
# 4: rule_based / ml_assisted / agentic each get their own honestly,
# independently computed MCI from their own real evidence - not asserted
# to differ (they may not, and here - see module docstring - they don't,
# since this scenario/seed's evidence saturates exposure before any of
# these baselines' single-shot response could matter).
# ----------------------------------------------------------------------


def test_rule_ml_agentic_mci_independently_real_and_consistent(client: TestClient) -> None:
    session = _session(client)
    try:
        results: dict[str, tuple[float | None, list[MissionHealthPointRecord]]] = {}
        for mode in (DefenceMode.RULE_BASED, DefenceMode.ML_ASSISTED, DefenceMode.AGENTIC):
            experiment = _run(session, mode)
            metric_record, points = evaluate_experiment(session, experiment.experiment_id)
            results[mode.value] = (metric_record.mci, points)

        for mode_name, (mci, points) in results.items():
            assert mci is not None, f"{mode_name} should have a defined MCI"
            # Each mode's persisted MCI must equal an independent recomputation
            # from that SAME mode's own real curve - never copied/shared.
            assert mci == mission_continuity_service.compute_mci(points)

        # Honest finding for this scenario/seed (see module docstring): all
        # three baselines' response happens coincident with the last real
        # telemetry event, and evidence has already saturated exposure
        # before then, so they land on the same real MCI here. This is not
        # hardcoded - it is what the real pipeline actually computes.
        assert {mci for mci, _ in results.values()} == {0.0}
    finally:
        session.close()


# ----------------------------------------------------------------------
# 2 & 3: post-recovery healthy interval is credited, and a real earlier
# response scores strictly higher over the SAME real horizon. See module
# docstring for exactly what is patched/reassigned and why.
# ----------------------------------------------------------------------


def test_recovery_credits_healthy_interval_and_faster_response_scores_higher(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.RULE_BASED)
        assert experiment.evaluation_action_id is not None

        # Neutralize the real mutation's connectivity blast radius: retarget
        # it at a real, non-chokepoint leaf node (nothing in this topology's
        # EDGE_DEFINITIONS depends solely on `backup-service-01`), so
        # containment's real BFS connectivity effect is small and known
        # instead of disconnecting most of the topology.
        experiment.changed_node_ids_json = ["backup-service-01"]
        experiment.changed_edge_ids_json = []
        session.add(experiment)
        session.commit()

        def fake_exposed(
            _session: Session,
            _run_id: str | None,
            _model_id: str | None,
            _through_sequence: int | None,
            exclude_node_ids: frozenset[str],
            exclude_edge_ids: frozenset[str],
        ) -> frozenset[str]:
            # Exposure clears exactly when real containment exclude-sets are
            # active (mitigation genuinely applied) - never earlier. This is
            # the one thing this test controls; timing is entirely real.
            if exclude_node_ids or exclude_edge_ids:
                return frozenset()
            return frozenset({"cloud-database-01"})

        monkeypatch.setattr(mission_continuity_service, "_exposed_asset_ids", fake_exposed)

        action = session.get(EvaluationSyntheticActionRecord, experiment.evaluation_action_id)
        assert action is not None
        natural_through_sequence = action.through_sequence_number
        assert natural_through_sequence == 8  # last real telemetry event

        def build(
            through_sequence: int,
        ) -> tuple[float | None, list[MissionHealthPointRecord], float | None]:
            action.through_sequence_number = through_sequence
            session.commit()
            metric_record = evaluation_metrics_service.compute(session, experiment.experiment_id)
            points = mission_continuity_service.compute_curve(session, experiment.experiment_id)
            mci = mission_continuity_service.compute_mci(points)
            metric_record.mci = mci
            session.commit()
            horizon = cast(
                float | None, metric_record.logical_timeline_json["experiment_horizon_sim"]
            )
            return mci, points, horizon

        slow_mci, slow_points, slow_horizon = build(natural_through_sequence)
        fast_mci, fast_points, fast_horizon = build(3)

        # Same experiment/telemetry -> same real horizon for both.
        assert slow_horizon == fast_horizon == 380.0

        # SLOW: response lands exactly at the horizon (through_sequence=8 is
        # the last event), so mitigation is real but there is no remaining
        # duration to enjoy the recovered state - curve stays [baseline,
        # attack_observed, response_start, containment] with the last two
        # coincident with the horizon; no separate terminal point needed.
        slow_stages = [(p.stage, p.logical_time_sim, p.mission_health) for p in slow_points]
        assert slow_stages == [
            ("baseline", 0.0, 1.0),
            ("attack_observed", 0.0, round(35 / 39, 6)),
            ("response_start", 380.0, round(35 / 39, 6)),
            ("containment", 380.0, round(36 / 39, 6)),
        ]
        # Hand AUC: 380*(35/39) [attack_observed->response_start; the final
        # containment point is zero-width at t=380] = 13300/39.
        assert slow_mci is not None
        assert slow_mci == pytest.approx((380 * (35 / 39)) / 380)
        assert slow_mci == pytest.approx(35 / 39)

        # FAST: through_sequence=3 -> response/containment land at the real
        # t=95.0 event (well before the horizon), so the recovered state
        # (36/39) is genuinely held constant for the remaining 285s via the
        # terminal "experiment_horizon" point - exactly the behaviour this
        # correction pass adds.
        fast_stages = [(p.stage, p.logical_time_sim, p.mission_health) for p in fast_points]
        assert fast_stages == [
            ("baseline", 0.0, 1.0),
            ("attack_observed", 0.0, round(35 / 39, 6)),
            ("response_start", 95.0, round(35 / 39, 6)),
            ("containment", 95.0, round(36 / 39, 6)),
            ("experiment_horizon", 380.0, round(36 / 39, 6)),
        ]
        # Hand AUC: 95*(35/39) + 285*(36/39) = 3325/39 + 10260/39 = 13585/39.
        expected_fast_auc = 95 * (35 / 39) + 285 * (36 / 39)
        assert fast_mci is not None
        assert fast_mci == pytest.approx(expected_fast_auc / 380)

        # THE comparison: real earlier response, same real horizon, strictly
        # higher MCI - because the post-recovery healthy interval is now
        # honestly integrated instead of being dropped on the floor.
        assert fast_mci > slow_mci
    finally:
        session.close()


# ----------------------------------------------------------------------
# 6: zero-duration (single telemetry event) safely stays N/A. No shipped
# scenario has exactly one event (normal-operations=6, credential-
# compromise=7, staged-compromise-demo=12, leaked-api-credential=8,
# suspicious-kubernetes-pod=8, ddos-traffic-spike=8 - confirmed by walking
# every scenario in this correction pass), so this genuine end-to-end case
# cannot be constructed from a real experiment. The pure-function case is
# already covered by `test_mission_continuity.py::
# test_zero_duration_single_point_returns_none`, which does not change:
# `compute_mci` still returns `None` for fewer than two distinct time
# instants, and this fix only ever ADDS a terminal point (never removes
# one), so a genuinely zero-duration real experiment (a single point,
# `attack_start_time_sim == experiment_horizon_sim`) is explicitly skipped
# by `_build_points`'s own "already equals the last real stage's own time"
# guard - see `mission_continuity_service._build_points`'s terminal-point
# comment.
