# forgeyard-provenance-graph/v1

This sidecar binds an opaque, redacted `agent-proof/graph/v1` summary to a
`forgeyard-provenance-packet/v1` digest. Forgeyard owns the packet attachment;
Agent Proof remains authoritative for graph construction, node/edge semantics,
source binding, and orphan-edge refusal. The existing provenance-packet schema
is unchanged.

`forgeyard graph-attach PACKET GRAPH --output ATTACHMENT` stores only the packet
digest, graph schema, graph/input digests, node and edge counts, and a redaction
marker. It never copies graph nodes, edges, paths, commands, or source payloads.

`forgeyard verify-graph-attachment ATTACHMENT --packet PACKET --graph GRAPH`
requires both live inputs. It refuses a changed packet, changed graph summary,
invalid graph digest, invalid attachment digest, or missing source-bound input.
The graph file must still be checked with Agent Proof's `verify-graph --input`
path when semantic node/edge validation is required; this sidecar is the
cross-repository binding layer, not a second graph implementation.
