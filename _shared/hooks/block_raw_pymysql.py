#!/usr/bin/env python3
"""pre_tool_call hook：禁止 agent 手写 pymysql.connect，强制走 query()。

为什么需要它（2026-07-17 agent.log 实证）：本地 27B 模型即便加载了含"用 query()"
的 SKILL.md，仍手写 pymysql.connect(password='') → 空密码/猎密码/连错库连环翻车。
文档约束不可靠，故在 harness 层拦截。

工作方式：
  - terminal：tool_input.command 可能是 'python3 /tmp/x.py'（看不到文件内容），
    所以扫 command 本身 + 读命令里引用的 .py 文件内容。
  - execute_code：直接扫 tool_input.code。
  - 命中 pymysql.connect( / pymysql.connections / connections.Connection( → block。
  - db.py 内部的 pymysql.connect 在 lib 文件里，不在 agent 提交的脚本/命令里，不会被误伤。

放行 query()/columns()：它们在 agent 脚本里只是 from db import query; query(sql)，
不含 pymysql.connect 字样。
"""
import json
import os
import re
import sys


def main() -> None:
    try:
        p = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 解析失败不阻断

    ti = p.get("tool_input") or {}
    cmd = (ti.get("command") or "") if isinstance(ti, dict) else ""
    code = (ti.get("code") or "") if isinstance(ti, dict) else ""

    texts = [cmd, code]

    # terminal 跑脚本文件时，把命令里引用的 .py 文件内容也纳入扫描。
    # agent 常用 "cd /root && python3 x.py"，相对路径要按 cd 目标 + 候选根解析，
    # 否则 hook CWD 不在脚本所在目录就读不到文件 → 漏拦（2026-07-17 实测踩过）。
    if cmd:
        cd_match = re.search(r"(?:^|&&|\s)cd\s+([^\s;&|]+)", cmd)
        cd_dir = cd_match.group(1) if cd_match else None
        roots = [cd_dir, os.getcwd(), "/", "/root", "/tmp", "/home/scada"]
        for m in re.finditer(r"([\w./\-]+\.py)", cmd):
            path = m.group(1)
            if path.startswith("-"):
                continue
            for root in roots:
                if root is None:
                    continue
                full = path if os.path.isabs(path) else os.path.join(root, path)
                try:
                    if os.path.isfile(full):
                        with open(full, encoding="utf-8", errors="ignore") as fh:
                            texts.append(fh.read())
                        break
                except OSError:
                    pass

    blob = "\n".join(texts)

    # 手写直连的模式
    patterns = [
        r"pymysql\.connect\s*\(",
        r"pymysql\.connections\b",
        r"connections\.Connection\s*\(",
    ]
    for pat in patterns:
        if re.search(pat, blob):
            print(json.dumps({
                "action": "block",
                "message": (
                    "🚫 禁止手写 pymysql.connect —— 凭证/连接/列名易错（实测反复翻车：空密码→猎密码→连错库）。"
                    "改用封装：\n"
                    "  import sys, os\n"
                    "  sys.path.insert(0, os.path.join(os.environ.get('POWERELF_SKILLS_ROOT','/home/scada/powerelf-skills'),'_shared','lib'))\n"
                    "  from db import query, columns\n"
                    "  rows = query('SELECT ... FROM ... WHERE deleted=0')   # 自动取凭证/开关连接/只读护栏\n"
                    "查列名用 columns('表名')，勿猜。写操作用 lib/writeback.py。"
                ),
            }, ensure_ascii=False))
            return

    print(json.dumps({"action": "allow"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
