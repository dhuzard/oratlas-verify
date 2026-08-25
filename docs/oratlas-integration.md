# Authoritative ORAtlas integration

This integration is pinned to ORAtlas merge commit
`999580bad1fee5b22e8113c5e1c7c9b888eb1217` (PR #188). The authoritative documents are
`docs/openapi.yaml` and `docs/scientific-verification.md` at that commit. Scientific-verification API
schema `1.0.0`, PublicationVersion packet `1.3.0`, and
`verification-publication-input/1.0.0` are supported. CI checks the exact commit and frozen OpenAPI
normalized-LF SHA-256 `6e3a2cff2d266e67bbf999186520bb404aea7921a9362a44e1fd2c47f14b0a26`; it never tracks
ORAtlas `main` implicitly.

ORAtlas is the immutable evidence ledger and run coordinator. It creates requested runs and frozen
inputs. `oratlas-verify` is an external scientific executor. It has no ORAtlas database access and
does not import Prisma or ORAtlas application functions in production code.

## Authentication, claim, and state

Worker configuration is `ORATLAS_BASE_URL` and `ORATLAS_VERIFIER_TOKEN`. The bearer credential needs
only `verification:read` and `verification:submit`. Tokens and leases are excluded from DTO reprs,
errors, and structured logs.

`POST /api/verification-runs/{id}/claim` sends `{"leaseSeconds":300}`. The accepted range is
60–900 seconds. The one-time `leaseToken` remains only in the client process and is sent as
`X-ORAtlas-Verification-Lease` on input retrieval, source downloads, artifact operations, finding
submission, and worker transitions. A worker executes `requested → claimed → running → completed`.
A fatal verifier exception attempts a bounded-reason transition to `failed`; lease expiry is detected
locally and ORAtlas authorization remains authoritative. There is no invented renewal endpoint.
Verification must fit within one lease; longer work needs a separately designed worker/renewal model.

HTTP 401 and 403 are authentication/authorization failures. HTTP 409 on claim or transition is a
lease/state conflict. HTTP 409 for an artifact or finding stable key is an immutable idempotency
conflict and is never treated as success. Exact 200 replay responses are accepted after their DTO and
identity are validated. Only network failures and 5xx responses use bounded retries with the same
payload.

## Exact routes

The client implements:

- `GET /api/verifiers` and `GET /api/verifiers/{id}` in the pinned public contract;
- `GET /api/verification-protocols` and `GET /api/verification-protocols/{id}`;
- `GET /api/verification-runs/{id}`;
- `POST /api/verification-runs/{id}/claim`;
- `GET /api/verification-runs/{id}/input`;
- `GET /api/verification-runs/{id}/source-artifacts/{artifactId}`;
- `POST /api/verification-runs/{id}/artifacts/prepare`;
- `PUT /api/verification-artifacts/{artifactId}/content`;
- `GET /api/verification-artifacts/{artifactId}/content` in the pinned public contract;
- `POST /api/verification-runs/{id}/artifacts/complete`;
- `POST` and `GET /api/verification-runs/{id}/findings`;
- `POST /api/verification-runs/{id}/transition`;
- `GET /api/publication-versions/{id}/verifications`.

The external worker deliberately does not create a run. The production CLI claims only an existing
ORAtlas-created run. `inspect` reads the public run without claiming it.

## Frozen input and source integrity

Transport DTOs are strict and separate from local scientific contracts. The worker validates the run
id, profile/profile version, envelope schema, envelope SHA-256, payload schema, internal packet digest,
publication-version subject, content-document text digests, and exact protocol identity. Canonical JSON
is UTF-8, recursively key-sorted, compact, and finite. Unknown schema/profile or protocol versions fail
closed.

For `blinded-scientific`, ORAtlas's frozen derivative is consumed exactly as supplied. The worker
checks that contributor and production-actor presentation arrays are empty and never applies its local
standalone blinding transform a second time.

Source downloads require membership in `sourceArtifacts` and agreement among frozen expected
metadata, `X-ORAtlas-SHA256`, `Content-Length`, `Content-Type`, and actual received bytes. Downloaded
content is returned only as inert bytes. It is never executed or deserialized with pickle/joblib.

## Statistics round trip

For `reported-statistic-consistency/0.1.0`, deterministic extraction preserves the exact
PublicationContentDocument id. Fully explicit t/F/chi-square/z assertions are recomputed with SciPy.
An incomplete t assertion is retained so missing p-value or sidedness becomes `unverifiable`, not a
failed run.

The canonical artifact is compact sorted JSON with schema
`oratlas-verify-statistics-report/0.1.0`. It records protocol/input identity, normalized assertions,
calculation procedure and results, Python/SciPy/NumPy/`oratlas-verify` versions, platform, input
profile/version, and execution timestamps. Its SHA-256 is calculated from the exact serialized bytes.
The digest is held in negotiated ORAtlas metadata and the worker result rather than placed recursively
inside the bytes it hashes.

Artifact transfer is exactly:

1. prepare `artifactKey`, `kind`, `mediaType`, SHA-256, byte length, and visibility;
2. raw `PUT` with authorization, lease, content type, and content length (never JSON wrapping or
   multipart);
3. complete with `artifactId`;
4. cite the completed id in the finding's `artifactRefs`.

The finding separately cites its `publication-content-document` in `evidenceRefs`. It does not
duplicate the same artifact as a `verification-artifact` evidence reference. A finding key is
`stat-<test-type>-<24 lowercase hex>`, where the suffix hashes protocol identity, normalized scientific
assertion, and exact evidence reference. No random UUID is used as `findingKey`.

### Status and impact rule

`oratlas-verify-statistics-impact/0.1.0` maps:

- within tolerance → `verified` / `informational`;
- missing or ambiguous evidence → `unverifiable` / `minor`;
- mismatch crossing the conventional p=0.05 decision boundary → `discrepancy` / `major`;
- other numerical mismatch → `discrepancy` / `minor`.

No numerical mismatch is automatically critical. Worker/runtime exceptions fail the run and do not
manufacture a scientific `failed` finding.

For the synthetic `t=3.12`, `df=38`, two-sided example, SciPy recomputes approximately
`0.00344497757`. Reported `0.0034` is verified under the protocol defaults; reported `0.2` is a major
discrepancy; omitting sidedness is unverifiable while the run completes.

## Cross-repository acceptance boundary

The compatibility job checks out the exact ORAtlas commit, uses its documented SQLite push/seed flow,
and copies `integration/oratlas/bootstrap.ts` into that checkout. That ORAtlas-owned setup phase uses
its existing database/application fixture mechanisms to create a verifier credential, three synthetic
PublicationVersions, and three requested runs. After setup, `integration/oratlas/acceptance.py` knows
only the base URL, one-time fixture credential, and run ids. Claim, input, SciPy execution, raw artifact
upload, finding submission, completion, and public projection assertions all cross HTTP.

The slice intentionally excludes polling, lease renewal, arbitrary publication code/container/R or
notebook execution, production LLM auditors, mass verification, reputation/scoring, certification
mutation, and changes to ORAtlas or `oratlas-myst`.
