import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch
from pathlib import Path
from op02.meter import Budget, BudgetExceeded, Meter
from op02.io import read_rows
from op02.transport import ProviderError

MODEL = "gpt-5-mini-2025-08-07"


class MeterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.budget = Budget(self.directory / "budget.json", 1)

    def test_shared_budget_enforces_existing_spend(self):
        self.budget.reserve("one", .7)
        self.budget.settle("one", .7)
        with self.assertRaises(BudgetExceeded):
            Budget(self.directory / "budget.json", 1).reserve("two", .4)

    def test_unknown_usage_freezes_future_calls(self):
        self.budget.reserve("one", .01)
        self.budget.settle("one", None)
        with self.assertRaises(BudgetExceeded):
            self.budget.reserve("two", .01)

    def test_exact_pinned_rates_and_raw_capture(self):
        def provider(*args, **kwargs):
            return {"content": "{}", "model": MODEL,
                    "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}}
        meter = Meter(provider, self.directory, MODEL, "live", self.budget)
        meter.start_case("x")
        meter([{"role": "user", "content": "Hello"}])
        self.assertAlmostEqual(meter.finish_case(), .000065)
        self.assertEqual(len(read_rows(self.directory / "requests.jsonl")), 1)
        self.assertEqual(len(read_rows(self.directory / "responses.jsonl")), 1)

    def test_transport_error_is_not_zero_cost(self):
        def provider(*args, **kwargs):
            raise TimeoutError("secret-looking provider body")
        meter = Meter(provider, self.directory, MODEL, "live", self.budget)
        meter.start_case("x")
        with self.assertRaises(TimeoutError):
            meter([])
        self.assertIsNone(meter.finish_case())
        self.assertEqual(read_rows(self.directory / "ledger.jsonl")[0]["error"], "TimeoutError")
        self.assertNotIn("secret-looking", (self.directory / "responses.jsonl").read_text())

    def test_missing_provider_usage_is_pending(self):
        meter = Meter(lambda *a, **k: {"model": MODEL, "usage": {}}, self.directory, MODEL, "live", self.budget)
        meter.start_case("x")
        with self.assertRaises(ValueError):
            meter([])
        self.assertIsNone(meter.finish_case())

    def test_no_call_has_explicit_zero_cost_ledger(self):
        meter = Meter(None, self.directory, MODEL, "offline")
        meter.start_case("x")
        self.assertEqual(meter.finish_case(), 0)
        self.assertTrue(read_rows(self.directory / "ledger.jsonl")[0]["no_call"])

    def test_cap_cannot_exceed_challenge_limit(self):
        with self.assertRaises(ValueError):
            Budget(self.directory / "other.json", 51)

    def test_meter_imports_in_fresh_process(self):
        result = subprocess.run([sys.executable, "-c", "from op02.meter import Budget"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rate_limit_retry_is_metered_and_not_unknown_spend(self):
        replies = iter([ProviderError(429, "rate_limit_exceeded"), {
            "content": "{}", "model": MODEL,
            "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}}])
        def provider(*args, **kwargs):
            result = next(replies)
            if isinstance(result, Exception):
                raise result
            return result
        meter = Meter(provider, self.directory, MODEL, "live", self.budget)
        meter.start_case("x")
        with patch("op02.meter.time.sleep"):
            meter([])
        self.assertFalse(meter.failed)
        self.assertEqual(len(read_rows(self.directory / "ledger.jsonl")), 2)
        self.assertAlmostEqual(meter.finish_case(), .000065)

    def test_exhausted_rate_limit_marks_case_error(self):
        def provider(*args, **kwargs):
            raise ProviderError(429, "rate_limit_exceeded")
        meter = Meter(provider, self.directory, MODEL, "live", self.budget)
        meter.start_case("x")
        with patch("op02.meter.time.sleep"), self.assertRaises(ProviderError):
            meter([])
        self.assertTrue(meter.failed)
        self.assertEqual(meter.finish_case(), 0)

    def test_quarantine_keeps_unknown_cost_encumbered(self):
        self.budget.reserve("unknown", .7)
        self.budget.settle("unknown", None)
        self.budget.quarantine_unknown()
        with self.assertRaises(BudgetExceeded):
            self.budget.reserve("next", .4)


if __name__ == "__main__":
    unittest.main()
