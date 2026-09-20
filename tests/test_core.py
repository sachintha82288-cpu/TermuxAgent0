"""Unit tests for the core pieces — no network needed.

Run:  python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from termuxagent import providers as prov
from termuxagent.config import Config
from termuxagent.llm import StreamedReply, _merge_tool_delta, chat, list_models
from termuxagent.theme import THEMES, banner, box, set_theme
from termuxagent.tools import (call_tool, is_dangerous, specs, summarize)


class ProviderCatalogTest(unittest.TestCase):
    def test_at_least_25_providers(self):
        self.assertGreaterEqual(len(prov.PROVIDERS), 25)

    def test_ids_unique(self):
        ids = prov.ids()
        self.assertEqual(len(ids), len(set(ids)))

    def test_groq_is_default_and_has_key_url(self):
        groq = prov.get("groq")
        self.assertEqual(groq["base_url"], "https://api.groq.com/openai/v1")
        self.assertTrue(groq["key_url"])
        self.assertTrue(groq["tools"])

    def test_lookup_unknown(self):
        self.assertIsNone(prov.get("nope"))


class ConfigTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("TERMUXAGENT_HOME", None)
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["TERMUXAGENT_HOME"] = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.environ.pop, "TERMUXAGENT_HOME", None)

    def test_defaults(self):
        cfg = Config()
        self.assertEqual(cfg.data["provider"], "groq")
        self.assertEqual(cfg.data["theme"], "neon")
        self.assertTrue(cfg.data["tools"])

    def test_provider_accessors(self):
        cfg = Config({"provider": "openai",
                      "api_keys": {"openai": "sk-test-1234567890"},
                      "models": {"openai": "gpt-4.1"}})
        self.assertEqual(cfg.provider_id, "openai")
        self.assertEqual(cfg.base_url(), "https://api.openai.com/v1")
        self.assertEqual(cfg.api_key(), "sk-test-1234567890")
        self.assertEqual(cfg.model(), "gpt-4.1")
        self.assertTrue(cfg.is_configured())
        self.assertNotIn("sk-test", cfg.masked_key())

    def test_key_env_fallback(self):
        os.environ["GROQ_API_KEY"] = "gsk_env_key_12345"
        self.addCleanup(os.environ.pop, "GROQ_API_KEY", None)
        cfg = Config()
        self.assertEqual(cfg.api_key(), "gsk_env_key_12345")

    def test_local_provider_needs_no_key(self):
        cfg = Config({"provider": "ollama"})
        self.assertTrue(cfg.is_configured())

    def test_save_and_reload(self):
        cfg = Config({"provider": "deepseek"})
        cfg.set_key("deepseek", "dk-abc")
        cfg.set_model("deepseek", "deepseek-chat")
        path = cfg.save()
        again = Config.load()
        self.assertEqual(again.api_key(), "dk-abc")
        self.assertEqual(again.model(), "deepseek-chat")
        self.assertTrue(path.exists())


class ToolSafetyTest(unittest.TestCase):
    def test_dangerous_commands_blocked(self):
        for cmd in ("rm -rf /", "rm -rf /*", "shutdown now", "mkfs.ext4 /dev/sda1"):
            self.assertIsNotNone(is_dangerous(cmd), cmd)

    def test_normal_commands_pass(self):
        for cmd in ("ls -la", "pkg install -y python", "echo hi", "rm -rf ./build"):
            self.assertIsNone(is_dangerous(cmd), cmd)

    def test_specs_shape(self):
        names = [s["function"]["name"] for s in specs()]
        self.assertIn("shell", names)
        self.assertIn("write_file", names)
        for s in specs():
            self.assertEqual(s["type"], "function")
            self.assertIn("parameters", s["function"])


class ToolExecutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workdir = Path(self.tmp.name)

    def test_shell(self):
        out = call_tool("shell", {"command": "echo agent-test"},
                        30, self.workdir)
        self.assertIn("agent-test", out)
        self.assertIn("exit code 0", out)

    def test_file_roundtrip(self):
        call_tool("write_file", {"path": "notes/a.txt", "content": "hello"},
                  30, self.workdir)
        out = call_tool("read_file", {"path": "notes/a.txt"}, 30, self.workdir)
        self.assertEqual(out, "hello")
        listing = call_tool("list_dir", {"path": "."}, 30, self.workdir)
        self.assertIn("notes/", listing)

    def test_edit_requires_unique_match(self):
        call_tool("write_file", {"path": "f.txt", "content": "aa bb aa"},
                  30, self.workdir)
        from termuxagent.tools import ToolError
        with self.assertRaises(ToolError):
            call_tool("edit_file", {"path": "f.txt", "old_text": "aa",
                                    "new_text": "zz"}, 30, self.workdir)
        out = call_tool("edit_file", {"path": "f.txt", "old_text": "aa bb",
                                      "new_text": "xx"}, 30, self.workdir)
        self.assertIn("1 replacement", out)

    def test_unknown_tool(self):
        from termuxagent.tools import ToolError
        with self.assertRaises(ToolError):
            call_tool("nope", {}, 30, self.workdir)

    def test_summarize(self):
        self.assertEqual(summarize("read_file", {"path": "x.py"}), "x.py")
        self.assertEqual(summarize("shell", {"command": "ls"}), "ls")


class StreamAccumulationTest(unittest.TestCase):
    def test_tool_delta_fragments(self):
        acc = StreamedReply()
        _merge_tool_delta(acc, {"index": 0, "id": "call_9", "type": "function",
                                "function": {"name": "sh", "arguments": ""}})
        _merge_tool_delta(acc, {"index": 0,
                                "function": {"arguments": '{"comm'}})
        _merge_tool_delta(acc, {"index": 0,
                                "function": {"arguments": 'and":"ls"}'}})
        msg = acc.to_message()
        self.assertEqual(msg["tool_calls"][0]["id"], "call_9")
        self.assertEqual(msg["tool_calls"][0]["function"]["name"], "sh")
        self.assertEqual(json.loads(msg["tool_calls"][0]["function"]["arguments"]),
                         {"command": "ls"})


class ThemeTest(unittest.TestCase):
    def test_twelve_themes(self):
        self.assertGreaterEqual(len(THEMES), 12)

    def test_banner_compact_on_narrow(self):
        from termuxagent import theme
        original = theme.term_width
        theme.term_width = lambda: 30
        try:
            lines = banner("TERMUX", "AGENT", "x")
            self.assertLessEqual(len(lines), 4)
        finally:
            theme.term_width = original

    def test_box_no_ansi_leak_in_plain(self):
        set_theme("mono")
        from termuxagent import theme
        theme.enable_colors(False)
        rendered = box(["hello"], title="t")
        theme.enable_colors(True)
        self.assertIn("hello", rendered)
        self.assertNotIn("\033", rendered)


class AgentLoopTest(unittest.TestCase):
    """End-to-end against the in-process mock server (streaming + tools)."""

    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import HTTPServer
        from tests.mock_server import Handler
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def make_cfg(self) -> Config:
        os.environ.pop("TERMUXAGENT_HOME", None)
        return Config({
            "provider": "custom",
            "custom_base_urls": {"custom": f"http://127.0.0.1:{self.port}/v1"},
            "models": {"custom": "mock-pro"},
            "stream": True,
        })

    def test_list_models(self):
        cfg = self.make_cfg()
        models = list_models(cfg.base_url(), "")
        self.assertIn("mock-pro", models)

    def test_chat_streaming_tool_roundtrip(self):
        from termuxagent.agent import Agent
        cfg = self.make_cfg()
        cfg.data["auto_approve"] = True
        agent = Agent(cfg, workdir=Path(tempfile.gettempdir()))
        agent.new_session()
        chunks = []
        agent.on_content = chunks.append
        reply = agent.chat("run the mock command")
        self.assertTrue(reply.startswith("MOCK:"))       # tool ran → reply built on it
        self.assertIn("exit code 0", reply)               # real shell executed
        self.assertTrue(any("MOCK" in c for c in chunks))  # streamed content

    def test_denied_tool(self):
        from termuxagent.agent import Agent
        cfg = self.make_cfg()
        cfg.data["auto_approve"] = False
        agent = Agent(cfg, workdir=Path(tempfile.gettempdir()),
                      approve=lambda name, args: False)
        agent.new_session()
        reply = agent.chat("try a command")
        self.assertIn("[denied by user]", reply)


if __name__ == "__main__":
    unittest.main()


class RegressionTest(unittest.TestCase):
    """Bugs users hit in 1.0.0 that must stay fixed."""

    def test_danger_check_is_not_a_substring_match(self):
        for cmd in ('git commit -m "fix reboot bug"', "grep shutdown log.txt",
                    "echo halted", "cat x > /dev/null"):
            self.assertIsNone(is_dangerous(cmd), cmd)
        for cmd in ("ls; reboot", "sudo rm -rf / --no-preserve-root",
                    "echo hi > /dev/sda", "rm -rf ~"):
            self.assertIsNotNone(is_dangerous(cmd), cmd)

    def test_flags_before_command_open_chat(self):
        from termuxagent.cli import _parse_flags
        flags, pos = _parse_flags(["-y", "-c", "--", "-x", "hello"])
        self.assertTrue(flags["yes"] and flags["continue"])
        self.assertEqual(pos, ["-x", "hello"])
        flags, _ = _parse_flags(["--bogus"])
        self.assertEqual(flags["unknown"], ["--bogus"])

    def test_config_repairs_bad_values(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.environ["TERMUXAGENT_HOME"] = tmp.name
        self.addCleanup(os.environ.pop, "TERMUXAGENT_HOME", None)
        Path(tmp.name, "config.json").write_text(json.dumps(
            {"theme": "nope", "timeout": "x", "api_keys": None}))
        cfg = Config.load()
        self.assertEqual(cfg.data["theme"], "neon")
        self.assertEqual(cfg.data["timeout"], 90)
        self.assertEqual(cfg.data["api_keys"], {})

    def test_storage_home_matches_installer(self):
        os.environ.pop("TERMUXAGENT_HOME", None)
        from termuxagent.config import storage_home
        self.assertEqual(storage_home().name, ".termux-agent")

    def test_anthropic_sends_x_api_key(self):
        cfg = Config({"provider": "anthropic",
                      "api_keys": {"anthropic": "sk-ant-1234567890"}})
        self.assertEqual(cfg.headers().get("x-api-key"), "sk-ant-1234567890")
        self.assertIn("anthropic-version", cfg.headers())

    def test_interrupt_leaves_valid_transcript(self):
        from termuxagent.agent import Agent
        cfg = Config({"provider": "ollama"})
        agent = Agent(cfg, workdir=Path("."))
        agent.new_session()
        mark = len(agent.messages)
        agent.messages.append({"role": "user", "content": "do it"})
        agent.messages.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "shell", "arguments": "{}"}}]})
        agent._repair_after_interrupt(mark)
        self.assertEqual(agent.messages[-1]["role"], "tool")
        self.assertEqual(agent.messages[-1]["tool_call_id"], "c1")
