# Red Scenario → MITRE ATT&CK Mapping

`app/services/red_scenario_catalogue.py` computes, for every built-in
scenario, which local MITRE ATT&CK technique (if any) each step is
*expected* to map to — before any telemetry is generated. It does this
by mirroring `correlation_service.CorrelationService._map`'s exact
condition chain (first match wins) statically over `ScenarioStep`
fields, so the result can never disagree with what real correlation
computes at runtime; it is not a second, independently-authored mapping
engine. Every technique id it can ever return is a member of the local
7-technique catalogue (`mitre_catalogue_service.CATALOGUE`) — attempting
to derive an id outside that set raises `ValueError` at import/summarize
time rather than silently inventing one.

## The local catalogue

| Technique ID | Name | Tactic |
|---|---|---|
| T1021 | Remote Services | Lateral Movement |
| T1041 | Exfiltration Over C2 Channel | Exfiltration |
| T1078 | Valid Accounts | Defense Evasion |
| T1098 | Account Manipulation | Persistence |
| T1110 | Brute Force | Credential Access |
| T1110.001 | Password Guessing | Credential Access |
| T1567 | Exfiltration Over Web Service | Exfiltration |

## Per-scenario mapping

| Scenario | Red-agent scenario? | Techniques exercised |
|---|---|---|
| `normal-operations` | No | *(none — routine traffic has no declared attack indicators)* |
| `credential-compromise` | No | T1110.001, T1078 |
| `staged-compromise-demo` | No | T1021, T1078, T1098, T1110.001, T1567 |
| `leaked-api-credential` | Yes | T1021, T1078, T1098, T1110.001, T1567 |
| `suspicious-kubernetes-pod` | Yes | T1021, T1041, T1098, T1110.001 |
| `ddos-traffic-spike` | Yes | T1110.001 |

("Red-agent scenario" = `scenario_id in RED_AGENT_SCENARIO_IDS`, the
existing flag distinguishing autonomous-red-agent scenarios from
scripted narrative ones — unrelated to which techniques a scenario maps
to.)

## Mapping conditions (mirrors `correlation_service._map`, first match wins)

1. `failed_attempts >= 5` or `attempt_pattern == "repeated"` → **T1110.001**
   (Password Guessing), and the step's `user_id` is recorded as having a
   failed-attempt history for condition 2's benefit on later steps.
2. `outcome == "success"` and `user_id` appears in that failed-attempt
   history and `event_type == "authentication"` → **T1078** (Valid
   Accounts) — a successful login following that same user's earlier
   repeated failures.
3. `account_manipulation is True` → **T1098** (Account Manipulation).
4. `remote_service` is a declared string → **T1021** (Remote Services).
5. `channel_type == "synthetic_c2"` → **T1041** (Exfiltration Over C2
   Channel).
6. `channel_type == "synthetic_web_service"` and `web_service` is a
   declared string → **T1567** (Exfiltration Over Web Service).
7. Otherwise → no technique (the step has no declared indicator matching
   the local catalogue).

## A known, documented conservatism

`ScenarioStep` has no authored `failed_attempts` count (that is a
telemetry-*generation-time* field on `TelemetryEventRecord`, not an
authored scenario field). `iter_scenario_techniques` conservatively
derives the same "repeated attempts" signal from whether the step's own
`description` text contains the word "repeated", rather than guessing a
specific event-generation-time number. This is documented here rather
than silently assumed: the derived expected-technique set is a
best-effort *static* preview, and the authoritative technique
observations for a specific run remain whatever
`correlation_service.analyze` actually persists as
`TechniqueObservationRecord`s once real telemetry exists.

## Where this is used

- `GET /api/v1/purple-team/scenarios` exposes this summary directly, per
  scenario, as `RedScenarioSummary`.
- `purple_team_service` uses `iter_scenario_techniques` to populate each
  `PurpleTeamStepResult.expected_technique_id` /
  `expected_technique_name`, which `detection_step_coverage` is computed
  against — see `docs/architecture/PURPLE_TEAM.md`.
