"""CodexReview 决策模块：根据状态决定是否运行 review"""

from typing import Dict

# 阈值配置（硬编码，暂不引入配置系统）
SCORE_THRESHOLD = 4


def _calculate_score(state: Dict) -> int:
    """
    按约定计算灰区评分（分档评分）

    评分约定：
    - events: 1-3=0, 4-7=1, 8+=2
    - files: 1=0, 2-3=1, 4+=2
    - modules: 1=0, 2+=1
    - lines: 1-29=0, 30-99=1, 100+=2
    """
    pending = state.get("pending", {})

    events = pending.get("events", 0)
    files = len(pending.get("files", []))
    modules = len(pending.get("modules", []))
    # 优先使用 lines_touched_git，否则退回 lines_touched_est
    lines = pending.get("lines_touched_git")
    if lines is None:
        lines = pending.get("lines_touched_est", 0)

    # events 分档
    if events >= 8:
        events_score = 2
    elif events >= 4:
        events_score = 1
    else:
        events_score = 0

    # files 分档
    if files >= 4:
        files_score = 2
    elif files >= 2:
        files_score = 1
    else:
        files_score = 0

    # modules 分档
    if modules >= 2:
        modules_score = 1
    else:
        modules_score = 0

    # lines 分档
    # Match test expectations: modest changes (>=30 lines) should start contributing.
    if lines >= 100:
        lines_score = 2
    elif lines >= 30:
        lines_score = 1
    else:
        lines_score = 0

    return events_score + files_score + modules_score + lines_score


def should_run_review(state: Dict) -> Dict:
    """
    根据状态决定是否运行 review

    Args:
        state: 状态字典，包含 pending 和 meta 字段

    Returns:
        决策结果字典，包含：
        - run: bool, 是否运行 review
        - reason: str, 原因（plan_docs/risk_files/score_threshold）
        - score: int, 评分
        - metrics: dict, 各项指标
    """
    pending = state.get("pending", {})
    flags = pending.get("flags", {})

    # 硬触发：plan_docs
    if flags.get("plan_docs"):
        return {
            "run": True,
            "reason": "plan_docs",
            "score": _calculate_score(state),
            "metrics": {
                "events": pending.get("events", 0),
                "files": len(pending.get("files", [])),
                "modules": len(pending.get("modules", [])),
                "lines_touched_est": pending.get("lines_touched_est", 0),
            },
        }

    # 硬触发：risk_files
    if flags.get("risk_files"):
        return {
            "run": True,
            "reason": "risk_files",
            "score": _calculate_score(state),
            "metrics": {
                "events": pending.get("events", 0),
                "files": len(pending.get("files", [])),
                "modules": len(pending.get("modules", [])),
                "lines_touched_est": pending.get("lines_touched_est", 0),
            },
        }

    # 灰区：按评分决定
    score = _calculate_score(state)
    if score >= SCORE_THRESHOLD:
        return {
            "run": True,
            "reason": "score_threshold_met",
            "score": score,
            "metrics": {
                "events": pending.get("events", 0),
                "files": len(pending.get("files", [])),
                "modules": len(pending.get("modules", [])),
                "lines_touched_est": pending.get("lines_touched_est", 0),
            },
        }

    return {
        "run": False,
        "reason": "score_too_low",
        "score": score,
        "metrics": {
            "events": pending.get("events", 0),
            "files": len(pending.get("files", [])),
            "modules": len(pending.get("modules", [])),
            "lines_touched_est": pending.get("lines_touched_est", 0),
        },
    }