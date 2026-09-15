"""Observable Chat Completions adapter; no silent redirects or hidden retries."""
import json
import os
import urllib.error
import urllib.request
from . import paths
from harbour import llm


class ProviderError(llm.LLMError):
    def __init__(self, status, code=None, metadata=None):
        self.status = status
        self.code = code
        self.metadata = metadata or {}
        self.rejected = status in {400, 401, 403, 404, 413, 422, 429}
        self.retryable = status == 429 and code != "insufficient_quota"
        super().__init__(f"provider HTTP {status}; code={code or 'unspecified'}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def metadata(headers):
    allowed = {"x-request-id", "retry-after", "x-ratelimit-limit-requests", "x-ratelimit-limit-tokens",
               "x-ratelimit-remaining-requests", "x-ratelimit-remaining-tokens",
               "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"}
    return {key.lower(): value for key, value in headers.items() if key.lower() in allowed}


def live_completion(messages, *, max_tokens, tools):
    model = os.environ["LLM_MODEL"]
    payload = {"model": model, "messages": messages, "max_completion_tokens": max_tokens}
    if tools:
        payload["tools"] = tools
    headers = {"Content-Type": "application/json"}
    key = os.getenv("LLM_API_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    headers.update(llm._extra_headers())
    request = urllib.request.Request(os.getenv("LLM_BASE_URL", llm.DEFAULT_BASE_URL).rstrip("/") + "/chat/completions",
                                     data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=float(os.getenv("LLM_TIMEOUT", "30"))) as response:
            raw = json.loads(response.read())
            normalized = llm._normalise(raw, model)
            normalized["provider_metadata"] = metadata(response.headers)
            normalized["response_id"] = raw.get("id")
            normalized["usage_details"] = raw.get("usage")
            return normalized
    except urllib.error.HTTPError as exc:
        code = None
        try:
            body = json.loads(exc.read())
            candidate = body.get("error", {}).get("code")
            if candidate in {"rate_limit_exceeded", "insufficient_quota", "invalid_api_key", "model_not_found", "context_length_exceeded"}:
                code = candidate
        except (ValueError, AttributeError):
            pass
        raise ProviderError(exc.code, code, metadata(exc.headers)) from None
