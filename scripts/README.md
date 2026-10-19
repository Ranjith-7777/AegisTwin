# Developer scripts

This directory is reserved for safe, documented development and demo helpers. It must not contain destructive operations, external targeting, scanning, exploitation, or real response commands.

- `bootstrap_demo.py` migrates an explicitly local database and prepares the deterministic synthetic model.
- `run_demo.ps1` is the Windows bootstrap entry point.
- `final_benchmark.py` writes synthetic JSON, CSV, and Markdown reports from an
  isolated persisted workflow, including versioned MCI/ARS and source-evidence IDs.
- `validate_release.ps1` runs the full backend, frontend, E2E, benchmark, migration, and repository checks.

