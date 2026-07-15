"""路径解析器：以 POWERELF_SKILLS_ROOT 为基准定位 _shared/ 下资源。

优先级:
  1. POWERELF_SKILLS_ROOT 环境变量（部署契约）
  2. 候选根兜底（从 __file__ 推算、symlink 解析、hermes skills 目录）

用法:
  from bootstrap import locate_shared, locate_shared_lib
  shared_dir = locate_shared()
  shared_lib = locate_shared_lib()

  # 然后直接用路径引用共享文件：
  import sys; sys.path.insert(0, str(locate_shared_lib()))
  from db import get_connection
"""
import os
from pathlib import Path

_LIB_MARKER = "bootstrap.py"  # 自身作为 marker

_KNOWN_ROOTS = (
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")),  # repo 根
    str(Path.home() / ".hermes" / "skills" / "powerelf"),
)


def _root() -> Path | None:
    r = os.environ.get("POWERELF_SKILLS_ROOT")
    if r and Path(r).is_dir():
        return Path(r)
    for c in _KNOWN_ROOTS:
        if (Path(c) / "_shared" / "lib" / _LIB_MARKER).exists():
            return Path(c)
    return None


def locate_shared() -> Path:
    r = _root()
    if r and (r / "_shared").is_dir():
        return r / "_shared"
    raise RuntimeError(
        "powerelf _shared/ not found. Set POWERELF_SKILLS_ROOT "
        "in the deployment environment."
    )


def locate_shared_lib() -> Path:
    return locate_shared() / "lib"