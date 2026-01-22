import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestCodeagentResolver(unittest.TestCase):
    def test_env_override_wins(self):
        from lib.codexreview_codeagent import resolve_agent_cmd

        with patch.dict(os.environ, {"CODEXREVIEW_AGENT_CMD": "myagent --flag"}, clear=False):
            cmd = resolve_agent_cmd(Path("/tmp/does-not-matter"))
            self.assertEqual(cmd, ["myagent", "--flag"])

    def test_env_override_json_array(self):
        from lib.codexreview_codeagent import resolve_agent_cmd

        with patch.dict(
            os.environ,
            {"CODEXREVIEW_AGENT_CMD": '["/opt/codeagent/bin/codeagent","--flag"]'},
            clear=False,
        ):
            cmd = resolve_agent_cmd(Path("/tmp/does-not-matter"))
            self.assertEqual(cmd, ["/opt/codeagent/bin/codeagent", "--flag"])

    def test_packaged_binary_selected_by_platform(self):
        from lib.codexreview_codeagent import resolve_agent_cmd

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "codeagent").mkdir(parents=True, exist_ok=True)
            bin_path = root / "codeagent" / "codeagent-wrapper-darwin-amd64"
            bin_path.write_bytes(b"fake")

            with patch(
                "lib.codexreview_codeagent._detect_platform",
                return_value=("darwin", "x86_64"),
            ):
                cmd = resolve_agent_cmd(root)
                self.assertEqual(cmd, [str(bin_path)])

    def test_missing_packaged_binary_falls_back_to_path(self):
        from lib.codexreview_codeagent import resolve_agent_cmd

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.dict(os.environ, {}, clear=True), patch(
                "lib.codexreview_codeagent._detect_platform",
                return_value=("darwin", "x86_64"),
            ):
                cmd = resolve_agent_cmd(root)
                self.assertEqual(cmd, ["codeagent"])


if __name__ == "__main__":
    unittest.main()
