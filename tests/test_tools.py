import tempfile
import unittest
from pathlib import Path

from termuxagent.config import Config
from termuxagent.tools import ToolError, call_tool


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.tmp = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # --------------------------------------------------------------- shell
    def test_shell_stdout(self):
        out = call_tool("shell", {"command": "echo hello-termux"}, self.cfg, self.workdir)
        self.assertIn("hello-termux", out)
        self.assertIn("exit code 0", out)

    def test_shell_nonzero_exit(self):
        out = call_tool("shell", {"command": "echo oops >&2; exit 3"}, self.cfg, self.workdir)
        self.assertIn("exit code 3", out)
        self.assertIn("oops", out)

    def test_shell_timeout(self):
        self.cfg.shell_timeout = 1
        out = call_tool("shell", {"command": "sleep 5"}, self.cfg, self.workdir)
        self.assertIn("timed out", out)

    def test_shell_runs_in_workdir(self):
        (self.workdir / "marker.txt").write_text("x")
        out = call_tool("shell", {"command": "ls"}, self.cfg, self.workdir)
        self.assertIn("marker.txt", out)

    # --------------------------------------------------------------- files
    def test_write_and_read(self):
        call_tool("write_file", {"path": "a/b.txt", "content": "line1\nline2\n"}, self.cfg, self.workdir)
        out = call_tool("read_file", {"path": "a/b.txt"}, self.cfg, self.workdir)
        self.assertEqual(out, "line1\nline2\n")
        self.assertTrue((self.workdir / "a" / "b.txt").exists())

    def test_read_missing(self):
        out = call_tool("read_file", {"path": "nope.txt"}, self.cfg, self.workdir)
        self.assertIn("[error]", out)
        self.assertIn("not found", out)

    def test_edit_unique(self):
        call_tool("write_file", {"path": "f.py", "content": "x = 1\ny = 2\n"}, self.cfg, self.workdir)
        out = call_tool(
            "edit_file",
            {"path": "f.py", "old_text": "x = 1", "new_text": "x = 42"},
            self.cfg,
            self.workdir,
        )
        self.assertIn("replaced 1", out)
        self.assertEqual((self.workdir / "f.py").read_text(), "x = 42\ny = 2\n")

    def test_edit_not_found(self):
        call_tool("write_file", {"path": "f.py", "content": "abc"}, self.cfg, self.workdir)
        out = call_tool(
            "edit_file",
            {"path": "f.py", "old_text": "zzz", "new_text": "q"},
            self.cfg,
            self.workdir,
        )
        self.assertIn("[error]", out)
        self.assertIn("not found", out)

    def test_edit_ambiguous(self):
        call_tool("write_file", {"path": "f.py", "content": "a\na\n"}, self.cfg, self.workdir)
        out = call_tool(
            "edit_file",
            {"path": "f.py", "old_text": "a", "new_text": "b"},
            self.cfg,
            self.workdir,
        )
        self.assertIn("[error]", out)
        self.assertIn("2 places", out)

    def test_list_dir(self):
        (self.workdir / "z.txt").write_text("z")
        (self.workdir / "sub").mkdir()
        out = call_tool("list_dir", {"path": "."}, self.cfg, self.workdir)
        lines = out.splitlines()
        self.assertIn("sub/", lines)
        file_lines = [l for l in lines if l.startswith("z.txt")]
        self.assertEqual(len(file_lines), 1)
        # directories sort before files
        self.assertLess(lines.index("sub/"), lines.index(file_lines[0]))

    def test_list_dir_missing(self):
        out = call_tool("list_dir", {"path": "ghost"}, self.cfg, self.workdir)
        self.assertIn("[error]", out)

    def test_unknown_tool(self):
        out = call_tool("launch_rockets", {}, self.cfg, self.workdir)
        self.assertIn("unknown tool", out)

    def test_path_traversal_resolves(self):
        # ../ escapes resolve under the temp dir's parent — read must still
        # return an error string rather than crashing.
        out = call_tool("read_file", {"path": "../../../etc/hostname.missing"}, self.cfg, self.workdir)
        self.assertIsInstance(out, str)


if __name__ == "__main__":
    unittest.main()
