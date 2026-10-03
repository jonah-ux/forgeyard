# Portfolio Suite v2 offline handoff

This example connects the three public tools with synthetic files. It does not read a native
transcript store, contact a model provider, or make a repository change.

1. In ChatLens, create a redacted trace envelope and project it:

   ```bash
   chatlens evidence-export ./artifacts/synthetic.trace.jsonl \
     --id fixture-session:001 \
     --subject "Synthetic release investigation" \
     --summary "A bounded local fixture" \
     --created-at 2026-01-01T00:00:00Z \
     --fixture-id portfolio-suite-v2 \
     --out ./artifacts/chatlens.evidence.json --json
   ```

2. In Atlas, run the approval/recovery fixture and project its receipt:

   ```bash
   atlas demo --state ./artifacts/atlas-events.jsonl
   atlas evidence demo-task --state ./artifacts/atlas-events.jsonl \
     --id fixture-task:001 \
     --created-at 2026-01-01T00:00:00Z \
     --subject "Synthetic approval" \
     --summary "A bounded approval fixture" \
     --fixture portfolio-suite-v2 \
     --out ./artifacts/atlas.evidence.json
   ```

3. In Forgeyard, compose the bounded projections into a review record:

   ```bash
   forgeyard compose \
     --task-id portfolio-suite-v2 \
     --repository fixture-repo \
     --request "review the synthetic evidence chain" \
     --input chatlens=./artifacts/chatlens.evidence.json \
     --input atlas=./artifacts/atlas.evidence.json \
     --revision fixture-revision \
     --output ./artifacts/portfolio-review.json
   ```

Forgeyard copies only the source schema and bounded status into its task record. The raw evidence
files remain independently inspectable and can be sealed later with a provenance packet. `observed`
means a local producer validated its own artifact; it does not mean deployed, merged, or user-visible.
