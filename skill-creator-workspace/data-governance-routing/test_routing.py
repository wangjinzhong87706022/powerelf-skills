#!/usr/bin/env python3
"""Batch routing test: send queries to LLM and check skill selection."""
import json, time, urllib.request, urllib.error

LLM_URL = "http://172.28.101.81:8080/v1/chat/completions"
MODEL = "Qwen3.6-27B-Q4_K_S.gguf"
EXPECTED_SKILL = "powerelf-data-governance"

SYSTEM_PROMPT = """你是一个skill路由判断器。给定一个用户问题和以下可用的skill列表，选择最匹配的skill名称。只输出skill名称，不要输出其他内容。

可用skills:
- powerelf-data-governance: 监测数据异常值、缺失、离线、卡滞检测，数据质量治理，MAD算法/插值/评分/报告
- powerelf-chatbi: NL2SQL智能查询，自然语言查数据库，生成SQL并执行
- powerelf-early-warning: 预警规则引擎，阈值判断，动态等级调整，通知分发
- powerelf-inspection: 智能巡检引擎，AI自主巡检，异常判定，质量评估
- powerelf-intelligent-inspection: 水利工程智能巡检智能体+实时监测
- forecasting: 水库水文预报，降雨预报解读，水位趋势预测
- plan-generation: 水库调度预案生成，防汛形势评估
- simulation: 水库预演，多方案对比
- early-warning: 智慧水利预警系统，告警分析诊断
- flood-season-review: 汛期调度效果复盘
- data-analysis: 数据分析，统计洞察
- diagnosis-verification: 水库四预系统诊断验证
- llm-wiki: LLM Wiki知识库查询
- hermes-agent: 配置扩展Hermes Agent
- simplify-code: 代码清理优化"""

def test_routing(query, timeout=60):
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ],
        "max_tokens": 10,
        "temperature": 0,
        "stream": False
    }).encode()

    req = urllib.request.Request(LLM_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        result = json.loads(resp.read())
        selected = result['choices'][0]['message']['content'].strip()
        tokens = result['usage']['total_tokens']
        return selected, tokens
    except Exception as e:
        return f"ERROR: {e}", 0

# Load test queries
with open('/home/scada/powerelf-skills/skill-creator-workspace/data-governance-routing/evals-database-v2.json') as f:
    data = json.load(f)

print(f"Testing {len(data['evals'])} queries for routing to {EXPECTED_SKILL}...")
print("=" * 80)

results = []
passed = 0
failed = 0
start_time = time.time()

for i, ev in enumerate(data['evals']):
    query = ev['prompt']
    print(f"\n[{i+1}/{len(data['evals'])}] {ev['name']}")
    print(f"    Q: {query[:80]}...")

    selected, tokens = test_routing(query)
    is_correct = selected == EXPECTED_SKILL

    status = "✅" if is_correct else "❌"
    if is_correct:
        passed += 1
    else:
        failed += 1

    print(f"    → {status} Selected: {selected} (tokens: {tokens})")

    results.append({
        "id": ev['id'],
        "name": ev['name'],
        "query": query,
        "expected": EXPECTED_SKILL,
        "selected": selected,
        "correct": is_correct,
        "tokens": tokens
    })

    # Small delay between queries
    time.sleep(0.5)

elapsed = time.time() - start_time
print("\n" + "=" * 80)
print(f"\nRESULTS: {passed}/{len(data['evals'])} passed ({passed/len(data['evals'])*100:.1f}%)")
print(f"Time: {elapsed:.1f}s ({elapsed/len(data['evals']):.1f}s per query)")

# Save results
output = {
    "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
    "total": len(data['evals']),
    "passed": passed,
    "failed": failed,
    "pass_rate": round(passed/len(data['evals'])*100, 1),
    "elapsed_seconds": round(elapsed, 1),
    "results": results
}

out_path = '/home/scada/powerelf-skills/skill-creator-workspace/data-governance-routing/iteration-1/routing_test_results.json'
with open(out_path, 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nResults saved to: {out_path}")