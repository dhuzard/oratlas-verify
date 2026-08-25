# oratlas-verify

oratlas-verify is the external, request-scoped scientific-verification executor used by ORAtlas and
ORA certification. It runs explicit scientific procedures against immutable inputs and returns
structured verification evidence. ORAtlas remains the registry, coordinator, provenance and
knowledge platform, and the owner of certification lifecycles.

```text
ORAtlas
   │ frozen run input through API
   ▼
oratlas-verify
   ├── statistics
   ├── figures
   ├── analyses
   └── independent auditors (interfaces only in 0.1.0)
   │
   ▼
VerificationFindings
   │ submit through API
   ▼
ORAtlas
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

## Current ORAtlas API assumptions

All assumptions below are isolated in `src/oratlas_verify/oratlas/` and can be adapted without changing
scientific code:

- bearer authentication uses `ORATLAS_VERIFIER_TOKEN`;
- `POST /api/verifications/runs` creates a run and returns `{ "runId": ... }`;
- `GET /api/verifications/runs/{runId}/input` returns the frozen input DTO described in
  `docs/oratlas-api-assumptions.md`;
- findings and output artifact metadata are posted to `/findings` and `/artifacts`;
- `POST /transition` accepts `completed` or `failed`;
- permitted input artifact content is downloaded only from the run-scoped endpoint and is verified
  against the frozen SHA-256 and byte length;
- artifact bytes are retained by the configured worker store in this slice; the final API must define
  upload negotiation or a durable object-store reference before distributed production deployment.

## Scope limits and next slice

This release deliberately stops before arbitrary code/container execution, production LLM auditors,
automatic certification, ORA Scientific Merit 0.2 integration, crawling/web browsing, and reputation
or global scoring. The recommended next slice is to finalize the generic ORAtlas VerificationRun API,
add authenticated artifact upload negotiation, and run contract tests against its published OpenAPI
schema. A separate isolated container worker can follow after a threat model and resource policy are
approved.
