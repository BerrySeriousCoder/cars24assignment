"""One fresh database per case, allowlisted agent input, immutable run directories."""
import argparse
import importlib
import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ProcessPoolExecutor

from . import paths
from .io import append_jsonl, read_rows, sha256, write_json, loads
from .meter import Budget, Meter, PRICES
from .environment import load_environment
from .transport import live_completion
from .metrics import aggregate, evaluate, score_database
from harbour import llm
from harbour.backend import Backend
from harbour.seed_data import load_seed


def source_hashes():
    files = list((paths.ROOT / "op02").glob("*.py")) + list((paths.ROOT / "configs").glob("*.json"))
    files += [path for path in paths.VENDOR.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    return {str(path.relative_to(paths.ROOT)): sha256(path) for path in sorted(files)}


def resolve_agent(spec):
    module, function = spec.split(":", 1)
    return getattr(importlib.import_module(module), function)


def execute_case(payload):
    case, number, output, model, mode, agent_spec, config_name, budget_path, budget_cap = payload
    output = Path(output)
    function = resolve_agent(agent_spec)
    budget = Budget(budget_path, budget_cap) if mode == "live" else None
    meter = Meter(llm.complete, output, model, mode, budget)
    meter.start_case(case["case_id"])
    db_path = output / "databases" / f"{number:04d}.sqlite"
    db_path.parent.mkdir(exist_ok=True)
    backend = Backend(str(db_path))
    try:
        load_seed(backend.conn, paths.SEED)
        started = time.monotonic()
        error, result = None, None
        try:
            with patch.object(llm, "complete", meter), patch.object(llm, "_live_completion", live_completion):
                result = function(backend, case_id=case["case_id"], customer_id=case["customer_id"],
                                  loan_id=case.get("loan_id"), message=case["message"])
        except Exception as exc:
            error = type(exc).__name__
        elapsed = time.monotonic()-started
        evidence = score_database(backend.conn, case)
        cost = meter.finish_case()
        if meter.failed:
            error = error or "model_call_failed"
        row = {"id": case["case_id"], "family": case["family"], "mode": mode,
               "config": config_name, "model": model if mode == "live" else "offline-starter-fake",
               "seconds": elapsed, "cost_usd": cost, "error": error, "agent_result": result,
               "database": str(db_path.relative_to(output)), **evidence}
        # Preserve completed cases even if the parent is interrupted while other cases run.
        append_jsonl(output / "cases.jsonl", row)
        return row
    finally:
        backend.close()


def run(args):
    if args.mode == "live":
        load_environment()
    config = loads((paths.ROOT / "configs" / (args.config + ".json")).read_text())
    cases = read_rows(args.cases, "case_id")
    refs = read_rows(args.reference)
    if args.limit:
        cases = cases[:args.limit]
    ids = {case["case_id"] for case in cases}
    refs = [row for row in refs if row["id"] in ids]
    if {row["id"] for row in refs} != ids:
        raise ValueError("every selected case needs a retiring decision")
    if args.mode == "live" and os.getenv("LLM_FAKE") == "1":
        raise ValueError("LLM_FAKE=1 is forbidden in live mode")
    model = os.getenv("LLM_MODEL") or config["model"]
    if args.mode == "live" and model not in PRICES:
        raise ValueError("model must have an exact approved pin and price")
    if args.mode == "live" and not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_BASE_URL")):
        raise ValueError("configure LLM_API_KEY and/or an authenticated LLM_BASE_URL before live runs")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    agent_spec = args.agent or os.getenv("HARBOUR_AGENT") or config["agent"]
    resolve_agent(agent_spec)
    manifest = {"run_id": output.name, "started_at": datetime.now(timezone.utc).isoformat(),
                "seed": 20260915, "model": model if args.mode == "live" else "offline-starter-fake",
                "configured_model": model, "mode": args.mode, "config": config,
                "agent": args.agent or os.getenv("HARBOUR_AGENT") or config["agent"],
                "input_sha256": sha256(args.cases), "reference_sha256": sha256(args.reference),
                "source_sha256": source_hashes(), "cases": len(cases), "case_ids": sorted(ids),
                "hardware": platform.platform(), "python": platform.python_version(), "concurrency": args.concurrency,
                "status": "running", "raw_path": "cases.jsonl", "transport": "observable_chat_completions",
                "call_interval_s": float(os.getenv("OP02_CALL_INTERVAL", "1.0")),
                "price_source": "vendor/MODELS.md (frozen Season 1 rates)",
                "qualification": "pending", "claimed": {"decision_agreement": None}}
    write_json(output / "manifest.json", manifest)
    environment = {"LLM_MODEL": model, "LLM_FAKE": "1" if args.mode == "offline" else "0",
                   "LLM_MAX_RETRIES": "1", "LLM_TIMEOUT": os.getenv("LLM_TIMEOUT", "30"),
                   "OP02_VARIANT": config["variant"], "HARBOUR_TRACE_FILE": str(output / "traces.jsonl")}
    if not os.getenv("LLM_API_KEY") and os.getenv("OPENAI_API_KEY"):
        environment["LLM_API_KEY"] = os.environ["OPENAI_API_KEY"]
    results = []
    try:
        with patch.dict(os.environ, environment), ProcessPoolExecutor(max_workers=args.concurrency) as executor:
            payloads = [(case, number, str(output), model, args.mode, agent_spec, args.config,
                         str(args.budget_state), args.budget) for number, case in enumerate(cases, 1)]
            for number, row in enumerate(executor.map(execute_case, payloads), 1):
                results.append(row)
                if number % 15 == 0 or number == len(cases):
                    print(f"{args.config}/{args.mode}: {number}/{len(cases)} cases", flush=True)
        metrics, inventory = aggregate(cases, results, refs)
        write_json(output / "metrics.json", metrics)
        write_json(output / "eval_report.json", evaluate(metrics))
        ref_map = {r["id"]: r["decision"] for r in refs}
        for row in results:
            append_jsonl(output / "equivalence.jsonl", {"id": row["id"], "old": ref_map[row["id"]], "new": row["decision"]})
        for row in inventory:
            append_jsonl(output / "disagreements.jsonl", row)
        write_json(output / "policy_report.json", {
            "violations": metrics["policy_violations"], "by_rule": metrics["policy_by_rule"],
            "identity_violations": metrics["identity_violations"],
            "scope": ["identity_before_money", "statement_after_contact_change", "money_without_commit"],
            "detail": [v for r in results for v in r["policy_violations"]]})
        manifest.update(status="completed_with_errors" if any(r["error"] for r in results) else "completed",
                        finished_at=datetime.now(timezone.utc).isoformat(),
                        measured_api_spend_usd=0 if args.mode == "offline" else metrics["cost_usd"],
                        claimed={"decision_agreement": metrics["decision_agreement"] if args.mode == "live" else None})
        write_json(output / "manifest.json", manifest)
        print(json.dumps({"results": str(output), "successes": metrics["successes"],
                          "agreement": metrics["decision_agreement"], "policy_violations": metrics["policy_violations"],
                          "development_screen_pass": evaluate(metrics)["pass"], "mode": args.mode}, indent=2))
        return 0
    except BaseException as exc:
        manifest.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                        error=type(exc).__name__, completed_cases=len(results))
        write_json(output / "manifest.json", manifest)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", choices=[p.stem for p in (paths.ROOT / "configs").glob("*.json")], default="new")
    parser.add_argument("--mode", choices=["offline", "live"], required=True)
    parser.add_argument("--cases", type=Path, default=paths.CASES)
    parser.add_argument("--reference", type=Path, default=paths.RETIRING)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agent", help="Reviewer replacement callable module:function; same input contract")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--budget", type=float, default=50)
    parser.add_argument("--budget-state", type=Path, default=paths.ROOT / "results/live/budget.json")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")
    if not 1 <= args.concurrency <= 8:
        parser.error("concurrency must be between 1 and 8")
    try:
        return run(args)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
