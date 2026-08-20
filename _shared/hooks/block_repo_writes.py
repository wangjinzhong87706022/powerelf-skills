#!/usr/bin/env python3
"""pre_tool_call hook：hermes 会话内禁止写 powerelf-skills 仓库代码（全局，评测+日常）。

为什么需要它（2026-08-19 hermes-eval-20260819-183116 实证）：
  - hermes 平台提示词鼓励「发现 skill 有错立即 patch」；
  - skill_manage 对软链注册的 skill 名解析失败（'powerelf-data-governance' not found），
    agent 降级用裸 patch 工具改了被测 SKILL.md；
  - 另一 agent 跑 impl/eval_runner.py --only ...，其 --out 默认值把 47 条验收记录
    整文件覆写。两处突变让 104 题级联判 CODE-MUTATED（取证见
    docs/eval-mutation-forensics-20260820.md）。
  评测对象必须在评测期间冻结；发现缺陷应「报告」而非「就地修改」。

拦截范围（与 docs/hermes_eval_runner.py 冻结护栏语义对齐，修改需两处同步）：
  - 仓库内 tracked 文件（任何后缀）→ 一律拦截
  - 仓库内 untracked 且不在 OK 清单（.md/.csv/报表/输出等运行产物）→ 拦截
  - OK 清单放行：*.md *.csv *.pdf *.png *.jpg *.svg *.log *.tsv、report_*、output/
    （evolution/feedback-log.md 等 .md 反馈文件仍可写——缺陷走正规反馈渠道）
  - /tmp 及仓库外 → 放行

覆盖的工具通道：
  - write_file / patch / edit_file 等直接路径工具（matcher 正则）
  - skill_manage 的写类 action（skill 目录经软链落在本仓库内时）
  - terminal / execute_code：重定向、sed -i、cp/mv/rm/touch/mkdir、git 写子命令、
    python open()/Path.write_text/shutil/os 写删调用；路径经
    os.path.realpath 解析——agent 实测会用 /root/.hermes/skills/powerelf/...
    软链路径写仓库，不解符号链接就漏拦。

人工开发确需改仓库代码时：临时注释 ~/.hermes/config.yaml 中本 hook 的条目，
或直接用本会话（Claude Code）改——本 hook 只作用于 hermes 会话。
"""
import json
import os
import re
import subprocess
import sys

_REPO = os.environ.get("POWERELF_SKILLS_ROOT", "/home/scada/powerelf-skills")
# 与 docs/hermes_eval_runner.py 的 _UNTRACKED_OK_SUFFIXES/_UNTRACKED_OK_PREFIXES 同步
_OK_SUFFIXES = (".md", ".csv", ".pdf", ".png", ".jpg", ".svg", ".log", ".tsv")
_OK_PREFIXES = ("report_", "output/")
# skill 注册目录（软链 → 本仓库）；skill_manage 无 path 参数，按名字定位
_SKILL_ROOTS = [os.path.expanduser("~/.hermes/skills")]
_SKILL_WRITE_ACTIONS = {"patch", "update", "create", "delete", "remove", "edit", "write", "install", "uninstall"}

_BLOCK_MSG = (
    "🚫 仓库代码只读（powerelf-skills 冻结区）——hermes 会话不得修改仓库内代码/数据文件。\n"
    "发现 skill 缺陷请在回复中如实报告缺陷与证据（人工会记录到该 skill 的 evolution/feedback-log.md\n"
    "并排期修复——feedback-log.md 本身也是 tracked 文件，同样冻结）；\n"
    "临时产物写 /tmp 或仓库 output/ 目录（untracked .md/.csv/报表放行）。"
    "评测期间的修改会导致该题判 CODE-MUTATED（score=0）。"
)


def _tracked_set():
    """仓库 tracked 路径集合（repo 相对）。git 失败返回 None（降级：只按 OK 清单判断）。"""
    try:
        r = subprocess.run(
            ["git", "-C", _REPO, "ls-files", "-z"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return None
        return {p for p in r.stdout.split("\0") if p}
    except Exception:
        return None


def _blocked_repo_rel(path):
    """path（任意形式：绝对/软链/相对皆先解析）若命中仓库冻结区，返回 repo 相对路径；否则 None。"""
    real = os.path.realpath(path)
    if real != _REPO and not real.startswith(_REPO + os.sep):
        return None
    rel = os.path.relpath(real, _REPO)
    if rel in _TRACKED:
        return rel
    if rel.endswith(_OK_SUFFIXES) or rel.startswith(_OK_PREFIXES):
        return None
    return rel


_TRACKED = _tracked_set()


def _in_repo(path):
    real = os.path.realpath(path)
    return real == _REPO or real.startswith(_REPO + os.sep)


def _resolve_hits(paths, roots):
    """对候选路径逐个解析（绝对直接用；相对按 roots 逐个试），返回命中的冻结区相对路径。"""
    for raw in paths:
        # 跳过 shell 元字符/选项等非路径 token（实测 '>' 曾被当相对路径解析进仓库根）
        if not raw or not re.match(r"^[\w./~]", raw) or raw in ("/dev/null", "-"):
            continue
        candidates = [raw] if os.path.isabs(raw) else [os.path.join(r, raw) for r in roots if r]
        for c in candidates:
            rel = _blocked_repo_rel(c)
            if rel:
                return rel
    return None


def _cd_roots(cmd, payload_cwd):
    """命令里出现过的 cd 目标 + payload cwd 等，作为相对路径解析根（仿 block_raw_pymysql）。"""
    roots = []
    for m in re.finditer(r"(?:^|&&|\s)cd\s+([^\s;&|]+)", cmd):
        d = m.group(1)
        roots.append(d if os.path.isabs(d) else os.path.join(roots[-1] if roots else payload_cwd or ".", d))
    roots += [payload_cwd, os.getcwd(), _REPO, "/root", "/tmp", "/home/scada"]
    return roots


# ---------------- 直接路径工具（write_file / patch / edit_file ...） ----------------

_PATH_KEYS = ("path", "file_path", "target", "file", "filename", "abs_path", "dest", "destination")


def check_path_tool(tool_input):
    for key in _PATH_KEYS:
        val = tool_input.get(key)
        if isinstance(val, str):
            rel = _blocked_repo_rel(val)
            if rel:
                return rel
    # 注意：不扫描 content 等正文参数——agent 往 /tmp 写的脚本常引用仓库路径
    # （sys.path.insert('/home/scada/powerelf-skills/...')），扫正文会大量误伤。
    # 未知字段名的路径工具漏拦由 runner 冻结护栏兜底。
    return None


# ---------------- skill_manage ----------------

def check_skill_manage(tool_input):
    action = str(tool_input.get("action", "")).lower()
    if action not in _SKILL_WRITE_ACTIONS:
        return None
    name = tool_input.get("name") or tool_input.get("skill") or tool_input.get("skill_name") or ""
    if not isinstance(name, str) or not name:
        return None
    parts = [p for p in name.split("/") if p]
    # 名字可能带层级（powerelf/powerelf-data-governance）→ 按前缀逐级试；
    # 也可能扁平名落在一级软链注册项之下（powerelf → 本仓库，
    # name='powerelf-data-governance' 实际是 ~/.hermes/skills/powerelf/ 的子目录）
    candidates = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    for root in _SKILL_ROOTS:
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for e in entries:
            if _in_repo(os.path.join(root, e)):
                candidates.append(f"{e}/{'/'.join(parts)}")
    for cand in candidates:
        for root in _SKILL_ROOTS:
            if _in_repo(os.path.join(root, cand)):
                return cand
    return None


# ---------------- terminal / execute_code ----------------

# 语句级写动作 → 从语句中提取写目标的提取器
_RE_REDIRECT = re.compile(r">{1,2}\s*(\S+)")
_RE_TEE = re.compile(r"\btee\s+(?:-a\s+)?(\S+)")
_RE_CP_LIKE = re.compile(r"\b(?:cp|mv|rsync|install)\s+((?:-\S+\s+)*)(\S+(?:\s+\S+)*?)\s+(\S+)$")
_RE_RM_LIKE = re.compile(r"\b(?:rm|rmdir|unlink|shred|truncate)\s+((?:-\S+\s+)*)(.+)$")
_RE_TOUCH = re.compile(r"\btouch\s+((?:-\S+\s+)*)(.+)$")
_RE_MKDIR = re.compile(r"\bmkdir\s+((?:-\S+\s+)*)(.+)$")  # 不含 md：会误匹配 *.md 文件名后缀
_RE_SED_I = re.compile(r"\bsed\s+((?:-\S+\s+)*)('(?:[^']|'\\'' )*'|\"[^\"]*\"|\S+)\s+(.+)$")
_RE_OUT_ARG = re.compile(r"(?:^|\s)--out(?:put)?(?:=|\s+)(\S+)")
# python 写调用（terminal heredoc 与 execute_code 共用）
_RE_PY_OPEN_W = re.compile(r"open\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"][wax+]")
_RE_PY_PATHIO = re.compile(r"Path\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\.\s*write_(?:text|bytes)")
_RE_PY_TWOARG = re.compile(
    r"(?:shutil\.(?:copy|copyfile|copytree|move)|os\.(?:rename|replace))\s*"
    r"\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]")
_RE_PY_RM = re.compile(r"(?:shutil\.rmtree|os\.(?:remove|unlink|rmdir))\s*\(\s*['\"]([^'\"]+)['\"]")
_RE_PY_MKDIR = re.compile(r"os\.makedirs?\s*\(\s*['\"]([^'\"]+)['\"]")
_GIT_WRITE = re.compile(
    r"\bgit\s+(?:-C\s+(\S+)\s+)?(add|commit|rm|mv|restore|checkout|reset|stash|apply|revert|merge|rebase|clean)\b")


def check_text(cmd, code, payload_cwd):
    """shell 模式只扫 command（heredoc 体抽出后单独按 python 扫），
    python 模式扫 execute_code 的 code——不能混扫：`x = 1 > 0` 里的比较符
    会被重定向模式误判（实测踩过）。"""
    py_texts, shell_texts = [], []
    if cmd:
        def _pull(m):
            py_texts.append(m.group(2))
            return " "
        # 起始行标记后可能还有内容（cat <<'EOF' | python3），用 [^\n]* 吃掉再换行
        shell_texts.append(re.sub(
            r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)(?:\n\1(?:\n|$))", _pull, cmd, flags=re.S))
    if code:
        py_texts.append(code)
    if not shell_texts and not py_texts:
        return None

    roots = _cd_roots(cmd or "", payload_cwd)

    def hit(pattern_targets):
        return _resolve_hits([t for t in pattern_targets if t], roots)

    # ---- shell 语句 ----
    for chunk in shell_texts:
        for line in chunk.splitlines():
            # 一行可能含 && 串联的多条命令，按语句切
            for stmt in re.split(r"&&|\|\||;|\|", line):
                stmt = stmt.strip()
                if not stmt:
                    continue
                m = _RE_REDIRECT.search(stmt)
                if m and (r := hit([m.group(1)])):
                    return f"重定向写入 {r}"
                m = _RE_TEE.search(stmt)
                if m and (r := hit([m.group(1)])):
                    return f"tee 写入 {r}"
                m = _RE_CP_LIKE.search(stmt)
                if m and (r := hit([m.group(3)])):  # cp/mv 目标是最后一个参数
                    return f"cp/mv 目标 {r}"
                m = _RE_RM_LIKE.search(stmt)
                if m and (r := hit(m.group(2).split())):
                    return f"删除 {r}"
                m = _RE_TOUCH.search(stmt)
                if m and (r := hit(m.group(2).split())):
                    return f"touch {r}"
                m = _RE_MKDIR.search(stmt)
                if m and (r := hit(m.group(2).split())):
                    return f"mkdir {r}"
                m = _RE_SED_I.search(stmt)
                if m and "-i" in m.group(1) and (r := hit(m.group(3).split())):
                    return f"sed -i {r}"
                m = _RE_OUT_ARG.search(stmt)
                if m and (r := hit([m.group(1)])):
                    return f"--out 输出 {r}"
                gm = _GIT_WRITE.search(stmt)
                if gm:
                    git_c = gm.group(1)
                    groots = ([git_c] if git_c else []) + roots
                    # git add/commit/rm/... 作用在仓库工作区/索引上：按 -C 参数或 cwd 判仓库归属
                    for base in groots:
                        if _in_repo(base if os.path.isabs(base) else os.path.join(os.getcwd(), base)):
                            return f"git {gm.group(2)}"
    # ---- python 源（execute_code / terminal heredoc） ----
    for chunk in py_texts:
        for line in chunk.splitlines():
            for pat, label in ((_RE_PY_OPEN_W, "open(...,'w')"), (_RE_PY_PATHIO, "Path().write_*"),
                               (_RE_PY_TWOARG, "shutil/os 两参写"), (_RE_PY_RM, "shutil/os 删除"),
                               (_RE_PY_MKDIR, "os.makedirs")):
                pm = pat.search(line)
                if pm and (r := hit([pm.group(1)])):
                    return f"python {label} → {r}"
    return None


def main() -> None:
    try:
        p = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 解析失败不阻断

    tool = p.get("tool_name") or ""
    ti = p.get("tool_input") or {}
    if not isinstance(ti, dict):
        ti = {}
    payload_cwd = p.get("cwd") or ""

    why = None
    if tool == "skill_manage":
        why = check_skill_manage(ti)
        if why:
            why = f"skill_manage 写 skill（{why}）"
    elif tool not in ("terminal", "execute_code"):
        # write_file / patch / edit_file 及任何带路径参数的工具，统一查已知路径字段
        why = check_path_tool(ti)
        if why:
            why = f"写 {why}"
    else:
        cmd = ti.get("command") or ""
        code = ti.get("code") or ""
        why = check_text(cmd, code, payload_cwd)

    if why:
        print(json.dumps({"action": "block", "message": f"{_BLOCK_MSG}\n（拦截原因：{why}）"},
                         ensure_ascii=False))
        return
    print(json.dumps({"action": "allow"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
