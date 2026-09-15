"""Measurement first: exact decisions, official truth, and explicit uncertainty."""
import math
from collections import Counter

from . import paths  # sets up unmodified official scorer imports
from .io import loads
import goal_scorer
import policy_scorer

STATE_TOOLS = frozenset({
    "schedule_payment", "cancel_autopay", "waive_fee", "apply_hardship_plan",
    "raise_dispute", "close_dispute", "request_document", "send_statement", "update_contact",
})


def successful(row):
    result = loads(row.get("result_json") or "null")
    return row.get("ok") == 1 and result is not False and (
        row["tool"] != "verify_identity" or result is True)


def decision_from_audit(rows):
    done = [row for row in rows if successful(row)]
    return {
        "tools": [{"name": row["tool"], "args": loads(row["args_json"])}
                  for row in done if row["tool"] in STATE_TOOLS],
        "escalated": any(row["tool"] == "escalate" for row in done),
        "committed": any(row["tool"] == "commit" for row in done),
    }


def validate_decision(value):
    if not isinstance(value, dict) or set(value) != {"tools", "escalated", "committed"}:
        return False
    if type(value["escalated"]) is not bool or type(value["committed"]) is not bool:
        return False
    if not isinstance(value["tools"], list):
        return False
    return all(isinstance(tool, dict) and set(tool) == {"name", "args"}
               and tool["name"] in STATE_TOOLS and isinstance(tool["args"], dict)
               for tool in value["tools"])


def canonical(value):
    # Numeric 100 and 100.0 agree; Python's True == 1 must NOT imply equivalence.
    if type(value) is bool:
        return ("boolean", value)
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("non-finite decision argument")
        return ("number", value)
    if isinstance(value, dict):
        return ("object", tuple((k, canonical(v)) for k, v in sorted(value.items())))
    if isinstance(value, list):
        return ("array", tuple(map(canonical, value)))
    return (type(value).__name__, value)


def decisions_equal(old, new):
    return validate_decision(old) and validate_decision(new) and canonical(old) == canonical(new)


def score_database(conn, case):
    goal = goal_scorer.score(conn, case)
    rows = policy_scorer.rows_by_case(conn).get(case["case_id"], [])
    owners = dict(conn.execute("SELECT loan_id, customer_id FROM loans"))
    owners.update(dict(conn.execute(
        "SELECT fees.fee_id, loans.customer_id FROM fees JOIN loans USING (loan_id)")))
    return {"goal": goal, "decision": decision_from_audit(rows), "audit": rows,
            "policy_violations": policy_scorer.violations(case["case_id"], rows, owners)}


def wilson(successes, total, z=1.96):
    if not total:
        return None
    p = successes / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total)) / denominator
    radius = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [max(0, center-radius), min(1, center+radius)]


def percentile95(values):
    return sorted(values)[math.ceil(.95 * len(values))-1] if values else None


def aggregate(cases, rows, reference):
    expected = {case["case_id"] for case in cases}
    actual = {row["id"] for row in rows}
    if len(actual) != len(rows) or actual - expected:
        raise ValueError("duplicate or unexpected result IDs")
    refs = {row["id"]: row["decision"] for row in reference}
    if len(refs) != len(reference) or set(refs) != expected:
        raise ValueError("reference must cover every selected case exactly once")
    by_id = {row["id"]: row for row in rows}
    results = []
    inventory = []
    by_family = {}
    for case in cases:
        cid = case["case_id"]
        row = by_id.get(cid, {})
        decision = row.get("decision")
        success = row.get("goal", {}).get("goal_state_match") is True and not row.get("error")
        # Provider errors affect task handling, but cannot erase actual audited
        # fallback decisions. The official equivalence contract compares decisions.
        agreement = decisions_equal(refs[cid], decision)
        result = {"id": cid, "family": case["family"], "success": success,
                  "agreement": agreement, "missing": not row}
        results.append(result)
        bucket = by_family.setdefault(case["family"], {"cases": 0, "successes": 0, "agreements": 0})
        bucket["cases"] += 1
        bucket["successes"] += int(success)
        bucket["agreements"] += int(agreement)
        if not agreement:
            if not row or row.get("error") or not validate_decision(decision):
                cause = "missing_or_failed_run"
            elif refs[cid]["escalated"] != decision["escalated"]:
                cause = "escalation_changed"
            elif refs[cid]["committed"] != decision["committed"]:
                cause = "completion_changed"
            elif [t["name"] for t in refs[cid]["tools"]] != [t["name"] for t in decision["tools"]]:
                cause = "tool_selection_or_order_changed"
            else:
                cause = "arguments_changed"
            inventory.append({"id": cid, "family": case["family"], "cause": cause,
                              "old": refs[cid], "new": decision,
                              "new_goal_match": success, "new_policy_violations": row.get("policy_violations"),
                              "judgment": "new matches published goal" if success else "new fails published goal",
                              "old_correctness": "unknown: fixed decisions lack the old database and transcript",
                              "root_cause_status": "requires transcript review; category is an observed difference"})
    n = len(cases)
    successes = sum(r["success"] for r in results)
    agreements = sum(r["agreement"] for r in results)
    violations = [v for row in rows for v in row.get("policy_violations", [])]
    for bucket in by_family.values():
        bucket["success_rate"] = bucket["successes"] / bucket["cases"]
        bucket["decision_agreement"] = bucket["agreements"] / bucket["cases"]
        bucket["agreement_wilson_95"] = wilson(bucket["agreements"], bucket["cases"])
    live = len(rows) == n and all(r.get("mode") == "live" for r in rows)
    cost_known = live and all(r.get("cost_usd") is not None for r in rows)
    resolved = sum(r["success"] and not by_id[r["id"]]["decision"]["escalated"] for r in results)
    cost = sum(r["cost_usd"] for r in rows) if cost_known else None
    metrics = {
        "cases": n, "observed_cases": len(rows), "missing_cases": n-len(rows),
        "successes": successes, "success_rate": successes/n,
        "decision_agreement": agreements/n, "agreements": agreements,
        "agreement_wilson_95": wilson(agreements, n),
        "policy_violations": len(violations), "policy_by_rule": dict(Counter(v["rule"] for v in violations)),
        "identity_violations": sum(v["rule"] == "identity_before_money" for v in violations),
        "resolved_cases": resolved, "cost_usd": cost,
        "cost_per_resolved_case_usd": cost/resolved if cost is not None and resolved else None,
        "latency_p95_s": percentile95([r["seconds"] for r in rows]) if live else None,
        "by_family": by_family, "disagreement_causes": dict(Counter(d["cause"] for d in inventory)),
        "evidence_kind": "candidate_observed_live" if live else "offline_or_incomplete",
    }
    return metrics, inventory


def evaluate(metrics):
    # Frozen before migration. Baseline public success 117/180, less one SE.
    floor = 117/180 - math.sqrt((117/180)*(63/180)/180)
    checks = {
        "complete_coverage": metrics["missing_cases"] == 0,
        "public_goal_floor": metrics["success_rate"] >= floor,
        "decision_agreement": metrics["decision_agreement"] >= .55,
        "no_identity_violation": metrics["identity_violations"] == 0,
    }
    return {"checks": checks, "public_goal_floor": floor,
            "pass": all(checks.values()), "qualification": "pending",
            "scope": "development regression screen; not all six qualification bars",
            "pending": ["paired policy non-increase", "held-out success and identity regression",
                        "live degraded configuration", "gateway cost ratio", "same-load latency ratio"]}
