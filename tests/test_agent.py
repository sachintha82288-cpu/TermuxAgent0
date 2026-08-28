import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from termuxagent import llm
from termuxagent.agent import Agent
from termuxagent.config import Config


def fake_chat_stream(messages, **kwargs):
    """Drive the agent loop: first call requests a shell tool, second answers."""
    last = messages[-1]
    if last["role"] != "tool":
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "shell", "arguments": json.dumps({"command": "echo pong"})},
                }
            ],
        }
    return {"role": "assistant", "content": "Done: " + last["content"]}


def fake_chat_plain(messages, **kwargs):
    return {"role": "assistant", "content": "plain answer"}


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.tmp = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _agent(self, approve=None):
        return Agent(
            self.cfg,
            workdir=self.workdir,
            on_content=None,
            approve=approve or (lambda name, args: True),
        )

    def test_tool_loop_runs_shell(self):
        with mock.patch("termuxagent.agent.chat", side_effect=fake_chat_stream):
            reply = self._agent().chat("ping")
        self.assertIn("pong", reply)
        self.assertIn("exit code 0", reply)

    def test_denied_tool(self):
        seen = {}

        def fake(messages, **kwargs):
            if messages[-1]["role"] == "tool":
                seen["result"] = messages[-1]["content"]
                return {"role": "assistant", "content": "ok"}
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c",
                        "type": "function",
                        "function": {"name": "shell", "arguments": '{"command": "rm -rf /"}'},
                    }
                ],
            }

        with mock.patch("termuxagent.agent.chat", side_effect=fake):
            agent = self._agent(approve=lambda name, args: False)
            agent.chat("destroy")
        self.assertEqual(seen["result"], "[denied by user]")

    def test_plain_chat(self):
        with mock.patch("termuxagent.agent.chat", side_effect=fake_chat_plain):
            reply = self._agent().chat("hi")
        self.assertEqual(reply, "plain answer")

    def test_bad_json_arguments(self):
        def fake(messages, **kwargs):
            if messages[-1]["role"] == "tool":
                return {"role": "assistant", "content": "recovered:" + messages[-1]["content"][:30]}
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "c", "type": "function",
                     "function": {"name": "read_file", "arguments": "{not json"}}
                ],
            }

        with mock.patch("termuxagent.agent.chat", side_effect=fake):
            agent = self._agent()
            reply = agent.chat("x")
        self.assertTrue(reply.startswith("recovered:"))
        tool_msg = [m for m in agent.messages if m["role"] == "tool"][0]
        self.assertIn("not valid JSON", tool_msg["content"])

    def test_iteration_cap(self):
        always_tool = mock.Mock(return_value={
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "c", "type": "function",
                 "function": {"name": "shell", "arguments": '{"command": "true"}'}}
            ],
        })
        with mock.patch("termuxagent.agent.chat", always_tool):
            reply = self._agent().chat("loop")
        self.assertIn("maximum number of tool steps", reply)
        self.assertLessEqual(always_tool.call_count, 12)

    def test_history_persists_without_system(self):
        with tempfile.TemporaryDirectory() as home:
            import os
            os.environ["TERMUXAGENT_HOME"] = home
            try:
                from termuxagent import history
                history.history_path().unlink(missing_ok=True)
                with mock.patch("termuxagent.agent.chat", side_effect=fake_chat_plain):
                    agent = self._agent()
                    agent.chat("remember this")
                    agent.persist()
                saved = json.loads(history.history_path().read_text())
                self.assertTrue(all(m["role"] != "system" for m in saved))
                self.assertTrue(any(m["role"] == "user" for m in saved))
            finally:
                os.environ.pop("TERMUXAGENT_HOME", None)

    def test_empty_response_raises(self):
        with mock.patch("termuxagent.agent.chat",
                        return_value={"role": "assistant", "content": ""}):
            with self.assertRaises(Exception) as ctx:
                self._agent().chat("x")
            self.assertIn("empty response", str(ctx.exception))

    def test_system_prompt_mentions_workdir(self):
        agent = self._agent()
        sysprompt = agent.messages[0]["content"]
        self.assertIn(str(self.workdir), sysprompt)


class StreamingAccumulatorTests(unittest.TestCase):
    def test_accumulates_content_and_tool_call(self):
        acc = llm.StreamingChatCompletion()
        for delta in [
            {"content": "Hel"},
            {"content": "lo"},
            {"tool_calls": [{"index": 0, "id": "x", "function": {"name": "shell", "arguments": ""}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": '{"command":'}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": ' "echo hi"}'}}]},
        ]:
            if "content" in delta:
                acc.content += delta["content"]
            for tc in delta.get("tool_calls", []):
                llm._merge_tool_delta(acc, tc)
        msg = acc.to_message()
        self.assertEqual(msg["content"], "Hello")
        self.assertEqual(msg["tool_calls"][0]["id"], "x")
        self.assertEqual(msg["tool_calls"][0]["function"]["name"], "shell")
        args = json.loads(msg["tool_calls"][0]["function"]["arguments"])
        self.assertEqual(args["command"], "echo hi")


if __name__ == "__main__":
    unittest.main()
