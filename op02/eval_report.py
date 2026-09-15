"""Unchanged evaluator entrypoint for retiring, migrated and replacement agents."""
import argparse
from pathlib import Path
from .io import read_rows, loads, write_json
from .metrics import evaluate, score_database, aggregate
from . import paths
import sqlite3


def recompute(directory, cases_path=paths.CASES, reference_path=paths.RETIRING):
    directory = Path(directory).resolve()
    rows = read_rows(directory / "cases.jsonl")
    cases = read_rows(cases_path, "case_id")
    cases_by_id = {c["case_id"]: c for c in cases}
    observed = []
    for row in rows:
        if row["id"] not in cases_by_id:
            raise ValueError("unexpected case in raw evidence")
        database = directory / row["database"]
        if database.is_symlink() or not database.resolve().is_relative_to(directory) or not database.is_file():
            raise ValueError("database artifact is missing or escapes run directory")
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
            # Raw success flags and decisions are NOT trusted on reread.
            observed.append({**row, **score_database(conn, cases_by_id[row["id"]])})
    reference = [row for row in read_rows(reference_path) if row["id"] in cases_by_id]
    metrics, _ = aggregate(cases, observed, reference)
    return {**evaluate(metrics), "metrics": metrics,
            "recomputed_from": "freshly reopened read-only database snapshots"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=paths.CASES)
    parser.add_argument("--reference", type=Path, default=paths.RETIRING)
    args = parser.parse_args()
    report = recompute(args.run, args.cases, args.reference)
    write_json(args.run / "eval_report.json", report)
    print("Development regression screen: " + ("PASS" if report["pass"] else "FAIL"))
    print("Qualification remains pending independent live and held-out evidence.")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
