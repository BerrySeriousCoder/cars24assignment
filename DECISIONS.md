# Consequential decisions

These notes were reconstructed from the dated experiment log, raw results and development conversation.
They are not presented as contemporaneous private reasoning or as independent user review.

## 1. Measure executed state and exact decisions, not textual resemblance

**Hypothesis.** A model migration can sound correct while making a different servicing decision.
Plausible options were semantic similarity between replies, an LLM judge, or deterministic comparison
of backend state and successful tool calls. The constraint was the published OP-02 decision contract
and the need for a suite that catches a degraded implementation.

**Observation.** Before the candidate agent existed, a seeded-backend test cancelled autopay without
verification and committed successfully. The official policy scorer caught the violation even though
the starter's completion-only logic would consider the request closed. Later, the real successor
and retiring runs differed on both goals and policy findings despite broadly similar servicing replies.

**Choice.** Reuse the unchanged official goal and policy scorers, preserve all tool arguments and
order, and keep agreement separate from correctness. Explicitly distinguish missing data from valid
empty decisions. Recompute from saved databases in the final evaluator.

**Trade-off and reversal condition.** Exact string arguments can disagree even when both dispute
reasons are defensible. We report that rather than weakening the official metric. A future policy
requiring summary truthfulness would justify an additional calibrated semantic evaluator, not a
replacement for authoritative database checks. See `tests-before-live.json` and the full inventories.

## 2. Use deterministic guards and a continuous loop around the successor

**Hypothesis.** Explicit prompt guidance helps, but a missing backend identity check should not depend
on the model remembering a sentence. Options were a prompt-only migration, patching the backend, or an
orchestration guard plus bounded continuation. Patching the benchmark environment was prohibited.

**Observation.** The unverified-autopay test exposed a real backend gap. The guard ablation reproduces
that gap in a controlled test, whereas the full guard blocks the call before the backend. Other tests
show the starter can partially update contact data and that numeric formatting could otherwise evade
naive duplicate detection. In the primary real runs, official findings decreased from two to zero;
success rose from 115/180 to 153/180. This is a combined-system result, not proof that one guard caused
all the improvement.

**Choice.** Add per-contact verification, read-only ownership checks, same-contact duplicate-write
prevention, contact-change restrictions, strict action parsing and a single bounded history. Keep
every actual business write in the original audited backend. Add targeted policy guidance rather than
rewriting the supplied policy. Never read goal labels or fixed retiring decisions at inference time.

**Trade-off and reversal condition.** The restrictions can defer legitimate compound requests.
Remove or narrow a guard only after an authorised workflow is specified and repeatable tests show
that the replacement maintains identity and ownership guarantees. The live `no_guard` and `no_prompt`
ablations are in `results/ablation_report.json`; their small single-run sample does not eliminate model
randomness. Durable cross-request idempotency remains future production work.

## 3. Recover from provider failure without deleting evidence or inventing usage

**Hypothesis.** Eight concurrent workers would be practical. Options after the failed run were to
discard it, silently rerun failed cases, or preserve the run and fix observable infrastructure limits.
The constraints were honest reporting, complete denominators and a shared $50 API ceiling.

**Inconclusive experiment.** `live-old-001` recorded only 13 successful goals and 160 error cases
after early provider errors froze the spend guard. The original adapter logged insufficient status
detail to prove those three requests' actual charges. Treating this as an ordinary baseline would
make a poor comparison. Treating their usage as zero would invent evidence.

**Choice.** Preserve that attempt, keep approximately $0.02423 of worst-case usage reserved, add
safe provider status/request-ID/rate-limit metadata, and pace calls across workers. Retries of known
rate-limit rejections are separately metered. Rerun all 180 retiring cases, then run the successor
under the same pacing and concurrency. The fresh successor's one HTTP 400 remains in its denominator.

**Trade-off and reversal condition.** Pacing contributes to measured case latency, so these results
do not establish unthrottled model speed. Gateway/invoice evidence could reconcile the three early
requests. A higher verified account limit could justify different pacing, followed by a new paired
comparison. Do not clear the budget state merely to continue calls.

## Assistance and ownership

I developed this submission collaboratively with substantial Codex assistance across implementation,
testing, analysis and documentation. I directed the scope and requirements, contributed to the design
and review process, supplied and controlled the API access, reviewed every source and documentation file,
and ran the solution myself. I independently checked the test outputs, source integrity, database outcomes,
headline calculations, ledger arithmetic and five paired regressions. I understand and own the decisions,
trade-offs and limitations presented here.
