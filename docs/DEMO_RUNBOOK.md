# AegisTwin Demonstration Runbook

For the packaged Windows judge workflow, use the [Local Demo Guide](LOCAL_DEMO_GUIDE.md). It isolates runtime state under `.aegistwin-demo` and defaults to a production frontend build.

## Safety

AegisTwin accepts only synthetic scenarios, identities, assets, telemetry, and response state. No workflow affects a real system or establishes production security effectiveness.

## Prerequisites and installation

Install Python 3.11+, Node.js 24, backend dependencies from `backend/requirements-dev.txt`, and frontend dependencies with `npm ci`. Copy the relevant `.env.example` files; never place secrets in frontend variables.

## One-command preparation

Windows:

```powershell
.\scripts\run_demo.ps1
```

Platform-neutral:

```text
python scripts/bootstrap_demo.py
```

The bootstrap applies migrations, creates ignored local directories, and trains or reuses the deterministic model. It prints backend and frontend startup commands. It does not bypass model scoring, analysis, approval, policy, or audit gates.

## Exact demonstration sequence

1. Start backend and frontend using the printed commands.
2. Open Overview and confirm the simulation banner and backend connection.
3. In Demo Mode confirm `staged-compromise-demo`, seed 84, speed 50, detection, correlation, prediction, and top three.
4. Start playback and observe normal events before suspicious synthetic activity.
5. Inspect anomaly assessment, observed MITRE techniques, Incident Candidates, predicted hypotheses, and Digital Twin layers.
6. Complete playback and generate Response Centre recommendations through sequence 10.
7. Select a reversible analyst-tier recommendation and create an orchestration.
8. Approve as Demo SOC Analyst, choose **Execute in Synthetic Twin**, verify the simulated outcome, and roll back.
9. Open Audit Trail and verify the hash chain.

## Expected outcomes

Observed, correlated, and predicted states remain visually distinct. Approval tiers remain enforced. Execution records use `completed_simulated`; rollback restores the recorded synthetic state reference. The immutable topology remains unchanged.

## Recovery and cleanup

Use the visible retry controls for failed API loads. Playback reconnects from the latest rendered sequence. Stop both local servers normally. Demo databases and artifacts are ignored and may be removed only after verifying their exact paths under `backend/`.
