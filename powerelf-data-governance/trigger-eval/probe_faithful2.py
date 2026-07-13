#!/usr/bin/env python3
"""
Faithful multi-candidate test under the REAL hermes system prompt (no appended
routing instruction). Substitutes each candidate description into the real
prompt and runs the borderline set 10x.

Goal: find a description that fixes P1c (河道水位数据...有没有异常 -> water-situation)
under real hermes routing, without regressing N1/N3.
"""
import json, re, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

ENDPOINT = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
BASE_PROMPT = open("/tmp/hermes_skills_prompt.txt", encoding="utf-8").read()
N = 10
CONCURRENCY = 8
TIMEOUT = 120

DESCS = {
    "ORIG": "数据异常分析报告/日报/评分报告一键生成，MAD异常检测、缺失检测、智能插值、离线监测、卡滞/相关性/极端事件检测、质量评分、数据回写。水利工程数据质量治理。",
    "A": "判断监测数据本身有没有异常/缺失/离线/质量问题（不查数据内容）：MAD异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。水利工程数据质量治理。",
    "D": "检测水位/渗压/雨量/流量等监测数据有没有异常、缺失、离线、卡滞、质量问题（查数据质量，不查数据值）：MAD异常检测、缺失检测、离线监测、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。",
    "E": "监测数据质量检测：水位/渗压/雨量/流量数据有没有异常、缺失、离线、卡滞（区别于查数据值）：MAD异常检测、缺失检测、离线监测、相关性、极端事件、质量评分、智能插值、数据回写、报告。",
}
QS = [
    ("P1",  True,  "XX水库最近7天的水位数据有没有异常？"),
    ("P1b", True,  "最近一周的水位数据有没有异常值"),
    ("P1c", True,  "河道水位数据最近有没有异常"),
    ("N1",  False, "XX水库当前水位是多少？"),
    ("N3",  False, "展示一下最近一周的水位变化曲线"),
]
TOOL = {"type": "function", "function": {"name": "skill_view",
        "description": "Load a skill's full content by name. Call with the exact skill name from <available_skills> that matches the task. If none is relevant, name=\"NONE\".",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}


def make_prompt(desc):
    return re.compile(r'(?m)^    - powerelf-data-governance: .*$').sub(
        f'    - powerelf-data-governance: {desc}', BASE_PROMPT, count=1)


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
    body = {"model": MODEL, "messages": [{"role": "system", "content": sysp}, {"role": "user", "content": user}],
            "max_tokens": 200, "temperature": 0, "tools": [TOOL], "tool_choice": "auto"}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return extract_choice(json.loads(r.read())["choices"][0]["message"])
    except Exception:
        return None


def main():
    t0 = time.time()
    print(f"Faithful (real hermes prompt, no extra instr) N={N}\n{'='*70}")
    print(f"{'desc':5} {'qid':5} {'want':5} {'DG#':6} {'ok':4}  top")
    winners = []
    for dname, desc in DESCS.items():
        sysp = make_prompt(desc)
        jobs = [(qid, want, q, i) for qid, want, q in QS for i in range(N)]
        res = {}
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
            futs = {ex.submit(call, sysp, q): (qid, want) for qid, want, q, i in jobs}
            for f in as_completed(futs):
                qid, want = futs[f]
                res.setdefault(qid, []).append(f.result())
        all_ok = True
        for qid, want, q in QS:
            ch = res[qid]
            dg = sum(1 for c in ch if c == "powerelf-data-governance")
            rate = dg / len(ch)
            ok = (rate == 1.0) if want else (rate == 0.0)
            all_ok = all_ok and ok
            top = Counter([c for c in ch if c]).most_common(1)
            topstr = f"{top[0][0][:24]}({top[0][1]})" if top else "none"
            print(f"{dname:5} {qid:5} {'DG' if want else 'oth':5} {dg}/{len(ch):<4} {'✓' if ok else '✗':4}  {topstr}")
        winners.append((dname, all_ok))
        print()
    print(f"elapsed {time.time()-t0:.1f}s")
    print("WINNERS (positives 100% DG AND negatives 0% DG, faithful):",
          [d for d, ok in winners if ok] or "NONE")


if __name__ == "__main__":
    main()
