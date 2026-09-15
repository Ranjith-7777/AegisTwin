# ADR-014: Azure Container Apps Over AKS/VMs for Hosting

## Status
Accepted.

## Context

Phase 6 needs to host AegisArena's single backend process and frontend
static bundle on Azure. The application is, by design (see ADR-013's
discussion of Phase 4 machinery and `docs/DEPLOYMENT_REQUIREMENTS.md`), a
single-process, in-process-stateful service: one uvicorn worker owns the
event bus and digital twin simulation state, and horizontal scaling beyond
one replica is out of scope for this phase. The hosting platform choice
needs to fit that shape cheaply, for a student project with no dedicated
platform-operations effort, rather than provision for scale this
application cannot use.

Azure offers several container-hosting options for this workload: Azure
Kubernetes Service (AKS), plain Azure VMs running Docker, and Azure
Container Apps (a managed, serverless-billed container platform built on
Kubernetes/KEDA underneath, without exposing cluster management to the
operator).

## Decision

Host the application on **Azure Container Apps**, Consumption plan, as a
single Container App running the frontend and backend as two containers in
one revision (see `docs/deployment/AZURE_ARCHITECTURE.md`), with
`minReplicas=0`/`maxReplicas=1`.

## Alternatives considered

1. **AKS.** Rejected: AKS bills for its control plane and worker node VMs
   continuously regardless of application load, and requires ongoing
   cluster operations (node pool sizing, upgrades, networking/ingress
   configuration) that have no payoff here — this application cannot use
   Kubernetes' horizontal scaling or multi-node scheduling anyway, since it
   is capped at one replica by its own state model. The operational
   overhead is unjustified for a project with no dedicated platform team.
2. **Plain Azure VMs running Docker/docker-compose directly.** Rejected:
   this would require manually managing OS patching, container restart
   policies, TLS termination, and scale-to-zero would not exist at all (a
   VM either runs, and bills, continuously, or is stopped/started manually)
   — losing the cost benefit that matters most for an intermittently-used
   student project.
3. **Azure Container Apps (chosen).** Provides HTTPS ingress, managed
   TLS, revision-based deployments, and — critically — scale-to-zero
   (`minReplicas=0`) with no persistent compute cost between uses, while
   still allowing the `maxReplicas=1` cap this application's architecture
   requires. No cluster to operate; the platform team surface area is
   effectively zero.

## Consequences

- Positive: near-zero idle cost (scale-to-zero) matching a student
  subscription's constraints; no Kubernetes cluster to patch or upgrade;
  deployment is "build an image, point Container Apps at it."
- Positive: the frontend+backend sidecar model maps directly onto Container
  Apps' multi-container-per-revision support, avoiding a second Container
  App / extra networking hop.
- Negative: Container Apps' Consumption plan has a cold start on
  scale-from-zero (container start + `alembic upgrade head` + uvicorn boot)
  — mitigated for demos via the manual scale-up procedure in
  `docs/deployment/COST_CONTROL.md`, and accounted for by retries in the
  deploy workflow's health gate.
- Negative: if this application's state model is ever redesigned to support
  true horizontal scaling, Container Apps' scaling rules (KEDA-based) would
  need to be reconfigured — not a blocker today, but a follow-up if that
  redesign happens.

## Future reconsideration trigger

Revisit if the application's in-process event bus/simulation state is ever
externalized (making `maxReplicas>1` safe) and sustained load makes
Consumption-plan cold starts or scaling limits a genuine problem — at which
point AKS or Container Apps' dedicated plan would become worth
re-evaluating against the operational cost they'd add.
