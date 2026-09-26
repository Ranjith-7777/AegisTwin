# Rollback Procedure

Azure Container Apps keeps prior deployments as **revisions**. Rolling back
means shifting ingress traffic back to a previous, known-good revision
rather than rebuilding or redeploying anything — this is the fastest
recovery path and the one this document describes.

Nothing below has been exercised against a live deployment yet; it
documents the intended procedure for when a deployment is live.

## 1. List revisions

```bash
az containerapp revision list \
  --name ca-aegisarena-dev \
  --resource-group rg-aegisarena-dev \
  --output table
```

This lists each revision's name, creation time, active/traffic-weight
status, and health state. Identify the last revision that was known-good
(e.g. the one active before the most recent `deploy-azure.yml` run) by its
creation timestamp or by cross-referencing the image tag (git SHA) it was
created from.

## 2. Understand traffic weighting

Container Apps supports splitting ingress traffic across multiple active
revisions by percentage weight (useful for canarying, though this project's
`maxReplicas=1` posture means we generally run single-revision mode with
100% weight on the current revision). Rollback is simply re-pointing 100%
of traffic at the previous revision:

```bash
az containerapp ingress traffic set \
  --name ca-aegisarena-dev \
  --resource-group rg-aegisarena-dev \
  --revision-weight <PREVIOUS_REVISION_NAME>=100
```

Traffic shifts immediately; no rebuild or image push is required, since the
previous revision's container image is already provisioned.

## 3. Deactivate the bad revision

Once traffic is confirmed healthy on the previous revision, deactivate the
bad one so it stops consuming resources and cannot accidentally receive
traffic again:

```bash
az containerapp revision deactivate \
  --name ca-aegisarena-dev \
  --resource-group rg-aegisarena-dev \
  --revision <BAD_REVISION_NAME>
```

## 4. Verify

Re-run the same health checks the deploy workflow uses, against the
Container App's public FQDN:

```bash
curl -f https://<containerAppFqdn>/api/health/live
curl -f https://<containerAppFqdn>/api/health/ready
```

## Notes

- Rolling back the *application* this way does not roll back any database
  schema migration that a bad deploy may have already applied (via
  `alembic upgrade head` in `backend/Dockerfile`'s entrypoint). If the bad
  revision ran a destructive migration, database-level recovery is a
  separate, manual concern outside the scope of this document.
- A revision-based rollback is not a substitute for fixing and redeploying
  the underlying issue — it buys time to do that safely.
