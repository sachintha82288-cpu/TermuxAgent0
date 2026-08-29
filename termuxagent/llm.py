"""Minimal OpenAI-compatible Chat Completions client (standard library only).

Supports streaming responses, tool calls and Bearer authentication, so it
works with OpenAI, Groq, OpenRouter, Together, LM Studio, Ollama, vLLM,
LiteLLM proxies and anything else exposing ``/chat/completions``.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional


class LLMError(Exception):
    """Raised when the model API cannot be reached or returns an error."""


class StreamingChatCompletion:
    """Accumulates a streamed chat completion.

    ``content`` holds the text deltas; ``tool_calls`` is a dict keyed by the
    tool-call index, each with accumulated ``arguments`` JSON text.
    """

    def __init__(self) -> None:
        self.content: str = ""
        self.tool_calls: Dict[int, dict] = {}
        self.finish_reason: Optional[str] = None

    def to_message(self) -> dict:
        msg: dict = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            calls = []
            for idx in sorted(self.tool_calls):
                call = self.tool_calls[idx]
                calls.append(
                    {
                        "id": call.get("id") or f"call_{idx}",
                        "type": "function",
                        "function": {
                            "name": call.get("name", ""),
                            "arguments": call.get("arguments", ""),
                        },
                    }
                )
            msg["tool_calls"] = calls
        return msg


def _merge_tool_delta(acc: StreamingChatCompletion, delta_tc: dict) -> None:
    idx = delta_tc.get("index", 0)
    slot = acc.tool_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
    if delta_tc.get("id"):
        slot["id"] = delta_tc["id"]
    fn = delta_tc.get("function") or {}
    if fn.get("name"):
        slot["name"] += fn["name"]
    if fn.get("arguments"):
        slot["arguments"] += fn["arguments"]


def _iter_sse_lines(resp) -> str:
    """Yield ``data:`` payloads from a Server-Sent-Events stream."""
    for raw in resp:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data:"):
            continue
        yield line[len("data:"):].strip()


def chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: List[dict],
    tools: Optional[List[dict]] = None,
    timeout: int = 60,
    stream: bool = True,
    on_content: Optional[Callable[[str], None]] = None,
) -> dict:
    """Call ``POST {base_url}/chat/completions`` and return the assistant message.

    With ``stream=True`` (default) content deltas are forwarded to
    *on_content* as they arrive; tool-call deltas are accumulated.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    payload: dict = {"model": model, "messages": messages, "stream": stream}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {"Content-Type": "application/json"}
    if api_key and api_key != "not-needed":
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise LLMError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"Cannot reach {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMError(f"Timed out after {timeout}s contacting {url}") from exc

    with resp:
        if not stream:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]

        acc = StreamingChatCompletion()
        for data_str in _iter_sse_lines(resp):
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            text = delta.get("content")
            if text:
                acc.content += text
                if on_content:
                    on_content(text)
            for tc in delta.get("tool_calls") or []:
                _merge_tool_delta(acc, tc)
            if choice.get("finish_reason"):
                acc.finish_reason = choice["finish_reason"]

        return acc.to_message()
