#!/usr/bin/env python3
"""
generate_formal_eval_set.py — 生成正式可用的完整评测问题集

输入：docs/eval-questions-master.json
输出：docs/eval-questions-formal.json

筛选标准：
  1. prompt_source != 'title-only'（避免简短标题）
  2. prompt 为完整问题语句（非"见文档预期"占位符）
  3. expected_output 不含"见文档预期"占位符
  4. 保留 placeholder-reconstructed 类型（补写的问题）

输出字段：id, set_id, name, prompt, expected_output, readiness
  - readiness: green（完整可自动判分）/ yellow（prompt完整但expected占位）/ red（不满足上述条件）
"""

import json
import sys
from pathlib import Path

_MASTER = Path("docs/eval-questions-master.json")
_OUTPUT = Path("docs/eval-questions-formal.json")


def load_master():
    if not _MASTER.exists():
        print(f"[ERROR] 文件不存在：{_MASTER}", file=sys.stderr)
        sys.exit(1)
    with open(_MASTER, encoding='utf-8') as f:
        return json.load(f)


def assess_readiness(eval_item, set_id):
    """
    判断题目就绪度：
    - green: prompt 完整 + expected_output 可自动判分
    - yellow: prompt 完整 + expected_output 为占位符（"见文档预期"等）
    - red: prompt 不完整（title-only 等）
    """
    prompt = eval_item.get('prompt', '')
    expected = eval_item.get('expected_output', '')
    prompt_source = eval_item.get('prompt_source', '')

    # 检查 prompt 是否完整
    if not prompt or prompt_source == 'title-only':
        return 'red'

    # 检查 expected_output 是否可判分
    placeholder_phrases = [
        '见文档预期',
        '（占位：非原文',
        '见文档',
        'expected_output 待补全',
    ]
    if any(phrase in expected for phrase in placeholder_phrases):
        return 'yellow'

    return 'green'


def transform_eval(eval_item, set_id):
    """转换为正式问题格式"""
    return {
        'id': eval_item['id'],
        'set_id': set_id,
        'name': eval_item['name'],
        'prompt': eval_item['prompt'],
        'expected_output': eval_item.get('expected_output', ''),
        'prompt_source': eval_item.get('prompt_source', ''),
        'readiness': assess_readiness(eval_item, set_id),
    }


def generate_formal_set():
    """生成正式问题集"""
    data = load_master()
    formal_evals = []
    stats = {'green': 0, 'yellow': 0, 'red': 0}

    print(f"[INFO] 开始生成正式问题集...")
    print(f"[INFO] 总题数：{data['summary']['total_questions']}")

    for set_data in data['sets']:
        set_id = set_data['set_id']
        evals = set_data.get('evals', [])

        set_formal = []
        for eval_item in evals:
            formal = transform_eval(eval_item, set_id)
            readiness = formal['readiness']

            # 过滤掉 red 类型（不满足条件）
            if readiness == 'red':
                continue

            stats[readiness] += 1
            set_formal.append(formal)

        if set_formal:
            print(f"  {set_id}: {len(set_formal)} 题（green={sum(1 for e in set_formal if e['readiness']=='green')}, yellow={sum(1 for e in set_formal if e['readiness']=='yellow')}）")
            formal_evals.extend(set_formal)

    # 保存输出
    output = {
        'meta': {
            'source': str(_MASTER),
            'generated_at': data.get('generated_at', ''),
            'description': '正式可用问题集（已过滤 title-only 类型）',
            'readiness_legend': {
                'green': 'prompt 完整 + expected_output 可自动判分',
                'yellow': 'prompt 完整 + expected_output 为占位符（需人工判分）',
                'red': 'prompt 不完整（已过滤）',
            }
        },
        'summary': {
            'total': len(formal_evals),
            'by_readiness': stats,
        },
        'evals': formal_evals,
    }

    with open(_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[SUCCESS] 生成完成：{_OUTPUT}")
    print(f"[SUMMARY] 正式问题总数：{len(formal_evals)}")
    print(f"  ✅ green 可自动判分：{stats['green']} 题")
    print(f"  ⚠️  yellow prompt完整但expected占位：{stats['yellow']} 题")
    print(f"  ❌ red 已过滤（title-only等）：{data['summary']['total_questions'] - len(formal_evals) - stats['yellow'] + sum(1 for s in data['sets'] for e in s.get('evals', []) if assess_readiness(e, s['set_id']) == 'red' and 'yellow' not in e.get('prompt', ''))} 题（需重新补全）")


if __name__ == '__main__':
    generate_formal_set()
