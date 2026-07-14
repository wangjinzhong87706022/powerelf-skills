# chatbi 去 Vanna 化 + agent 自主 NL2SQL 直连库 实施计划（B 簇）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 powerelf-chatbi 从"依赖后端 Vanna 的纯文档 skill"改造为"agent 自主 NL2SQL + 本地安全执行"的执行型 skill，新增 7 层护栏的 `query_exec.py` 和跨域 SQL 纪律文档。

**Architecture:** hermes agent 用 LLM + schema.md + few_shots 自主生成只读 SELECT，经 `chatbi/impl/query_exec.py` 的 7 层安全护栏（只读账号 → sqlparse 类型 → 单语句 → 系统库黑名单 → 强制 LIMIT → 超时 → 只读事务）后，通过 `_shared/lib/db.py` 只读直连水利库执行。SQL 写作纪律落 `_shared/references/sql-discipline.md` 跨域复用。

**Tech Stack:** Python 3、sqlparse、SQLAlchemy、PyMySQL、MySQL 5.7.4+（MAX_EXECUTION_TIME）/5.6+（READ ONLY 事务）、Markdown。

## Global Constraints

- **MySQL 版本**：≥5.7.4（层6 `MAX_EXECUTION_TIME` 毫秒级超时）、≥5.6（层7 `SET SESSION TRANSACTION READ ONLY`）。
- **只读账号（部署前提）**：DBA 建 `chatbi_ro`，`GRANT SELECT ON powerelf_srm_yml.* TO 'chatbi_ro'@'%'`；凭证走 `~/.hermes/.env` 的 `POWERELF_DB_READONLY_USER/PASSWORD`。开发期未配则后备主账号（层1 降级，层2-7 仍生效）。
- **护栏常量**：`MAX_LIMIT=2000`、`QUERY_TIMEOUT_SEC=120`、`display` 默认 20。
- **关联键铁律**（来自 `_shared/references/schema.md`，few_shots 必须遵从）：`st_rsvr_r/st_pptn_r/st_percolation_r`→`stcd`(varchar)；`st_pressure_r`→`eq_id`(bigint)；`eq_equip_base.code` 是字符串，不能塞进 `eq_id='...'`（会 Unknown column）。
- **文档约定**：方法论文档进 `_shared/`、可运行代码进 skill、被动护栏为文档（沿用 A 簇）。
- **依赖**：`pip install sqlparse`（governance 已用 sqlalchemy/pandas/numpy/pymysql）。
- **git proxy**：push 失败按 `HTTPS_PROXY=socks5://192.168.200.71:7897` → `ALL_PROXY=...` 顺序重试，**不 git config**。

---

## File Structure

| 文件 | 责任 | 任务 |
|------|------|------|
| `_shared/lib/db.py` | 加 `get_readonly_sqlalchemy_url()`（运行时读 env，后备链 readonly→POWERELF→SRM） | Task 1 |
| `_shared/bootstrap.sh` | 扩展导出 `RO_DB_URL` | Task 1 |
| `powerelf-chatbi/impl/query_exec.py` | 7 层护栏 + 只读执行 + CLI（纯函数护栏无 DB；execute 层连库） | Task 2-3 |
| `powerelf-chatbi/impl/test_query_exec.py` | 护栏纯函数单测 + db 只读 URL 单测 + CLI 参数单测 | Task 1-3 |
| `_shared/references/sql-discipline.md` | 通用 SQL 写作纪律（跨域） | Task 4 |
| `powerelf-chatbi/rules/sql-generation.md` | 删 Vanna 流程 + 接入 schema 铁律 + 表映射瘦身 | Task 5 |
| `powerelf-chatbi/references/few_shots.md` | 修正 `st_id`→`stcd/eq_id`、去 `powerelf_data.` 前缀 | Task 5 |
| `powerelf-chatbi/rules/intent-classification.md` | 后端虚构类名→hermes agent 编排 | Task 6 |
| `powerelf-chatbi/SKILL.md` | 删 aiReporter 端点 + 加 query_exec 说明 + env | Task 6 |
| `powerelf-chatbi/rules/chart-selection.md` | 去 Builder 类名列后端耦合（类型不扩充） | Task 6 |

---

### Task 1: `_shared/lib/db.py` 加只读 URL + bootstrap 导出 RO_DB_URL

**Files:**
- Modify: `_shared/lib/db.py`（文件末尾追加函数）
- Modify: `_shared/bootstrap.sh`（加 RO_DB_URL 导出）
- Create: `powerelf-chatbi/impl/test_query_exec.py`

**Interfaces:**
- Produces: `db.get_readonly_sqlalchemy_url(host=None, port=None, user=None, password=None, database=None) -> str`；环境变量 `RO_DB_URL`（由 bootstrap 导出）。

- [ ] **Step 1: 写失败测试（db 只读 URL 优先级 + 后备链）**

创建 `powerelf-chatbi/impl/test_query_exec.py`：

```python
"""query_exec + db 只读 URL 单元测试（纯函数，无 DB 连接）。"""
import os
import sys

# 加载 _shared/lib 到 path
_HERE = os.path.dirname(os.path.abspath(__file__))
_SHARED_LIB = os.path.abspath(os.path.join(_HERE, "..", "..", "_shared", "lib"))
if _SHARED_LIB not in sys.path:
    sys.path.insert(0, _SHARED_LIB)

from db import get_readonly_sqlalchemy_url  # noqa: E402


def test_readonly_url_uses_readonly_creds(monkeypatch):
    """层1：配了只读账号时，URL 用只读账号。"""
    monkeypatch.setenv("POWERELF_DB_READONLY_USER", "chatbi_ro")
    monkeypatch.setenv("POWERELF_DB_READONLY_PASSWORD", "ropass")
    monkeypatch.setenv("POWERELF_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("POWERELF_DB_PORT", "3306")
    monkeypatch.setenv("POWERELF_DB_NAME", "powerelf_srm_yml")
    url = get_readonly_sqlalchemy_url()
    assert url.startswith("mysql+pymysql://chatbi_ro:ropass@127.0.0.1:3306/powerelf_srm_yml")


def test_readonly_url_falls_back_to_main(monkeypatch):
    """层1 降级：未配只读账号时，后备主账号（告警由调用方/部署保证）。"""
    monkeypatch.delenv("POWERELF_DB_READONLY_USER", raising=False)
    monkeypatch.delenv("POWERELF_DB_READONLY_PASSWORD", raising=False)
    monkeypatch.setenv("POWERELF_DB_USER", "root")
    monkeypatch.setenv("POWERELF_DB_PASSWORD", "mainpass")
    monkeypatch.setenv("POWERELF_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("POWERELF_DB_PORT", "3306")
    monkeypatch.setenv("POWERELF_DB_NAME", "powerelf_srm_yml")
    url = get_readonly_sqlalchemy_url()
    assert "root:mainpass" in url
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /home/scada/powerelf-skills && python3 -m pytest powerelf-chatbi/impl/test_query_exec.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_readonly_sqlalchemy_url'`

- [ ] **Step 3: 实现 `get_readonly_sqlalchemy_url`**

在 `_shared/lib/db.py` 末尾（`create_engine` 函数之后）追加：

```python
def get_readonly_sqlalchemy_url(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
) -> str:
    """chatbi 专用只读连接串。

    优先级（运行时读 env，便于测试 monkeypatch）：
        POWERELF_DB_READONLY_*  →  POWERELF_DB_*  →  SRM_DB_*  →  默认值
    只读账号 chatbi_ro 仅 GRANT SELECT，作 query_exec.py 层1 DB 兜底。
    未配只读账号时后备主账号（层1 降级，但 query_exec 层2-7 代码护栏仍生效）。
    """
    ro_user = (user or os.getenv("POWERELF_DB_READONLY_USER")
               or os.getenv("POWERELF_DB_USER") or os.getenv("SRM_DB_USER", "root"))
    ro_pwd = (password or os.getenv("POWERELF_DB_READONLY_PASSWORD")
              or os.getenv("POWERELF_DB_PASSWORD") or os.getenv("SRM_DB_PASSWORD", ""))
    ro_host = host or os.getenv("POWERELF_DB_HOST") or os.getenv("SRM_DB_HOST", "localhost")
    _raw = os.getenv("POWERELF_DB_PORT") or os.getenv("SRM_DB_PORT", "3306")
    try:
        ro_port = port or int(_raw)
    except ValueError:
        ro_port = 3306
    ro_db = database or os.getenv("POWERELF_DB_NAME") or os.getenv("SRM_DB_NAME", "powerelf_srm_yml")
    return f"mysql+pymysql://{ro_user}:{ro_pwd}@{ro_host}:{ro_port}/{ro_db}"
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /home/scada/powerelf-skills && python3 -m pytest powerelf-chatbi/impl/test_query_exec.py -v`
Expected: 2 passed

- [ ] **Step 5: bootstrap.sh 扩展导出 RO_DB_URL**

在 `_shared/bootstrap.sh` 的 `export DB_URL=...` 行之后插入：

```bash
export RO_DB_URL="$(python3 -c "import sys; sys.path.insert(0,'$_HERE/lib'); from db import get_readonly_sqlalchemy_url; print(get_readonly_sqlalchemy_url())" 2>/dev/null)"

if [ -n "$RO_DB_URL" ]; then
  echo "[bootstrap] RO_DB_URL 已设置（chatbi 只读，来自 get_readonly_sqlalchemy_url）"
else
  echo "[bootstrap] ⚠️ RO_DB_URL 为空 —— chatbi query_exec 将后备主账号" >&2
fi
```

- [ ] **Step 6: 手动验证 bootstrap**

Run: `cd /home/scada/powerelf-skills && source _shared/bootstrap.sh`
Expected: 两行 `[bootstrap] DB_URL 已设置` + `[bootstrap] RO_DB_URL 已设置`（或后备告警）

- [ ] **Step 7: Commit**

```bash
git add _shared/lib/db.py _shared/bootstrap.sh powerelf-chatbi/impl/test_query_exec.py
git commit -m "feat(_shared): db.py 加 get_readonly_sqlalchemy_url + bootstrap 导出 RO_DB_URL"
```

---

### Task 2: `query_exec.py` 护栏纯函数（层2-5，核心）

**Files:**
- Create: `powerelf-chatbi/impl/query_exec.py`
- Modify: `powerelf-chatbi/impl/test_query_exec.py`（追加护栏测试）

**Interfaces:**
- Produces: `validate_readonly(sql, limit=MAX_LIMIT) -> str`（消毒后 SQL 或抛 ValueError）；`ensure_limit(sql, limit) -> str`；常量 `FORBIDDEN_KEYWORDS/SYSTEM_SCHEMAS/MAX_LIMIT/QUERY_TIMEOUT_SEC`。

- [ ] **Step 1: 写失败测试（追加到 test_query_exec.py 末尾）**

```python
# === query_exec 护栏测试 ===
sys.path.insert(0, _HERE)  # 加载 impl/query_exec.py
import query_exec  # noqa: E402
from query_exec import validate_readonly, ensure_limit, MAX_LIMIT  # noqa: E402


# --- 层2：拒绝写语句 ---
def test_reject_insert():
    import pytest
    with pytest.raises(ValueError, match="只读 SELECT|写操作关键字"):
        validate_readonly("INSERT INTO t VALUES (1)")

def test_reject_update():
    import pytest
    with pytest.raises(ValueError):
        validate_readonly("UPDATE t SET a=1")

def test_reject_delete():
    import pytest
    with pytest.raises(ValueError):
        validate_readonly("DELETE FROM t")

def test_reject_drop():
    import pytest
    with pytest.raises(ValueError):
        validate_readonly("DROP TABLE t")

def test_reject_alter():
    import pytest
    with pytest.raises(ValueError):
        validate_readonly("ALTER TABLE t ADD c INT")

def test_reject_create():
    import pytest
    with pytest.raises(ValueError):
        validate_readonly("CREATE TABLE t (a INT)")

def test_reject_truncate():
    import pytest
    with pytest.raises(ValueError):
        validate_readonly("TRUNCATE TABLE t")

# --- 层2：合法 SELECT / CTE ---
def test_accept_simple_select():
    out = validate_readonly("SELECT * FROM st_rsvr_r")
    assert "SELECT" in out.upper()

def test_accept_cte_with_select():
    sql = "WITH x AS (SELECT * FROM st_rsvr_r) SELECT * FROM x"
    out = validate_readonly(sql)
    assert "WITH" in out.upper()

# --- 层2双保险：关键字不误杀字段名 ---
def test_not_killing_update_time_column():
    """update_time 是字段名；\bupdate\b 不匹配 update_time（_ 是单词字符）。"""
    out = validate_readonly("SELECT update_time FROM st_rsvr_r")
    assert "update_time" in out

# --- 层3：单语句 ---
def test_reject_multiple_statements():
    import pytest
    with pytest.raises(ValueError, match="单条语句"):
        validate_readonly("SELECT 1; SELECT 2")

def test_reject_semicolon_injection():
    import pytest
    with pytest.raises(ValueError):
        validate_readonly("SELECT 1; DROP TABLE t")

# --- 层4：系统库黑名单 ---
def test_reject_mysql_schema():
    import pytest
    with pytest.raises(ValueError, match="系统库"):
        validate_readonly("SELECT * FROM mysql.user")

def test_reject_information_schema():
    import pytest
    with pytest.raises(ValueError, match="系统库"):
        validate_readonly("SELECT * FROM information_schema.tables")

# --- 层5：强制 LIMIT ---
def test_inject_limit_when_missing():
    out = validate_readonly("SELECT * FROM st_rsvr_r")
    assert "LIMIT" in out.upper()

def test_preserve_existing_limit():
    sql = "SELECT * FROM st_rsvr_r LIMIT 10"
    out = validate_readonly(sql)
    assert out.upper().count("LIMIT") == 1  # 不产生双 LIMIT

def test_injected_limit_uses_custom_max():
    out = validate_readonly("SELECT * FROM st_rsvr_r", limit=500)
    assert "500" in out

# --- 空 SQL ---
def test_reject_empty_sql():
    import pytest
    with pytest.raises(ValueError, match="空"):
        validate_readonly("")
    with pytest.raises(ValueError):
        validate_readonly("   ")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /home/scada/powerelf-skills && python3 -m pytest powerelf-chatbi/impl/test_query_exec.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'query_exec'`

- [ ] **Step 3: 实现 query_exec.py（护栏纯函数部分）**

创建 `powerelf-chatbi/impl/query_exec.py`：

```python
#!/usr/bin/env python3
"""
只读 SQL 安全执行工具（chatbi query_exec）
=============================================
接收 agent 生成的 SQL，经 7 层安全护栏后只读直连水利库执行。输出 JSON / table。

7 层护栏：
  层1 只读账号（DB 兜底，chatbi_ro 仅 GRANT SELECT；URL 由 --db 传入）
  层2 语句类型（sqlparse get_type==SELECT，含 WITH CTE）+ 关键字黑名单
  层3 单语句（拒绝 ; 堆叠）
  层4 系统库黑名单（mysql./information_schema./performance_schema./sys.）
  层5 强制 LIMIT（无则子查询包裹注入，上限 MAX_LIMIT）
  层6 超时（MySQL MAX_EXECUTION_TIME，QUERY_TIMEOUT_SEC 秒）
  层7 只读事务（SET SESSION TRANSACTION READ ONLY）

用法:
  source ../_shared/bootstrap.sh   # 导出 DB_URL + RO_DB_URL
  python3 impl/query_exec.py --sql "SELECT ..." --db "$RO_DB_URL"
  python3 impl/query_exec.py --sql "..." --db "$RO_DB_URL" --limit 2000 --display 20 --format table
"""

import argparse
import json
import os
import re
import sys

try:
    import sqlparse
    from sqlalchemy import create_engine, text
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# ============================================================
# 护栏常量
# ============================================================

FORBIDDEN_KEYWORDS = frozenset({
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "grant", "revoke", "replace", "merge",
    "call", "load", "handler", "rename", "lock", "unlock",
})
SYSTEM_SCHEMAS = frozenset({
    "mysql", "information_schema", "performance_schema", "sys",
})
MAX_LIMIT = 2000
QUERY_TIMEOUT_SEC = 120


# ============================================================
# 层2-5：纯函数护栏（无 DB，可单测）
# ============================================================

def ensure_limit(sql, limit):
    """层5：若无 LIMIT 则子查询包裹注入；已有 LIMIT 则保留（信任 agent 语义）。"""
    if re.search(r"\blimit\b", sql.lower()):
        return sql
    return f"SELECT * FROM ({sql.rstrip(';').strip()}) AS _chatbi_t LIMIT {limit}"


def validate_readonly(sql, limit=MAX_LIMIT):
    """层2-5 护栏：返回消毒后 SQL，或抛 ValueError。

    层1（只读账号）、层6（超时）、层7（只读事务）在 execute() 中。
    """
    if not sql or not sql.strip():
        raise ValueError("SQL 为空")

    # 层3：单语句
    stmts = [s for s in sqlparse.split(sql) if s.strip()]
    if len(stmts) != 1:
        raise ValueError(f"仅允许单条语句，检测到 {len(stmts)} 条（拒绝 ; 堆叠）")

    raw = stmts[0]
    parsed = sqlparse.parse(raw)[0]
    lowered = raw.lower()

    # 层2：语句类型必须是 SELECT（含 WITH ... SELECT 即 CTE）
    stmt_type = parsed.get_type()
    is_cte = raw.lstrip().upper().startswith("WITH")
    if stmt_type != "SELECT" and not is_cte:
        raise ValueError(f"仅允许只读 SELECT，检测到语句类型: {stmt_type or '未知/写语句'}")

    # 层2双保险：关键字黑名单（词边界，避免误杀 update_time 等字段名）
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", lowered):
            raise ValueError(f"检测到写操作关键字: {kw}，已拒绝")

    # 层4：系统库黑名单
    for sch in SYSTEM_SCHEMAS:
        if f"{sch}." in lowered:
            raise ValueError(f"禁止访问系统库: {sch}")

    # 层5：强制 LIMIT
    return ensure_limit(raw, limit)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /home/scada/powerelf-skills && python3 -m pytest powerelf-chatbi/impl/test_query_exec.py -v`
Expected: 19 passed（2 db URL + 17 护栏）

- [ ] **Step 5: Commit**

```bash
git add powerelf-chatbi/impl/query_exec.py powerelf-chatbi/impl/test_query_exec.py
git commit -m "feat(chatbi): query_exec 7层护栏纯函数 validate_readonly + 单测"
```

---

### Task 3: `query_exec.py` execute + CLI（层1/6/7）

**Files:**
- Modify: `powerelf-chatbi/impl/query_exec.py`（追加 execute/format_table/main）
- Modify: `powerelf-chatbi/impl/test_query_exec.py`（追加 CLI 参数测试）

**Interfaces:**
- Consumes: `validate_readonly`（Task 2）
- Produces: CLI 入口 `python3 impl/query_exec.py --sql --db [--limit] [--display] [--format]`；`execute(sql, db_url, display, limit) -> dict`。

- [ ] **Step 1: 写 CLI 参数解析测试（mock execute，无 DB）**

追加到 `test_query_exec.py`：

```python
# === CLI 参数解析测试（mock execute，无 DB 连接） ===
from unittest.mock import patch  # noqa: E402


def test_cli_requires_sql():
    """缺 --sql 应非零退出。"""
    import pytest
    with pytest.raises(SystemExit):
        query_exec.main.__wrapped__ if hasattr(query_exec.main, "__wrapped__") else None
        # argparse 缺必填参数会 SystemExit(2)
        sys.argv = ["query_exec.py", "--db", "x"]
        query_exec.main()


def test_cli_invokes_execute_with_args():
    """正常参数应调 execute(sql, db, display, limit)。"""
    with patch.object(query_exec, "execute", return_value={"columns": [], "rows": [], "row_count": 0, "truncated": False, "sql_sanitized": "", "execution_timeout_sec": 120}) as mock_exec:
        sys.argv = ["query_exec.py", "--sql", "SELECT 1", "--db", "mysql+pymysql://u:p@h/d",
                    "--limit", "500", "--display", "5", "--format", "json"]
        query_exec.main()
        mock_exec.assert_called_once_with("SELECT 1", "mysql+pymysql://u:p@h/d", display=5, limit=500)


def test_format_table_renders_markdown():
    result = {"columns": ["a", "b"], "rows": [{"a": 1, "b": "x"}],
              "row_count": 1, "truncated": False}
    out = query_exec.format_table(result)
    assert "| a | b |" in out
    assert "| 1 | x |" in out
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /home/scada/powerelf-skills && python3 -m pytest powerelf-chatbi/impl/test_query_exec.py -v`
Expected: FAIL（`execute`/`format_table`/`main` 不存在或 AttributeError）

- [ ] **Step 3: 实现 execute + format_table + main**

追加到 `query_exec.py`（在 `validate_readonly` 之后）：

```python
# ============================================================
# 层1/6/7 + 执行
# ============================================================

def execute(sql, db_url, display=20, limit=MAX_LIMIT):
    """执行只读 SQL。层2-5 经 validate_readonly；层1/6/7 在此。返回结果 dict。"""
    sanitized = validate_readonly(sql, limit)
    engine = create_engine(db_url, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as conn:
            # 层7：只读事务（双保险，主防线是只读账号）
            conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
            # 层6：语句级超时（MySQL 5.7.4+，毫秒）
            conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME={QUERY_TIMEOUT_SEC * 1000}"))
            result = conn.execute(text(sanitized))
            cols = list(result.keys())
            rows = [dict(row._mapping) for row in result.fetchmany(display)]
    except SystemExit:
        raise
    except Exception as e:
        # 透传 SQL 错误（喂给 agent 自修正重试）
        print(f"[ERROR] 执行失败: {e}", file=sys.stderr)
        sys.exit(2)
    return {
        "sql_sanitized": sanitized,
        "columns": cols,
        "rows": rows,
        "row_count": len(rows),
        "truncated": len(rows) == display,
        "execution_timeout_sec": QUERY_TIMEOUT_SEC,
    }


def format_table(result):
    """简易 markdown 表格输出。"""
    cols = result["columns"]
    if not cols:
        return "(无数据)"
    lines = ["| " + " | ".join(cols) + " |",
             "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in result["rows"]:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
    if result.get("truncated"):
        lines.append(f"\n(显示前 {result['row_count']} 行，结果可能被截断)")
    return "\n".join(lines)


def main():
    if not HAS_DEPS:
        print("需要安装: pip install sqlparse sqlalchemy pymysql", file=sys.stderr)
        sys.exit(1)
    parser = argparse.ArgumentParser(description="只读 SQL 安全执行（7 层护栏）")
    parser.add_argument("--sql", required=True, help="要执行的只读 SELECT SQL")
    parser.add_argument("--db", required=True, help="只读数据库连接 URL ($RO_DB_URL)")
    parser.add_argument("--limit", type=int, default=MAX_LIMIT, help=f"强制 LIMIT 上限（默认 {MAX_LIMIT}）")
    parser.add_argument("--display", type=int, default=20, help="返回行数（默认 20）")
    parser.add_argument("--format", choices=["json", "table"], default="json", help="输出格式")
    args = parser.parse_args()

    result = execute(args.sql, args.db, display=args.display, limit=args.limit)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        print(format_table(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /home/scada/powerelf-skills && python3 -m pytest powerelf-chatbi/impl/test_query_exec.py -v`
Expected: 22 passed（含 3 CLI 测试）

- [ ] **Step 5: 验证 CLI help 正常**

Run: `cd /home/scada/powerelf-skills/powerelf-chatbi/impl && python3 query_exec.py --help`
Expected: 打印 usage，含 `--sql --db [--limit] [--display] [--format]`

- [ ] **Step 6: Commit**

```bash
git add powerelf-chatbi/impl/query_exec.py powerelf-chatbi/impl/test_query_exec.py
git commit -m "feat(chatbi): query_exec execute/CLI 层1/6/7 + 参数解析测试"
```

---

### Task 4: `_shared/references/sql-discipline.md`（通用 SQL 纪律，跨域）

**Files:**
- Create: `_shared/references/sql-discipline.md`

**Interfaces:**
- Produces: 跨域 SQL 写作纪律文档（被 Task 5 的 sql-generation.md 引用）。

- [ ] **Step 1: 写文档**

创建 `_shared/references/sql-discipline.md`：

````markdown
# SQL 写作纪律（跨域通用，单一事实源）

> 通用 SQL 写作方法论，所有手写或 agent 生成 SQL 的 skill 共用。
> 来源：复用 `knowledge-work-plugins/data` 的 `write-query`/`sql-queries`（方言中立条目），
> 丢弃 PostgreSQL/Snowflake/BigQuery/Redshift/Databricks 方言段，保留 MySQL 适用部分。
> 水利特化（表映射/单位陷阱/软删除）在各 skill 的 `sql-generation.md`，不在本文件。
> 姊妹文档：[`schema.md`](schema.md)（关联键铁律）、[`data-profiling.md`](data-profiling.md)（画像）、
> [`analysis-qa-checklist.md`](analysis-qa-checklist.md)（交付前 QA）、[`statistical-caution.md`](statistical-caution.md)（措辞）。

## 1. 何时用

agent 生成 SQL **之前**（NL2SQL 前置 checklist）+ 人工写 SQL **之时**。

## 2. 6 维需求解析（NL2SQL 前置）

生成 SQL 前先把自然语言拆成 6 维：
- **输出列**：要哪些字段（避免 `SELECT *`）
- **过滤**：时间范围 / 状态 / 分段
- **聚合**：GROUP BY / 计数 / 求和 / 平均
- **JOIN**：是否多表，关联键是否正确（查 `schema.md`）
- **排序**：如何排序
- **LIMIT**：top-N 或采样

## 3. 7 条性能纪律

1. **禁止 `SELECT *`**：只指定需要的列。
2. **早过滤**：WHERE 尽量贴近基表，先筛再 JOIN/聚合。
3. **时间过滤必带**：时序查询必须带时间条件（水利表数据量大，全表扫描代价高）。
4. **`EXISTS` 优于 `IN`**：子查询结果集大时用 EXISTS。
5. **JOIN 类型正确**：该 INNER 别用 LEFT。
6. **避免相关子查询**：JOIN 或窗口函数能做就别用相关子查询。
7. **警惕 JOIN 爆炸**：多对多 JOIN 前先聚合到相同粒度。

## 4. 窗口函数 / CTE 规范

**窗口函数**（MySQL 8+ 支持）：
- 排名：`ROW_NUMBER()/RANK()/DENSE_RANK() OVER (PARTITION BY ... ORDER BY ...)`
- 偏移：`LAG(col,n)/LEAD(col,n) OVER (...)`（同比/环比、前后值）
- 运行总数/移动平均：`SUM() OVER (ORDER BY ... ROWS BETWEEN N PRECEDING AND CURRENT ROW)`
- 占比：`SUM() OVER ()`（分组总计做分母）
- `FIRST_VALUE/LAST_VALUE`：注意必须写 `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`，否则取错。

**去重范式**（取每组最新一条）：
```sql
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY stcd ORDER BY tm DESC) AS rn
  FROM st_rsvr_r WHERE tm > DATE_SUB(NOW(), INTERVAL 7 DAY)
)
SELECT * FROM ranked WHERE rn = 1;
```

**CTE 可读性**：每 CTE 表达一个逻辑变换，语义命名（`daily_rainfall`/`latest_reading`），不要 `a/b/c`。

## 5. 6 条错误排查铁律

1. **除零**：用 `NULLIF(denominator, 0)`（返回 NULL 而非报错）。
2. **列名限定**：JOIN 中列名必须加表别名（`r.rz` 不是 `rz`），防歧义。
3. **GROUP BY**：必须包含所有非聚合列（或用 ANY_VALUE）。
4. **类型不匹配**：比较前显式 CAST（水利电气参数是 varchar，数值比较前 `CAST(p AS DECIMAL)`）。
5. **MySQL 方言**：`DATE_FORMAT(tm,'%Y-%m')`、`DATE_ADD(tm,INTERVAL 7 DAY)`、`JSON_EXTRACT`、`REGEXP`、`DAYOFWEEK()`。
6. **关联键**：查 `schema.md` 铁律，`stcd`(varchar) vs `eq_id`(bigint) 不能混用。
````

- [ ] **Step 2: 验证无方言泄漏**

Run: `cd /home/scada/powerelf-skills && grep -niE "ilike|safe_divide|approx_count|flatten|unnest|date_trunc|dateadd|zorder|split_part" _shared/references/sql-discipline.md`
Expected: 无输出（零方言泄漏；`DATE_TRUNC` 在文档里仅作为"被丢弃方言"的反例不算——若命中请确认是反例语境或删除）

- [ ] **Step 3: Commit**

```bash
git add _shared/references/sql-discipline.md
git commit -m "docs(_shared): sql-discipline.md 通用 SQL 写作纪律（跨域）"
```

---

### Task 5: `sql-generation.md` 去 Vanna + 接入铁律 + `few_shots.md` 修正

**Files:**
- Modify: `powerelf-chatbi/rules/sql-generation.md`
- Modify: `powerelf-chatbi/references/few_shots.md`

**Interfaces:**
- Consumes: `_shared/references/{schema,sql-discipline}.md`（引用）、`impl/query_exec.py`（执行）。

- [ ] **Step 1: 改造 sql-generation.md 顶部（Vanna 流程 + 铁律接入）**

把 `powerelf-chatbi/rules/sql-generation.md` 第 5-14 行（NL2SQL 流程段）替换为：

```markdown
## NL2SQL 流程（agent 自主，弃 Vanna）

```
用户问题 → hermes agent（LLM + schema.md + few_shots.md + sql-discipline.md）→ 只读 SQL
        → chatbi/impl/query_exec.py --sql "..." --db "$RO_DB_URL"（7 层护栏只读执行）
        → 数据 → agent 解读/选图/回复

SQL 错误（BadSqlGrammar/Unknown column）由 agent 见错误信息自修正重试（query_exec 透传 MySQL 错误）。
不再依赖后端 Vanna API（路径 A 已废弃）。
```

> 📖 **SQL 写作纪律**：见 `_shared/references/sql-discipline.md`（6 维需求解析 / 7 条性能纪律 / 窗口函数 / 错误排查）。
> 📖 **表结构唯一事实源**：见 `_shared/references/schema.md`。本文件下方表映射仅作水利语义提示，关联键/完整字段以 schema.md 为准。

## ⚠️ 关联键铁律（生成 JOIN 必读）

| 业务表 | 关联键 | 关联方式 |
|--------|--------|----------|
| st_rsvr_r / st_pptn_r / st_percolation_r | **stcd** (varchar) | `WHERE stcd = eq_equip_base.code` |
| st_pressure_r | **eq_id** (bigint) | `WHERE eq_id = eq_equip_base.id` |
| dsm_dfr_srvrds_srhrds (GNSS) | **eq_id** (int) | `WHERE eq_id = eq_equip_base.id` |

**铁律**：`eq_equip_base.code` 是字符串（如 `'606K215001'`），**不能**写 `eq_id = '606K215001'`（会 Unknown column）。完整铁律见 `schema.md`。
```

- [ ] **Step 2: 修正 few_shots.md（st_id → stcd/eq_id，去库名前缀）**

Run（先看残留范围）：
```bash
cd /home/scada/powerelf-skills && grep -nE "\bst_id\b|powerelf_data\." powerelf-chatbi/references/few_shots.md
```

逐处修正（用 Edit/replace）：
- `r.st_id = s.id` 类 JOIN → 按 schema.md 铁律改为 `stcd = ...` 或 `eq_id = ...`（依据具体表）
- `powerelf_data.st_rsvr_r` → `st_rsvr_r`（去库名前缀，库名由 db.py 统一）
- 涉及 `st_pressure_r` 的 JOIN 用 `eq_id`；涉及 `st_rsvr_r/st_pptn_r/st_percolation_r` 的用 `stcd`

修正后验证零残留：
Run: `cd /home/scada/powerelf-skills && grep -nE "\bst_id\b|powerelf_data\." powerelf-chatbi/references/few_shots.md`
Expected: 无输出

- [ ] **Step 3: sql-generation.md 末尾注意事项段加纪律引用**

把 `sql-generation.md` 末尾"## 注意事项"段最后追加一行：

```markdown
- SQL 写作纪律（禁 SELECT *、EXISTS>IN、JOIN 爆炸、窗口函数、NULLIF 除零）：见 `_shared/references/sql-discipline.md`
```

- [ ] **Step 4: 验证链接完整**

Run: `cd /home/scada/powerelf-skills && grep -n "sql-discipline.md\|schema.md" powerelf-chatbi/rules/sql-generation.md`
Expected: 至少各 1 处引用

- [ ] **Step 5: Commit**

```bash
git add powerelf-chatbi/rules/sql-generation.md powerelf-chatbi/references/few_shots.md
git commit -m "docs(chatbi): sql-generation 去 Vanna + 接入 schema 铁律 + few_shots 修正 st_id/库名"
```

---

### Task 6: `intent-classification.md` + `SKILL.md` + `chart-selection.md` 去 Vanna 改造

**Files:**
- Modify: `powerelf-chatbi/rules/intent-classification.md:38-48`
- Modify: `powerelf-chatbi/SKILL.md:43-55`
- Modify: `powerelf-chatbi/rules/chart-selection.md:5-13`

- [ ] **Step 1: intent-classification.md 流水线去后端类名**

把 `intent-classification.md` 第 34-48 行（流水线组合段）替换为：

```markdown
## 流水线组合（hermes agent 编排，弃后端 Vanna）

```
TEXT_TO_SQL 流水线:
  意图分类 → agent 生成 SQL（用 sql-discipline.md/schema.md/few_shots.md）
           → chatbi/impl/query_exec.py 只读执行（7 层护栏）→ 数据表格

VISUALIZATION 流水线:
  数据 → agent 按 chart-selection.md 选图 → 生成 ECharts option

INTERPRETATION 流水线:
  数据 → agent 解读（过 analysis-qa-checklist.md / statistical-caution.md）→ 分析文本

完整流水线 (首次):
  意图分类 → 生成SQL → query_exec 执行 → 图表决策 → 图表生成 → 数据解读
```
```

- [ ] **Step 2: SKILL.md 删 aiReporter 端点 + 加 query_exec 说明**

把 `SKILL.md` 第 43-55 行（API 附录段）替换为：

```markdown
## 数据访问

chatbi 走 **agent 自主 NL2SQL 直连库**（弃后端 Vanna）：

```bash
source ../_shared/bootstrap.sh   # 导出 RO_DB_URL（只读账号 chatbi_ro）
python3 impl/query_exec.py --sql "SELECT ..." --db "$RO_DB_URL" [--limit 2000] [--display 20] [--format json|table]
```

`query_exec.py` 7 层安全护栏（只读账号/sqlparse/单语句/系统库黑名单/强制 LIMIT/超时 120s/只读事务），详见 [`rules/sql-generation.md`](rules/sql-generation.md)。

## API 附录（非 NL2SQL 能力，平台端点）

| 端点 | 说明 |
|------|------|
| `GET /knowledge/base/search?content=&size=` | 知识库检索 |
| `GET /knowledge/neo4j-graph/graphEcharts?fileName=` | 知识图谱 |
| `GET /llm-api/streamChat?message=&promptType=` | LLM对话 |
| `GET /aiMenu/search-menus?question=&prefix=` | 菜单导航 |

通用头与鉴权约定：见 [`../_shared/api-auth.md`](../_shared/api-auth.md)（`Authorization: Bearer ${POWERELF_API_TOKEN}` + `tenant-id: 1`）
```

并在 `SKILL.md` frontmatter `prerequisites.env_vars` 追加只读账号变量：

```yaml
prerequisites:
  env_vars: [POWERELF_API_BASE, POWERELF_API_TOKEN, POWERELF_DB_READONLY_USER, POWERELF_DB_READONLY_PASSWORD]
```

- [ ] **Step 3: chart-selection.md 去 Builder 后端耦合**

把 `chart-selection.md` 第 5-13 行（图表类型表）替换为：

```markdown
## 图表类型

| chartType | 适用场景 |
|-----------|----------|
| line + 多组 | 多系列时间序列对比 |
| line + 多Y字段 | 同一时间轴多个Y指标 |
| line + 单Y字段 | 单指标时间序列 |
| bar + 分组 | 分类对比（多系列） |
| bar + 单系列 | 分类对比（单系列） |
| pie | 占比分析 |
| none | 数据不适合图表 |

> 图表类型扩充（热力/散点/地图/双轴/堆叠等）见 B' 簇后续。agent 生成 ECharts option 时按本表语义选择。
```

- [ ] **Step 4: 验证无 Vanna/aiReporter 残留**

Run: `cd /home/scada/powerelf-skills && grep -rniE "vanna|aiReporter" powerelf-chatbi/`
Expected: 无输出

- [ ] **Step 5: Commit**

```bash
git add powerelf-chatbi/rules/intent-classification.md powerelf-chatbi/SKILL.md powerelf-chatbi/rules/chart-selection.md
git commit -m "docs(chatbi): intent/SKILL/chart-selection 去 Vanna + 后端类名改 agent 编排"
```

---

### Task 7: 最终验证（单测 / 导入 / 链接 / grep / 冒烟 / 推送）

**Files:** 无新增（验证全簇）

- [ ] **Step 1: 全量单测**

Run: `cd /home/scada/powerelf-skills && python3 -m pytest powerelf-chatbi/impl/test_query_exec.py -v`
Expected: 22 passed

- [ ] **Step 2: query_exec 导入 + CLI**

Run: `cd /home/scada/powerelf-skills/powerelf-chatbi/impl && python3 -c "import query_exec; print('OK')" && python3 query_exec.py --help`
Expected: `OK` + usage 打印

- [ ] **Step 3: 链接完整性（sql-discipline 被引用 / schema 铁律被引用）**

Run: `cd /home/scada/powerelf-skills && grep -rl "sql-discipline.md" powerelf-chatbi/ && grep -rl "schema.md" powerelf-chatbi/rules/sql-generation.md`
Expected: sql-generation.md 引用了两者

- [ ] **Step 4: Vanna/aiReporter/st_id/powerelf_data. 零残留**

Run: `cd /home/scada/powerelf-skills && grep -rniE "vanna|aiReporter" powerelf-chatbi/ ; grep -rnE "\bst_id\b|powerelf_data\." powerelf-chatbi/`
Expected: 均无输出

- [ ] **Step 5: 冒烟（真实库 + 只读账号，若已配）**

Run（若 `chatbi_ro` 已配）:
```bash
cd /home/scada/powerelf-skills && source _shared/bootstrap.sh
python3 powerelf-chatbi/impl/query_exec.py \
  --sql "SELECT tm, eq_id, water_pressure FROM st_pressure_r WHERE tm > DATE_SUB(NOW(), INTERVAL 1 DAY) ORDER BY tm DESC" \
  --db "$RO_DB_URL" --display 5 --format json
```
Expected: JSON 输出，含 `columns/rows/row_count`；若账号未配则后备主账号（仍只读执行，层1 降级告警）
（若库无 st_pressure_r 数据，换 st_rsvr_r / rz；只验证护栏+执行链跑通）

- [ ] **Step 6: 推送（先裸 push，失败按 proxy 规则）**

Run:
```bash
cd /home/scada/powerelf-skills && git push origin main
# 若失败：
# HTTPS_PROXY=socks5://192.168.200.71:7897 git push origin main
# 仍失败：
# ALL_PROXY=socks5://192.168.200.71:7897 git push origin main
```
Expected: 推送成功

- [ ] **Step 7: 标记完成**

确认全簇交付：query_exec.py（7 层护栏）+ test_query_exec.py（22 测试）+ sql-discipline.md + sql-generation/few_shots/intent/SKILL/chart-selection 改造 + db.py/bootstrap 只读 URL。

---

## Self-Review

**1. Spec coverage**：
- §3 query_exec.py + test → Task 2-3 ✓
- §3 sql-discipline.md → Task 4 ✓
- §3 sql-generation.md 改造 + schema 铁律 → Task 5 ✓
- §3 few_shots.md 修正 → Task 5 ✓
- §3 intent-classification.md → Task 6 ✓
- §3 SKILL.md 删端点 + env → Task 6 ✓
- §3 chart-selection.md → Task 6 ✓
- §3 db.py get_readonly_sqlalchemy_url → Task 1 ✓
- §3 bootstrap.sh RO_DB_URL → Task 1 ✓
- §3 只读账号配置（DBA）→ Global Constraints（部署前提，非仓库 Task）✓
- §7 测试（单测/文档验证/链接/冒烟）→ Task 7 ✓

**2. Placeholder scan**：无 TBD/TODO；每步含完整代码或精确命令 ✓

**3. Type consistency**：`validate_readonly(sql, limit=MAX_LIMIT)`、`ensure_limit(sql, limit)`、`execute(sql, db_url, display=20, limit=MAX_LIMIT)` 在 Task 2-3 + 测试中签名一致 ✓；常量 `MAX_LIMIT/QUERY_TIMEOUT_SEC/FORBIDDEN_KEYWORDS/SYSTEM_SCHEMAS` 定义（Task 2）与使用（Task 3）一致 ✓。

**注**：sqlparse 对 `WITH ... SELECT` 的 `get_type()` 行为依赖版本；`is_cte` 兜底（Task 2 Step 3）保证 CTE 合法性判定不依赖版本。若实测 `test_accept_cte_with_select` 失败，检查 sqlparse 版本并确认 `is_cte` 分支生效。
