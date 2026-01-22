import os
import subprocess
import tempfile
import unittest

from lib.codexreview_state import load_state, save_state, DEFAULT_STATE
from lib.codexreview_decider import should_run_review


class TestGitNumstat(unittest.TestCase):

    def test_default_state_has_lines_touched_git(self):
        """验证 DEFAULT_STATE 包含 lines_touched_git 字段"""
        self.assertIn("lines_touched_git", DEFAULT_STATE["pending"])
        self.assertIsNone(DEFAULT_STATE["pending"]["lines_touched_git"])

    def test_decider_prefers_lines_touched_git_over_est(self):
        """验证打分时优先使用 lines_touched_git，否则退回 lines_touched_est"""
        # 当 lines_touched_git 有值时，应使用它计算评分
        st = {
            "pending": {
                "events": 10,
                "files": ["a.py", "b.py", "c.py", "d.py"],
                "modules": ["src/a", "lib/b"],
                "lines_touched_est": 10,  # 估计值较小
                "lines_touched_git": 100,  # git numstat 值较大
                "flags": {"plan_docs": False, "risk_files": False},
            }
        }
        decision = should_run_review(st)
        # lines=100 -> score 2，总评分应 >= 4
        self.assertGreaterEqual(decision["score"], 4)
        self.assertTrue(decision["run"])

        # 当 lines_touched_git 为 None 时，应退回使用 lines_touched_est
        st["pending"]["lines_touched_git"] = None
        decision = should_run_review(st)
        # lines=10 -> score 0，总评分应较低
        self.assertEqual(decision["score"], 5)  # events=2 + files=2 + modules=1 + lines=0
        self.assertTrue(decision["run"])  # 仍然触发因为其他指标足够

    def test_compute_git_numstat_in_temp_repo(self):
        """在临时 git repo 中测试 numstat 计算"""
        with tempfile.TemporaryDirectory() as td:
            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=td, check=True, capture_output=True)

            # 创建初始文件并提交
            test_file = os.path.join(td, "test.py")
            with open(test_file, "w") as f:
                f.write("line1\nline2\nline3\n")
            subprocess.run(["git", "add", "test.py"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=td, check=True, capture_output=True)

            # 修改文件
            with open(test_file, "w") as f:
                f.write("line1\nline2\nline3\nline4\nline5\n")

            # 计算未暂存变更的 numstat
            result = subprocess.run(
                ["git", "diff", "--numstat"],
                cwd=td,
                check=True,
                capture_output=True,
                text=True
            )
            output = result.stdout.strip()

            # 验证 numstat 输出格式
            # 格式: <added> <deleted> <filename>
            parts = output.split()
            self.assertEqual(len(parts), 3)
            added = int(parts[0])
            deleted = int(parts[1])

            # 我们添加了 2 行，删除了 0 行
            self.assertEqual(added, 2)
            self.assertEqual(deleted, 0)

    def test_git_numstat_with_staged_changes(self):
        """测试暂存变更的 numstat 计算"""
        with tempfile.TemporaryDirectory() as td:
            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=td, check=True, capture_output=True)

            # 创建初始文件并提交
            test_file = os.path.join(td, "test.py")
            with open(test_file, "w") as f:
                f.write("line1\nline2\nline3\n")
            subprocess.run(["git", "add", "test.py"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=td, check=True, capture_output=True)

            # 修改文件并暂存
            with open(test_file, "w") as f:
                f.write("line1\nmodified\nline3\nline4\n")
            subprocess.run(["git", "add", "test.py"], cwd=td, check=True, capture_output=True)

            # 计算暂存变更的 numstat
            result = subprocess.run(
                ["git", "diff", "--cached", "--numstat"],
                cwd=td,
                check=True,
                capture_output=True,
                text=True
            )
            output = result.stdout.strip()

            parts = output.split()
            added = int(parts[0])
            deleted = int(parts[1])

            # 删除了 1 行 (line2)，添加了 2 行 (modified, line4)
            self.assertEqual(added, 2)
            self.assertEqual(deleted, 1)

    def test_git_numstat_mixed_changes(self):
        """测试混合变更（暂存+未暂存）的 numstat 计算"""
        with tempfile.TemporaryDirectory() as td:
            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=td, check=True, capture_output=True)

            # 创建初始文件并提交
            test_file = os.path.join(td, "test.py")
            with open(test_file, "w") as f:
                f.write("line1\nline2\nline3\n")
            subprocess.run(["git", "add", "test.py"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=td, check=True, capture_output=True)

            # 暂存部分修改
            with open(test_file, "w") as f:
                f.write("line1\nline2\nline3\nline4\n")
            subprocess.run(["git", "add", "test.py"], cwd=td, check=True, capture_output=True)

            # 再做未暂存的修改
            with open(test_file, "w") as f:
                f.write("line1\nline2\nline3\nline4\nline5\nline6\n")

            # 计算 HEAD 到工作目录的总变更
            result = subprocess.run(
                ["git", "diff", "HEAD", "--numstat"],
                cwd=td,
                check=True,
                capture_output=True,
                text=True
            )
            output = result.stdout.strip()

            parts = output.split()
            added = int(parts[0])
            deleted = int(parts[1])

            # 总共添加了 3 行
            self.assertEqual(added, 3)
            self.assertEqual(deleted, 0)

    def test_git_numstat_multiple_files(self):
        """测试多文件变更的 numstat 计算"""
        with tempfile.TemporaryDirectory() as td:
            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=td, check=True, capture_output=True)

            # 创建两个初始文件并提交
            file1 = os.path.join(td, "file1.py")
            file2 = os.path.join(td, "file2.py")
            with open(file1, "w") as f:
                f.write("line1\nline2\n")
            with open(file2, "w") as f:
                f.write("line1\n")
            subprocess.run(["git", "add", "."], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=td, check=True, capture_output=True)

            # 修改两个文件
            with open(file1, "w") as f:
                f.write("line1\nline2\nline3\nline4\n")  # +2
            with open(file2, "w") as f:
                f.write("line1\nline2\n")  # +1

            # 计算总变更
            result = subprocess.run(
                ["git", "diff", "--numstat"],
                cwd=td,
                check=True,
                capture_output=True,
                text=True
            )
            output = result.stdout.strip()

            lines = output.split("\n")
            self.assertEqual(len(lines), 2)

            total_added = 0
            for line in lines:
                parts = line.split()
                total_added += int(parts[0])

            # 总共添加了 3 行
            self.assertEqual(total_added, 3)

    def test_is_inside_work_tree(self):
        """测试 git rev-parse --is-inside-work-tree"""
        with tempfile.TemporaryDirectory() as td:
            # 非 git 目录
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=td,
                capture_output=True,
                text=True
            )
            self.assertNotEqual(result.returncode, 0)

            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=td, check=True, capture_output=True)

            # git 目录
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=td,
                check=True,
                capture_output=True,
                text=True
            )
            self.assertEqual(result.stdout.strip(), "true")


if __name__ == "__main__":
    unittest.main()