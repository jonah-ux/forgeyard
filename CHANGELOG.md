# Changelog

## 0.5.0 — Agent Systems Lab reference flow and benchmark (unreleased)

- Add an offline `forgeyard-reference-flow/v1` harness covering context admission, capability
  policy, sandbox receipt, Atlas lifecycle, proof, resume, and Forgeyard verification.
- Exercise reviewable, unknown-status blocked, and digest-tampered refusal outcomes with synthetic
  owner-shaped reports and no external service dependency.

## Unreleased — Agent Systems Lab benchmark

- Add `forgeyard-lab-benchmark/v1` for fixed-dataset parse, validation, indexing, replay,
  composition, and provenance-packet verification measurements.
- Record dataset identity, runtime bounds, reviewability/privacy guards, and explicit machine-local
  limitations alongside operation timings.

## Unreleased — Agent Systems Lab conformance corpus

- Add a deterministic `ai-work-evidence/v1` corpus and runner covering valid, malformed, tampered,
  unsafe-path, bad-hash, unknown-version, and non-reviewable status cases.

## 0.4.0 — shared work evidence contract

- Add the dependency-free `ai-work-evidence/v1` validator and canonical fixture.
- Let `compose` consume Atlas and ChatLens projections without copying raw payloads.

## 0.3.2 — governed release identity (unreleased)

- Reissued the verified interoperability release through the annotated-tag workflow.
- Kept the installed CLI version, package metadata, and release identity aligned.

## 0.3.1 — verified interoperability (unreleased)

- Accepted source-bound Agent Proof `agent-proof/interop/v1` envelopes through their reviewed
  `projection.status.ok` field, and added a Context Integrity Lab report to the Workbench fixture.
- Aligned the installed `forgeyard --version` entry point with the 0.3.1 package release.

## 0.3.0 — portable provenance packets

- Added explicit `forgeyard-evidence-receipt/v1` records bound to task evidence and source paths.
- Added `forgeyard-provenance-packet/v1` with embedded record/receipt bytes, source SHA-256 seals,
  revision binding, canonical packet integrity, and fail-closed live-source freshness verification.
- Added CLI `receipt`, `packet`, and `verify-packet` commands without changing planned worktree or
  resume boundaries.

## 0.2.6 — guided review demo

- Add a zero-setup `forgeyard demo` walkthrough that creates, verifies, and packets a synthetic record in a temporary directory.


## 0.2.5 — evidence identity contract

- Reject empty or duplicate evidence names before a task record can become reviewable.
## 0.2.4 — revision provenance contract

- Reject review packets whose declared revision disagrees with passing evidence revisions.

## 0.2.3 — path contract hardening

- Reject empty, ambiguous, absolute, and traversal-style changed paths in review packets.

## 0.2.2 — release checksum portability

- Generate release checksums from artifact basenames so downloaded GitHub assets verify without path rewriting.

## 0.2.1 — review integrity release

- Published digest-pinned review packet construction and tamper rejection in the installable CLI.

## 0.2.0 — review integrity

- Added digest-pinned record verification to the review command.
- Review packets now carry the exact SHA-256 digest of the evidence record they were built from.
- Added regression coverage for tampered records and documented the packet provenance contract.

## 0.1.0 — foundation

- Added a framework-free task record with explicit evidence states.
- Added a CLI that emits stable JSON and blocks review readiness on failed or unknown evidence.
- Added synthetic contract tests and public provenance boundaries.
