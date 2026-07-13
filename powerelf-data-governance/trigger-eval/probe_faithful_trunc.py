#!/usr/bin/env python3
"""FAITHFUL probe: replicates hermes's extract_skill_description truncation
(skill_utils.py: desc[:57]+"..." when len>60) before substituting the candidate.

The earlier probes (probe_optimize/probe_final) substituted the FULL untruncated
candidate description, giving data-governance an unfair advantage over every
other skill (which stayed truncated in /tmp). That is why they showed P1c->DG
while REAL hermes (which truncates ALL descriptions to 57 chars) routed P1c->
water-situation. This probe truncates faithfully, so it should reproduce real
hermes (A->water-situation) and let us iterate candidates whose FIRST 57 chars
win the P1c contest without breaking N-cases.

Validation gate: candidate A (current) MUST route P1c -> water-situation here
(matching real hermes session 20260713_112909). If it does, the probe is faithful.
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


def trunc_desc(desc):
    """Replicate extract_skill_description EXACTLY."""
    d = str(desc).strip().strip("'\"")
    if len(d) > 60:
        return d[:57] + "..."
    return d


# Candidates. A = current baseline (must reproduce water-situation here).
# J/K/M put winning keywords (河道水位 + 数据有没有异常 + 数据质量) in the FIRST 57 chars,
# since the trailing disambiguator is truncated away and invisible.
CANDIDATES = {
    "A": "判断监测数据本身有没有异常/缺失/离线/质量问题（不查数据内容）：MAD异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。水利工程数据质量治理。",
    "J": "河道水位/水库水位/雨量/渗压等监测数据有没有异常值、缺失、离线？数据质量治理（MAD检测、插值、评分、报告）。查水位数值/趋势/超警戒用 water-situation。",
    "K": "监测数据（河道水位/水库水位/雨量/渗压）有没有异常值、缺失、离线、卡滞？→数据质量治理：MAD/缺失/离线检测、评分、插值、报告。数值/趋势/超警戒查询用 water-situation。",
    "M": "监测数据有没有异常/缺失/离线/卡滞？水利数据质量治理（河道水位/水库水位/雨量/渗压等；MAD检测、评分、插值）。查数值/趋势/超警戒→water-situation。",
}


def make_prompt(desc):
    td = trunc_desc(desc)
    pat = re.compile(r'(?m)^    - powerelf-data-governance: .*$')
    if not pat.search(BASE):
        raise SystemExit("ERROR: could not find data-governance line in base prompt")
    return pat.sub(lambda m: f'    - powerelf-data-governance: {td}', BASE, count=1)


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
    # show the truncated form the model will actually see (first 60 chars shown)
    print("=== truncated descriptions the model sees ([:57]+'...') ===")
    for c, d in CANDIDATES.items():
        print(f"  {c}: {trunc_desc(d)}")
    print()

    jobs = []
    prompts = {}
    for cname, desc in CANDIDATES.items():
        prompts[cname] = make_prompt(desc)
        for ev in evals:
            for i in range(N):
                jobs.append((cname, prompts[cname], ev))
    print(f"total calls = {len(jobs)}", flush=True)

    res = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futs = {pool.submit(call, sysp, ev["prompt"]): (cname, ev) for cname, sysp, ev in jobs}
        for f in as_completed(futs):
            cname, ev = futs[f]
            res.setdefault((cname, ev["id"]), []).append(f.result())
    print(f"done in {time.time()-t0:.1f}s\n", flush=True)

    out = []
    for cname in CANDIDATES:
        summ = []
        for ev in evals:
            ch = res[(cname, ev["id"])]
            voted = Counter([c for c in ch if c]).most_common(1)
            voted = voted[0][0] if voted else None
            picked = voted == "powerelf-data-governance"
            ok = picked == ev["should_trigger"]
            summ.append({"id": ev["id"], "should": ev["should_trigger"], "voted": voted, "ok": ok})
        pos_ok = sum(s["ok"] for s in summ if s["should"])
        neg_ok = sum(s["ok"] for s in summ if not s["should"])
        acc = (pos_ok + neg_ok) / len(summ)
        p1c = next(s for s in summ if s["id"] == "P1c")
        p1b = next(s for s in summ if s["id"] == "P1b")
        n1 = next(s for s in summ if s["id"] == "N1")
        n8 = next(s for s in summ if s["id"] == "N8")
        out.append((cname, acc, pos_ok, neg_ok, p1b["voted"], p1c["voted"], n1["voted"], n8["voted"], summ))

    print(f"{'cand':4} {'acc':5} {'pos':5} {'neg':5} {'P1b':22} {'P1c':22} {'N1':22} {'N8':22}")
    for cname, acc, pos_ok, neg_ok, p1b, p1c, n1, n8, _ in out:
        npos = sum(1 for e in evals if e["should_trigger"])
        nneg = len(evals) - npos
        print(f"{cname:4} {acc:.0%}  {pos_ok}/{npos}  {neg_ok}/{nneg}  {str(p1b)[:22]:22} {str(p1c)[:22]:22} {str(n1)[:22]:22} {str(n8)[:22]:22}")
    print("\n--- per-eval detail for non-A candidates ---")
    for cname, acc, pos_ok, neg_ok, p1b, p1c, n1, n8, summ in out:
        if cname == "A":
            continue
        print(f"\n  candidate {cname} (acc {acc:.0%}):")
        for s in summ:
            if not s["ok"] or s["id"] in ("P1b", "P1c", "N1", "N8"):
                mark = "" if s["ok"] else "  <-- MISS"
                print(f"    {s['id']:4} voted={str(s['voted'])[:28]:28} {'✓' if s['ok'] else '✗'}{mark}")

    # faithfulness check
    a_p1c = next(x[5] for x in out if x[0] == "A")
    print(f"\n=== FAITHFULNESS GATE: A P1c -> {a_p1c} (expect water-situation, matching real hermes) ===")
    if a_p1c == "water-situation":
        print("    ✓ probe reproduces real hermes -> faithful. Candidate results below are actionable.")
    else:
        print(f"    ✗ probe does NOT match real hermes (got {a_p1c}). Truncation alone doesn't explain it; investigate full-context.")


if __name__ == "__main__":
    main()
