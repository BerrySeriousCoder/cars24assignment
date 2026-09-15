# OP-02 — The Deprecation Notice

This solution addresses **problem 2 only**. It migrates Harbour from the pinned
`gpt-4.1-mini-2025-04-14` to `gpt-5-mini-2025-08-07`, adds a guarded servicing loop,
and measures actual database outcomes, decisions, policy findings, API cost and latency.

Start with [MIGRATION_REPORT.md](MIGRATION_REPORT.md) for the measured evidence and
[MEMO.md](MEMO.md) for the engineering VP's rollout decision. The complete case-level analysis is
in [DISAGREEMENTS.md](DISAGREEMENTS.md), while [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) records the
sequence of work, failed attempts and what was actually executed.

## Run locally

Python 3.12.3 was used. The candidate runtime and its tests need no third-party packages.

```bash
make test
bash scripts/reproduce.sh smoke
```

Smoke mode uses the starter's canned fake model. Those outputs test plumbing, not model quality.
Every run has a distinct directory; rerunning never overwrites a prior run.

For real runs, create `.env` locally (it is ignored by Git):

```dotenv
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.openai.com/v1
```

The runner loads these settings without shell execution. Environment variables supplied by a
reviewer gateway take precedence. Do not set a global model override when comparing configurations.

```bash
make eval CONFIG=old MODE=live
make eval CONFIG=new MODE=live
make eval CONFIG=degraded MODE=live
bash scripts/reproduce.sh ablation
```

`make eval` collects results, reopens every database and exits nonzero when its development screen
fails. The intentionally degraded control is expected to fail. The collection-only runner exits zero
when collection completes, even when its measured agent fails; inspect the report or use `make eval`.
The current degraded control calls the real successor model but disables business execution.
It tests evaluator sensitivity; the reviewer's undisclosed degraded model remains a separate check.
The earlier `offline-degraded-001` run used a deterministic commit-only control and is labelled accordingly.

`ablation` runs old, unchanged swap, full candidate, candidate without prompt guidance, candidate
without guards and the local degraded control. All paid runs share `results/live/budget.json`.
Do not delete or replace that accounting state between experiments. It stops spending at $50 and
freezes further calls if provider usage is unknown. Rate-limit retries are bounded and individually
metered. Shared request pacing defaults to one second; `OP02_CALL_INTERVAL` can configure it. Keep
the same setting for latency comparisons. Unknown calls can be quarantined while retaining their
full maximum reservations; their actual cost remains unreconciled and must not be labelled zero.

The recorded exploratory ablation used a smaller, predeclared stratified subset:

```bash
python3 -m op02.ablation --per-family 3 --output results/raw/my-ablation
```

To evaluate another implementation without changing the suite, set `HARBOUR_AGENT=module:function`.
The callable takes `(backend, case_id, customer_id, message, *, loan_id=None)` and must use the
same model boundary (`harbour.llm.complete`) so calls are metered. A reviewer must independently
enforce gateway-only egress; candidate-side metering cannot attest its own completeness.

For a custom case set, the runner accepts `--cases` and `--reference`. The agent receives only
case/customer/loan identifiers and the message; the evaluator alone reads family and goal labels.

```bash
python3 -m op02.runner --config new --mode live --concurrency 8 \
  --output results/raw/my-new-run
python3 -m op02.eval_report --run results/raw/my-new-run
python3 -m op02.compare --old results/raw/my-old-run/cases.jsonl \
  --new results/raw/my-new-run/cases.jsonl --output results/my-comparison.json
```

## Artifacts and boundaries

Each run preserves `cases.jsonl`, per-case SQLite databases, model requests/responses, the token
ledger, traces, exact equivalence rows, all disagreements, policy findings, metrics and a manifest
with source hashes, model pin, timestamp and concurrency. Request files contain synthetic customer
data; keep the solution and artifacts private as required by the challenge. No API keys are stored
in run artifacts. Headers are never logged.

`vendor/` is an unchanged, attributed copy of the relevant challenge inputs and scorers.
`python3 -m op02.integrity` checks those files against the published release manifest.
The original challenge checkout was not modified; the vendored copy is checked independently by hash.

The official 60 hidden cases, independent gateway ledger, hardware-controlled rerun and private
degraded configuration can only be assessed by the reviewers. Public measurements do not replace
those checks. Candidate-side reports always leave final qualification pending.

Optional original Harbour tests:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest vendor/OP-01/harbour/tests -q
```
