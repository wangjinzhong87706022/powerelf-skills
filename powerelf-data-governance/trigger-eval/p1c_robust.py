#!/usr/bin/env python3
"""Robust quantification: P1c under ORIG vs A, 20 runs each, interleaved.
Estimates the true DG-trigger rate to cut through endpoint non-determinism."""
import json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

ENDPOINT = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
BASE = open("/tmp/hermes_skills_prompt.txt", encoding="utf-8").read()
N = 20
P1C = "河道水位数据最近有没有异常"
DESCS = {
    "ORIG": "数据异常分析报告/日报/评分报告一键生成，MAD异常检测、缺失检测、智能插值、离线监测、卡滞/相关性/极端事件检测、质量评分、数据回写。水利工程数据质量治理。",
    "A": "判断监测数据本身有没有异常/缺失/离线/质量问题（不查数据内容）：MAD异常检测、缺失检测、离线监测、卡滞、相关性、极端事件、质量评分、智能插值、数据回写、日报/异常/评分报告。水利工程数据质量治理。",
}
TOOL = {"type": "function", "function": {"name": "skill_view",
        "description": "Load a skill's full content by name. Call with the exact skill name from <available_skills> that matches the task. If none is relevant, name=\"NONE\".",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}


def mk(desc):
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
    body = {"model": MODEL, "messages": [{"role": "system", "content": sysp}, {"role": "user", "content": P1C}],
            "max_tokens": 200, "temperature": 0, "tools": [TOOL], "tool_choice": "auto"}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return ex(json.loads(r.read())["choices"][0]["message"])
    except Exception:
        return None


def main():
    t0 = time.time()
    for dname, desc in DESCS.items():
        sysp = mk(desc)
        with ThreadPoolExecutor(max_workers=8) as ex_:
            futs = [ex_.submit(call, sysp) for _ in range(N)]
            choices = [f.result() for f in as_completed(futs)]
        dg = sum(1 for c in choices if c == "powerelf-data-governance")
        ws = sum(1 for c in choices if c == "water-situation")
        print(f"{dname:5} P1c over {N} runs: DG={dg}/{N} ({dg/N:.0%})  water-situation={ws}/{N}  other={N-dg-ws}")
    print(f"elapsed {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
