import os
import tempfile
import unittest

from lib.codexreview_state import update_state_from_post_tool_use, load_state

class TestRuleFlags(unittest.TestCase):
    def test_plan_docs_sets_flag(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "s.json")
            event = {
                "session_id": "s",
                "cwd": td,
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": os.path.join(td, "docs", "plans", "2026-01-22-x-design.md"),
                    "old_string": "a\n",
                    "new_string": "b\n",
                },
                "tool_use_id": "toolu_1",
            }
            update_state_from_post_tool_use(event, state_path)
            st = load_state(state_path)
            self.assertTrue(st["pending"]["flags"]["plan_docs"])

    def test_risk_files_sets_flag(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "s.json")
            event = {
                "session_id": "s",
                "cwd": td,
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": os.path.join(td, "package.json"),
                    "content": "{}\n",
                },
                "tool_use_id": "toolu_2",
            }
            update_state_from_post_tool_use(event, state_path)
            st = load_state(state_path)
            self.assertTrue(st["pending"]["flags"]["risk_files"])

if __name__ == "__main__":
    unittest.main()