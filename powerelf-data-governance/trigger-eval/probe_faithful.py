#!/usr/bin/env python3
"""
Most-faithful probe: uses ONLY hermes's real system prompt
(build_skills_system_prompt() output — already contains the '## Skills (mandatory)'
instruction + <available_skills>) with NO appended routing instruction, plus the
skill_view tool, exactly as hermes's agent loop presents it. Tests the borderline
set 10x to confirm P1c is fixed under real hermes routing conditions.
"""
import json, re, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

ENDPOINT = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
# Real hermes system prompt — NO appended instruction.
SYS = open("/tmp/hermes_skills_prompt.txt", encoding="utf-8").read()
N = 10
CONCURRENCY = 8
TIMEOUT = 120

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


def call(user):
    body = {"model": MODEL, "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
            "max_tokens": 200, "temperature": 0, "tools": [TOOL], "tool_choice": "auto"}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return extract_choice(json.loads(r.read())["choices"][0]["message"])
    except Exception:
        return None


def main():
    jobs = [(qid, want, q, i) for qid, want, q in QS for i in range(N)]
    res = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(call, q): (qid, want) for qid, want, q, i in jobs}
        for f in as_completed(futs):
            qid, want = futs[f]
            res.setdefault(qid, []).append(f.result())
    print(f"\nFaithful probe (real hermes prompt, no extra instruction) N={N}\n{'='*64}")
    print(f"{'id':5} {'want':5} {'DG#':6} {'ok':4}  top-choice")
    all_ok = True
    for qid, want, q in QS:
        ch = res[qid]
        dg = sum(1 for c in ch if c == "powerelf-data-governance")
        rate = dg / len(ch)
        ok = (rate == 1.0) if want else (rate == 0.0)
        all_ok = all_ok and ok
        top = Counter([c for c in ch if c]).most_common(1)
        topstr = f"{top[0][0][:28]}({top[0][1]})" if top else "none"
        print(f"{qid:5} {'DG' if want else 'oth':5} {dg}/{len(ch):<4} {'✓' if ok else '✗':4}  {topstr}")
    print(f"\nelapsed {time.time()-t0:.1f}s")
    print("VERDICT:", "P1c fixed under real hermes conditions; no regressions." if all_ok else "STILL a gap.")


if __name__ == "__main__":
    main()
