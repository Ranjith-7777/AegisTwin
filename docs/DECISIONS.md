# AegisTwin Initial Architectural Decisions

Statuses use **Accepted**, **Proposed**, **Superseded**, or **Rejected**. These initial records may be split into numbered ADR files when implementation begins.

## React + TypeScript + Vite

- **Decision:** Build the dashboard with React, TypeScript, and Vite.
- **Reason:** React supports component-driven dashboards; TypeScript makes API and graph view models explicit; Vite gives fast local iteration and a simple production build suitable for a hackathon.
- **Alternatives considered:** Next.js, Vue, Svelte, and server-rendered templates.
- **Consequences:** The team must maintain frontend contracts and choose state/test tooling. Server-side rendering and framework-provided backend features are intentionally unnecessary for the local operations dashboard.
- **Status:** Accepted.

## shadcn/ui as the dashboard foundation

- **Decision:** Use shadcn/ui components and Tailwind design tokens as the dashboard foundation.
- **Reason:** It provides accessible, composable source-level primitives that can produce a restrained professional UI without inventing every interaction.
- **Alternatives considered:** Material UI, Ant Design, Chakra UI, and fully custom components.
- **Consequences:** Components live in the repository and must be maintained; accessibility still requires verification; visual consistency depends on disciplined tokens and reuse. Applicable upstream licence notices must be preserved.
- **Status:** Accepted.

## React Flow for topology visualisation

- **Decision:** Use React Flow to render and interact with the cyber digital twin.
- **Reason:** It directly supports custom typed nodes, directed edges, selection, zooming, overlays, and controlled graph state in React.
- **Alternatives considered:** Cytoscape.js, Sigma.js, D3, and a static Mermaid/SVG view.
- **Consequences:** A view-model adapter and layout strategy are required; large graphs need filtering; React Flow remains presentation-only while NetworkX owns graph calculations.
- **Status:** Accepted.

## FastAPI backend

- **Decision:** Implement the API as a Python 3.11+ FastAPI modular monolith.
- **Reason:** FastAPI aligns with scikit-learn/NetworkX, supplies Pydantic validation and OpenAPI, supports WebSockets, and enables rapid typed development.
- **Alternatives considered:** Django/DRF, Flask, Node.js/NestJS, and multiple microservices.
- **Consequences:** Async and blocking analytical/database work must be separated carefully; architectural module boundaries require discipline because they are not process boundaries; deployment needs an ASGI server.
- **Status:** Accepted.

## SQLite during prototype development

- **Decision:** Use SQLite for local development and the single-instance prototype demo.
- **Reason:** It has no external service dependency, is easy to reset/seed, and is adequate for the bounded data volume and write rate.
- **Alternatives considered:** PostgreSQL, an in-memory store, and document databases.
- **Consequences:** Concurrent writes and production scaling are limited; transactions must be short and WAL mode should be evaluated; schema and repository design must avoid SQLite-specific assumptions so PostgreSQL remains a migration path.
- **Status:** Accepted for prototype only.

## SQLAlchemy ORM

- **Decision:** Use SQLAlchemy 2 for persistence behind repository interfaces.
- **Reason:** It provides explicit models, mature transaction control, SQLite/PostgreSQL portability, and a strong Python ecosystem.
- **Alternatives considered:** SQLModel, Django ORM, raw SQL, and an event-only document store.
- **Consequences:** Domain, ORM, and API models must be kept distinct; migrations require an additional tool (proposed: Alembic); repository tests are necessary to prevent abstraction leakage.
- **Status:** Accepted.

## Isolation Forest as the baseline anomaly detector

- **Decision:** Use a seeded scikit-learn Isolation Forest as the first anomaly-scoring baseline, supplemented by explicit correlation rules.
- **Reason:** It can rank unusual multidimensional behaviour without labelled attack data, is quick to train on synthetic benign fixtures, and is suitable for an honest prototype baseline.
- **Alternatives considered:** Z-score/threshold rules, One-Class SVM, Local Outlier Factor, autoencoders, supervised classifiers, and LLM-only detection.
- **Consequences:** Scores are not probabilities; contamination, features, thresholds, and random seed must be versioned; explanations require derived feature deviations; synthetic performance cannot establish production effectiveness; the model cannot directly trigger actions.
- **Status:** Accepted as baseline, not final production model.

## Safe simulated response actions

- **Decision:** Implement response actions only as allow-listed, idempotent state transitions in a simulated digital twin, with human approval for credential revocation and endpoint isolation.
- **Reason:** The project must demonstrate response reasoning without creating risk to real identities, endpoints, networks, or data.
- **Alternatives considered:** Recommendations only with no execution, live IAM/EDR integrations, arbitrary playbooks, and fully autonomous response.
- **Consequences:** The prototype cannot claim operational containment; persistent simulation labels, boundary checks, approval records, reversibility, and audit tests are mandatory; no external action adapter or arbitrary command interface will be included.
- **Status:** Accepted and non-negotiable for the MVP.

## One primary attack scenario before more scenarios

- **Decision:** Complete and polish the compromised-employee-account scenario before considering any additional scenario.
- **Reason:** One coherent path exercises the full product thesis and is more credible and testable within hackathon constraints than several incomplete demonstrations.
- **Alternatives considered:** Multiple shallow scenarios, a configurable free-form simulator, and a generic alert dashboard without a scripted story.
- **Consequences:** Initial ATT&CK coverage and evaluation are deliberately narrow; scenario contracts must still permit future additions; new scenarios are excluded until all finished-prototype acceptance criteria pass for the primary path.
- **Status:** Accepted.
