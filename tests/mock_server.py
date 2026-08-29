"""A tiny OpenAI-compatible mock server for tests (no third-party deps).

Run:  python3 tests/mock_server.py [port]

Endpoints:
  GET  /v1/models                      → {"data": [{"id": "mock-1"}, ...]}
  POST /v1/chat/completions            → scripted behaviour:
       last message role=user  → tool call: shell "echo hello-from-mock"
       last message role=tool  → content: "MOCK: <first line of tool result>"
Supports both streaming (SSE) and non-streaming requests.
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

MODELS = ["mock-mini", "mock-pro", "mock-reasoner"]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._json({"data": [{"id": m} for m in MODELS]})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        messages = payload.get("messages", [])
        last = messages[-1] if messages else {}

        if last.get("role") == "tool":
            first_line = (last.get("content") or "").splitlines()[0]
            content, tool_calls = f"MOCK: {first_line}", None
        else:
            content, tool_calls = "", [{
                "id": "call_1", "type": "function",
                "function": {"name": "shell",
                             "arguments": json.dumps({"command": "echo hello-from-mock"})},
            }]

        if not payload.get("stream"):
            msg = {"role": "assistant", "content": content or None}
            if tool_calls:
                msg["tool_calls"] = tool_calls
            self._json({"choices": [{"message": msg, "finish_reason": "stop"}]})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def event(obj):
            data = ("data: " + json.dumps(obj) + "\n\n").encode()
            self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")

        if content:
            event({"choices": [{"delta": {"content": content}}]})
        if tool_calls:
            event({"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_1", "type": "function",
                 "function": {"name": "shell", "arguments": ""}}]}}]})
            args = json.dumps({"command": "echo hello-from-mock"})
            for i in range(0, len(args), 10):  # stream the args in fragments
                event({"choices": [{"delta": {"tool_calls": [
                    {"index": 0,
                     "function": {"arguments": args[i:i + 10]}}]}}]})
        event({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        data = b"data: [DONE]\n\n"
        self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
        self.wfile.write(b"0\r\n\r\n")  # end of chunked body


def serve(port=8901):
    server = HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8901
    print(f"mock server on http://127.0.0.1:{port}/v1")
    serve(port)
    threading.Event().wait()
