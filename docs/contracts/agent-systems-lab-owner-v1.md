# Forgeyard's Agent Systems Lab declaration

[`conformance/agent-systems-lab.json`](../../conformance/agent-systems-lab.json) is the
`forgeyard-lab-conformance/v1` owner declaration. It lists a bounded set of native JSON
protocols and binds each declared capability to the protocol versions emitted by its
local producers. A protocol suffix such as `/v1` identifies that JSON contract; it is
independent of Forgeyard's package version and the umbrella compatibility version.

The declaration complements the older
[`conformance/manifest.json`](../../conformance/manifest.json), which remains the
seven-case `ai-work-evidence/v1` fixture index. The fixture index bytes and meaning are
unchanged. It does not declare repository identity or the other native protocols.

The source tests in
[`tests/test_lab_conformance.py`](../../tests/test_lab_conformance.py) invoke the real
compose, record verification, review, receipt, provenance packet, packet verification,
and refusal evaluation producers. Their observed schema names must match the declaration's
capability bindings. The evaluation check also requires the declared corpus digest,
case count, and named refusal outcomes to match actual native execution. Run:

```sh
python -m pytest -q tests/test_lab_conformance.py tests/test_runtime_evaluation.py
forgeyard evaluate-refusals
```

A compatibility consumer should pin the source revision and SHA-256 of the exact UTF-8
declaration bytes, then validate the owner, repository, declaration schema, native
protocols, and capability bindings before negotiating. Downloading matching bytes proves
the content pin; native execution is separate evidence. No claim of a hosted provider
call, deployment, external adoption, or security certification follows from this metadata.

This is a source-tree declaration. The current distributions retain their existing
package contents; consumers can fetch the declaration from an immutable source URL.
The declaration intentionally omits protocols not exercised by these producer checks.
