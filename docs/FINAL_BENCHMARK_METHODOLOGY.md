# Final Benchmark Methodology

Run `python scripts/final_benchmark.py` from the repository root with backend dependencies available. The runner creates an isolated temporary database and artifact directory, uses staged-compromise seed 84 and model random state 17, and exports JSON, CSV, and Markdown under `reports/`.

The report consolidates detection, conservative MITRE mapping, correlation, prediction, response impact, orchestration, audit integrity, and synthetic demonstration workflow timings. It never tunes algorithms using the resulting values.

Detection evaluates frozen held-out seeds. Prediction uses the repository truth manifest and most-common-valid-transition baseline. Response aggregates sequence-10 cloned-topology simulations. Orchestration completes an analyst-approved reversible workflow, verification, rollback, and audit validation.

The benchmark is a deterministic regression aid. Its small synthetic sample and local timings cannot support production performance, MTTD, MTTR, containment, or security-effectiveness claims.
