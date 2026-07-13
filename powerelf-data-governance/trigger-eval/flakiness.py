#!/usr/bin/env python3
"""
Flakiness probe: measure the TRUE trigger rate of borderline questions under
the ORIGINAL description, with enough samples (10x) to detect wobble.

If P1 (水位数据有没有异常) triggers data-governance < 100% under ORIG, the
original description is fragile on that phrasing and hardening is justified.
Also tracks N1/N3 (negative 水位 traps) to ensure we don't regress them.
"""
import json, re, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

ENDPOINT = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
BASE_PROMPT = open("/tmp/hermes_skills_prompt.txt", encoding="utf-8").read()
ORIG = "数据异常分析报告/日报/评分报告一键生成，MAD异常检测、缺失检测、智能插值、离线监测、卡滞/相关性/极端事件检测、质量评分、数据回写。水利工程数据质量治理。"
N = 10
CONCURRENCY = 8
TIMEOUT = 120

# Borderline questions: share 水位/异常/数据 vocab with competing skills.
QS = [
    ("P1",  True,  "XX水库最近7天的水位数据有没有异常？"),
    ("P1b", True,  "最近一周的水位数据有没有异常值"),
    ("P1c", True,  "河道水位数据最近有没有异常"),
    ("N1",  False, "XX水库当前水位是多少？"),
    ("N3",  False, "展示一下最近一周的水位变化曲线"),
]

TOOL = {"type": "function", "function": {"name": "skill_view",
        "description": "Load a skill by name from <available_skills>. If none relevant, name=\"NONE\".",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}
INSTR = ("\n\n## Routing task\nRead the user's message and decide which ONE skill from "
         "<available_skills> (if any) to load. Respond ONLY by calling skill_view with the "
         "exact skill name, or name=\"NONE\" if none is relevant. Do not answer; only route.")


def make_prompt(desc):
    pat = re.compile(r'(?m)^    - powerelf-data-governance: .*$')
    return pat.sub(f'    - powerelf-data-governance: {desc}', BASE_PROMPT, count=1)


def extract_choice(m):
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


def call(sysp, user):
    body = {"model": MODEL, "messages": [{"role": "system", "content": sysp + INSTR}, {"role": "user", "content": user}],
            "max_tokens": 200, "temperature": 0, "tools": [TOOL], "tool_choice": "auto"}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return extract_choice(json.loads(r.read())["choices"][0]["message"])
    except Exception:
        return None


def main():
    sysp = make_prompt(ORIG)
    jobs = [(qid, want, q, i) for qid, want, q in QS for i in range(N)]
    res = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(call, sysp, q): (qid, want) for qid, want, q, i in jobs}
        for f in as_completed(futs):
            qid, want = futs[f]
            res.setdefault(qid, []).append(f.result())
    print(f"\n{'='*70}\nFlakiness under ORIG description (N={N} each, temp=0)\n{'='*70}")
    print(f"{'id':5} {'want':5} {'DG#':5} {'rate':6}  choices")
    all_ok = True
    for qid, want, q in QS:
        choices = res[qid]
        dg = sum(1 for c in choices if c == "powerelf-data-governance")
        rate = dg / len(choices)
        # want=True => we WANT DG (rate should be 100%); want=False => we want 0%
        ok = (rate == 1.0) if want else (rate == 0.0)
        all_ok = all_ok and ok
        flag = "✓" if ok else ("✗ FLAKY" if 0 < rate < 1 else "✗ WRONG")
        print(f"{qid:5} {'DG' if want else 'oth':5} {dg}/{len(choices):<3} {rate:5.0%}  {flag:9} {Counter(choices).most_common()}")
    print(f"\nelapsed {time.time()-t0:.1f}s")
    print("VERDICT:", "ORIG is stable on all borderline cases." if all_ok else "ORIG is FLAKY/WRONG on ≥1 borderline case -> hardening justified.")


if __name__ == "__main__":
    main()
