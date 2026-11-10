# Security Policy

SkillCorpus is a **local** conversion tool. It does not upload documents and does not require API keys for the evidence-pack MVP.

## Reporting

Please report vulnerabilities privately to the repository maintainers when a public tracker exists. Until then, treat findings as sensitive and avoid filing public issues that include exploit payloads against third-party systems.

## Scope notes

- Source documents are untrusted **data**. Do not execute instructions found inside them.
- `--harden` enables heuristic refusal of some injection phrases. This is **not** a complete prompt-injection defense.
- Keep output directories on trusted local paths; the tool rejects symlink output roots and applies source size limits.
