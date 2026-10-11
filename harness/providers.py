"""
Model adapters.

Two transports cover every arm in the study:

  AnthropicProvider      -- native Messages API, structured output via a forced
                            tool call. Runs in the cloud container.
  OpenAICompatProvider   -- the OpenAI chat-completions shape, which OpenAI,
                            DeepSeek, and Ollama all speak. Runs on the
                            reviewer's laptop, since the container's egress
                            proxy refuses every host except anthropic.com.

Every call returns a RunResult carrying not just the findings but the metadata
the method section promises: the model string the API actually resolved to,
token counts, wall-clock latency, the host that measured it, and any schema
violations. A malformed response is recorded, not raised -- the error rate is
itself a reported metric.
"""
from __future__ import annotations

import json
import os
import platform
import socket
import time
import http.client
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict

from schema import RESPONSE_SCHEMA, JSON_FALLBACK_INSTRUCTION, validate, empty_response

MEASUREMENT_HOST = f"{platform.system().lower()}/{socket.gethostname()}"

# $ per million tokens (input, output). August 2026 published list prices.
RATES = {
    "claude-opus-5":      (5.00, 25.00),
    "claude-sonnet-5":    (2.00, 10.00),
    "gpt-5.6-terra":      (2.00, 12.00),
    "deepseek-v4-flash":  (0.14, 0.28),
    "gemma4:12b":         (0.00, 0.00),
}


@dataclass
class RunResult:
    model: str
    resolved_model: str = ""
    findings: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    attempts: int = 1
    schema_problems: list = field(default_factory=list)
    thinking_chars: int = 0
    reasoning: bool = False
    error: str = ""
    measurement_host: str = MEASUREMENT_HOST
    raw_text: str = ""

    @property
    def cost_usd(self) -> float:
        ri, ro = RATES.get(self.model, (0.0, 0.0))
        return self.input_tokens / 1e6 * ri + self.output_tokens / 1e6 * ro

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cost_usd"] = round(self.cost_usd, 6)
        return d


def _post(url: str, headers: dict, body: dict, timeout: int = 180) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (408, 409, 429, 500, 502, 503, 504, 529)
    # IncompleteRead: the connection dropped mid-response. A transport
    # failure, not a model failure, so retry it.
    return isinstance(exc, (urllib.error.URLError, TimeoutError, socket.timeout,
                            http.client.IncompleteRead, ConnectionError))


def _extract_json(text: str) -> dict | None:
    """Best-effort recovery when a model wraps JSON in prose or fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text[4:] if text.lower().startswith("json") else text
    try:
        return json.loads(text)
    except Exception:
        pass
    start, depth = text.find("{"), 0
    if start < 0:
        return None
    for i, ch in enumerate(text[start:], start):
        depth += (ch == "{") - (ch == "}")
        if depth == 0:
            try:
                return json.loads(text[start:i + 1])
            except Exception:
                return None
    return None


class BaseProvider:
    max_attempts = 5
    base_backoff = 2.0

    def __init__(self, model: str, **kw):
        self.model = model
        self.opts = kw

    def _invoke(self, system: str, user: str, max_tokens: int) -> tuple[dict, str]:
        raise NotImplementedError

    def run(self, system: str, user: str, max_tokens: int = 4096) -> RunResult:
        res = RunResult(model=self.model, reasoning=bool(self.opts.get("reasoning")))
        started = time.time()
        for attempt in range(1, self.max_attempts + 1):
            res.attempts = attempt
            try:
                payload, raw = self._invoke(system, user, max_tokens)
                res.latency_s = round(time.time() - started, 3)
                res.raw_text = raw[:4000]
                res.resolved_model = payload.get("_resolved", self.model)
                res.input_tokens = payload.get("_in", 0)
                res.output_tokens = payload.get("_out", 0)
                res.thinking_chars = payload.get("_thinking_chars", 0)
                parsed = payload.get("_parsed") or empty_response()
                ok, problems = validate(parsed)
                res.schema_problems = problems
                res.findings = parsed.get("findings", []) if ok or parsed.get("findings") else []
                return res
            except Exception as exc:                      # noqa: BLE001
                if attempt >= self.max_attempts or not _retryable(exc):
                    res.latency_s = round(time.time() - started, 3)
                    detail = ""
                    if isinstance(exc, urllib.error.HTTPError):
                        try:
                            detail = exc.read()[:300].decode(errors="replace")
                        except Exception:
                            pass
                    res.error = f"{type(exc).__name__}: {exc} {detail}".strip()
                    return res
                time.sleep(self.base_backoff * (2 ** (attempt - 1)))
        return res


class AnthropicProvider(BaseProvider):
    """
    Claude 5 reasoning notes, established by probe:

      - thinking.type "enabled" is rejected; this generation requires
        "adaptive".
      - Forcing a tool call SUPPRESSES the thinking block entirely, even under
        adaptive. "Thinking may not be enabled when tool_choice forces tool
        use." So a reasoning-on run must use tool_choice auto and accept that
        the model decides whether to call the tool.

    A useful consequence: the reasoning-OFF runs, which force the tool, were
    genuinely reasoning-free rather than merely nominally so.
    """
    URL = "https://api.anthropic.com/v1/messages"

    def _invoke(self, system, user, max_tokens):
        reasoning = self.opts.get("reasoning")
        if reasoning:
            max_tokens = max(max_tokens, 8000)
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [{
                "name": "report_findings",
                "description": "Report every security vulnerability found.",
                "input_schema": RESPONSE_SCHEMA,
            }],
        }
        if reasoning:
            body["thinking"] = {"type": "adaptive"}
        else:
            body["tool_choice"] = {"type": "tool", "name": "report_findings"}
        if self.opts.get("temperature") is not None:
            body["temperature"] = self.opts["temperature"]
        d = _post(self.URL, {
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, body)
        parsed, raw, thinking = None, "", ""
        for block in d.get("content", []):
            t = block.get("type")
            if t == "tool_use" and block.get("name") == "report_findings":
                parsed = block.get("input")
                raw = json.dumps(parsed)[:4000]
            elif t == "text":
                raw = raw or block.get("text", "")
            elif t == "thinking":
                thinking = block.get("thinking", "") or ""
        # With tool_choice auto the model may answer in prose instead.
        if parsed is None and raw:
            parsed = _extract_json(raw)
        u = d.get("usage", {})
        return ({"_parsed": parsed, "_resolved": d.get("model", self.model),
                 "_in": u.get("input_tokens", 0), "_out": u.get("output_tokens", 0),
                 "_thinking_chars": len(thinking)}, raw)


class OpenAICompatProvider(BaseProvider):
    """OpenAI, DeepSeek, and Ollama all speak this shape."""

    def __init__(self, model, base_url, api_key_env, use_tools=True,
                 token_param="max_tokens", extra_body=None, **kw):
        super().__init__(model, **kw)
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.use_tools = use_tools
        # gpt-5.6-terra rejects max_tokens and requires max_completion_tokens.
        self.token_param = token_param
        # Reasoning is disabled on every arm so the chain-of-thought variant
        # measures a real effect rather than competing with native reasoning.
        # gpt-5.6-terra additionally refuses function tools unless
        # reasoning_effort is "none"; deepseek-v4-flash refuses a forced
        # tool_choice while thinking mode is active.
        self.extra_body = extra_body or {}

    def _invoke(self, system, user, max_tokens):
        if self.opts.get("reasoning") and self.opts.get("responses_api"):
            return self._invoke_responses(system, user, max_tokens)
        if self.opts.get("reasoning"):
            # A ceiling chosen so that it does not bind: DeepSeek's reasoning
            # responses truncated at 4,096 and once at 8,000; none reached
            # 16,000 (SUPPLEMENT.md, "Reasoning-on output ceilings").
            max_tokens = max(max_tokens, 16000)
        msgs = [{"role": "system", "content": system}]
        body = {"model": self.opts.get("model_slug", self.model), "messages": msgs}
        body[self.token_param] = max_tokens
        body.update(self.extra_body)
        if self.opts.get("reasoning"):
            # deepseek-v4-flash refuses a forced tool_choice while thinking is
            # active, so reasoning-on runs use auto and fall back to parsing
            # JSON out of the text if the model declines the tool.
            body.pop("thinking", None)
        if self.use_tools:
            body["tools"] = [{"type": "function", "function": {
                "name": "report_findings",
                "description": "Report every security vulnerability found.",
                "parameters": RESPONSE_SCHEMA}}]
            body["tool_choice"] = ("auto" if self.opts.get("reasoning")
                                   else {"type": "function",
                                         "function": {"name": "report_findings"}})
            msgs.append({"role": "user", "content": user})
        else:
            msgs.append({"role": "user", "content": user + "\n\n" + JSON_FALLBACK_INSTRUCTION})
        if self.opts.get("temperature") is not None:
            body["temperature"] = self.opts["temperature"]

        key = os.environ.get(self.api_key_env, "")
        headers = {"content-type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        d = _post(f"{self.base_url}/chat/completions", headers, body)

        choice = (d.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        parsed, raw = None, msg.get("content") or ""
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            if fn.get("name") == "report_findings":
                try:
                    parsed = json.loads(fn.get("arguments") or "{}")
                    raw = fn.get("arguments", "")[:4000]
                except Exception:
                    parsed = None
        if parsed is None and raw:
            parsed = _extract_json(raw)
        u = d.get("usage", {})
        return ({"_parsed": parsed, "_resolved": d.get("model", self.model),
                 "_in": u.get("prompt_tokens", 0), "_out": u.get("completion_tokens", 0)}, raw)


    def _invoke_responses(self, system, user, max_tokens):
        """gpt-5.6-terra rejects function tools on chat/completions unless
        reasoning_effort is 'none'. With reasoning on, /v1/responses is the
        supported path and it does allow a forced tool call."""
        body = {
            "model": self.opts.get("model_slug", self.model),
            "instructions": system,
            "input": user,
            "max_output_tokens": max(max_tokens, 8000),
            "reasoning": {"effort": self.opts.get("reasoning_effort", "medium")},
            # strict mode demands that every property appear in `required`,
            # which would force the optional `cwe` and `confidence` fields and
            # change the experimental condition. The chat/completions path does
            # not use strict either, so this keeps the two consistent.
            "tools": [{"type": "function", "name": "report_findings",
                       "parameters": RESPONSE_SCHEMA, "strict": False}],
            "tool_choice": {"type": "function", "name": "report_findings"},
        }
        key = os.environ.get(self.api_key_env, "")
        d = _post(f"{self.base_url}/responses",
                  {"content-type": "application/json",
                   "Authorization": f"Bearer {key}"}, body)
        parsed, raw, think_chars = None, "", 0
        for item in d.get("output", []):
            if item.get("type") == "function_call" and item.get("name") == "report_findings":
                raw = item.get("arguments", "") or ""
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = _extract_json(raw)
            elif item.get("type") == "reasoning":
                think_chars += len(json.dumps(item.get("summary", "")))
        u = d.get("usage", {})
        return ({"_parsed": parsed, "_resolved": d.get("model", self.model),
                 "_in": u.get("input_tokens", 0), "_out": u.get("output_tokens", 0),
                 "_thinking_chars": think_chars}, raw[:4000])


def make_provider(name: str, temperature: float | None = None,
                  reasoning: bool = False) -> BaseProvider:
    """
    Factory keyed on the study's model names.

    Sampling is left at each provider's default on every arm. Temperature is
    NOT alignable across this lineup: Claude 5 rejects the parameter outright
    ("`temperature` is deprecated for this model"), while gpt-5.6-terra,
    deepseek-v4-flash, and Ollama accept it. Setting it on the three that
    accept it while leaving Claude uncontrolled would make Claude the only
    warm arm, so any widening of its confidence interval would be a
    measurement artifact rather than a finding.

    Run-to-run variation is therefore controlled the way the method section
    already specifies as primary -- repetition with bootstrap confidence
    intervals -- and output stability is measured and reported per arm rather
    than assumed. He (2025), already cited in the method, establishes that
    temperature=0 never guaranteed determinism in any case.
    """
    if name in ("claude-opus-5", "claude-sonnet-5"):
        return AnthropicProvider(name, temperature=None, reasoning=reasoning)
    if name == "gpt-5.6-terra":
        return OpenAICompatProvider(
            name, "https://api.openai.com/v1", "OPENAI_API_KEY",
            token_param="max_completion_tokens",
            extra_body={} if reasoning else {"reasoning_effort": "none"},
            reasoning=reasoning, responses_api=True, temperature=temperature)
    if name == "deepseek-v4-flash":
        return OpenAICompatProvider(
            name, os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "DEEPSEEK_HOST_KEY",
            model_slug=os.environ.get("DEEPSEEK_MODEL_SLUG", "deepseek-v4-flash"),
            extra_body={} if reasoning else {"thinking": {"type": "disabled"}},
            reasoning=reasoning, temperature=temperature)
    if name.startswith("gemma"):
        # Ollama's OpenAI-compatible endpoint; no key, no tool-calling.
        return OpenAICompatProvider(name, os.environ.get("OLLAMA_BASE_URL",
                                                         "http://localhost:11434/v1"),
                                    "OLLAMA_API_KEY", use_tools=False,
                                    temperature=temperature)
    raise ValueError(f"unknown model {name!r}")
