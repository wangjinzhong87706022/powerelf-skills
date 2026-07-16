#!/usr/bin/env python3
"""Batch routing test - sequential, with retry, saves partial results."""
import json, time, sys, os
import urllib.request, urllib.error

LLM_URL = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
EXPECTED = "powerelf-data-governance"
TIMEOUT = 120

SKILLS = """可用skills:
- powerelf-data-governance: 监测数据异常值、缺失、离线、卡滞检测，数据质量治理，MAD算法/插值/评分/报告
- powerelf-chatbi: NL2SQL智能查询，自然语言查数据库
- powerelf-early-warning: 预警规则引擎，阈值判断，动态等级调整
- powerelf-inspection: 智能巡检引擎
- powerelf-intelligent-inspection: 水利工程智能巡检智能体
- forecasting: 水库水文预报
- plan-generation: 水库调度预案生成
- simulation: 水库预演
- early-warning: 智慧水利预警系统
- flood-season-review: 汛期调度效果复盘
- data-analysis: 数据分析
- diagnosis-verification: 水库四预系统诊断验证
- llm-wiki: LLM Wiki知识库
- hermes-agent: Hermes Agent配置
- simplify-code: 代码清理"""

SYSTEM_PROMPT = f"""你是一个skill路由判断器。给定用户问题和以下可用skills，选择最匹配的skill名称。
注意：只输出skill名称本身（如powerelf-data-governance），不要输出任何其他文字。

{SKILLS}"""

def test_one(query, timeout=TIMEOUT):
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ],
        "max_tokens": 10, "temperature": 0, "stream": False
    }).encode()
    req = urllib.request.Request(LLM_URL, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(2):
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            result = json.loads(resp.read())
            selected = result['choices'][0]['message']['content'].strip()
            tokens = result['usage']['total_tokens']
            return selected, tokens
        except Exception as e:
            if attempt == 0:
                print(f"    ⚠ RETRY: {e}")
                time.sleep(2)
            else:
                return f"TIMEOUT", 0
    return "FAIL", 0

# Load
with open('skill-creator-workspace/data-governance-routing/evals-database-v2.json') as f:
    data = json.load(f)

start = time.time()
results = []
passed = 0
failed = 0

print(f"Testing {len(data['evals'])} queries for routing to {EXPECTED}...")
print(f"Model: {MODEL} | Timeout: {TIMEOUT}s/query")
print("=" * 70)

for i, ev in enumerate(data['evals']):
    q = ev['prompt']
    sys.stdout.write(f"\n[{i+1:2d}/{len(data['evals'])}] {ev['name']}\n    Q: {q[:70]}...\n    ")
    sys.stdout.flush()

    selected, tokens = test_one(q)
    correct = selected == EXPECTED

    if correct:
        passed += 1
        ch = "✅"
    else:
        failed += 1
        ch = "❌"
    sys.stdout.write(f"→ {ch} Sel: {selected} tok:{tokens}\n")
    sys.stdout.flush()

    results.append({
        "id": ev['id'], "name": ev['name'],
        "query": q, "expected": EXPECTED,
        "selected": selected, "correct": correct, "tokens": tokens
    })

    # Save partial results every 10 queries
    if (i+1) % 10 == 0:
        partial = {
            "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "total": i+1, "passed": passed, "failed": failed,
            "pass_rate": round(passed/(i+1)*100, 1),
            "results": results
        }
        with open('skill-creator-workspace/data-governance-routing/iteration-1/partial_results.json', 'w') as f:
            json.dump(partial, f, ensure_ascii=False, indent=2)

    time.sleep(0.3)

elapsed = time.time() - start
print("\n" + "=" * 70)
print(f"\n{'='*30} FINAL {'='*30}")
print(f"  Total: {len(data['evals'])} | ✅ Passed: {passed} | ❌ Failed: {failed}")
print(f"  Pass rate: {passed/len(data['evals'])*100:.1f}%")
print(f"  Time: {elapsed:.0f}s ({elapsed/len(data['evals']):.1f}s/q)")

output = {
    "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
    "model": MODEL,
    "total": len(data['evals']), "passed": passed, "failed": failed,
    "pass_rate": round(passed/len(data['evals'])*100, 1),
    "elapsed_seconds": round(elapsed, 1),
    "results": results
}

out_path = 'skill-creator-workspace/data-governance-routing/iteration-1/routing_test_results.json'
with open(out_path, 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"  Results: {out_path}")