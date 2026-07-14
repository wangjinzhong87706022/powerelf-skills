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
