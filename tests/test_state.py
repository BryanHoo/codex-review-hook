import io
import json
import os
import tempfile
import unittest

from lib.codexreview_state import update_state_from_post_tool_use, load_state

class TestState(unittest.TestCase):
    def test_record_edit_updates_pending(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "s.json")
            event = {
                "session_id": "s",
                "cwd": td,
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": os.path.join(td, "src", "a.py"),
                    "old_string": "a\n",
                    "new_string": "b\n\nc\n",
                },
                "tool_use_id": "toolu_1",
            }
            update_state_from_post_tool_use(event, state_path)
            st = load_state(state_path)
            self.assertEqual(st["pending"]["events"], 1)
            self.assertIn(os.path.join(td, "src", "a.py"), st["pending"]["files"])
            self.assertGreaterEqual(st["pending"]["lines_touched_est"], 3)

if __name__ == "__main__":
    unittest.main()