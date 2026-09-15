"""Predeclared, stratified ablations: sample by ID hash, never by observed outcome."""
import argparse
import hashlib
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from . import paths
from .io import read_rows, append_jsonl, write_json, sha256


def select(cases, per_family):
    families = defaultdict(list)
    for case in cases:
        families[case["family"]].append(case)
    chosen = []
    for family in sorted(families):
        candidates = sorted(families[family], key=lambda row: hashlib.sha256(
            ("op02-ablation-v1:" + row["case_id"]).encode()).hexdigest())
        chosen.extend(candidates[:per_family])
    return sorted(chosen, key=lambda row: row["case_id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-family", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.per_family <= 15:
        parser.error("per-family must be between 1 and 15")
    args.output.mkdir(parents=True, exist_ok=False)
    cases_path = args.output / "cases.jsonl"
    selected = select(read_rows(paths.CASES, "case_id"), args.per_family)
    for row in selected:
        append_jsonl(cases_path, row)
    write_json(args.output / "selection.json", {
        "method": "first K per family sorted by SHA256(op02-ablation-v1:case_id)",
        "per_family": args.per_family, "cases": len(selected), "source_sha256": sha256(paths.CASES),
        "selection_sha256": sha256(cases_path), "case_ids": [r["case_id"] for r in selected],
        "outcomes_used_for_selection": False,
        "scope": "public development ablation; small slices, one repetition; not held-out qualification"})
    # The full candidate is repeated on the same subset to avoid mixing workloads.
    for config in ("swap", "new", "no_prompt", "no_guard"):
        command = [sys.executable, "-m", "op02.runner", "--config", config, "--mode", "live",
                   "--cases", str(cases_path), "--concurrency", "8", "--output", str(args.output / config)]
        result = subprocess.run(command)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
