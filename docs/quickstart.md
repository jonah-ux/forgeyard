# Forgeyard in 60 seconds

Forgeyard turns a handful of specialist checks into a small, reviewable record. The
happy path is intentionally boring to run and satisfying to inspect:

```text
install → demo → make it fail → inspect the contract
```

Think of it as a very picky bouncer for agent work: a green wristband only appears
when the receipt is valid, and a failed signal stays at the door.

The package is standalone. It does not require ChatLens, Atlas, a model provider, a
database, credentials, or a running service. Other tools can hand Forgeyard a JSON
report later, but the first run below only uses the repository itself.

## 1. Install the local CLI

From a fresh clone:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Forgeyard supports Python 3.11 or newer and has no runtime dependencies. If you
already have an environment, the only install command you need is:

```bash
python -m pip install -e .
```

## 2. Run the whole story

The offline demo creates a record, verifies its digest, and builds a reviewer packet
in a temporary directory. It prints one JSON document and leaves no project files
behind:

```bash
forgeyard demo | python -m json.tool
```

Look for these three lines in the formatted output:

```text
"schema": "forgeyard-demo/v1"
"status": "ready_for_review"
"reviewable": true
```

That is the smallest useful Forgeyard loop: evidence becomes a bounded decision and
the exact record bytes are carried into a handoff packet.

## 3. Make the record fail on purpose

Forgeyard is more interesting when the evidence is bad. This command composes a
failing specialist report without needing a provider or service:

```bash
tmp_dir="$(mktemp -d)"
cat > "$tmp_dir/drift.json" <<'JSON'
{"schema":"mcp-doctor/v1","ok":false,"revision":"demo-revision"}
JSON
forgeyard compose \
  --task-id demo-drift \
  --repository fixture-repo \
  --request "review the tool contract" \
  --input drift="$tmp_dir/drift.json" \
  --output "$tmp_dir/record.json"; status=$?
printf 'exit_status=%s\n' "$status"
forgeyard verify "$tmp_dir/record.json"
rm -rf "$tmp_dir"
```

The compose command exits with status `2`, and the record reports `blocked`. That is
the feature: a failed signal stays visible instead of being polished into a green
story.

## 4. Open the visual walkthrough

The public Workbench is a static, synthetic tour of the same boundary:

**[Open Forgeyard Workbench](https://jonah-ux.github.io/forgeyard/)**

Try the buttons in this order:

1. **Load passing demo** — three specialist reports arrive as bounded inputs.
2. **Compose record** — the page produces a `READY` decision and a digest.
3. **Simulate tamper** — changing the displayed request produces `REFUSED`.
4. **Load failing case** — one drift report produces a `BLOCKED` decision.
5. **Load adversarial matrix** — six explicit stale, denied, unenforced, partial, queued, and tampered signals produce a sealed `BLOCKED` record.

The Workbench contains no credentials, customer data, hidden provider state, or
network calls. It is a visual fixture, not a deployment or production verification
claim.

For the same lifecycle in a terminal, run the checked-in reference harness:

```bash
python scripts/run_reference_flow.py --scenario passing
python scripts/run_reference_flow.py --scenario blocked
python scripts/run_reference_flow.py --scenario tampered
```

Each scenario returns zero when its expected result is observed and prints a
`forgeyard-reference-flow/v1` receipt. The harness is synthetic and offline; it
does not connect to the surrounding repositories or claim production adoption.

## What to read next

| If you want to… | Read |
| --- | --- |
| Integrate a specialist JSON report | [`docs/contracts/forgeyard-compose-v1.md`](contracts/forgeyard-compose-v1.md) |
| Understand the record and digest boundary | [`docs/architecture.md`](architecture.md) |
| Build a verified reviewer handoff | [`README.md`](../README.md#build-a-reviewer-handoff) |
| See the current CLI performance receipt | [`scripts/benchmark_compose.py`](../scripts/benchmark_compose.py) |
| Understand current limits | [`docs/limitations.md`](limitations.md) |

## Keep the claims straight

`ready_for_review` means the supplied record passed Forgeyard's local checks. It does
not mean a pull request was merged, an artifact was deployed, or a production system
was verified. Those are separate steps owned by the surrounding workflow.
