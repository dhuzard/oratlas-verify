# Security policy

Treat all publication content and artifacts as untrusted. oratlas-verify 0.1.0 accepts structured JSON and
immutable bytes only. It does not run supplied code, shell commands, macros, extensions, notebooks,
pickles, or joblib payloads, and it does not follow publication-provided URLs.

Report vulnerabilities privately to the repository owner. Do not include bearer tokens, unpublished
datasets, or private publication content in an issue. Rotate `ORATLAS_VERIFIER_TOKEN` immediately if
it may have been disclosed.

