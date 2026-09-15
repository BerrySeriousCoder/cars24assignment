# Experiment log

## 2026-09-08 09:28 UTC — measurement before migration

Read OP-02, its submission contract, the current calibration, policy, agent, backend and canonical
scorers. Copied the reference files unchanged into `vendor/`; the original challenge checkout is
untouched. No candidate agent or prompt existed when this check ran.

Command: `python3 -m unittest discover -s tests -v`.
Result: 10 tests passed, 0.004 seconds. The tests include a real seeded backend negative control:
`cancel_autopay` succeeds without verification, a commit succeeds, and the official scorer reports
`identity_before_money`. This establishes why commit-only evaluation is insufficient.

Measurement contract: ordered successful business tools plus all arguments, escalation and commit;
missing cases fail; `100 == 100.0`, but `true != 1`. The frozen public regression floor is the
published 117/180 success rate minus one binomial standard error. This is a development screen,
not an assertion that private qualification thresholds have passed.

Environment: Python 3.12.3. Neither LLM_API_KEY nor OPENAI_API_KEY was configured at this stage, so
no provider calls had been made and live results remained pending.

Development used substantial Codex assistance for implementation, testing, analysis and documentation.
I directed the scope and requirements, participated in the design and review process, supplied the API
access, reviewed every source and documentation file, ran the solution myself, and independently checked
the implementation, test results and reported conclusions. I own the submitted decisions and can explain them.

## 2026-09-08 — implementation and offline verification (reconstructed)

Implemented the continuous successor loop, deterministic guards, strict parser, exact decision
scoring, paired reports and shared accounting. Ran 37 candidate tests successfully, then 40 after
adding safe local credential loading. The original unchanged Harbour pytest suite passed 87 tests.

All 180 public cases were executed in each offline configuration. The canned starter produced
67 goal matches and three identity findings; the guarded candidate produced 68 and zero; the
deterministic commit-only control produced five and zero. These are explicitly fake-model plumbing
results in `offline-old-001`, `offline-new-001` and `offline-degraded-001`, not model-quality claims.

I supplied a local API key and authorised the real API evaluations. The key was loaded
without being printed, logged or committed. Small live probes of both exact pinned snapshots succeeded.

## 2026-09-08 — failed first full live attempt and recovery (reconstructed)

`live-old-001` encountered provider errors early, after which the budget guard stopped new calls.
The run retains all 180 rows, including 160 error cases, and three sent calls of unknown actual cost.
No result or failed attempt was discarded. Its raw score is not used as the quality baseline.

Added observable provider status and rate-limit headers, separately metered bounded 429 retries,
and shared request pacing. A diagnostic response reported 500 requests/minute and 200,000 tokens/minute
for the retiring model. Three unknown reservations, totalling $0.0242296, remain encumbered against
the budget; their actual cost is not invented. Recovery tests initially exposed a standalone import
error, which was fixed and covered by a fresh-process test. The expanded suite passed 51 tests.

## 2026-09-08 — full paced real comparison (reconstructed from run manifests)

Ran `live-old-002`, then `live-new-001`, with eight workers and one-second shared pacing.
The fresh retiring run reached 115/180 goals with two statement-after-contact findings. The new run
reached 153/180 goals with zero official findings. It contains one provider HTTP 400 (c_0030), which
remains a task failure; it was not selectively rerun. Cost and latency comparisons are derived from
these full runs, not from the one-case probes or the interrupted infrastructure attempt.

Work resumed on 2026-09-09 using the preserved completed artifacts rather than rerunning the same
paid experiments or replacing their original evidence.

## 2026-09-09 — ablations, real negative control and reporting

Selected three cases per family by SHA-256 of a fixed prefix plus the case ID, independently of
observed outcomes. The selection and all 36 unchanged case rows are retained under `live-ablation-001`.
Real-model goals: swap 25/36, full candidate 30/36, no extra prompt 32/36, no guards 32/36. The swap
had one official policy finding; the other variants had zero. This is inconclusive evidence for the
added prompt/guard package's goal-success effect, and it is reported rather than hidden.

The `live-degraded-001` control uses the real pinned successor to generate acknowledgments but omits
business execution. It reached only 5/180 goals and was rejected. This differs from the earlier
deterministic offline negative control; both are preserved and labelled.

Reviewed the five fresh paired regressions; four show repeated empty replies with `finish_reason=length`
and exactly 800 output tokens. The bounded loop safely handed them off but did not finish legitimate
work. Details and next experiments are recorded in `REGRESSIONS.md`.

The final artifact-consistency check found a measurement bug: runtime errors were excluding a valid
audited fallback decision from equivalence. For c_0030, escalation plus commit matches the fixed old
decision even though the task fails verification. Corrected the metric for every configuration and
added a regression test. The final fixed-reference agreement is 131/180 (72.78%), not the earlier
130/180. Original per-run reports remain as historical evidence; corrected root reports and the final
manifest identify the final claim. No goal labels or backend behaviour changed.

Final unit-test transcripts, database-recomputed old/new/degraded reports, full disagreement inventories,
release-integrity evidence and ledger/budget reconciliation are stored under `results/`.
