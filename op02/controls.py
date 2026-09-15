"""Explicit local mutants. They are never presented as successor models."""
from . import paths
from harbour import llm
from .agent import parse_action


def commit_only(backend, case_id, customer_id, message, *, loan_id=None):
    return backend.commit(case_id, "Request completed.", [])


def escalate_everything(backend, case_id, customer_id, message, *, loan_id=None):
    backend.escalate(case_id, "All work goes to a human.")
    return backend.commit(case_id, "Escalated.", ["escalate"])


def model_commit_only(backend, case_id, customer_id, message, *, loan_id=None):
    """Real-model negative control: remove business execution, retain model-generated closure."""
    reply = llm.complete([
        {"role": "system", "content":
         'Return a JSON object with tool="commit" and args containing a brief nonempty summary '
         'and actions_taken=[]. Only acknowledge receipt of this customer request; no servicing '
         'actions have been performed. No markdown or extra text.'},
        {"role": "user", "content": message},
    ], max_tokens=800)
    tool, args = parse_action(reply.get("content", ""))
    if tool != "commit":
        raise ValueError("degraded closure did not return commit")
    return backend.commit(case_id, args["summary"], [])
