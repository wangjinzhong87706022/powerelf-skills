#!/usr/bin/env python3
"""
Test multiple candidate descriptions for powerelf-data-governance WITHOUT
editing SKILL.md. Substitutes the data-governance description line in the
hermes skills prompt (byte-equivalent to editing the frontmatter, since the
prompt renders `    - powerelf-data-governance: <description>`), then runs the
full eval set per candidate.

Picks the candidate that fixes the P1 failure (水位数据有没有异常) without
raising the negative false-trigger rate.
"""
import json, re, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

ENDPOINT = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
BASE_PROMPT = open("/tmp/hermes_skills_prompt.txt", encoding="utf-8").read()
N_RUNS = 3
CONCURRENCY = 8
TIMEOUT = 120

SKILL_VIEW_TOOL = {
    "type": "function",
    "function": {
        "name": "skill_view",
        "description": "Load a skill's full content by name. Call with the exact name of the skill that matches the user's task from <available_skills>. If none relevant, name=\"NONE\".",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string"}},
                       "required": ["name"]},
    },
}
INSTR = ("\n\n## Routing task\nRead the user's message and decide which ONE skill from "
         "<available_skills> (if any) to load. Respond ONLY by calling skill_view with the "
         "exact skill name, or name=\"NONE\" if none is relevant. Do not answer; only route.")

CANDIDATES = {
    "ORIG": "数据异常分析报告/日报/评分报告一键生成，MAD异常检测、缺失检测、智能插值、离线监测、卡滞/相关性/极端事件检测、质量评分、数据回写。水利工程数据质量治理。",
    "A": "判断监测数据本身有没有异常/缺失/离线/质量问题（不查数据内容）：MAD异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。水利工程数据质量治理。",
    "C": "数据质量治理：检测监测数据有无异常/缺失/离线/卡滞（不查数据内容）：MAD异常检测、缺失检测、离线监测、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。",
}


def make_prompt(desc):
    # Replace the data-governance line. Match the full current line robustly.
    pattern = re.compile(r'(?m)^    - powerelf-data-governance: .*$')
    new_line = f'    - powerelf-data-governance: {desc}'
    if not pattern.search(BASE_PROMPT):
        raise SystemExit("ERROR: could not find data-governance line in base prompt")
    return pattern.sub(lambda m: new_line, BASE_PROMPT, count=1)


def extract_choice(message):
    tc = message.get("tool_calls")
    if tc:
        try:
            args = json.loads(tc[0]["function"]["arguments"])
            if args.get("name"):
                return args["name"].strip()
        except Exception:
            pass
    txt = message.get("content") or ""
    for pat in (r'skill_view\(\s*name\s*=\s*["\']([^"\']+)', r'SKILL_VIEW:\s*([^\s\n]+)',
                r'`?skill_view\(\s*["\']([^"\']+)'):
        m = re.search(pat, txt)
        if m:
            return m.group(1).strip().strip("`")
    return None


def call(prompt_text, user_msg, use_tools):
    msgs = [{"role": "system", "content": prompt_text + INSTR}, {"role": "user", "content": user_msg}]
    body = {"model": MODEL, "messages": msgs, "max_tokens": 200, "temperature": 0}
    if use_tools:
        body["tools"] = [SKILL_VIEW_TOOL]
        body["tool_choice"] = "auto"
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())["choices"][0]["message"]
    except Exception:
        return {"content": "", "tool_calls": None}


def probe(prompt_text, user_msg):
    msg = call(prompt_text, user_msg, True)
    ch = extract_choice(msg)
    if ch is None or (ch and ch.startswith("__")):
        msg2 = call(prompt_text, user_msg, False)
        ch2 = extract_choice(msg2)
        if ch2:
            return ch2
    return ch


def run_candidate(name, desc, evals):
    prompt_text = make_prompt(desc)
    jobs = [(ev, i) for ev in evals for i in range(N_RUNS)]
    res = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(probe, prompt_text, ev["prompt"]): (ev["id"], i) for ev, i in jobs}
        for f in as_completed(futs):
            eid, i = futs[f]
            res.setdefault(eid, {})[i] = f.result()
    summ = []
    for ev in evals:
        choices = [res[ev["id"]][i] for i in range(N_RUNS)]
        valid = [c for c in choices if c and not str(c).startswith("__")]
        voted = Counter(valid).most_common(1)[0][0] if valid else None
        picked = voted == "powerelf-data-governance"
        summ.append({"id": ev["id"], "should": ev["should_trigger"], "voted": voted, "picked": picked, "choices": choices})
    pos = [s for s in summ if s["should"]]
    neg = [s for s in summ if not s["should"]]
    pos_rate = sum(s["picked"] for s in pos) / len(pos)
    fneg = sum(s["picked"] for s in neg) / len(neg)
    acc = sum(s["picked"] == s["should"] for s in summ) / len(summ)
    p1 = next(s for s in summ if s["id"] == "P1")
    return {"name": name, "pos_rate": pos_rate, "false_trig": fneg, "acc": acc,
            "p1_voted": p1["voted"], "p1_picked": p1["picked"], "detail": summ}


def main():
    evals = json.load(open("evals.json", encoding="utf-8"))["evals"]
    results = []
    t0 = time.time()
    for name, desc in CANDIDATES.items():
        print(f"\n>>> testing candidate {name} ...", flush=True)
        r = run_candidate(name, desc, evals)
        results.append(r)
        print(f"    pos_rate={r['pos_rate']:.0%}  false_trig={r['false_trig']:.0%}  acc={r['acc']:.0%}  P1->{r['p1_voted']} (picked DG: {r['p1_picked']})", flush=True)
    print(f"\n{'='*78}\n{'cand':5} {'pos_rate':9} {'false_trig':11} {'acc':6} {'P1':20}")
    for r in results:
        print(f"{r['name']:5} {r['pos_rate']:9.0%} {r['false_trig']:11.0%} {r['acc']:6.0%} {r['p1_voted'][:20]:20}")
    print(f"\nelapsed {time.time()-t0:.1f}s")
    json.dump(results, open("candidates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # show per-question for non-ORIG candidates
    for r in results:
        if r["name"] == "ORIG":
            continue
        print(f"\n--- candidate {r['name']} per-question ---")
        for s in r["detail"]:
            ok = "✓" if s["picked"] == s["should"] else "✗"
            print(f"  {s['id']:4} expect={'DG' if s['should'] else 'oth'} voted={(s['voted'] or 'None')[:30]:30} {ok}")


if __name__ == "__main__":
    main()
