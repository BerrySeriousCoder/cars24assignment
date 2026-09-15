"""Recompute and assemble the final private development evidence package."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import paths
from .io import read_rows, loads, sha256, write_json, append_jsonl
from .metrics import decisions_equal
from .eval_report import recompute
from .compare import compare
from .integrity import verify


def pretty(value, places=4):
    return "pending" if value is None else f"{value:.{places}f}"


def successful(row):
    return row["goal"]["goal_state_match"] and not row.get("error")


def observed_difference(old, new):
    if old is None or new is None:
        return "missing_decision"
    if old["escalated"] != new["escalated"]:
        return "escalation_changed"
    if old["committed"] != new["committed"]:
        return "completion_changed"
    if [t["name"] for t in old["tools"]] != [t["name"] for t in new["tools"]]:
        return "tool_selection_or_order_changed"
    return "arguments_changed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, default=paths.ROOT / "results/raw/live-old-002")
    parser.add_argument("--new", type=Path, default=paths.ROOT / "results/raw/live-new-001")
    parser.add_argument("--degraded", type=Path, default=paths.ROOT / "results/raw/live-degraded-001")
    parser.add_argument("--ablation", type=Path, default=paths.ROOT / "results/raw/live-ablation-001")
    args = parser.parse_args()
    output = paths.ROOT / "results"
    integrity = verify()
    write_json(output / "vendor_integrity.json", integrity)
    reports = {}
    row_sets = {}
    for name, directory in (("old", args.old), ("new", args.new), ("degraded", args.degraded)):
        reports[name] = recompute(directory)
        row_sets[name] = read_rows(directory / "cases.jsonl")
        write_json(output / f"eval_report_{name}.json", reports[name])
    paired = compare(row_sets["old"], row_sets["new"])
    write_json(output / "paired_comparison.json", paired)
    old_metrics, new_metrics = reports["old"]["metrics"], reports["new"]["metrics"]
    cases = {r["case_id"]: r for r in read_rows(paths.CASES, "case_id")}
    old_rows = {r["id"]: r for r in row_sets["old"]}
    new_rows = {r["id"]: r for r in row_sets["new"]}
    refs = {r["id"]: r["decision"] for r in read_rows(paths.RETIRING)}
    equivalence, inventory, live_inventory = [], [], []
    for cid, case in cases.items():
        old, new = old_rows[cid], new_rows[cid]
        equivalence.append({"id": cid, "old": refs[cid], "new": new["decision"]})
        old_ok = successful(old) and not old["policy_violations"]
        new_ok = successful(new) and not new["policy_violations"]
        if old_ok and new_ok:
            judgment = "Both fresh runs satisfy the checked goal and rules; strict decisions differ."
        elif new_ok:
            judgment = "Prefer the new fresh outcome on the available goal/policy evidence."
        elif old_ok:
            judgment = "Prefer the old fresh outcome; this is a candidate regression requiring review."
        else:
            judgment = "Neither fresh outcome satisfies all checked goal/rule requirements."
        common = {"id": cid, "family": case["family"], "customer_message": case["message"],
                  "fixed_old": refs[cid], "fresh_old": old["decision"], "new": new["decision"],
                  "old_goal_match": successful(old), "new_goal_match": successful(new),
                  "old_policy_findings": old["policy_violations"], "new_policy_findings": new["policy_violations"],
                  "old_goal_failures": old["goal"]["failures"], "new_goal_failures": new["goal"]["failures"],
                  "judgment_on_fresh_runs": judgment,
                  "fixed_old_correctness": "not fully observable: no fixed-reference database or transcript is published",
                  "guard_events": (new.get("agent_result") or {}).get("guard_events", []),
                  "new_runtime_error": new.get("error"),
                  "new_summary": (new.get("agent_result") or {}).get("summary"),
                  "old_evidence": str((args.old / old["database"]).relative_to(paths.ROOT)),
                  "new_evidence": str((args.new / new["database"]).relative_to(paths.ROOT))}
        if not decisions_equal(refs[cid], new["decision"]):
            inventory.append({**common, "cause": "runtime_error" if new.get("error") else observed_difference(refs[cid], new["decision"])})
        if not decisions_equal(old["decision"], new["decision"]):
            live_inventory.append({**common, "cause": observed_difference(old["decision"], new["decision"])})
    # These are derived reports; raw per-run evidence is never overwritten.
    for filename, rows in (("equivalence.jsonl", equivalence), ("disagreement_inventory.jsonl", inventory),
                           ("fresh_disagreement_inventory.jsonl", live_inventory)):
        (output / filename).write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))
    ablations = {}
    for config in ("swap", "new", "no_prompt", "no_guard"):
        directory = args.ablation / config
        report = recompute(directory, args.ablation / "cases.jsonl")
        ablations[config] = report["metrics"]
    write_json(output / "ablation_report.json", {
        "selection": loads((args.ablation / "selection.json").read_text()), "variants": ablations,
        "limitations": "36 public cases, three per family, one run per variant; exploratory, not causal proof or held-out performance"})
    all_ledgers = sorted((output / "raw").rglob("ledger.jsonl"))
    known_spend = 0.0
    unknown_calls = []
    call_ids = set()
    for path in all_ledgers:
        for entry in read_rows(path):
            if entry["id"] in call_ids:
                raise ValueError("duplicate model call ID across runs")
            call_ids.add(entry["id"])
            if entry.get("mode") == "live":
                if entry.get("cost_usd") is None:
                    unknown_calls.append({"id": entry["id"], "source": str(path.relative_to(paths.ROOT))})
                else:
                    known_spend += entry["cost_usd"]
    budget = loads((output / "live/budget.json").read_text())
    unknown_upper = sum(budget["reservations"].values())
    spend = {"known_api_spend_usd": known_spend, "unreconciled_calls": unknown_calls,
             "unreconciled_reserved_upper_bound_usd": unknown_upper,
             "total_api_spend_upper_bound_usd": known_spend + unknown_upper,
             "within_50_usd_ceiling": known_spend + unknown_upper <= 50,
             "compute": "local CPU; no rented GPU or cloud compute charge",
             "price_treatment": "pinned uncached list prices, not provider invoice; all failed and probe runs included"}
    if abs(known_spend-budget["spent_usd"]) > 1e-8:
        raise ValueError("ledger spend does not reconcile with shared budget state")
    write_json(output / "spend_report.json", spend)
    runs = []
    for path in sorted((output / "raw").rglob("manifest.json")):
        manifest = loads(path.read_text())
        manifest["raw_reported_claimed"] = manifest.pop("claimed", None)
        manifest["raw_path"] = str((path.parent / "cases.jsonl").relative_to(paths.ROOT))
        manifest["manifest_path"] = str(path.relative_to(paths.ROOT))
        manifest["manifest_sha256"] = sha256(path)
        runs.append(manifest)
    filenames = ["eval_report_old.json", "eval_report_new.json", "eval_report_degraded.json",
                 "paired_comparison.json", "equivalence.jsonl", "disagreement_inventory.jsonl",
                 "fresh_disagreement_inventory.jsonl", "ablation_report.json", "spend_report.json", "vendor_integrity.json"]
    write_json(output / "manifest.json", {
        "problem": "OP-02", "generated_at": datetime.now(timezone.utc).isoformat(),
        "claimed": {"decision_agreement": new_metrics["decision_agreement"]}, "runs": runs,
        "primary_old_run": args.old.name, "primary_new_run": args.new.name,
        "primary_selection": "First complete paced baseline and first full paced successor; one successor HTTP 400 remains a failure in the denominator.",
        "spend": spend, "qualification": "pending independent reviewer checks",
        "artifacts": {"results/"+name: sha256(output / name) for name in filenames}})
    table = ["# Measured migration report", "", "## Primary real-model results", "",
             "All 180 public cases were run on each configuration with fresh databases. "
             "The retiring and successor runs used the same host, eight workers and one-second shared request pacing.", "",
             "| Metric | Retiring | Successor |", "|---|---:|---:|",
             f"| Goal matches | {old_metrics['successes']}/180 | {new_metrics['successes']}/180 |",
             f"| Agreement with fixed retiring decisions | {old_metrics['decision_agreement']:.2%} | {new_metrics['decision_agreement']:.2%} |",
             f"| Official policy findings | {old_metrics['policy_violations']} | {new_metrics['policy_violations']} |",
             f"| Identity findings | {old_metrics['identity_violations']} | {new_metrics['identity_violations']} |",
             f"| Correctly resolved non-handoff cases | {old_metrics['resolved_cases']} | {new_metrics['resolved_cases']} |",
             f"| API cost, all cases | ${old_metrics['cost_usd']:.6f} | ${new_metrics['cost_usd']:.6f} |",
             f"| Cost per resolved case | ${old_metrics['cost_per_resolved_case_usd']:.6f} | ${new_metrics['cost_per_resolved_case_usd']:.6f} |",
             f"| p95 case latency | {old_metrics['latency_p95_s']:.3f}s | {new_metrics['latency_p95_s']:.3f}s |", "",
             f"Cost ratio: **{paired['candidate_cost_ratio']:.4f}×**. p95 ratio: **{paired['candidate_p95_ratio']:.4f}×**. "
             f"Fresh old/new decision agreement: **{paired['paired_decision_agreement']:.2%}**. "
             f"Fixed-reference successor agreement Wilson 95% interval: **{new_metrics['agreement_wilson_95'][0]:.2%}–{new_metrics['agreement_wilson_95'][1]:.2%}**.", "",
             "One successor case (c_0030) received a provider HTTP 400 and remains a failure. It was not removed "
             "or selectively rerun. The initial unpaced full baseline failed at the provider boundary and remains "
             "in the raw evidence as an infrastructure attempt, not the primary quality baseline.", "",
             f"The current published swap measured 56.11% agreement. Our {new_metrics['decision_agreement']:.2%} is a different run and implementation. "
             "It is not a paired significance test against their private traces. Historical injected-instruction "
             "agreement was 20%; the successor here agrees on 5/15 (33.33%) and reaches 10/15 goals in that family.", "",
             "## Family breakdown", "", "| Family | Old goals | New goals | Fixed agreement | Improved | Regressed |",
             "|---|---:|---:|---:|---:|---:|"]
    for family, bucket in paired["by_family"].items():
        current = new_metrics["by_family"][family]
        table.append(f"| {family} | {bucket['old_successes']}/{bucket['cases']} | {bucket['new_successes']}/{bucket['cases']} | "
                     f"{current['agreements']}/{current['cases']} | {bucket['improved']} | {bucket['regressed']} |")
    table += ["", "Each family has only 15 public cases. The paired details and descriptive uncertainty are in "
              "[paired_comparison.json](results/paired_comparison.json). Improved totals do not excuse the individual regressions.",
              "", "## Unchanged evaluation and degraded control", "",
              "| Configuration | Screen result | Goal matches | Agreement |", "|---|---|---:|---:|"]
    for name, report in reports.items():
        table.append(f"| {name} | {'PASS' if report['pass'] else 'FAIL'} | {report['metrics']['successes']}/180 | {report['metrics']['decision_agreement']:.2%} |")
    table += ["", "The degraded control calls the real successor model but removes business execution. "
              "The same evaluator reopens all three configurations' databases. This demonstrates a local "
              "negative control; the hiring team's undisclosed degraded model remains untested.",
              "", "## Ablation", "", "The subset contains three deterministically hashed cases from each of twelve families. "
              "Selection does not depend on outcomes. These 36-case, single-repeat comparisons are exploratory.", "",
              "| Variant | Goals | Fixed agreement | Policy findings | API cost |", "|---|---:|---:|---:|---:|"]
    for config, m in ablations.items():
        table.append(f"| {config} | {m['successes']}/{m['cases']} | {m['decision_agreement']:.2%} | {m['policy_violations']} | ${m['cost_usd']:.6f} |")
    table += ["", "Removing the added guidance and removing the guard package each scored 32/36 goals, versus 30/36 "
              "for the full candidate. This does not establish a live goal-success benefit for those additions. "
              "The guard's targeted safety properties are established separately by deterministic tests. The "
              "36-case subset did not expose policy findings in either removal variant. Repeated full-set "
              "comparisons would be needed to choose confidently between these variants.", "",
              "## Disagreements and judgment", "",
              f"There are {len(inventory)} fixed-reference disagreements and {len(live_inventory)} fresh old/new differences. "
              "Every fixed disagreement is included in [DISAGREEMENTS.md](DISAGREEMENTS.md) with raw old/new decisions, "
              "goal failures, guard events and a judgment grounded in the fresh database outcomes.", "",
              "These are observed-difference categories, not automatic proof of psychological model causes. "
              "The old fixed decision lacks its original database and transcript, so its full correctness remains "
              "unobservable; fresh retiring evidence is explicitly identified as a different run.", "",
              "## Spend and qualification limits", "",
              f"Known API spend across all preserved experiments: **${known_spend:.6f}**. Three unreconciled early "
              f"requests retain a maximum reservation of **${unknown_upper:.7f}**. Total bounded spend: "
              f"**≤ ${known_spend+unknown_upper:.6f}**, below $50. The ledger reconciles with the shared accounting state.", "",
              "The observed public agreement, cost ratio, latency ratio, policy comparison and local eval sensitivity "
              "support the corresponding development claims. **Do not claim final qualification or unrestricted rollout:** "
              "the 60 hidden cases, independently operated gateway, controlled reviewer timing and private degraded "
              "configuration remain unavailable. Identity-challenge and injected-instruction weaknesses need human routing "
              "and more targeted evaluation. See [MEMO.md](MEMO.md)."]
    (paths.ROOT / "MIGRATION_REPORT.md").write_text("\n".join(table) + "\n")
    sections = ["# Complete disagreement inventory", "", "Generated from preserved real API runs and reopened database evidence. "
                "The fixed reference and the fresh retiring run are distinct. Judgment below is about the observed "
                "fresh outcomes under the published goal and the three official policy checks.", ""]
    for cause in sorted({r["cause"] for r in inventory}):
        subset = [r for r in inventory if r["cause"] == cause]
        sections += [f"## {cause} ({len(subset)})", ""]
        for row in subset:
            sections += [f"### {row['id']} — {row['family']}", "", row["judgment_on_fresh_runs"], "",
                         "Customer request: " + row["customer_message"], "",
                         "```json", json.dumps({key:row[key] for key in (
                             "fixed_old", "fresh_old", "new", "old_goal_match", "new_goal_match", "old_goal_failures",
                             "new_goal_failures", "old_policy_findings", "new_policy_findings", "guard_events", "new_runtime_error")}, indent=2),
                         "```", "", f"Database evidence: [{row['id']} old]({row['old_evidence']}) · [{row['id']} new]({row['new_evidence']}).", ""]
    (paths.ROOT / "DISAGREEMENTS.md").write_text("\n".join(sections) + "\n")
    print(json.dumps({"primary_metrics": new_metrics, "paired": paired,
                      "known_spend_usd": known_spend, "spend_upper_bound_usd": known_spend+unknown_upper,
                      "artifacts": filenames}, indent=2))


if __name__ == "__main__":
    main()
