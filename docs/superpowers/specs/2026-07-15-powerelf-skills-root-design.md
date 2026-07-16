# POWERELF_SKILLS_ROOT: 环境变量驱动的路径解析方案

## 问题

当前 powerelf-skills 各模块引用 `_shared/` 共享目录时，使用硬编码相对路径：

- `powerelf-*/lib/db.py`: `os.path.join(.., "..", "_shared", "lib", "db.py")`
- `_shared/bootstrap.sh`: `dirname $BASH_SOURCE` + `../_shared/lib/db.py`
- 各 `lib/*.py` docstring: `../_shared/references/xxx`

这要求各 skill 必须位于 `powerelf-skills/<skill>/` 固定目录深度下，部署在不同路径或容器中时需要修改代码。

## 方案

新增 `POWERELF_SKILLS_ROOT` 环境变量作为基准路径，统一所有 `_shared/` 引用。

参考项目：[water-resources-skills](/opt/git/water-resources-skills/skills/lib/bootstrap.py) 的 `WATER_RESOURCES_ROOT` 模式。

## 变更范围

### 1. `_shared/lib/bootstrap.py`（新建）

路径解析器，优先级链：
1. `POWERELF_SKILLS_ROOT` 环境变量（部署契约）
2. `POWERELF_SKILLS_ROOT_LIB` / `POWERELF_SKILLS_ROOT_SHARED` 显式覆盖
3. 候选根兜底（从 `__file__` 推算、symlink 解析、hermes skills 目录）

```python
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
```

### 2. `powerelf-*/lib/db.py` shim（修改每个 skill）

```python
import importlib.util
import os

# POWERELF_SKILLS_ROOT 优先 → 相对路径兜底（开发环境）
_root = os.environ.get("POWERELF_SKILLS_ROOT")
if _root:
    _SHARED_DB = os.path.join(_root, "_shared", "lib", "db.py")
else:
    _SHARED_DB = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "_shared", "lib", "db.py")
    )

if not os.path.isfile(_SHARED_DB):
    raise ImportError(
        f"找不到共享数据库层：{_SHARED_DB}\n"
        "请设置 POWERELF_SKILLS_ROOT 环境变量指向 powerelf-skills 根目录。"
    )

_spec = importlib.util.spec_from_file_location("_shared_db", _SHARED_DB)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# re-export
get_connection = _mod.get_connection
get_sqlalchemy_url = _mod.get_sqlalchemy_url
create_engine = _mod.create_engine
DB_HOST = _mod.DB_HOST
DB_PORT = _mod.DB_PORT
DB_NAME = _mod.DB_NAME
DB_USER = _mod.DB_USER
DB_PASSWORD = _mod.DB_PASSWORD
```

涉及 skill：`powerelf-data-governance`、`powerelf-inspection`、`powerelf-chatbi`、`powerelf-early-warning`、`powerelf-monitor`

### 3. `_shared/bootstrap.sh`（修改）

```bash
_HERE="${POWERELF_SKILLS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)}"
export DB_URL="$(python3 -c "import sys; sys.path.insert(0,'$_HERE/_shared/lib'); from db import get_sqlalchemy_url; print(get_sqlalchemy_url())" 2>/dev/null)"
```

### 4. `.env.example`（追加）

```bash
# === 路径配置 ===
# POWERELF_SKILLS_ROOT=部署时指向 powerelf-skills 仓库根目录
# 不设置则自动从 symlink / 相对路径推算（开发环境默认可用）
POWERELF_SKILLS_ROOT=/home/scada/powerelf-skills
```

### 5. 各 `SKILL.md` 标准导入片段（更新）

在"数据库连接"章节补充 `POWERELF_SKILLS_ROOT` 方式的导入示范：

```python
# 部署环境（推荐）：通过环境变量定位
import sys, os
sys.path.insert(0, os.path.join(os.environ['POWERELF_SKILLS_ROOT'], '_shared', 'lib'))
from db import get_connection, get_sqlalchemy_url

# 开发环境（自动推算）：通过 bootstrap 解析
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '_shared', 'lib'))
from db import get_connection
```

## 向后兼容

- `POWERELF_SKILLS_ROOT` 未设置时，回落当前相对路径逻辑，**开发环境零改动**
- 部署环境只需在 `~/.hermes/.env` 加一行 `POWERELF_SKILLS_ROOT=/opt/deploy/powerelf-skills`
- 所有现有 API 签名不变

## 测试验证

```bash
# 1. 不设环境变量，验证兜底仍正常
python3 -c "from lib.db import get_connection; print('OK')"

# 2. 设 POWERELF_SKILLS_ROOT 为正确路径
POWERELF_SKILLS_ROOT=/home/scada/powerelf-skills \
  python3 -c "from lib.db import get_connection; print('OK')"

# 3. 设 POWERELF_SKILLS_ROOT 为无效路径，验证错误提示
POWERELF_SKILLS_ROOT=/invalid/path \
  python3 -c "from lib.db import get_connection" 2>&1 | grep -q 'Set POWERELF_SKILLS_ROOT'

# 4. bootstrap 模块直接测试
python3 _shared/lib/bootstrap.py -c "from bootstrap import locate_shared; print(locate_shared())"
```