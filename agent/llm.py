"""OpenAI-compatible chat client with tool-call loop."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import requests

from .tools import TOOL_DISPATCH, TOOL_SCHEMAS


@dataclass
class LLMClient:
    api_key: str
    base_url: str
    model: str
    stream: bool = True
    system_prompt: str = ""
    max_tool_rounds: int = 8

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_messages(self, history: list[dict]) -> list[dict]:
        msgs: list[dict] = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(history)
        return msgs

    def chat(
        self,
        history: list[dict],
        on_token: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> str:
        """
        Send messages + run the tool-call loop.

        Returns the assistant's final text (also appends messages to history in-place).
        """
        url = f"{self.base_url}/chat/completions"

        for _ in range(self.max_tool_rounds):
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": self._build_messages(history),
                "tools": TOOL_SCHEMAS,
                "tool_choice": "auto",
                "stream": self.stream,
            }

            if not self.stream:
                resp = requests.post(url, headers=self._headers(), json=payload, timeout=120)
                if resp.status_code >= 400:
                    raise RuntimeError(f"API error {resp.status_code}: {resp.text[:500]}")
                data = resp.json()
                message = data["choices"][0]["message"]
                text_content = message.get("content") or ""
                if on_token and text_content:
                    on_token(text_content)
                tool_calls = message.get("tool_calls")
                history.append({
                    "role": "assistant",
                    "content": message.get("content"),
                    "tool_calls": tool_calls,
                })
                if not tool_calls:
                    return text_content
            else:
                text_content, tool_calls = self._stream_chat(url, payload, on_token)
                history.append({
                    "role": "assistant",
                    "content": text_content or None,
                    "tool_calls": tool_calls or None,
                })
                if not tool_calls:
                    return text_content or ""

            # Execute tool calls
            for tc in tool_calls:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_fn = TOOL_DISPATCH.get(name)
                if tool_fn is None:
                    result = f"ERROR: unknown tool '{name}'."
                else:
                    try:
                        result = tool_fn(**args)
                    except TypeError as e:
                        result = f"ERROR: bad arguments for {name}: {e}"
                    except Exception as e:  # noqa: BLE001
                        result = f"ERROR in {name}: {e}"
                history.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": result,
                })
                preview = result[:200] + ("…" if len(result) > 200 else "")
                if on_status:
                    on_status(f"\n  🔧 tool:{name} → {preview}\n")
                elif on_token:
                    on_token(f"\n  🔧 tool:{name} → {preview}\n")

        return "(tool-call loop reached maximum rounds; stopping.)"

    def _stream_chat(
        self, url: str, payload: dict, on_token: Callable[[str], None] | None
    ) -> tuple[str, list[dict] | None]:
        """Stream SSE chunks and assemble assistant text + any tool calls."""
        text_buf: list[str] = []
        # tool_calls indexed by position; each is {id, type, function: {name, arguments}}
        tool_calls: dict[int, dict] = {}

        with requests.post(url, headers=self._headers(), json=payload, stream=True, timeout=180) as resp:
            if resp.status_code >= 400:
                raise RuntimeError(f"API error {resp.status_code}: {resp.text[:500]}")
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                if raw_line.startswith(":"):
                    continue
                if not raw_line.startswith("data:"):
                    continue
                data = raw_line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                if delta.get("content"):
                    piece = delta["content"]
                    text_buf.append(piece)
                    if on_token:
                        on_token(piece)
                    sys.stdout.flush()
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    slot = tool_calls.setdefault(
                        idx,
                        {"id": None, "type": "function", "function": {"name": "", "arguments": ""}},
                    )
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["function"]["arguments"] += fn["arguments"]

        if tool_calls:
            # Sort by index and return as a list
            tc_list = [tool_calls[i] for i in sorted(tool_calls)]
            return "".join(text_buf), tc_list
        return "".join(text_buf), None
