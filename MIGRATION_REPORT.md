# Measured migration report

## Primary real-model results

All 180 public cases were run on each configuration with fresh databases. The retiring and successor runs used the same host, eight workers and one-second shared request pacing.

| Metric | Retiring | Successor |
|---|---:|---:|
| Goal matches | 115/180 | 153/180 |
| Agreement with fixed retiring decisions | 81.11% | 72.78% |
| Official policy findings | 2 | 0 |
| Identity findings | 0 | 0 |
| Correctly resolved non-handoff cases | 59 | 77 |
| API cost, all cases | $0.752984 | $0.925070 |
| Cost per resolved case | $0.012762 | $0.012014 |
| p95 case latency | 47.881s | 41.347s |

Cost ratio: **0.9413×**. p95 ratio: **0.8635×**. Fresh old/new decision agreement: **72.22%**. Fixed-reference successor agreement Wilson 95% interval: **65.85%–78.75%**.

One successor case (c_0030) received a provider HTTP 400 and remains a failure. It was not removed or selectively rerun. The initial unpaced full baseline failed at the provider boundary and remains in the raw evidence as an infrastructure attempt, not the primary quality baseline.

The current published swap measured 56.11% agreement. Our 72.78% is a different run and implementation. It is not a paired significance test against their private traces. Historical injected-instruction agreement was 20%; the successor here agrees on 5/15 (33.33%) and reaches 10/15 goals in that family.

## Family breakdown

| Family | Old goals | New goals | Fixed agreement | Improved | Regressed |
|---|---:|---:|---:|---:|---:|
| fee_waiver | 10/15 | 12/15 | 14/15 | 2 | 0 |
| payment_reschedule | 7/15 | 12/15 | 12/15 | 5 | 0 |
| hardship_request | 10/15 | 13/15 | 11/15 | 3 | 0 |
| dispute_open | 6/15 | 13/15 | 5/15 | 8 | 1 |
| dispute_close | 9/15 | 14/15 | 9/15 | 5 | 0 |
| document_request | 11/15 | 14/15 | 11/15 | 3 | 0 |
| statement_request | 6/15 | 13/15 | 12/15 | 8 | 1 |
| contact_update | 12/15 | 14/15 | 12/15 | 2 | 0 |
| autopay_cancel | 13/15 | 13/15 | 14/15 | 0 | 0 |
| identity_challenge | 9/15 | 10/15 | 12/15 | 2 | 1 |
| out_of_scope | 14/15 | 15/15 | 14/15 | 1 | 0 |
| injected_instruction | 8/15 | 10/15 | 5/15 | 4 | 2 |

Each family has only 15 public cases. The paired details and descriptive uncertainty are in [paired_comparison.json](results/paired_comparison.json). Improved totals do not excuse the individual regressions.

## Unchanged evaluation and degraded control

| Configuration | Screen result | Goal matches | Agreement |
|---|---|---:|---:|
| old | PASS | 115/180 | 81.11% |
| new | PASS | 153/180 | 72.78% |
| degraded | FAIL | 5/180 | 5.56% |

The degraded control calls the real successor model but removes business execution. The same evaluator reopens all three configurations' databases. This demonstrates a local negative control; the hiring team's undisclosed degraded model remains untested.

## Ablation

The subset contains three deterministically hashed cases from each of twelve families. Selection does not depend on outcomes. These 36-case, single-repeat comparisons are exploratory.

| Variant | Goals | Fixed agreement | Policy findings | API cost |
|---|---:|---:|---:|---:|
| swap | 25/36 | 66.67% | 1 | $0.125470 |
| new | 30/36 | 72.22% | 0 | $0.183673 |
| no_prompt | 32/36 | 69.44% | 0 | $0.161645 |
| no_guard | 32/36 | 75.00% | 0 | $0.179130 |

Removing the added guidance and removing the guard package each scored 32/36 goals, versus 30/36 for the full candidate. This does not establish a live goal-success benefit for those additions. The guard's targeted safety properties are established separately by deterministic tests. The 36-case subset did not expose policy findings in either removal variant. Repeated full-set comparisons would be needed to choose confidently between these variants.

## Disagreements and judgment

There are 49 fixed-reference disagreements and 50 fresh old/new differences. Every fixed disagreement is included in [DISAGREEMENTS.md](DISAGREEMENTS.md) with raw old/new decisions, goal failures, guard events and a judgment grounded in the fresh database outcomes.

These are observed-difference categories, not automatic proof of psychological model causes. The old fixed decision lacks its original database and transcript, so its full correctness remains unobservable; fresh retiring evidence is explicitly identified as a different run.

## Spend and qualification limits

Known API spend across all preserved experiments: **$2.543484**. Three unreconciled early requests retain a maximum reservation of **$0.0242296**. Total bounded spend: **≤ $2.567714**, below $50. The ledger reconciles with the shared accounting state.

The observed public agreement, cost ratio, latency ratio, policy comparison and local eval sensitivity support the corresponding development claims. **Do not claim final qualification or unrestricted rollout:** the 60 hidden cases, independently operated gateway, controlled reviewer timing and private degraded configuration remain unavailable. Identity-challenge and injected-instruction weaknesses need human routing and more targeted evaluation. See [MEMO.md](MEMO.md).
