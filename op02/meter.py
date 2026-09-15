"""Candidate-side accounting, never a substitute for the reviewer gateway ledger."""
import copy
import fcntl
import json
import os
import time
import uuid
import random
from contextlib import contextmanager
from pathlib import Path

from .io import append_jsonl, loads, write_json
from .transport import ProviderError

PRICES = {"gpt-4.1-mini-2025-04-14": (.40, 1.60),
          "gpt-5-mini-2025-08-07": (.25, 2.00)}


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    """Reserve before each call across local processes; uncertainty stops spending.

    Keep this shared state between experiments. Deleting it loses the accounting
    boundary. Each reservation includes a conservative input estimate and the full
    output cap. A failed/unknown call retains its reservation and blocks more calls
    until an operator reconciles it with gateway usage.
    """
    def __init__(self, path, cap=50.0):
        if not 0 < cap <= 50:
            raise ValueError("API budget must be greater than zero and at most $50")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cap = cap

    @contextmanager
    def state(self):
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = loads(self.path.read_text()) if self.path.exists() else {"spent_usd": 0.0, "reservations": {}, "uncertain": False}
            try:
                yield state
            finally:
                write_json(self.path, state)
                fcntl.flock(lock, fcntl.LOCK_UN)

    def reserve(self, call_id, amount):
        with self.state() as state:
            if state["uncertain"]:
                raise BudgetExceeded("unreconciled provider usage; inspect ledger before more calls")
            if state["spent_usd"] + sum(state["reservations"].values()) + amount > self.cap:
                raise BudgetExceeded("shared API spend ceiling reached")
            state["reservations"][call_id] = amount

    def quarantine_unknown(self):
        """Retain the full reserved upper bounds; do not invent missing actual usage."""
        with self.state() as state:
            if state["uncertain"]:
                state.setdefault("quarantines", []).append({
                    "timestamp": time.time(), "reservations": dict(state["reservations"]),
                    "reason": "Unknown actual spend; maximum reserved cost remains encumbered against cap."})
                state["uncertain"] = False

    def pace(self):
        interval = float(os.getenv("OP02_CALL_INTERVAL", "1.0"))
        with self.state() as state:
            now = time.time()
            slot = max(now, state.get("next_request_at", now))
            state["next_request_at"] = slot + interval
        time.sleep(max(0, slot-time.time()))

    def settle(self, call_id, cost):
        with self.state() as state:
            if cost is None:
                state["uncertain"] = True
            else:
                reserved = state["reservations"].pop(call_id)
                state["spent_usd"] += cost
                if cost > reserved or state["spent_usd"] > self.cap:
                    state["uncertain"] = True
                    raise BudgetExceeded("actual usage exceeded reservation; further calls blocked")


class Meter:
    def __init__(self, complete, directory, model, mode, budget=None):
        self.complete = complete
        self.directory = Path(directory)
        self.model = model
        self.mode = mode
        self.budget = budget
        self.case_id = None
        self.calls = []
        self.failed = False
        self.unknown_usage = False

    def start_case(self, case_id):
        self.case_id = case_id
        self.calls = []
        self.failed = False
        self.unknown_usage = False

    def __call__(self, messages, *, max_tokens=800, tools=None):
        for attempt in range(4):
            try:
                return self._attempt(messages, max_tokens=max_tokens, tools=tools)
            except ProviderError as exc:
                if not exc.retryable or attempt == 3:
                    self.failed = True
                    raise
                # Every rejected attempt is already in the ledger with its status.
                time.sleep(min(30, 5 * 2**attempt) + random.uniform(0, .5))

    def _attempt(self, messages, *, max_tokens=800, tools=None):
        call_id = uuid.uuid4().hex
        raw = {"id": call_id, "case_id": self.case_id, "mode": self.mode,
               "requested_model": self.model, "messages": copy.deepcopy(messages),
               "max_completion_tokens": max_tokens, "started_unix": time.time()}
        # Persist the attempted call even if the process dies during the request.
        append_jsonl(self.directory / "requests.jsonl", raw)
        started = time.monotonic()
        response = None
        cost = 0.0 if self.mode == "offline" else None
        error = None
        provider_error = None
        reserved = False
        sent = False
        try:
            if self.mode == "live":
                in_rate, out_rate = PRICES[self.model]
                maximum_input = len(json.dumps(messages, ensure_ascii=False).encode()) + 4096
                self.budget.reserve(call_id, (maximum_input*in_rate + max_tokens*out_rate)/1e6)
                reserved = True
                self.budget.pace()
            sent = True
            response = self.complete(messages, max_tokens=max_tokens, tools=tools)
            if self.mode == "live":
                usage = response.get("usage", {})
                counts = [usage.get(key) for key in ("input_tokens", "output_tokens", "total_tokens")]
                if any(type(value) is not int or value < 0 for value in counts) or counts[0] <= 0 or counts[2] != sum(counts[:2]):
                    raise ValueError("missing or inconsistent provider usage")
                if response.get("model") != self.model:
                    raise ValueError("provider did not confirm the exact pinned snapshot")
                cost = (counts[0]*in_rate + counts[1]*out_rate)/1e6
            return response
        except Exception as exc:
            self.failed |= not (isinstance(exc, ProviderError) and exc.retryable)
            # Provider exception bodies can contain URLs or authentication details.
            error = type(exc).__name__
            if isinstance(exc, ProviderError):
                provider_error = {"status": exc.status, "code": exc.code, "headers": exc.metadata}
                if exc.rejected:
                    cost = 0.0
            if not sent:
                cost = 0.0
            raise
        finally:
            entry = {"id": call_id, "case_id": self.case_id, "mode": self.mode,
                     "model": self.model if self.mode == "live" else "offline-starter-fake",
                     "seconds": time.monotonic()-started, "cost_usd": cost,
                     "usage": response.get("usage") if response and self.mode == "live" else None,
                     "error": error, "sent": sent,
                     "provider_error": provider_error,
                     "provider_metadata": response.get("provider_metadata") if response else None,
                     "provenance": "candidate_observed_not_independent_gateway"}
            self.calls.append(entry)
            self.unknown_usage |= cost is None
            append_jsonl(self.directory / "ledger.jsonl", entry)
            append_jsonl(self.directory / "responses.jsonl", {
                "id": call_id, "case_id": self.case_id, "response": response, "error": error})
            if reserved:
                self.budget.settle(call_id, cost)

    def finish_case(self):
        if not self.calls:
            append_jsonl(self.directory / "ledger.jsonl", {
                "id": uuid.uuid4().hex, "case_id": self.case_id, "mode": self.mode,
                "model": None, "seconds": 0.0, "cost_usd": 0.0, "usage": None,
                "sent": False, "no_call": True, "provenance": "candidate_observed_not_independent_gateway"})
        return None if self.unknown_usage else sum(row["cost_usd"] for row in self.calls)
