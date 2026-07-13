#!/usr/bin/env python3
"""Optimization probe: test multiple candidate descriptions for
powerelf-data-governance against the FULL 20-eval set (incl. P1b/P1c traps),
faithfully (real hermes skills prompt, NO routing-INSTR suffix, real Qwen model,
skill_view tool, temperature=0, 3x vote).

Mirrors probe_final.py's faithful call() (tools + tool_choice=auto, no INSTR) but
iterates candidates like probe_candidates.py. Substitutes the data-governance
description line in /tmp/hermes_skills_prompt.txt — byte-equivalent to editing
the SKILL.md frontmatter description.

Picks the candidate that fixes P1b/P1c without breaking the 18 already-correct
cases or raising the negative false-trigger rate.
"""
import json, re, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

ENDPOINT = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
BASE = open("/tmp/hermes_skills_prompt.txt", encoding="utf-8").read()
N = 3
CONCURRENCY = 8

TOOL = {"type": "function", "function": {"name": "skill_view",
        "description": "Load a skill's full content by name. Call with the exact skill name from <available_skills> that matches the task. If none is relevant, name=\"NONE\".",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}

# A = current SKILL.md description (baseline, known to fail P1c).
# D/F/G = pushier candidates that explicitly claim the "数据有没有异常" pattern
# (including 河道水位) and disambiguate against water-situation/early-warning.
CANDIDATES = {
    "A": "判断监测数据本身有没有异常/缺失/离线/质量问题（不查数据内容）：MAD异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。水利工程数据质量治理。",
    "D": "水利工程监测数据质量治理。判断监测数据本身有没有异常/缺失/离线/卡滞（不查数值内容）。当用户问'水位数据/河道水位/水库水位/雨量/渗压数据有没有异常、数据质量怎么样、数据缺失或离线'时用本 skill——只要问的是'数据有没有问题'（而非'水位是多少/趋势/超警戒'，那些归 water-situation / early-warning）。MAD异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。",
    "F": "水利工程监测数据质量治理 — 判断数据本身有没有异常/缺失/离线/卡滞/质量问题（不查数值内容，只看数据质量）。河道水位/水库水位/雨量/渗压/渗流/GNSS 数据的异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。问'数据有没有异常/质量问题'用本 skill；问'水位是多少/趋势/超警戒'用 water-situation/early-warning。",
    "G": "水利工程数据质量治理 — 监测数据(河道水位/水库水位/雨量/渗压/渗流/GNSS)有没有异常/缺失/离线/卡滞/质量问题（看数据质量，不查数值）。MAD异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。问'数据有没有异常/质量怎么样'→本skill；问'水位是多少/趋势/超警戒'→water-situation/early-warning。",
}


def make_prompt(desc):
    pat = re.compile(r'(?m)^    - powerelf-data-governance: .*$')
    if not pat.search(BASE):
        raise SystemExit("ERROR: could not find data-governance line in base prompt")
    return pat.sub(lambda m: f'    - powerelf-data-governance: {desc}', BASE, count=1)


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


def call(sysp, user):
    body = {"model": MODEL, "messages": [{"role": "system", "content": sysp},
                                         {"role": "user", "content": user}],
            "max_tokens": 200, "temperature": 0, "tools": [TOOL], "tool_choice": "auto"}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return ex(json.loads(r.read())["choices"][0]["message"])
    except Exception:
        return None


def main():
    evals = json.load(open("evals.json", encoding="utf-8"))["evals"]
    # Build all jobs: (candidate, eval, run_idx)
    jobs = []
    for cname, desc in CANDIDATES.items():
        sysp = make_prompt(desc)
        for ev in evals:
            for i in range(N):
                jobs.append((cname, sysp, ev))
    print(f"total calls = {len(jobs)} across {len(CANDIDATES)} candidates x {len(evals)} evals x {N} runs", flush=True)

    res = {}  # (cname, eid) -> [choices]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futs = {pool.submit(call, sysp, ev["prompt"]): (cname, ev) for cname, sysp, ev in jobs}
        for f in as_completed(futs):
            cname, ev = futs[f]
            res.setdefault((cname, ev["id"]), []).append(f.result())
    print(f"all calls done in {time.time()-t0:.1f}s\n", flush=True)

    out = []
    for cname in CANDIDATES:
        summ = []
        for ev in evals:
            ch = res[(cname, ev["id"])]
            voted = Counter([c for c in ch if c]).most_common(1)
            voted = voted[0][0] if voted else None
            picked = voted == "powerelf-data-governance"
            ok = picked == ev["should_trigger"]
            summ.append({"id": ev["id"], "should": ev["should_trigger"], "expected": ev["expected_skill"],
                         "voted": voted, "picked": picked, "correct": ok, "choices": ch})
        pos = [s for s in summ if s["should"]]
        neg = [s for s in summ if not s["should"]]
        pos_ok = sum(s["correct"] for s in pos)
        neg_ok = sum(s["correct"] for s in neg)
        acc = (pos_ok + neg_ok) / len(summ)
        p1c = next(s for s in summ if s["id"] == "P1c")
        p1b = next(s for s in summ if s["id"] == "P1b")
        out.append({"name": cname, "acc": acc, "pos_ok": f"{pos_ok}/{len(pos)}",
                    "neg_ok": f"{neg_ok}/{len(neg)}", "P1b": p1b["voted"], "P1c": p1c["voted"],
                    "detail": summ})

    print(f"{'cand':4} {'acc':5} {'pos':8} {'neg':8} {'P1b':26} {'P1c':26}")
    for r in out:
        print(f"{r['name']:4} {r['acc']:.0%}  {r['pos_ok']:8} {r['neg_ok']:8} {str(r['P1b'])[:26]:26} {str(r['P1c'])[:26]:26}")
    print()
    # per-eval detail for non-baseline candidates
    for r in out:
        if r["name"] == "A":
            continue
        print(f"--- candidate {r['name']} (acc {r['acc']:.0%}) per-eval ---")
        for s in r["detail"]:
            ok = "✓" if s["correct"] else "✗"
            flag = " <== TRAP" if s["id"] in ("P1b", "P1c") else ""
            print(f"  {s['id']:4} expect={'DG' if s['should'] else s['expected'][:10]:10} voted={str(s['voted'])[:30]:30} {ok}{flag}")

    json.dump(out, open("results_optimize.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\nsaved results_optimize.json")


if __name__ == "__main__":
    main()
