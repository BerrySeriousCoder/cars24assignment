"""Paired reports with family regressions and no unsupported qualification claims."""
import argparse
import math
from pathlib import Path
from .io import read_rows, loads, write_json
from .metrics import decisions_equal, percentile95


def compare(old, new):
    old_map, new_map = ({r["id"]: r for r in rows} for rows in (old, new))
    if len(old_map) != len(old) or len(new_map) != len(new) or old_map.keys() != new_map.keys() or not old:
        raise ValueError("paired comparison needs identical nonempty unique case IDs")
    n = len(old)
    by_family = {}
    for cid, before in old_map.items():
        after = new_map[cid]
        a = int(before["goal"]["goal_state_match"] and not before.get("error"))
        b = int(after["goal"]["goal_state_match"] and not after.get("error"))
        bucket = by_family.setdefault(before["family"], {"cases": 0, "old_successes": 0,
            "new_successes": 0, "improved": 0, "regressed": 0, "new_identity_cases": []})
        bucket["cases"] += 1
        bucket["old_successes"] += a
        bucket["new_successes"] += b
        bucket["improved"] += int(b > a)
        bucket["regressed"] += int(a > b)
        before_identity = any(v["rule"] == "identity_before_money" for v in before["policy_violations"])
        after_identity = any(v["rule"] == "identity_before_money" for v in after["policy_violations"])
        if after_identity and not before_identity:
            bucket["new_identity_cases"].append(cid)
    for bucket in by_family.values():
        count = bucket["cases"]
        delta = (bucket["new_successes"]-bucket["old_successes"])/count
        # Paired differences are -1, 0, +1. Use the observed paired variance.
        variance = max(0, (bucket["improved"]+bucket["regressed"]-count*delta*delta)/(count-1)) if count > 1 else None
        se = math.sqrt(variance/count) if variance is not None else None
        bucket.update(success_delta=delta, paired_standard_error=se,
                      approximate_delta_95=[max(-1, delta-1.96*se), min(1, delta+1.96*se)] if se else None,
                      review_required=bucket["regressed"] > 0,
                      uncertainty_note="normal paired interval is descriptive; small slices need more repeats; zero observed variance has no reported confidence interval")
    old_violations = sum(len(r["policy_violations"]) for r in old)
    new_violations = sum(len(r["policy_violations"]) for r in new)
    live = all(r["mode"] == "live" for r in old+new)
    cost_known = live and all(r["cost_usd"] is not None for r in old+new)
    def resolved(rows):
        return sum(r["goal"]["goal_state_match"] and not r.get("error") and not r["decision"]["escalated"] for r in rows)
    old_cost = sum(r["cost_usd"] for r in old)/resolved(old) if cost_known and resolved(old) else None
    new_cost = sum(r["cost_usd"] for r in new)/resolved(new) if cost_known and resolved(new) else None
    old_p95 = percentile95([r["seconds"] for r in old]) if live else None
    new_p95 = percentile95([r["seconds"] for r in new]) if live else None
    new_identity = [cid for b in by_family.values() for cid in b["new_identity_cases"]]
    return {"cases": n, "paired_decision_agreement": sum(
                decisions_equal(old_map[cid]["decision"], new_map[cid]["decision"]) for cid in old_map)/n,
            "policy_nonincrease": new_violations <= old_violations,
            "old_policy_violations": old_violations, "new_policy_violations": new_violations,
            "new_identity_cases": new_identity, "identity_gate": not new_identity,
            "candidate_cost_ratio": new_cost/old_cost if old_cost and new_cost is not None else None,
            "candidate_p95_ratio": new_p95/old_p95 if old_p95 and new_p95 is not None else None,
            "by_family": by_family, "ship": False, "qualification": "pending",
            "pending": ["private cases", "independent gateway accounting", "paired evaluator hardware/load",
                        "reviewer degraded configuration", "human disagreement review"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(read_rows(args.old), read_rows(args.new))
    write_json(args.output, report)
    print(f"Paired report written to {args.output}; qualification pending")


if __name__ == "__main__":
    main()
