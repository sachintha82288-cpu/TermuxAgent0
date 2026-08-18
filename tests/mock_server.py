"""
Tiny mock OpenAI-compatible server for end-to-end testing of TermuxAgent0.

Behaviours:
  * If the user asks "shell_test" -> responds with a tool_call to shell("echo hello from mock")
    then, after receiving the tool result, streams a final answer.
  * If the user asks "file_test" -> tool_calls write_file + read_file in parallel, then final answer.
  * Otherwise -> streams a short greeting.
"""
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def _sse_line(obj):
    return f"data: {json.dumps(obj)}\n\n".encode()


DONE = b"data: [DONE]\n\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silence default logging
        print(f"[mock-srv] {fmt % args}")

    def _send_json(self, code, payload, stream=False):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/event-stream" if stream else "application/json")
        self.send_header("Content-Length", str(len(body)) if not stream else None)
        self.send_header("Transfer-Encoding", "chunked" if stream else None)
        self.end_headers()
        if stream:
            self.wfile.write(body)
        else:
            self.wfile.write(body)

    def _stream_simple(self, text):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        # initial role
        self.wfile.write(_sse_line({"id":"c1","object":"chat.completion.chunk","created":1,"model":"test-model",
                                     "choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":None}]}))
        for ch in text:
            self.wfile.write(_sse_line({"id":"c1","object":"chat.completion.chunk","created":1,"model":"test-model",
                                         "choices":[{"index":0,"delta":{"content":ch},"finish_reason":None}]}))
            time.sleep(0.005)
        self.wfile.write(_sse_line({"id":"c1","object":"chat.completion.chunk","created":1,"model":"test-model",
                                     "choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}))
        self.wfile.write(DONE)

    def _stream_tool_then_text(self, tool_calls, final_text):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        # role delta
        self.wfile.write(_sse_line({"id":"c1","object":"chat.completion.chunk","created":1,"model":"test-model",
                                     "choices":[{"index":0,"delta":{"role":"assistant","content":None,"tool_calls":[{"index":i,"id":f"call_{i}","type":"function","function":{"name":tc["name"],"arguments":""}} for i,tc in enumerate(tool_calls)]},"finish_reason":None}]}))
        for i, tc in enumerate(tool_calls):
            args = json.dumps(tc["args"])
            # stream arguments in small chunks
            for pos in range(0, len(args), 3):
                piece = args[pos:pos+3]
                self.wfile.write(_sse_line({"id":"c1","object":"chat.completion.chunk","created":1,"model":"test-model",
                                             "choices":[{"index":0,"delta":{"tool_calls":[{"index":i,"function":{"arguments":piece}}]},"finish_reason":None}]}))
                time.sleep(0.002)
        self.wfile.write(_sse_line({"id":"c1","object":"chat.completion.chunk","created":1,"model":"test-model",
                                     "choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}))
        self.wfile.write(DONE)

        # Server now expects the client to POST the tool results, then we answer.
        # (We don't get to "see" them here; the next POST will be a separate request
        #  where messages include the tool role — handled in do_POST.)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            payload = {}
        auth = self.headers.get("Authorization", "")
        assert auth.startswith("Bearer "), "missing auth"

        messages = payload.get("messages", [])
        stream = bool(payload.get("stream", False))
        last_user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
        text = (last_user.get("content") or "").lower()

        # Check if there are tool results present -> final answer mode
        has_tool_result = any(m.get("role") == "tool" for m in messages)

        if has_tool_result:
            # Build a summary answer
            tool_msgs = [m for m in messages if m.get("role") == "tool"]
            summary_parts = []
            for m in tool_msgs:
                summary_parts.append(f"[{m.get('name')}]: {m.get('content','')[:80]}")
            final = "Done! Tool results:\n- " + "\n- ".join(summary_parts)
            if stream:
                self._stream_simple(final)
            else:
                self._send_json(200, {"id":"c1","object":"chat.completion","created":1,"model":"test-model",
                                      "choices":[{"index":0,"message":{"role":"assistant","content":final},"finish_reason":"stop"}]})
            return

        # Decide scenario based on user prompt
        if "shell_test" in text:
            tool_calls = [{"name": "shell", "args": {"command": "echo hello from mock", "timeout": 5}}]
        elif "file_test" in text:
            tool_calls = [
                {"name": "write_file", "args": {"path": "/tmp/mock_agent_test.txt", "content": "mock content here\n"}},
                {"name": "read_file", "args": {"path": "/tmp/mock_agent_test.txt"}},
            ]
        elif "ls_test" in text:
            tool_calls = [{"name": "ls", "args": {"path": "/tmp"}}]
        else:
            # Simple text
            answer = "Hi! I am the mock TermuxAgent0. Say 'shell_test', 'file_test', or 'ls_test' to try tools."
            if stream:
                self._stream_simple(answer)
            else:
                self._send_json(200, {"id":"c1","object":"chat.completion","created":1,"model":"test-model",
                                      "choices":[{"index":0,"message":{"role":"assistant","content":answer},"finish_reason":"stop"}]})
            return

        # Stream the tool call(s)
        if stream:
            self._stream_tool_then_text(tool_calls, "")
        else:
            tc_msg = {"role":"assistant","content":None,"tool_calls":[
                {"id":f"call_{i}","type":"function","function":{"name":t["name"],"arguments":json.dumps(t["args"])}}
                for i,t in enumerate(tool_calls)
            ]}
            self._send_json(200, {"id":"c1","object":"chat.completion","created":1,"model":"test-model",
                                  "choices":[{"index":0,"message":tc_msg,"finish_reason":"tool_calls"}]})

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"mock openai server is up\n")


if __name__ == "__main__":
    port = int(__import__("os").environ.get("MOCK_PORT", "8765"))
    srv = HTTPServer(("127.0.0.1", port), Handler)
    print(f"[mock-srv] listening on http://127.0.0.1:{port}")
    srv.serve_forever()
