import json
import os
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

from termuxagent import llm
from termuxagent.config import Config, config_path


class ConfigTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as home:
            os.environ["TERMUXAGENT_HOME"] = home
            try:
                cfg = Config(api_key="secret", model="test-model")
                path = cfg.save()
                self.assertTrue(path.exists())
                mode = oct(path.stat().st_mode & 0o777)
                self.assertEqual(mode, oct(0o600))

                loaded = Config.load()
                self.assertEqual(loaded.api_key, "secret")
                self.assertEqual(loaded.model, "test-model")
            finally:
                os.environ.pop("TERMUXAGENT_HOME", None)

    def test_env_overrides_file(self):
        with tempfile.TemporaryDirectory() as home:
            os.environ["TERMUXAGENT_HOME"] = home
            os.environ["TERMUXAGENT_MODEL"] = "env-model"
            try:
                Config(api_key="k", model="file-model").save()
                loaded = Config.load()
                self.assertEqual(loaded.model, "env-model")
            finally:
                os.environ.pop("TERMUXAGENT_HOME", None)
                os.environ.pop("TERMUXAGENT_MODEL", None)

    def test_corrupt_config_falls_back(self):
        with tempfile.TemporaryDirectory() as home:
            os.environ["TERMUXAGENT_HOME"] = home
            try:
                config_path().write_text("{ this is not json")
                cfg = Config.load()  # must not raise
                self.assertTrue(cfg.model)
            finally:
                os.environ.pop("TERMUXAGENT_HOME", None)


# ----------------------------------------------------------------- fake server
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not self.path.startswith("/v1"):
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        # Stream a tool call, then (after the client sends the tool result on
        # the next request) the final answer.
        last = body["messages"][-1]
        if last.get("role") == "tool":
            chunks = [
                {"choices": [{"delta": {"content": "tool said: "}}]},
                {"choices": [{"delta": {"content": last["content"]}}]},
                {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            ]
        else:
            chunks = [
                {"choices": [{"delta": {"content": "Running "}}]},
                {"choices": [{"delta": {"tool_calls": [
                    {"index": 0, "id": "t1", "function": {"name": "shell", "arguments": ""}}]}}]},
                {"choices": [{"delta": {"tool_calls": [
                    {"index": 0, "function": {"arguments": '{"command": "echo e2e"}'}}]}}]},
                {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
            ]
        for ch in chunks:
            self.wfile.write(b"data: " + json.dumps(ch).encode() + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")


class StreamingLLMTests(unittest.TestCase):
    def setUp(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.httpd.server_address[1]
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)

    def test_streaming_tool_call(self):
        collected = []
        msg = llm.chat(
            base_url=f"http://127.0.0.1:{self.port}/v1",
            api_key="not-needed",
            model="fake",
            messages=[{"role": "user", "content": "go"}],
            tools=[{"type": "function", "function": {"name": "shell"}}],
            on_content=collected.append,
        )
        self.assertEqual("".join(collected), "Running ")
        tc = msg["tool_calls"][0]
        self.assertEqual(tc["id"], "t1")
        self.assertEqual(tc["function"]["name"], "shell")
        self.assertEqual(json.loads(tc["function"]["arguments"]), {"command": "echo e2e"})

    def test_streaming_followup(self):
        collected = []
        msg = llm.chat(
            base_url=f"http://127.0.0.1:{self.port}/v1",
            api_key="not-needed",
            model="fake",
            messages=[
                {"role": "user", "content": "go"},
                {"role": "assistant", "content": None,
                 "tool_calls": [{"id": "t1", "type": "function",
                                 "function": {"name": "shell", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "t1", "name": "shell", "content": "(exit code 0)"},
            ],
            on_content=collected.append,
        )
        self.assertEqual(msg["content"], "tool said: (exit code 0)")

    def test_http_error_raises_llmerror(self):
        with self.assertRaises(llm.LLMError):
            llm.chat(
                base_url=f"http://127.0.0.1:{self.port}/does-not-exist",
                api_key="k",
                model="m",
                messages=[{"role": "user", "content": "x"}],
            )


if __name__ == "__main__":
    unittest.main()
