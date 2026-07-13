#!/usr/bin/env python3
"""Final faithful verification: full eval set (20), real hermes prompt (edited
with candidate A), NO appended instruction, 3x per eval."""
import json, re, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

ENDPOINT = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
SYS = open("/tmp/hermes_skills_prompt.txt", encoding="utf-8").read()  # real, A-edited
N = 3
CONCURRENCY = 8
TOOL = {"type": "function", "function": {"name": "skill_view",
        "description": "Load a skill's full content by name. Call with the exact skill name from <available_skills> that matches the task. If none is relevant, name=\"NONE\".",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}


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


def call(user):
    body = {"model": MODEL, "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
            "max_tokens": 200, "temperature": 0, "tools": [TOOL], "tool_choice": "auto"}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return ex(json.loads(r.read())["choices"][0]["message"])
    except Exception:
        return None


def main():
    evals = json.load(open("evals.json", encoding="utf-8"))["evals"]
    jobs = [(ev, i) for ev in evals for i in range(N)]
    res = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex_:
        futs = {ex_.submit(call, ev["prompt"]): ev["id"] for ev, i in jobs}
        for f in as_completed(futs):
            eid = futs[f]
            res.setdefault(eid, []).append(f.result())
    pos = neg = pos_ok = neg_ok = 0
    print(f"\nFinal faithful verification (real A-edited prompt, no extra instr) N={N}\n{'='*72}")
    print(f"{'id':5} {'exp':5} {'voted':32} {'ok':3}  prompt")
    for ev in evals:
        ch = res[ev["id"]]
        voted = Counter([c for c in ch if c]).most_common(1)
        voted = voted[0][0] if voted else None
        picked = voted == "powerelf-data-governance"
        ok = picked == ev["should_trigger"]
        if ev["should_trigger"]:
            pos += 1; pos_ok += ok
        else:
            neg += 1; neg_ok += ok
        print(f"{ev['id']:5} {'DG' if ev['should_trigger'] else 'oth':5} {(voted or 'None')[:32]:32} {'✓' if ok else '✗':3}  {ev['prompt'][:46]}")
    print(f"\npositives: {pos_ok}/{pos} triggered DG  |  negatives: {neg_ok}/{neg} correctly NOT DG")
    print(f"routing accuracy: {(pos_ok+neg_ok)/(pos+neg):.0%}  ({pos_ok+neg_ok}/{pos+neg})")
    print(f"elapsed {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
