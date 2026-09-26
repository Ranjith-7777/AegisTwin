# AegisTwin Simulator

Phase 8A freezes the submission demonstration at `staged-compromise-demo`, seed 84, accelerated playback speed 50, model random state 17, and top-three predictions. These are regression inputs, not production performance claims.

Phase 6A derives observed topology layers only from persisted synthetic telemetry prefixes; it does not inspect host or real network topology.

Prediction consumes persisted synthetic event prefixes only; scenario metadata and future steps remain excluded from predictive features.

Phase 4A builds isolated in-memory normal training and validation datasets from the deterministic generator without mutating persisted operational runs. Held-out normal and credential-compromise runs are used only for synthetic evaluation, with scenario identity applied after scoring. Detection remains inside backend services and makes no network or operating-system calls. This directory remains reserved for future standalone fixtures or replay tooling; anything added here must stay synthetic, deterministic, and free of scanning or response behavior.

Phase 4A.1 adds a separate evaluation-only step manifest so routine events inside an exercise scenario are not automatically benchmark positives. The manifest never enters telemetry persistence, feature extraction, model fitting, or calibration. V2 contextual features consume only the current and preceding events within each synthetic run.

Phase 4B keeps scoring offline and persists every synthetic assessment before playback. The run-scoped WebSocket only synchronises stored event/assessment pairs; it does not contain a detector. Anomaly is deviation from the synthetic baseline, never proof of an attack.

Phase 5A adds the independent deterministic `staged-compromise-demo` scenario. It does not alter the frozen normal-operations or credential-compromise benchmarks. Explicit synthetic protocol/channel metadata supports conservative local MITRE mapping without any external lookup.

Phase 6B consumes those already-persisted staged events in sequence to animate the curated topology. It adds no generator look-ahead, scanner, host integration, command execution, or response capability; reconnect recovery is constrained to the requested persisted prefix.

Phase 7A reads persisted prefixes but does not change the deterministic generator. Defensive options mutate only cloned in-memory topology collections and persist bounded impact summaries; no playbook is approved or executed.

