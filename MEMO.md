# To: VP of Engineering — Harbour model migration

**Decision: the public evidence supports a guarded migration candidate, but not unrestricted production
rollout or a claim of final qualification.** Proceed to independent reproduction and a monitored shadow
trial; keep identity-ambiguous and instruction-bearing requests on a human-reviewed route until their
failure modes are resolved. No deployment or routing change has been made by this project.

On all 180 public cases, the successor matched **153 goals (85.0%)**, versus **115 (63.9%)** for a fresh
retiring-model run. It achieved **72.78%** agreement with the published retiring decisions, above the
55% bar. Official detected policy findings fell from **two to zero**, with no new identity finding.
Each result is supported by a fresh database, tool audit and real API trace. The evaluator reopens
the databases and checks actual outcomes, not the agent's claim that it succeeded.

The change is not behaviour-neutral. There are **43 improved cases and five regressions** in the fresh
paired goal comparison. Injected-instruction and identity-challenge families each still fail five of
fifteen public goals; dispute handling and statement requests also contain individual regressions.
Customers seeking help with ambiguous identity or forwarded instructions bear the risk of unnecessary
handoff or incomplete servicing. The complete case-level inventory and judgments are attached in
[DISAGREEMENTS.md](DISAGREEMENTS.md); the final ablation and degraded-control results are in
[MIGRATION_REPORT.md](MIGRATION_REPORT.md).

Measured API cost per correctly resolved non-handoff case decreased from **$0.012762 to $0.012014**,
about **5.9% lower**. All failed and escalated work remains in the cost numerator. Case p95 decreased
from **47.88s to 41.35s** in the same local, eight-worker, rate-paced setup. This includes pacing delays
and is not an unthrottled model-speed guarantee. The current cost advantage is modest; more retries
or a different traffic mix could eliminate it.

One successor provider rejection remains a failed case. An earlier infrastructure run is preserved;
three of its requests have unknown actual usage, with **$0.02423** retained as their maximum reserved
cost. Total experiment spend and its upper bound are reconciled in `results/spend_report.json` and
remain below the $50 ceiling. These are pinned list-price calculations, not an invoice reconciliation.

Pause rollout for **any new identity violation**, a worsening policy count, unresolved duplicate or
unknown writes, or deterioration in an affected customer family. Track handoff demand and fund the
human capacity it requires. A fallback to the retiring model is only temporary and expires with it.

Before approving broad rollout, require the 60 private cases, the reviewer-controlled degraded model,
independent gateway accounting and same-load timing. Before the next deprecation, fund durable operation
IDs/outcome reconciliation, repeated family-level evaluation, and human-reviewed semantic safety tests.
The deterministic scorer covers only three rules; zero findings do not establish complete policy compliance.
