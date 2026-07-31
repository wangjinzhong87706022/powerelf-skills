#!/usr/bin/env python3
"""envelope 输出校验器（Phase 5.1 静态评测闸）。

用法:
  python3 verify_output.py /path/to/envelope.json [--exit-code N]

硬校验（任一失败 → FAIL，退出码 1）:
  1. summary 计数 ≡ findings 明细（输出纪律 #4）
  2. 退出码与 agent.status 一致（若传入 --exit-code）
  3. CRITICAL finding 必带实体锚点（data_source 表.列+时间窗、title 含具名测点、detail 非空）

red-flag 元检查（任一命中 → FAIL 待人工复核）:
  R1 跨期变化 >50% 无解释（detail 含双值但无原因措辞）
  R2 可疑精确整数（大数值恰为 10^n）
  R3 恰好 0% / 100% 的比率
  R4 多条 finding 数值完全相同（查询丢维度嫌疑）
  R5 结果与预期完美一致声明（"完全一致/perfectly matches"式措辞）
"""

import argparse
import json
import re
import sys

_STATUS_EXIT = {"critical": 2, "warning": 0, "ok": 0, "no_data": 0, "inconclusive": 4}
_ERROR_EXIT = {"DB_CONNECT_FAILED": 3, "TABLE_MISSING": 5, "QUERY_TIMEOUT": 3, "BAD_ARGS": 3}


def _numbers(txt):
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", txt or "")]


def check_summary_consistency(env, problems):
    agent = env.get("agent", {})
    fnds = agent.get("findings", [])
    c = sum(1 for f in fnds if f.get("severity") == "critical")
    w = sum(1 for f in fnds if f.get("severity") == "warning")
    summary = agent.get("summary", "")
    if env.get("ok") and agent.get("status") != "no_data":
        if f"CRITICAL {c}" not in summary:
            problems.append(f"summary 口径漂移: findings 有 {c} 条 critical，summary 未含 'CRITICAL {c}'")
        if f"WARNING {w}" not in summary:
            problems.append(f"summary 口径漂移: findings 有 {w} 条 warning，summary 未含 'WARNING {w}'")


def check_exit_code(env, exit_code, problems):
    if exit_code is None:
        return
    if not env.get("ok"):
        expect = _ERROR_EXIT.get((env.get("error") or {}).get("code"), 3)
    else:
        expect = _STATUS_EXIT.get(env.get("agent", {}).get("status"), 0)
    if exit_code != expect:
        problems.append(f"退出码不一致: 实际 {exit_code}，按 status/error 应为 {expect}")


def check_critical_entities(env, problems):
    for f in env.get("agent", {}).get("findings", []):
        if f.get("severity") != "critical":
            continue
        fid = f.get("id", "?")
        ds = f.get("data_source", "")
        if "@" not in ds or "." not in ds.split("@")[0]:
            problems.append(f"{fid}: data_source 缺表.列+时间窗锚点: {ds!r}")
        if not re.search(r"(?:测站|渗压计|渗流计|雨量站|闸门|泵|站|设备)\S*\d", f.get("title", "")):
            problems.append(f"{fid}: CRITICAL title 未点名具名测点/设备: {f.get('title')!r}")
        if not (f.get("detail") or "").strip():
            problems.append(f"{fid}: CRITICAL detail 为空，读者无法行动")


_EXPLAIN_WORDS = ("因", "由于", "降雨", "调度", "闸门", "泵", "汛", "诊断", "外因", "季节")


def red_flags(env):
    flags = []
    fnds = env.get("agent", {}).get("findings", [])
    seen_values = {}
    for f in fnds:
        txt = f"{f.get('title', '')} {f.get('detail', '')}"
        nums = [n for n in _numbers(txt) if n > 0]
        # R1: 双值变化 >50% 且无解释措辞
        pair = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|kPa|mm|L/s)?\s*(?:→|/窗口峰值)\s*(\d+(?:\.\d+)?)", txt)
        if pair:
            a, b = float(pair.group(1)), float(pair.group(2))
            if a > 0 and abs(b - a) / a > 0.5 and not any(w in txt for w in _EXPLAIN_WORDS):
                flags.append(f"R1 {f.get('id')}: 跨期变化 {a}→{b}（>50%）无解释")
        # R2: 可疑精确整数（≥1000 且首位后全 0，如 1000/20000/500000）
        for n in nums:
            if n >= 1000 and n == int(n) and set(str(int(n))[1:]) <= {"0"}:
                flags.append(f"R2 {f.get('id')}: 可疑精确整数 {int(n)}")
                break
        # R3: 恰好 0% / 100%
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", txt):
            if float(m.group(1)) in (0.0, 100.0):
                flags.append(f"R3 {f.get('id')}: 恰好 {m.group(1)}% 的比率")
        # R4: 跨 finding 完全相同数值序列（查询丢维度嫌疑）
        key = tuple(nums[:4])
        if len(key) >= 2:
            if key in seen_values:
                flags.append(f"R4 {f.get('id')} 与 {seen_values[key]}: 数值序列完全相同 {key}")
            else:
                seen_values[key] = f.get("id")
        # R5: 完美一致声明
        if re.search(r"完全一致|完美|perfectly matches|exactly as expected", txt):
            flags.append(f"R5 {f.get('id')}: '与预期完美一致'式措辞")
    return flags


def main():
    ap = argparse.ArgumentParser(description="envelope 输出校验器")
    ap.add_argument("envelope", help="envelope JSON 文件路径（- 表示 stdin）")
    ap.add_argument("--exit-code", type=int, default=None, help="analyzer 实际退出码（校验一致性）")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.envelope == "-" else open(args.envelope, encoding="utf-8").read()
    try:
        env = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"FAIL: 不是合法 JSON: {e}")
        sys.exit(1)

    problems = []
    check_summary_consistency(env, problems)
    check_exit_code(env, args.exit_code, problems)
    check_critical_entities(env, problems)
    flags = red_flags(env)

    for p in problems:
        print(f"[硬校验] {p}")
    for fl in flags:
        print(f"[red-flag] {fl}")

    if problems or flags:
        print(f"FAIL: {len(problems)} 项硬校验失败, {len(flags)} 项 red-flag（待人工复核）")
        sys.exit(1)
    print("PASS: envelope 一致性与 red-flag 元检查全部通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
