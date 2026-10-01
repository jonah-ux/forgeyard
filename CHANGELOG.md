# Changelog

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
