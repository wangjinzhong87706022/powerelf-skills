#!/usr/bin/env python3
"""
Routing trigger-probe for powerelf-data-governance.

Faithful to hermes's actual routing surface: uses the EXACT system prompt that
hermes builds (build_skills_system_prompt(), dumped to /tmp/hermes_skills_prompt.txt)
and the SAME model hermes uses (Qwen3.6-27B via the configured OpenAI-compatible
endpoint). The model is given a `skill_view` tool (same as hermes's real loop)
and asked only to ROUTE, not execute.

Each eval query is run N=3 times (matches skill-creator's "3x for reliable
trigger rate"); majority vote decides the chosen skill.
"""
import json, os, re, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

ENDPOINT = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
SKILLS_PROMPT = open("/tmp/hermes_skills_prompt.txt", encoding="utf-8").read()
N_RUNS = 3
CONCURRENCY = 6
TIMEOUT = 120

SKILL_VIEW_TOOL = {
    "type": "function",
    "function": {
        "name": "skill_view",
        "description": "Load a skill's full content by name. Call this with the exact name of the skill that matches the user's task from <available_skills>. If no skill is relevant, pass name=\"NONE\".",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "exact skill name from the <available_skills> list, or NONE"}},
            "required": ["name"],
        },
    },
}

ROUTING_INSTRUCTION = (
    "\n\n## Routing task\n"
    "You are the routing layer. Read the user's message and decide which ONE skill from "
    "<available_skills> (if any) should be loaded to handle it. Respond ONLY by calling the "
    "skill_view tool with the exact skill name. If genuinely no skill is relevant, call "
    "skill_view with name=\"NONE\". Do not answer the user's question; only choose the skill."
)

TEXT_FALLBACK_INSTRUCTION = (
    "\n\n## Routing task\n"
    "Read the user's message and decide which ONE skill from <available_skills> (if any) should "
    "be loaded. Reply with EXACTLY one line in the form `SKILL_VIEW: <skill-name>` using the "
    "exact skill name, or `SKILL_VIEW: NONE` if no skill is relevant. Do not answer the question."
)


def _extract_choice(message):
    """Return chosen skill name from a chat message (tool_call or text)."""
    tc = message.get("tool_calls")
    if tc:
        try:
            args = json.loads(tc[0]["function"]["arguments"])
            n = args.get("name")
            if n:
                return n.strip()
        except Exception:
            pass
    txt = message.get("content") or ""
    # patterns: skill_view(name="X"), SKILL_VIEW: X, bare name on a line
    for pat in (r'skill_view\(\s*name\s*=\s*["\']([^"\']+)', r'SKILL_VIEW:\s*([^\s\n]+)',
                r'`?skill_view\(\s*["\']([^"\']+)'):
        m = re.search(pat, txt)
        if m:
            return m.group(1).strip().strip("`")
    return None


def _call_once(prompt, use_tools):
    msgs = [
        {"role": "system", "content": SKILLS_PROMPT + (ROUTING_INSTRUCTION if use_tools else TEXT_FALLBACK_INSTRUCTION)},
        {"role": "user", "content": prompt},
    ]
    body = {"model": MODEL, "messages": msgs, "max_tokens": 200, "temperature": 0}
    if use_tools:
        body["tools"] = [SKILL_VIEW_TOOL]
        body["tool_choice"] = "auto"
    import urllib.request
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        return _extract_choice(msg), msg
    except Exception as e:
        return f"__ERR:{type(e).__name__}", {"error": str(e)}


def probe_once(prompt):
    """One routing decision. Tries tool-call mode, falls back to text mode."""
    choice, msg = _call_once(prompt, use_tools=True)
    # If tool mode returned nothing usable AND no tool_calls were emitted, retry text mode.
    if choice is None or choice.startswith("__ERR"):
        choice2, msg2 = _call_once(prompt, use_tools=False)
        if choice2 and not choice2.startswith("__ERR"):
            return choice2, msg2
    return choice, msg


def main():
    evals_path = sys.argv[1] if len(sys.argv) > 1 else "evals.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "results.json"
    evals = json.load(open(evals_path, encoding="utf-8"))["evals"]

    # Build all (eval, run_index) jobs
    jobs = [(ev, i) for ev in evals for i in range(N_RUNS)]
    results = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = {ex.submit(probe_once, ev["prompt"]): (ev["id"], i) for ev, i in jobs}
        for fut in as_completed(futures):
            ev_id, run_i = futures[fut]
            choice, msg = fut.result()
            results.setdefault(ev_id, {})[run_i] = {"choice": choice, "raw": msg.get("content") if isinstance(msg, dict) else None,
                                                    "had_tool_calls": bool(msg.get("tool_calls")) if isinstance(msg, dict) else False}
    elapsed = time.time() - t0

    # Aggregate
    summary = []
    for ev in evals:
        rid = ev["id"]
        runs = results[rid]
        choices = [runs[i]["choice"] for i in range(N_RUNS)]
        valid = [c for c in choices if c and not str(c).startswith("__ERR")]
        counter = Counter(valid)
        voted = counter.most_common(1)[0][0] if counter else None
        picked_dg = voted == "powerelf-data-governance"
        correct = (picked_dg == ev["should_trigger"])
        summary.append({
            "id": rid, "prompt": ev["prompt"], "should_trigger": ev["should_trigger"],
            "expected_skill": ev["expected_skill"], "category": ev["category"],
            "choices": choices, "voted": voted, "picked_data_governance": picked_dg,
            "correct": correct,
        })

    pos = [s for s in summary if s["should_trigger"]]
    neg = [s for s in summary if not s["should_trigger"]]
    pos_rate = sum(s["picked_data_governance"] for s in pos) / len(pos)
    false_trig = sum(s["picked_data_governance"] for s in neg) / len(neg)
    accuracy = sum(s["correct"] for s in summary) / len(summary)

    out = {
        "model": MODEL, "n_runs_per_eval": N_RUNS, "elapsed_seconds": round(elapsed, 1),
        "positive_trigger_rate": round(pos_rate, 3),
        "negative_false_trigger_rate": round(false_trig, 3),
        "routing_accuracy": round(accuracy, 3),
        "summary": summary,
    }
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n{'='*72}")
    print(f"MODEL={MODEL}  runs/eval={N_RUNS}  elapsed={elapsed:.1f}s")
    print(f"positive trigger rate (should pick data-governance): {pos_rate:.0%} ({sum(s['picked_data_governance'] for s in pos)}/{len(pos)})")
    print(f"negative false-trigger rate (should NOT):              {false_trig:.0%} ({sum(s['picked_data_governance'] for s in neg)}/{len(neg)})")
    print(f"routing accuracy:                                      {accuracy:.0%}")
    print(f"{'='*72}\n")
    hdr = f"{'id':4} {'expect':6} {'voted':34} {'ok':3}  prompt"
    print(hdr)
    for s in summary:
        exp = "DG" if s["should_trigger"] else "other"
        ok = "✓" if s["correct"] else "✗"
        print(f"{s['id']:4} {exp:6} {(s['voted'] or 'None')[:34]:34} {ok:3}  {s['prompt'][:50]}")
    print(f"\nFull results -> {out_path}")


if __name__ == "__main__":
    main()
