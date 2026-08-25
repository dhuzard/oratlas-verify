# ORAtlas verification transport assumptions (oratlas-verify 0.1.0)

The transport is provisional. JSON field casing is camelCase at the run envelope and frozen input
boundary. Finding and artifact bodies currently use oratlas-verify's explicit snake_case contract fields;
ORAtlas should either accept those fields or publish final mapping names.

## Retrieve frozen input

`GET /api/verifications/runs/{runId}/input`

```json
{
  "runId": "vr_123",
  "correlationId": "corr_123",
  "requestedAt": "2026-08-25T08:00:00Z",
  "protocols": [
    {"name": "reported-statistic-consistency", "version": "0.1.0"}
  ],
  "frozenInput": {
    "publicationId": "opaque-publication-id",
    "publicationVersionId": "opaque-version-id",
    "payload": {},
    "evidenceIds": [],
    "artifactReferences": [
      {
        "artifactId": "artifact-id",
        "sha256": "64-lowercase-hex-characters",
        "mediaType": "application/json",
        "byteLength": 123
      }
    ],
    "executionPassport": null,
    "inputSha256": "SHA-256 of canonical payload JSON"
  }
}
```

`inputSha256` is mandatory in remote DTOs and is checked before execution. Canonical JSON uses UTF-8,
sorted object keys, no insignificant whitespace, and rejects NaN/infinity. IDs are opaque: oratlas-verify
does not parse or infer publication identity.

## Submissions and transition

- `POST /api/verifications/runs/{runId}/findings`: `{ "findings": [...] }`
- `POST /api/verifications/runs/{runId}/artifacts`: `{ "artifacts": [...] }`
- `POST /api/verifications/runs/{runId}/transition`: `{ "state": "completed" }` or
  `{ "state": "failed", "reason": "ExceptionClass" }`

Endpoints should be idempotent by `finding_id`, `artifact_id`, and terminal run state. The API must
reject submissions whose run, requested protocol version, or frozen input hash does not match.
oratlas-verify does not currently assume retries, leases, or optimistic concurrency tokens; those need to
be specified before multiple workers consume the same run.

## Artifact transfer

Permitted input content is read from
`GET /api/verifications/runs/{runId}/artifacts/{artifactId}/content`. Redirects are disabled. Content
is deleted locally on a hash/length mismatch. Output metadata includes SHA-256, media type, byte
length, generator protocol/version, input hashes, tool versions, timestamp, and finding relations.

The final API still needs to define how output bytes are uploaded or how a durable object-store URI is
registered. oratlas-verify will not follow an arbitrary upload URL supplied inside publication metadata.

