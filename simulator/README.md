# AegisTwin Simulator

Phase 4A builds isolated in-memory normal training and validation datasets from the deterministic generator without mutating persisted operational runs. Held-out normal and credential-compromise runs are used only for synthetic evaluation, with scenario identity applied after scoring. Detection remains inside backend services and makes no network or operating-system calls. This directory remains reserved for future standalone fixtures or replay tooling; anything added here must stay synthetic, deterministic, and free of scanning or response behavior.

