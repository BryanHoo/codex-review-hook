import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from lib.codexreview_stop_runner import run_review_if_needed


class TestStopRunner(unittest.TestCase):
    def test_success_clears_pending(self):
        """成功时清空 pending，更新 meta.last_review_at"""
        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "state.json")
            cwd = td

            # 初始化状态，包含 pending 数据
            initial_state = {
                "pending": {
                    "events": 5,
                    "files": ["a.py", "b.py"],
                    "modules": ["src", "lib"],
                    "lines_touched_est": 100,
                    "flags": {"plan_docs": True, "risk_files": False},
                },
                "meta": {"last_review_at": None},
            }
            with open(state_path, "w") as f:
                json.dump(initial_state, f)

            agent_cmd = ["mock-agent"]
            prompt = "Review these files"

            # Mock subprocess.run 返回成功
            with patch("lib.codexreview_stop_runner.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                run_review_if_needed(state_path, cwd, agent_cmd, prompt)

                # 断言 subprocess.run 被正确调用
                mock_run.assert_called_once_with(
                    agent_cmd,
                    input=prompt,
                    text=True,
                    cwd=cwd,
                    capture_output=True,
                )

            # 验证 pending 被清空
            with open(state_path, "r") as f:
                result_state = json.load(f)

            self.assertEqual(result_state["pending"]["events"], 0)
            self.assertEqual(result_state["pending"]["files"], [])
            self.assertEqual(result_state["pending"]["modules"], [])
            self.assertEqual(result_state["pending"]["lines_touched_est"], 0)
            self.assertEqual(result_state["pending"]["flags"], {"plan_docs": False, "risk_files": False})
            # 验证 last_review_at 被更新
            self.assertIsNotNone(result_state["meta"]["last_review_at"])

    def test_failure_preserves_pending(self):
        """失败时保留 pending 不变"""
        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "state.json")
            cwd = td

            # 初始化状态
            initial_state = {
                "pending": {
                    "events": 3,
                    "files": ["a.py"],
                    "modules": ["src"],
                    "lines_touched_est": 50,
                    "flags": {"plan_docs": False, "risk_files": True},
                },
                "meta": {"last_review_at": "2025-01-01"},
            }
            with open(state_path, "w") as f:
                json.dump(initial_state, f)

            agent_cmd = ["mock-agent"]
            prompt = "Review these files"

            # Mock subprocess.run 返回失败
            with patch("lib.codexreview_stop_runner.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="error")

                run_review_if_needed(state_path, cwd, agent_cmd, prompt)

            # 验证 pending 保持不变
            with open(state_path, "r") as f:
                result_state = json.load(f)

            self.assertEqual(result_state["pending"]["events"], 3)
            self.assertEqual(result_state["pending"]["files"], ["a.py"])
            self.assertEqual(result_state["pending"]["modules"], ["src"])
            self.assertEqual(result_state["pending"]["lines_touched_est"], 50)
            self.assertEqual(result_state["pending"]["flags"], {"plan_docs": False, "risk_files": True})
            # last_review_at 保持不变
            self.assertEqual(result_state["meta"]["last_review_at"], "2025-01-01")


if __name__ == "__main__":
    unittest.main()