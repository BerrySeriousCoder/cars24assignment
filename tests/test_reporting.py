import copy
import unittest
from op02.compare import compare
from op02.metrics import aggregate, evaluate
from op02.integrity import verify


def row(cid="x", success=True, escalated=False, violations=None):
    return {"id": cid, "family": "synthetic", "goal": {"goal_state_match": success},
            "decision": {"tools": [], "committed": True, "escalated": escalated},
            "mode": "live", "seconds": 2, "cost_usd": .01, "policy_violations": violations or []}


class ReportingTests(unittest.TestCase):
    def test_reference_files_match_release(self):
        self.assertGreater(verify()["checked_files"], 10)

    def test_cost_includes_escalations_but_denominator_excludes_them(self):
        before = [row("a"), row("b", escalated=True)]
        after = [row("a"), row("b")]
        report = compare(before, after)
        self.assertEqual(report["candidate_cost_ratio"], .5)

    def test_new_identity_case_fails_even_when_total_is_equal(self):
        finding = [{"rule": "identity_before_money"}]
        before = [row("a", violations=finding), row("b")]
        after = [row("a"), row("b", violations=finding)]
        report = compare(before, after)
        self.assertTrue(report["policy_nonincrease"])
        self.assertFalse(report["identity_gate"])
        self.assertEqual(report["new_identity_cases"], ["b"])

    def test_unpaired_and_duplicate_results_are_rejected(self):
        for before, after in [([row()], [row("other")]), ([row(), row()], [row()])]:
            with self.assertRaises(ValueError):
                compare(before, after)

    def test_goal_failures_and_deferrals_still_cost_money(self):
        before = [row("a"), row("b", success=False)]
        after = copy.deepcopy(before)
        after[1]["cost_usd"] = .03
        self.assertEqual(compare(before, after)["candidate_cost_ratio"], 2)

    def test_synthetic_good_screen_passes_and_degraded_screen_fails(self):
        # Explicit plumbing fixtures, not performance claims for either model.
        cases = [{"case_id": "x", "family": "synthetic"}]
        baseline = row()
        reference = [{"id": "x", "decision": baseline["decision"]}]
        good, _ = aggregate(cases, [baseline], reference)
        self.assertTrue(evaluate(good)["pass"])
        bad = row(success=False)
        degraded, _ = aggregate(cases, [bad], reference)
        self.assertFalse(evaluate(degraded)["pass"])

    def test_policy_and_task_success_are_independent(self):
        baseline = row(violations=[{"rule": "identity_before_money"}])
        metrics, _ = aggregate([{"case_id": "x", "family": "synthetic"}], [baseline],
                               [{"id": "x", "decision": baseline["decision"]}])
        self.assertEqual(metrics["success_rate"], 1)
        self.assertFalse(evaluate(metrics)["pass"])
