# Agent guidance — oratlas-verify

## Purpose and boundary
This repository is the request-scoped, independent scientific-verification **executor** for ORAtlas, not a certification or peer-review authority. ORAtlas owns publication identifiers, verification request lifecycle, persistence, assessment records and certification policy. This worker executes supported, explicitly versioned procedures against immutable, validated inputs and returns structured findings/evidence. It must not import ORAtlas database/Prisma models.

## Scientific and security rules
- Never infer unreported statistical parameters or invent missing inputs. Treat uncertainty or unsupported assertions as explicit failures.
- Preserve exact input and artifact hashes, protocol names/versions, tolerances, replay/idempotency identifiers and source references. Do not silently redefine a protocol's semantics within a version.
- External JSON is untrusted. No arbitrary execution, untrusted URLs, pickle/joblib deserialization, shell from metadata or publication-supplied code. The synthetic backend is test-only.
- Verification evidence is **not** certification. Agent-extracted assertions (if introduced later) remain proposals pending deterministic checks.

## Contracts
The authoritative integration is described in `docs/oratlas-integration.md` and `README.md`. Compare against an explicit ORAtlas API/protocol version; do not assume the live ORAtlas main branch is compatible. Any contract change needs schema/schema-version review, success and rejection fixtures, idempotent replay checks and an ORAtlas-side consumer test.

## Validation
```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run mypy
```
For cross-repo changes, use an immutable ORAtlas fixture and report which commit/version it represents, plus precisely which checks were executed. Do not contact a live deployment unless explicitly authorized.
