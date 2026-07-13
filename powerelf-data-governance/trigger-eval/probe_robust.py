#!/usr/bin/env python3
"""Robustness probe: P1c trap under A vs F vs G, 15 runs each, interleaved.
Estimates the true DG-trigger rate to cut through endpoint non-determinism.

If A is already ~15/15 -> routing is stably correct today, keep A (lean).
If A is borderline and F/G are stably DG -> switch to the stronger candidate.
"""
import json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

ENDPOINT = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
BASE = open("/tmp/hermes_skills_prompt.txt", encoding="utf-8").read()
N = 15
P1C = "河道水位数据最近有没有异常"

CANDIDATES = {
    "A": "判断监测数据本身有没有异常/缺失/离线/质量问题（不查数据内容）：MAD异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。水利工程数据质量治理。",
    "F": "水利工程监测数据质量治理 — 判断数据本身有没有异常/缺失/离线/卡滞/质量问题（不查数值内容，只看数据质量）。河道水位/水库水位/雨量/渗压/渗流/GNSS 数据的异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。问'数据有没有异常/质量问题'用本 skill；问'水位是多少/趋势/超警戒'用 water-situation/early-warning。",
    "G": "水利工程数据质量治理 — 监测数据(河道水位/水库水位/雨量/渗压/渗流/GNSS)有没有异常/缺失/离线/卡滞/质量问题（看数据质量，不查数值）。MAD异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。问'数据有没有异常/质量怎么样'→本skill；问'水位是多少/趋势/超警戒'→water-situation/early-warning。",
}

TOOL = {"type": "function", "function": {"name": "skill_view",
        "description": "Load a skill's full content by name. Call with the exact skill name from <available_skills> that matches the task. If none is relevant, name=\"NONE\".",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}


def make_prompt(desc):
    return re.compile(r'(?m)^    - powerelf-data-governance: .*$').sub(
        f'    - powerelf-data-governance: {desc}', BASE, count=1)


def ex(m):
    tc = m.get("tool_calls")
    if tc:
        try:
            a = json.loads(tc[0]["function"]["arguments"])
            if a.get("name"):
                return a["name"].strip()
        except Exception:
            pass
    txt = m.get("content") or ""
    for p in (r'skill_view\(\s*name\s*=\s*["\']([^"\']+)', r'SKILL_VIEW:\s*([^\s\n]+)'):
        mm = re.search(p, txt)
        if mm:
            return mm.group(1).strip().strip("`")
    return None


def call(sysp):
    body = {"model": MODEL, "messages": [{"role": "system", "content": sysp},
                                         {"role": "user", "content": P1C}],
            "max_tokens": 200, "temperature": 0, "tools": [TOOL], "tool_choice": "auto"}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return ex(json.loads(r.read())["choices"][0]["message"])
    except Exception:
        return None


def main():
    t0 = time.time()
    # interleave: build (cname, sysp) jobs round-robin so server load is mixed
    prompts = {c: make_prompt(d) for c, d in CANDIDATES.items()}
    jobs = []
    for i in range(N):
        for c in CANDIDATES:
            jobs.append((c, prompts[c]))
    res = {}
    with ThreadPoolExecutor(max_workers=8) as ex_:
        futs = {ex_.submit(call, sysp): c for c, sysp in jobs}
        for f in as_completed(futs):
            c = futs[f]
            res.setdefault(c, []).append(f.result())
    print(f"\nRobustness: P1c '{P1C}' over {N} runs each (interleaved, temp=0)\n{'='*64}")
    decision = {}
    for c in CANDIDATES:
        ch = res[c]
        from collections import Counter
        dg = sum(1 for x in ch if x == "powerelf-data-governance")
        ws = sum(1 for x in ch if x == "water-situation")
        other = [x for x in ch if x not in ("powerelf-data-governance", "water-situation")]
        print(f"  {c}: DG={dg}/{N} ({dg/N:.0%})  water-situation={ws}/{N}  other={len(other)}  dist={dict(Counter(ch))}")
        decision[c] = dg
    print(f"\nelapsed {time.time()-t0:.1f}s")
    # recommendation
    a_rate = decision["A"] / N
    g_rate = decision["G"] / N
    f_rate = decision["F"] / N
    print("\n--- recommendation ---")
    if a_rate >= 14/15:
        print(f"A 已稳定正确 ({decision['A']}/{N})，保持 A（lean），不改。")
    elif g_rate > a_rate or f_rate > a_rate:
        best = max(("F", f_rate), ("G", g_rate), key=lambda x: x[1])
        print(f"A 不稳定 ({decision['A']}/{N})，{best[0]} 更稳 ({best[1]*N:.0f}/{N})，建议换 {best[0]}。")
    else:
        print(f"A={decision['A']}/{N} F={decision['F']}/{N} G={decision['G']}/{N}，均不稳定，需再设计候选。")


if __name__ == "__main__":
    main()
