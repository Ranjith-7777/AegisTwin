# AegisTwin Simulator

Phase 3B replays persisted deterministic events through a backend WebSocket controller; it does not regenerate or mutate them. The engine and playback service remain inside the backend so persistence and typed protocol boundaries stay together. This directory remains reserved for future standalone fixtures or replay tooling. Anything added here must remain synthetic, deterministic, and free of operating-system execution, network access, scanning, or real response behavior.

