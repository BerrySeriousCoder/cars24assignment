import json
import tempfile
import unittest
from pathlib import Path
from op02 import paths
from op02.ablation import select
from op02.eval_report import recompute
from op02.io import read_rows
from op02.metrics import aggregate
from harbour.backend import Backend
from harbour.seed_data import load_seed


class EvalEvidenceTests(unittest.TestCase):
    def test_model_error_does_not_erase_audited_fallback_agreement(self):
        decision = {"tools": [], "escalated": True, "committed": True}
        metrics, disagreements = aggregate([{"case_id": "x", "family": "synthetic"}],
            [{"id": "x", "error": "provider_error", "decision": decision,
              "goal": {"goal_state_match": False}}], [{"id": "x", "decision": decision}])
        self.assertEqual(metrics["decision_agreement"], 1)
        self.assertEqual(metrics["success_rate"], 0)
        self.assertEqual(disagreements, [])

    def test_recomputation_rejects_fabricated_success_and_filters_reference(self):
        case = read_rows(paths.CASES, "case_id")[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = Backend(str(root / "case.sqlite"))
            load_seed(backend.conn, paths.SEED)
            backend.commit(case["case_id"], "A fabricated success claim", [])
            backend.close()
            (root / "cases.jsonl").write_text(json.dumps({
                "id": case["case_id"], "database": "case.sqlite", "mode": "offline", "seconds": 0,
                "cost_usd": 0, "goal": {"goal_state_match": True},
                "decision": {"tools": [], "escalated": False, "committed": True}}) + "\n")
            selected = root / "inputs.jsonl"
            selected.write_text(json.dumps(case) + "\n")
            report = recompute(root, selected)
            self.assertFalse(report["pass"])
            self.assertEqual(report["metrics"]["successes"], 0)

    def test_ablation_is_outcome_independent_and_order_independent(self):
        cases = read_rows(paths.CASES, "case_id")
        selected = select(cases, 3)
        self.assertEqual(len(selected), 36)
        reversed_cases = [{**case, "goal_state": {"changed": True}} for case in reversed(cases)]
        self.assertEqual([c["case_id"] for c in selected], [c["case_id"] for c in select(reversed_cases, 3)])
        self.assertEqual(len({c["family"] for c in selected}), 12)

    def test_database_escape_rejected(self):
        case = read_rows(paths.CASES, "case_id")[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cases.jsonl").write_text(json.dumps({"id": case["case_id"], "database": "../escape.sqlite"}) + "\n")
            with self.assertRaises(ValueError):
                recompute(root)
