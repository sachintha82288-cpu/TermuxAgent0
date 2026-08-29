"""OpenAI-compatible Chat Completions client (standard library only).

Works with every provider in ``providers.py`` plus any server that exposes
``POST {base_url}/chat/completions``.  Handles streaming (SSE), streamed
tool-call accumulation, reasoning tokens (DeepSeek-R1 style), Bearer auth,
extra per-provider headers and ``GET {base_url}/models``.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional


class LLMError(Exception):
    """Raised when the model API cannot be reached or returns an error."""


class StreamedReply:
    """Accumulates a streamed chat completion."""

    def __init__(self) -> None:
        self.content: str = ""
        self.reasoning: str = ""
        self.tool_calls: Dict[int, dict] = {}
        self.finish_reason: Optional[str] = None
        self.usage: Optional[dict] = None

    def to_message(self) -> dict:
        msg: dict = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            calls = []
            for idx in sorted(self.tool_calls):
                call = self.tool_calls[idx]
                calls.append({
                    "id": call.get("id") or f"call_{idx}",
                    "type": "function",
                    "function": {
                        "name": call.get("name", ""),
                        "arguments": call.get("arguments", "") or "{}",
                    },
                })
            msg["tool_calls"] = calls
        return msg


def _merge_tool_delta(acc: StreamedReply, delta_tc: dict) -> None:
    idx = delta_tc.get("index", 0)
    slot = acc.tool_calls.setdefault(
        idx, {"id": "", "name": "", "arguments": ""})
    if delta_tc.get("id"):
        slot["id"] = delta_tc["id"]
    fn = delta_tc.get("function") or {}
    if fn.get("name"):
        slot["name"] += fn["name"]
    if fn.get("arguments"):
        slot["arguments"] += fn["arguments"]


def _friendly_error(url: str, code: int, body: str) -> str:
    hint = {
        401: "invalid API key?",
        403: "key not allowed for this model?",
        404: "wrong base URL or model name?",
        413: "request too large — try a shorter conversation (/reset)",
        422: "model rejected the request — is the model name right?",
        429: "rate limited — wait a moment or switch model (/model)",
        500: "provider error — retry in a moment",
        503: "provider overloaded — retry or switch provider (/provider)",
    }.get(code, "")
    text = body[:300].replace("\n", " ")
    msg = f"HTTP {code} from {url.split('/chat')[0]}"
    if hint:
        msg += f" — {hint}"
    if text:
        msg += f"\n  {text}"
    return msg


def _post(url: str, payload: dict, api_key: str, timeout: int,
          headers: Optional[dict] = None):
    hdrs = {"Content-Type": "application/json"}
    if api_key:
        hdrs["Authorization"] = f"Bearer {api_key}"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=hdrs, method="POST")
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise LLMError(_friendly_error(url, exc.code, body)) from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"cannot reach {url}\n  ({exc.reason}) — "
                       f"check your internet connection") from exc
    except TimeoutError as exc:
        raise LLMError(f"timed out after {timeout}s contacting the API") from exc


def _iter_sse(resp) -> str:
    for raw in resp:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data:"):
            continue
        yield line[len("data:"):].strip()


def chat(*, base_url: str, api_key: str, model: str, messages: List[dict],
         tools: Optional[List[dict]] = None, timeout: int = 90,
         stream: bool = True, temperature: float = 0.6,
         extra_headers: Optional[dict] = None,
         on_content: Optional[Callable[[str], None]] = None,
         on_reasoning: Optional[Callable[[str], None]] = None) -> dict:
    """Call the chat API and return the assistant message dict.

    Streams content/reasoning deltas through the callbacks while
    accumulating tool calls.  If a provider rejects streaming, the call is
    retried once without it.
    """
    url = base_url.rstrip("/") + "/chat/completions"

    def build(do_stream: bool) -> dict:
        payload = {"model": model, "messages": messages,
                   "temperature": temperature, "stream": do_stream}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    try:
        resp = _post(url, build(stream), api_key, timeout, extra_headers)
    except LLMError as exc:
        if stream and "timed out" not in str(exc).lower():
            stream = False  # some providers reject SSE — retry plain
            resp = _post(url, build(False), api_key, timeout, extra_headers)
        else:
            raise

    with resp:
        if not stream:
            try:
                data = json.loads(resp.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise LLMError(f"invalid JSON from {url}: {exc}") from exc
            if "error" in data:
                raise LLMError(str(data["error"])[:300])
            return data["choices"][0]["message"]

        acc = StreamedReply()
        for data_str in _iter_sse(resp):
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if chunk.get("usage"):
                acc.usage = chunk["usage"]
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            text = delta.get("content")
            if text:
                acc.content += text
                if on_content:
                    on_content(text)
            think = delta.get("reasoning_content") or delta.get("reasoning")
            if think:
                acc.reasoning += think
                if on_reasoning:
                    on_reasoning(think)
            for tc in delta.get("tool_calls") or []:
                _merge_tool_delta(acc, tc)
            if choice.get("finish_reason"):
                acc.finish_reason = choice["finish_reason"]
        return acc.to_message()


def list_models(base_url: str, api_key: str,
                headers: Optional[dict] = None) -> List[str]:
    """GET {base_url}/models → sorted list of model ids."""
    url = base_url.rstrip("/") + "/models"
    hdrs = {}
    if api_key:
        hdrs["Authorization"] = f"Bearer {api_key}"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LLMError(_friendly_error(url, exc.code,
                       exc.read().decode("utf-8", errors="replace")[:300])) from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"cannot reach {url} ({exc.reason})") from exc
    items = data.get("data") or data.get("models") or []
    ids = sorted({(m.get("id") or m.get("name") or "").strip()
                  for m in items if isinstance(m, dict)})
    return [i for i in ids if i]


def ping(base_url: str, api_key: str) -> bool:
    try:
        list_models(base_url, api_key)
        return True
    except LLMError:
        return False
