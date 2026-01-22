"""CodexReview codeagent-wrapper 本地解析与校验（离线分发）"""

from __future__ import annotations

import json
import os
import platform
import shlex
import sys
from pathlib import Path
from typing import List, Mapping, Optional, Tuple


def _truthy_env(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return default


def _detect_platform() -> Tuple[str, str]:
    sp = sys.platform
    if sp.startswith("darwin"):
        os_name = "darwin"
    elif sp.startswith("linux"):
        os_name = "linux"
    elif sp.startswith("win"):
        os_name = "windows"
    else:
        os_name = sp

    machine = platform.machine().lower()
    return os_name, machine


def _normalize_arch(machine: str) -> str:
    m = machine.lower()
    if m in ("x86_64", "amd64"):
        return "amd64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    return m


def _asset_filename(os_name: str, arch: str) -> str:
    suffix = ".exe" if os_name == "windows" else ""
    return f"codeagent-wrapper-{os_name}-{arch}{suffix}"


def resolve_packaged_binary(project_root: Path) -> Optional[Path]:
    os_name, machine = _detect_platform()
    arch = _normalize_arch(machine)
    filename = _asset_filename(os_name, arch)

    candidate = project_root / "codeagent" / filename
    if candidate.exists():
        return candidate
    return None


def resolve_agent_cmd(project_root: Path, env: Mapping[str, str] | None = None) -> List[str]:
    """
    解析用于执行 review 的 agent 命令。

    优先级：
    1) 显式环境变量 `CODEXREVIEW_AGENT_CMD`
    2) 仓库内离线分发的 `codeagent/codeagent-wrapper-<os>-<arch>[.exe]`
    3) PATH 中的 `codeagent`
    """
    if env is None:
        env = os.environ

    override = env.get("CODEXREVIEW_AGENT_CMD")
    if override:
        s = override.strip()
        # 允许用 JSON 数组指定命令，避免 Windows 路径/空格/引号导致的解析差异：
        # 例如：["C:\\Program Files\\codeagent\\codeagent.exe","--flag"]
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed) and parsed:
                    return parsed
            except Exception:
                pass

        # 兼容传统写法（需要在含空格路径时自行加引号）
        return shlex.split(override)

    packaged = resolve_packaged_binary(project_root)
    if packaged is None:
        return ["codeagent"]

    # 确保在类 Unix 上可执行（Windows 不做处理）
    if not packaged.name.lower().endswith(".exe"):
        try:
            mode = packaged.stat().st_mode
            packaged.chmod(mode | 0o111)
        except Exception:
            pass

    return [str(packaged)]
