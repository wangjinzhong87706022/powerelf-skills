#!/usr/bin/env python3
"""
sql_lint.py — chatbi SQL 语义 linter（Layer A）

抓 query_exec.py 的注入护栏抓不到、MySQL 也报不出来的"成功但错误"SQL：
  - stcd 关联键：st_rsvr_r/st_pptn_r/st_percolation_r 的 stcd 实测大量为空（st_rsvr_r 99.8% NULL），
    用 stcd 关联/过滤会沉默返回空集；应改 eq_id。
  - deleted 列存在性：对无 deleted 列的表写 X.deleted=0 会运行时 MySQL 报错（stats_*_daily 等）。
  - 特征水位硬编码：项目无"警戒水位/汛限水位"列（domain-knowledge.md §2.2），阈值在 ew_info_rules.extend。
  - 表存在性：FROM/JOIN 的表不在库里（幽灵表，如 st_deformation_r）。

真相源：_shared/lib/db.py 的 columns(table)（live RO 库）。不执行 SQL，只 lint 文本对照 schema。
解析用正则（sqlglot 不可用），靶向已知 bug 模式；不做全列存在性（需别名解析/AST，留 extension）。

用法：
  python3 sql_lint.py < sql_file         # stdin
  python3 sql_lint.py sql_file.sql       # 文件
  python3 sql_lint.py --sql "SELECT ..." # 直传
"""

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "_shared", "lib"))

import db  # noqa: E402

# stcd 实测大量为空的铁律表（schema.md 首选 eq_id；db.py COLUMN_MEANINGS 注明 stcd 勿用于 JOIN）
STCD_TABLES = {"st_rsvr_r", "st_pptn_r", "st_percolation_r"}

# domain-knowledge.md §2.2：项目无特征水位列，出现这些词即硬编码反例
WATER_LEVEL_TERMS = ("警戒水位", "汛限水位", "设计水位", "校核水位", "保证水位", "死水位", "正常蓄水位")

# FROM/JOIN 后跟 AS 别名时，排除 SQL 关键字被误当别名
_KEYWORDS = {"WHERE", "ON", "LEFT", "RIGHT", "INNER", "OUTER", "JOIN", "FROM",
             "ORDER", "GROUP", "LIMIT", "HAVING", "AND", "OR", "UNION", "SET"}

_SCHEMA_CACHE = {}


def table_columns(table):
    """返回 {col: type}；表不存在返回 None（缓存）。"""
    if table not in _SCHEMA_CACHE:
        try:
            _SCHEMA_CACHE[table] = {c["column"]: c["type"] for c in db.columns(table)}
        except Exception:
            _SCHEMA_CACHE[table] = None
    return _SCHEMA_CACHE[table]


def _strip_sql_literals(sql):
    """去掉字符串字面量（'...'/"..."），避免把引号里的 stcd/deleted 当列引用。"""
    return re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", "''", sql)


def extract_tables(sql):
    """FROM/JOIN <table>（子查询的 ( 不会被 \\w 匹配，自然跳过）。"""
    return [m.group(1) for m in re.finditer(r"(?:FROM|JOIN)\s+`?(\w+)`?", sql, re.IGNORECASE)]


def extract_aliases(sql):
    """FROM/JOIN <table> [AS] <alias> → {alias: table}（子查询别名 ... ) r 不匹配，跳过）。"""
    amap = {}
    for m in re.finditer(r"(?:FROM|JOIN)\s+`?(\w+)`?\s+(?:AS\s+)?(\w+)", sql, re.IGNORECASE):
        tbl, alias = m.group(1), m.group(2)
        if alias.upper() not in _KEYWORDS:
            amap[alias] = tbl
    return amap


# ============================================================
# 检查函数：每个返回 [(severity, msg)]，severity ∈ {"fail","warn"}
# ============================================================

def check_table_exists(sql, _ctx):
    finds = []
    for tbl in set(extract_tables(sql)):
        if table_columns(tbl) is None:
            finds.append(("fail", f"表 `{tbl}` 不存在于库（幽灵表，LLM 编造）"))
    return finds


def check_stcd_join_key(sql, _ctx):
    """铁律表出现 stcd 列引用 → fail（stcd 大量为空，应改 eq_id）。"""
    finds = []
    tables = set(extract_tables(sql))
    hit_tables = tables & STCD_TABLES
    if not hit_tables:
        return finds
    if re.search(r"\bstcd\b", sql, re.IGNORECASE):
        finds.append(("fail",
                      f"在铁律表 {sorted(hit_tables)} 上用 stcd 关联/过滤——"
                      "stcd 实测大量为空（st_rsvr_r 99.8% NULL），会沉默返回空集；应改 eq_id"))
    return finds


def check_deleted_column(sql, _ctx):
    """<alias>.deleted=0 且 alias 映射的实表无 deleted 列 → fail。"""
    finds = []
    amap = extract_aliases(sql)
    flagged = set()
    for m in re.finditer(r"(\w+)\.deleted\s*=", sql, re.IGNORECASE):
        alias = m.group(1)
        tbl = amap.get(alias)
        if tbl is None:
            continue  # 子查询别名或未解析，跳过避免误报
        cols = table_columns(tbl)
        if cols is not None and "deleted" not in cols and tbl not in flagged:
            flagged.add(tbl)
            finds.append(("fail", f"{alias}.deleted：表 `{tbl}` 无 deleted 列（移除该过滤）"))
    return finds


def check_hardcoded_water_level(sql, _ctx):
    """SQL 文本含特征水位术语 → fail（项目无此列，阈值在 ew_info_rules.extend JSON）。"""
    for term in WATER_LEVEL_TERMS:
        if term in sql:
            return [("fail", f"硬编码特征水位'{term}'——项目无此列，阈值须从 ew_info_rules.extend 取")]
    return []


_CHECKS = (check_table_exists, check_stcd_join_key, check_deleted_column, check_hardcoded_water_level)


def lint(sql):
    """对一条 SQL 跑全部检查，返回 [(severity, msg)]。"""
    sql = _strip_sql_literals(sql)
    finds = []
    for chk in _CHECKS:
        finds.extend(chk(sql, None))
    return finds


def main():
    import argparse
    ap = argparse.ArgumentParser(description="chatbi SQL 语义 linter")
    ap.add_argument("sql_file", nargs="?", help="SQL 文件（缺省读 stdin）")
    ap.add_argument("--sql", help="直接传 SQL 字符串")
    args = ap.parse_args()
    if args.sql:
        sql = args.sql
    elif args.sql_file:
        sql = open(args.sql_file, encoding="utf-8").read()
    else:
        sql = sys.stdin.read()
    finds = lint(sql)
    if not finds:
        print("✓ 无语义问题")
        return 0
    for sev, msg in finds:
        print(f"[{sev.upper()}] {msg}")
    return 1 if any(s == "fail" for s, _ in finds) else 0


if __name__ == "__main__":
    sys.exit(main())
