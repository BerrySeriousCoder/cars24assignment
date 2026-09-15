import sqlite3
import tempfile
import unittest
from pathlib import Path

from op02 import paths
from op02.io import loads, read_rows
from op02.metrics import aggregate, decisions_equal, decision_from_audit, evaluate, score_database, wilson
from harbour.backend import Backend
from harbour.seed_data import load_seed


def decision(tools=None, escalated=False, committed=True):
    return {"tools": tools or [], "escalated": escalated, "committed": committed}


class MetricsTests(unittest.TestCase):
    def test_numeric_arguments_not_boolean(self):
        a = decision([{"name": "schedule_payment", "args": {"amount": 100}}])
        b = decision([{"name": "schedule_payment", "args": {"amount": 100.0}}])
        self.assertTrue(decisions_equal(a, b))
        b["tools"][0]["args"]["amount"] = True
        a["tools"][0]["args"]["amount"] = 1
        self.assertFalse(decisions_equal(a, b))

    def test_missing_decisions_never_agree(self):
        for value in (None, {}, {"tools": []}):
            self.assertFalse(decisions_equal(value, value))
        self.assertTrue(decisions_equal(decision(), decision()))

    def test_order_arguments_and_commit_matter(self):
        a = decision([{"name": "request_document", "args": {"kind": "id_proof"}},
                      {"name": "request_document", "args": {"kind": "income_proof"}}])
        self.assertFalse(decisions_equal(a, decision(list(reversed(a["tools"])))))
        self.assertFalse(decisions_equal(decision(), decision(committed=False)))
        self.assertFalse(decisions_equal(decision(), decision(escalated=True)))

    def test_failed_and_false_tools_not_decisions(self):
        rows = [{"tool": "waive_fee", "ok": 0, "args_json": "{}", "result_json": "null"},
                {"tool": "cancel_autopay", "ok": 1, "args_json": "{}", "result_json": "false"},
                {"tool": "verify_identity", "ok": 1, "args_json": "{}", "result_json": "true"},
                {"tool": "commit", "ok": 1, "args_json": "{}", "result_json": "{}"}]
        self.assertEqual(decision_from_audit(rows), decision())

    def test_ambiguous_json_rejected(self):
        for value in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}'):
            with self.assertRaises(ValueError):
                loads(value)

    def test_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_text('{"id":"x"}\n{"id":"x"}\n')
            with self.assertRaises(ValueError):
                read_rows(path)

    def test_missing_cases_stay_in_denominator(self):
        cases = [{"case_id": str(i), "family": "f"} for i in range(2)]
        refs = [{"id": str(i), "decision": decision()} for i in range(2)]
        rows = [{"id": "0", "decision": decision(), "goal": {"goal_state_match": True}}]
        metrics, inventory = aggregate(cases, rows, refs)
        self.assertEqual(metrics["decision_agreement"], .5)
        self.assertEqual(metrics["success_rate"], .5)
        self.assertFalse(evaluate(metrics)["pass"])
        self.assertEqual(inventory[0]["cause"], "missing_or_failed_run")

    def test_offline_cost_and_latency_are_not_claims(self):
        metrics, _ = aggregate([{"case_id": "x", "family": "f"}],
            [{"id": "x", "decision": decision(), "goal": {"goal_state_match": True},
              "mode": "offline", "cost_usd": 0, "seconds": .01}],
            [{"id": "x", "decision": decision()}])
        self.assertIsNone(metrics["cost_per_resolved_case_usd"])
        self.assertIsNone(metrics["latency_p95_s"])

    def test_real_backend_exposes_identity_defect(self):
        backend = Backend()
        self.addCleanup(backend.close)
        load_seed(backend.conn, paths.SEED)
        loan = backend.conn.execute("SELECT loan_id FROM loans WHERE autopay=1 LIMIT 1").fetchone()[0]
        backend.cancel_autopay("probe", loan)
        backend.commit("probe", "Cancelled", ["cancel_autopay"])
        result = score_database(backend.conn, {"case_id": "probe", "goal_state": {"audit_must_include": ["commit"]}})
        self.assertTrue(result["goal"]["goal_state_match"])
        self.assertEqual(result["policy_violations"][0]["rule"], "identity_before_money")

    def test_zero_findings_not_zero_uncertainty(self):
        self.assertGreater(wilson(0, 15)[1], .2)


if __name__ == "__main__":
    unittest.main()
