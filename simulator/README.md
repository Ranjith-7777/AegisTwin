# AegisTwin Simulator

Phase 4A builds isolated in-memory normal training and validation datasets from the deterministic generator without mutating persisted operational runs. Held-out normal and credential-compromise runs are used only for synthetic evaluation, with scenario identity applied after scoring. Detection remains inside backend services and makes no network or operating-system calls. This directory remains reserved for future standalone fixtures or replay tooling; anything added here must stay synthetic, deterministic, and free of scanning or response behavior.

Phase 4A.1 adds a separate evaluation-only step manifest so routine events inside an exercise scenario are not automatically benchmark positives. The manifest never enters telemetry persistence, feature extraction, model fitting, or calibration. V2 contextual features consume only the current and preceding events within each synthetic run.

Phase 4B keeps scoring offline and persists every synthetic assessment before playback. The run-scoped WebSocket only synchronises stored event/assessment pairs; it does not contain a detector. Anomaly is deviation from the synthetic baseline, never proof of an attack.

