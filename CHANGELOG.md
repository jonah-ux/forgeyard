# Changelog

## 0.3.0 — portable provenance packets (unreleased)

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
