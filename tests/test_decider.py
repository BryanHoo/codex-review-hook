import unittest

from lib.codexreview_decider import should_run_review

class TestDecider(unittest.TestCase):
    def test_hard_trigger_plan_docs(self):
        st = {"pending": {"events": 1, "files": ["x"], "modules": ["m"], "lines_touched_est": 1, "flags": {"plan_docs": True, "risk_files": False}}}
        decision = should_run_review(st)
        self.assertTrue(decision["run"])
        self.assertEqual(decision["reason"], "plan_docs")

    def test_hard_trigger_risk_files(self):
        st = {"pending": {"events": 1, "files": ["x"], "modules": ["m"], "lines_touched_est": 1, "flags": {"plan_docs": False, "risk_files": True}}}
        decision = should_run_review(st)
        self.assertTrue(decision["run"])
        self.assertEqual(decision["reason"], "risk_files")

    def test_gray_zone_low_score_no_run(self):
        st = {"pending": {"events": 2, "files": ["a"], "modules": ["src"], "lines_touched_est": 10, "flags": {"plan_docs": False, "risk_files": False}}}
        decision = should_run_review(st)
        self.assertFalse(decision["run"])  # score should be low
        self.assertEqual(decision["reason"], "score_too_low")

    def test_gray_zone_high_score_runs(self):
        st = {"pending": {"events": 10, "files": ["a", "b", "c", "d", "e"], "modules": ["src", "lib", "test"], "lines_touched_est": 100, "flags": {"plan_docs": False, "risk_files": False}}}
        decision = should_run_review(st)
        self.assertTrue(decision["run"])  # score should be high (>=4)
        self.assertEqual(decision["reason"], "score_threshold_met")

    def test_score_calculation(self):
        st = {"pending": {"events": 5, "files": ["a.py", "b.py"], "modules": ["src/a"], "lines_touched_est": 30, "flags": {"plan_docs": False, "risk_files": False}}}
        decision = should_run_review(st)
        # events=5 -> score 1, files=2 -> score 1, modules=1 -> score 0, lines=30 -> score 1, total=3 (not run)
        self.assertEqual(decision["score"], 3)
        self.assertFalse(decision["run"])

    def test_score_exactly_threshold(self):
        st = {"pending": {"events": 8, "files": ["a.py", "b.py", "c.py"], "modules": ["src/a", "lib/b"], "lines_touched_est": 50, "flags": {"plan_docs": False, "risk_files": False}}}
        decision = should_run_review(st)
        # events=8 -> score 2, files=3 -> score 2, modules=2 -> score 1, lines=50 -> score 1, total=6 (run)
        self.assertGreaterEqual(decision["score"], 4)
        self.assertTrue(decision["run"])

    def test_decision_has_all_fields(self):
        st = {"pending": {"events": 1, "files": ["x"], "modules": ["m"], "lines_touched_est": 1, "flags": {"plan_docs": False, "risk_files": False}}}
        decision = should_run_review(st)
        self.assertIn("run", decision)
        self.assertIn("reason", decision)
        self.assertIn("score", decision)
        self.assertIn("metrics", decision)

if __name__ == "__main__":
    unittest.main()