# POWERELF_SKILLS_ROOT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `POWERELF_SKILLS_ROOT` 环境变量，作为 `_shared/` 路径定位的基准，消除硬编码相对路径，部署时零代码修改。

**Architecture:** 新增 `_shared/lib/bootstrap.py`（path resolver），修改 2 个 `lib/db.py` shim 优先读取环境变量，修改 `bootstrap.sh` 和 `.env.example`，更新各 SKILL.md 导入片段。POWERELF_SKILLS_ROOT 未设时自动回落当前相对路径逻辑，开发环境零改动。

**Tech Stack:** Python 3, os.environ, pathlib

**Files:**
- Create: `_shared/lib/bootstrap.py`
- Modify: `powerelf-data-governance/lib/db.py`
- Modify: `powerelf-inspection/lib/db.py`
- Modify: `_shared/bootstrap.sh`
- Modify: `.env.example`
- Modify: `powerelf-data-governance/SKILL.md`
- Modify: `powerelf-inspection/SKILL.md`
- Modify: `powerelf-chatbi/SKILL.md`
- Modify: `powerelf-monitor/SKILL.md`
- Modify: `powerelf-early-warning/SKILL.md`

---

### Task 1: 新建 `_shared/lib/bootstrap.py`

**Files:**
- Create: `_shared/lib/bootstrap.py`

**Interfaces:**
- Produces: `locate_shared() -> Path` — 返回 `_shared/` 绝对路径
- Produces: `locate_shared_lib() -> Path` — 返回 `_shared/lib/` 绝对路径

- [ ] **Step 1: 写 bootstrap.py**

```python
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
```

- [ ] **Step 2: 验证 bootstrap.py 导入正常**

```bash
cd /home/scada/powerelf-skills
python3 -c "
import sys; sys.path.insert(0, '_shared/lib')
from bootstrap import locate_shared, locate_shared_lib
print('shared:', locate_shared())
print('lib:', locate_shared_lib())
"
```

预期输出（路径按实际）：
```
shared: /home/scada/powerelf-skills/_shared
lib: /home/scada/powerelf-skills/_shared/lib
```

- [ ] **Step 3: 验证 POWERELF_SKILLS_ROOT 环境变量生效**

```bash
cd /home/scada/powerelf-skills
POWERELF_SKILLS_ROOT=/home/scada/powerelf-skills python3 -c "
import sys; sys.path.insert(0, '_shared/lib')
from bootstrap import locate_shared
assert 'powerelf-skills/_shared' in str(locate_shared())
print('OK: env var works')
"
```

- [ ] **Step 4: 验证无效路径给出友好错误**

```bash
cd /home/scada/powerelf-skills
POWERELF_SKILLS_ROOT=/nonexistent python3 -c "
import sys; sys.path.insert(0, '_shared/lib')
from bootstrap import locate_shared
try:
    locate_shared()
    print('FAIL: should have raised')
except RuntimeError as e:
    print('OK:', e)
" 2>&1
```

预期输出包含 `Set POWERELF_SKILLS_ROOT`。

- [ ] **Step 5: Commit**

```bash
git add _shared/lib/bootstrap.py
git commit -m "feat(_shared): add bootstrap.py as POWERELF_SKILLS_ROOT path resolver"
```

---

### Task 2: 修改 `powerelf-data-governance/lib/db.py` shim

**Files:**
- Modify: `powerelf-data-governance/lib/db.py`

**Interfaces:**
- Consumes: `POWERELF_SKILLS_ROOT` env var (optional)
- Produces: 同现有 `get_connection, get_sqlalchemy_url, create_engine, DB_*` — 接口不变

- [ ] **Step 1: 修改 db.py 添加 POWERELF_SKILLS_ROOT 优先判断**

在 import 段后、`_SHARED_DB` 赋值处：

```python
# POWERELF_SKILLS_ROOT 优先（部署环境）→ 相对路径兜底（开发环境）
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
```

- [ ] **Step 2: 测试无环境变量时回落正常**

```bash
cd /home/scada/powerelf-skills/powerelf-data-governance
python3 -c "from lib.db import get_connection; print('OK: no-env fallback works')"
```

- [ ] **Step 3: 测试环境变量生效**

```bash
cd /home/scada/powerelf-skills/powerelf-data-governance
POWERELF_SKILLS_ROOT=/home/scada/powerelf-skills \
  python3 -c "from lib.db import get_connection; print('OK: env var works')"
```

- [ ] **Step 4: 测试无效路径的错误提示**

```bash
cd /home/scada/powerelf-skills/powerelf-data-governance
POWERELF_SKILLS_ROOT=/invalid/path \
  python3 -c "from lib.db import get_connection" 2>&1 | grep -q 'Set POWERELF_SKILLS_ROOT' && echo 'OK: error message' || echo 'FAIL'
```

- [ ] **Step 5: Commit**

```bash
git add powerelf-data-governance/lib/db.py
git commit -m "feat(data-governance): add POWERELF_SKILLS_ROOT env var support in db.py shim"
```

---

### Task 3: 修改 `powerelf-inspection/lib/db.py` shim

**Files:**
- Modify: `powerelf-inspection/lib/db.py`

**Interfaces:**
- Consumes: `POWERELF_SKILLS_ROOT` env var (optional)
- Produces: 同现有 `get_connection, get_sqlalchemy_url, create_engine, DB_*` — 接口不变

- [ ] **Step 1: 修改 db.py（与 Task 2 Step 1 完全相同的修改）**

```python
# POWERELF_SKILLS_ROOT 优先（部署环境）→ 相对路径兜底（开发环境）
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
```

- [ ] **Step 2: 测试无 env var 回落正常**

```bash
cd /home/scada/powerelf-skills/powerelf-inspection
python3 -c "from lib.db import get_connection; print('OK: no-env fallback works')"
```

- [ ] **Step 3: 测试 env var 生效**

```bash
cd /home/scada/powerelf-skills/powerelf-inspection
POWERELF_SKILLS_ROOT=/home/scada/powerelf-skills \
  python3 -c "from lib.db import get_connection; print('OK: env var works')"
```

- [ ] **Step 4: Commit**

```bash
git add powerelf-inspection/lib/db.py
git commit -m "feat(inspection): add POWERELF_SKILLS_ROOT env var support in db.py shim"
```

---

### Task 4: 修改 `_shared/bootstrap.sh`

**Files:**
- Modify: `_shared/bootstrap.sh`

**Interfaces:**
- Consumes: `POWERELF_SKILLS_ROOT` env var (optional)
- Produces: `DB_URL`, `RO_DB_URL` 环境变量

- [ ] **Step 1: 修改 `_HERE` 赋值**

```bash
_HERE="${POWERELF_SKILLS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)}"
```

- [ ] **Step 2: 测试无 env var 回落正常**

```bash
cd /home/scada/powerelf-skills
source _shared/bootstrap.sh 2>&1 | head -5
```

预期输出 `DB_URL 已设置`。

- [ ] **Step 3: 测试 env var 生效**

```bash
cd /tmp
POWERELF_SKILLS_ROOT=/home/scada/powerelf-skills \
  bash -c 'source /home/scada/powerelf-skills/_shared/bootstrap.sh' 2>&1 | head -5
```

预期输出 `DB_URL 已设置`。

- [ ] **Step 4: Commit**

```bash
git add _shared/bootstrap.sh
git commit -m "feat(_shared): add POWERELF_SKILLS_ROOT support in bootstrap.sh"
```

---

### Task 5: 追加 `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: 在文件末尾追加路径配置节**

```bash
# === 路径配置 ===
# POWERELF_SKILLS_ROOT=部署时指向 powerelf-skills 仓库根目录
# 不设置则自动从 symlink / 相对路径推算（开发环境默认可用）
# POWERELF_SKILLS_ROOT=/home/scada/powerelf-skills
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add POWERELF_SKILLS_ROOT to .env.example"
```

---

### Task 6: 更新各 SKILL.md 导入片段

**Files:**
- Modify: `powerelf-data-governance/SKILL.md`
- Modify: `powerelf-inspection/SKILL.md`
- Modify: `powerelf-chatbi/SKILL.md`
- Modify: `powerelf-monitor/SKILL.md`
- Modify: `powerelf-early-warning/SKILL.md`

**范围：** 在"数据库连接"或"标准导入"章节补充 POWERELF_SKILLS_ROOT 方式。

- [ ] **Step 1: 更新 powerelf-data-governance/SKILL.md**

在 `## 数据库连接` 章节的 `sys.path.insert` 部分上方追加：

````markdown
**部署环境（推荐）：通过环境变量定位**
```python
import sys, os
sys.path.insert(0, os.path.join(os.environ['POWERELF_SKILLS_ROOT'], '_shared', 'lib'))
from db import get_connection, get_sqlalchemy_url
```
````

- [ ] **Step 2: 更新 powerelf-inspection/SKILL.md**

同样追加部署环境导入片段。

- [ ] **Step 3~5: 更新其余 powerelf-* SKILL.md**

同样追加。如果某个 SKILL.md 没有数据库连接章节，则在文件适当位置追加。

- [ ] **Step 6: Commit**

```bash
git add powerelf-data-governance/SKILL.md powerelf-inspection/SKILL.md powerelf-chatbi/SKILL.md powerelf-monitor/SKILL.md powerelf-early-warning/SKILL.md
git commit -m "docs: add POWERELF_SKILLS_ROOT import snippet to SKILL.md files"
```

---

### Task 7: 验证集成

- [ ] **Step 1: 完整验证流程**

```bash
cd /home/scada/powerelf-skills

# 无环境变量
echo "=== 无 env var ==="
python3 -c "import sys; sys.path.insert(0, '_shared/lib'); from bootstrap import locate_shared; print(locate_shared())"

# 环境变量
echo "=== 设 POWERELF_SKILLS_ROOT ==="
POWERELF_SKILLS_ROOT=/home/scada/powerelf-skills \
  python3 -c "import sys; sys.path.insert(0, '_shared/lib'); from bootstrap import locate_shared; print(locate_shared())"

# 各 skill db.py 导入
echo "=== data-governance ==="
python3 -c "import sys; sys.path.insert(0, 'powerelf-data-governance'); from lib.db import get_sqlalchemy_url; print('OK')"

echo "=== inspection ==="
python3 -c "import sys; sys.path.insert(0, 'powerelf-inspection'); from lib.db import get_sqlalchemy_url; print('OK')"

echo "=== bootstrap.sh ==="
source _shared/bootstrap.sh 2>&1 | head -3
```

- [ ] **Step 2: 最终 commit（如需）**

```bash
git log --oneline -10
```