# Limitations

Forgeyard does not execute agent commands, invoke model providers, resume interrupted processes, or
merge code. It can validate a worktree request and create a detached checkout with a bounded Git
invocation, but it does not capture commands, preserve dirty source state, or infer whether a
revision is deployed.

The provenance packet records caller-supplied evidence and source-byte digests. It does not prove
that a test command actually ran, that a revision exists on a remote, or that a source path was the
only changed path. Receipts and records are embedded for portability, but the verifier requires a
live `--source-root` to report fresh source bytes. Treat `ok=true` as a review-input integrity
result, not proof of merge, deployment, or production behavior.
