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
    """层1 降级：readonly 凭证全缺（env + .env 文件）时，后备主账号。"""
    import db
    # 基线 db.py 会读 ~/.hermes/.env；清空 _FILE_ENV 以模拟"无 readonly 凭证"，测试降级路径
    monkeypatch.setattr(db, "_FILE_ENV", {})
    monkeypatch.delenv("POWERELF_DB_READONLY_USER", raising=False)
    monkeypatch.delenv("POWERELF_DB_READONLY_PASSWORD", raising=False)
    monkeypatch.setenv("POWERELF_DB_USER", "root")
    monkeypatch.setenv("POWERELF_DB_PASSWORD", "mainpass")
    monkeypatch.setenv("POWERELF_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("POWERELF_DB_PORT", "3306")
    monkeypatch.setenv("POWERELF_DB_NAME", "powerelf_srm_yml")
    url = get_readonly_sqlalchemy_url()
    assert "root:mainpass" in url


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

# --- P0-3：DoS + 文件写出向量（SELECT 形态，靠关键字黑名单拦截）---
def test_reject_sleep_dos():
    import pytest
    with pytest.raises(ValueError, match="写操作关键字"):
        validate_readonly("SELECT SLEEP(5)")

def test_reject_benchmark_dos():
    import pytest
    with pytest.raises(ValueError, match="写操作关键字"):
        validate_readonly("SELECT BENCHMARK(1000000, MD5('x'))")

def test_reject_into_outfile():
    import pytest
    with pytest.raises(ValueError, match="写操作关键字"):
        validate_readonly("SELECT * FROM st_rsvr_r INTO OUTFILE '/tmp/x'")

def test_reject_into_dumpfile():
    import pytest
    with pytest.raises(ValueError, match="写操作关键字"):
        validate_readonly("SELECT * FROM st_rsvr_r INTO DUMPFILE '/tmp/x'")

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

# --- P1-8：已有 LIMIT 超上限 → clamp 到 MAX_LIMIT ---
def test_clamp_oversized_limit():
    out = validate_readonly("SELECT * FROM st_rsvr_r LIMIT 999999999")
    assert "999999999" not in out
    assert str(MAX_LIMIT) in out  # 被 clamp 到上限

# --- P1-10：反引号绕过系统库黑名单（`mysql`.`user`）---
def test_reject_backtick_schema_bypass():
    import pytest
    with pytest.raises(ValueError, match="系统库"):
        validate_readonly("SELECT * FROM `mysql`.`user`")

# --- P1-11：层6(超时)/层7(只读事务) 执行时下发 SET SESSION（mock，无 DB）---
def test_l6_l7_set_readonly_and_timeout(monkeypatch):
    executed = []

    class FakeResult:
        def keys(self):
            return ["c"]
        def fetchmany(self, n):
            return []

    class FakeConn:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def execute(self, stmt):
            executed.append(str(stmt).upper())
            return FakeResult()  # 主查询需要一个 result 对象

    class FakeEngine:
        def connect(self):
            return FakeConn()

    import query_exec
    monkeypatch.setattr(query_exec, "create_engine", lambda *a, **k: FakeEngine())
    query_exec.execute("SELECT 1 AS c", "mysql+pymysql://u:p@h/d")
    assert any("READ ONLY" in s for s in executed), f"L7 未下发只读事务: {executed}"
    assert any("MAX_EXECUTION_TIME" in s for s in executed), f"L6 未下发超时: {executed}"

# --- 空 SQL ---
def test_reject_empty_sql():
    import pytest
    with pytest.raises(ValueError, match="空"):
        validate_readonly("")
    with pytest.raises(ValueError):
        validate_readonly("   ")


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
