"""CodexReview Stop Runner：执行 review agent 的运行器"""

import datetime
import subprocess
from typing import Dict

from lib.codexreview_state import load_state, save_state


def run_review_if_needed(state_path: str, cwd: str, agent_cmd: list, prompt: str) -> Dict:
    """
    执行 review agent，并根据结果更新状态

    Args:
        state_path: 状态文件路径
        cwd: 工作目录
        agent_cmd: agent 命令列表
        prompt: 传递给 agent 的输入

    Returns:
        结果字典，包含：
        - success: bool, 是否成功
        - returncode: int, 子进程返回码
    """
    result = subprocess.run(
        agent_cmd, input=prompt, text=True, cwd=cwd, capture_output=True
    )

    if result.returncode == 0:
        # 成功：清空 pending，更新 last_review_at
        state = load_state(state_path)
        state["pending"] = {
            "events": 0,
            "files": [],
            "modules": [],
            "lines_touched_est": 0,
            "flags": {"plan_docs": False, "risk_files": False},
        }
        state["meta"]["last_review_at"] = datetime.datetime.now().isoformat()
        save_state(state_path, state)

    return {"success": result.returncode == 0, "returncode": result.returncode}