# `forgeyard-installed-flow-release-lock/v1`

The checked-in [`conformance/installed-flow-release-lock-v1.json`](../../conformance/installed-flow-release-lock-v1.json)
locks the four packages exercised by Forgeyard's opt-in installed reference
flow: ChatLens, Atlas Agent Runtime, Agent Proof, and Forgeyard. It records the
tag commit, release channel, package version, CLI name, native schemas, wheel and
sdist SHA-256 values, and the runtime used for the fresh local observation.

The lock is an orchestration artifact owned by Forgeyard. It does not redefine
the native schemas or create a second adapter registry. The source repositories
remain authoritative for their own contracts and release workflows.

The release channel is explicit: ChatLens v0.4.0 is stable; Atlas v0.2.0, Agent
Proof v0.4.1, and Forgeyard v0.5.0 are prereleases. The fresh consumer
observation used public-main editable installs under Python 3.14, while the
published wheel and sdist hashes are locked independently. Keeping those two
facts separate prevents a source checkout from being presented as artifact
consumer proof. The observation also records the exact four public-main
revisions used for that run, so a reviewer can distinguish it from a later
checkout or release tag.

This lock covers the installed reference path only. It does not claim that the
remaining Agent Systems Lab owners share a release channel, that the packages
are deployed together, or that an external user adopted the flow. A future lock
may add another owner only after its command, native schema, artifact identity,
and fresh consumer boundary have direct evidence.
