# oratlas-verify

oratlas-verify is the external, request-scoped scientific-verification executor used by ORAtlas and
ORA certification. It runs explicit scientific procedures against immutable inputs and returns
structured verification evidence. ORAtlas remains the registry, coordinator, provenance and
knowledge platform, and the owner of certification lifecycles.

```text
ORAtlas
   │ evidence ledger / requested run + frozen input
   ▼
oratlas-verify
   │ deterministic scientific executor (SciPy in the first live flow)
   │
   ▼
ORAtlas immutable findings + completed artifacts
   │
   ▼
future ORA certification
```

oratlas-verify has no ORAtlas database connection, does not import Prisma models, and never writes to
ORAtlas persistence except through its HTTP API client. ORAtlas identifiers are carried as opaque,
exact strings; this repository does not recreate canonical publication identity.

## Scientific meaning

- Verification is evidence for certification; it is not certification.
- Regeneration uses the original workflow; independent reproduction uses an independent
  implementation. They are recorded separately.
- An execution-attested result has provenance, but is not thereby reproduced.
- Visual similarity is supplementary evidence, not scientific replication.
- `unverifiable` means required evidence is missing or ambiguous; it is not a procedure failure.
- AI audit is interpretive and cannot replace deterministic numerical verification.

The review architecture aims at **bias reduction**, not an “unbiased” system. First-pass auditors
receive the same blinded scientific input independently and their outputs remain separate. Planned
critical and strength reviewers provide complementary perspectives. No production LLM auditor is
enabled in this release.

## Implemented protocols

Protocol behavior is selected by the exact name and semantic version. Scientific semantics will
never change silently within an existing version.

| Protocol | State | Behavior |
|---|---|---|
| `reported-statistic-consistency/0.1.0` | implemented | SciPy recomputation of t, F, chi-square and z p-values |
| `figure-structured-comparison/0.1.0` | implemented | dimensions, ordered series, x/y values, and meaningful labels |
| `analysis-result-comparison/0.1.0` | implemented | bounded scalars, vectors/arrays, tables, and named metrics |
| `methods-audit/0.1.0` | reserved | production auditor not enabled |
| `claim-evidence-audit/0.1.0` | reserved | production auditor not enabled |
| `statistical-design-audit/0.1.0` | reserved | production auditor not enabled |
| `reproducibility-audit/0.1.0` | reserved | production auditor not enabled |

F and chi-square tests use the upper tail and therefore require `"sidedness": "greater"`. t and z
support `two-sided`, `greater`, and `less`. Every result includes normalized input, the exact SciPy
procedure, library version, recomputed value, absolute difference, and explicit absolute/relative
tolerances. Missing sidedness or degrees of freedom is `unverifiable`; invalid degrees of freedom,
NaN/infinity, or impossible parameters fail closed.

Figure and analysis tolerances are supplied by the request. There is intentionally no universal
scientific tolerance. Figure comparison is structured-data comparison; optional local image hashes,
dimensions, and perceptual similarity are labeled `visual-consistency` and cannot establish
reproduction.

## Install and run

Python 3.11–3.13 is supported. The committed `uv.lock` resolves exact transitive versions.

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run mypy
```

Verify a local structured assertion:

```json
{
  "test_type": "t",
  "statistic": 3.12,
  "degrees_of_freedom": [38],
  "reported_p": 0.0034,
  "sidedness": "two-sided",
  "absolute_tolerance": 0.00005,
  "relative_tolerance": 0.0001
}
```

```bash
uv run oratlas-verify verify-statistic --input assertion.json
```

Remote operation requires secrets in the environment, never in source:

```bash
export ORATLAS_BASE_URL=https://oratlas.example
export ORATLAS_VERIFIER_TOKEN=...
uv run oratlas-verify run verification-run-id
uv run oratlas-verify inspect verification-run-id
uv run oratlas-verify validate-result --input response.json
```

Generated canonical JSON artifacts are retained under `.oratlas-verify/artifacts` by default; set
`ORATLAS_VERIFY_ARTIFACT_DIR` to an operator-managed immutable store location. Logs are structured JSON
and include run/correlation IDs but never input payloads or authorization tokens.

## Input envelopes

A run carries a single `VerificationInput`. For one protocol, `payload` is that protocol's object.
For multiple protocols, `payload.protocol_inputs` maps each exact `name/version` to its object. The
envelope also carries opaque publication/version IDs, evidence IDs, immutable artifact references,
and an optional ORAtlas-verified `ExecutionPassport`. Passport attestation is recorded; oratlas-verify
still performs and owns the comparison finding.

The optional deterministic extractor recognizes only explicit t, F, chi-square and z assertions
that include the statistic, p-value, required df, sidedness, source span, and evidence ID. It never
guesses. A future AI extractor may propose the same strict structure, but proposals must still pass
the independent deterministic verifier.

## Safety boundary

Inputs are untrusted structured JSON. oratlas-verify does not evaluate strings, deserialize pickle/joblib,
follow input URLs, invoke shells from metadata, or execute publication code. Available execution
modes are built-in deterministic procedures, verified externally supplied results, and an explicitly
enabled test-only synthetic backend. The sandbox namespace is an extension point that always rejects
untrusted execution in 0.1.0.

## Authoritative ORAtlas integration

The production worker boundary is ORAtlas verification API `1.0.0`, pinned to merge commit
`999580bad1fee5b22e8113c5e1c7c9b888eb1217`. ORAtlas creates a requested run; the CLI claims it,
validates full PublicationVersion `1.3.0` or blinded
`verification-publication-input/1.0.0`, transitions it to running, executes SciPy, prepares and uploads
exact raw canonical report bytes, completes the artifact, submits immutable findings, completes the
run, and verifies both public projections.

Every run-scoped worker request uses the one-time in-memory
`X-ORAtlas-Verification-Lease`. Stable artifact/finding keys provide exact replay semantics; a
different payload under an existing key raises an explicit 409 idempotency conflict. See
[`docs/oratlas-integration.md`](docs/oratlas-integration.md) for routes, DTOs, integrity checks,
finding mapping, and the pinned cross-repository acceptance boundary.

## Scope limits and next slice

This release deliberately stops before lease renewal, continuous polling, arbitrary code/container
execution, production LLM auditors, automatic certification, ORA Scientific Merit 0.2 integration,
crawling/web browsing, and reputation or global scoring. The recommended next slice is a separately
designed renewable-lease worker model for bounded long-running deterministic jobs; isolated
arbitrary-code execution remains out of scope until it has its own threat model and resource policy.
