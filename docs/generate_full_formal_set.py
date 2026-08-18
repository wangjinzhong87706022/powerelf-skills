#!/usr/bin/env python3
"""
generate_full_formal_set.py — 生成完整正式问题集（包含所有题目，即使是 yellow 类型）

输入：docs/eval-questions-formal.json + docs/eval-questions-master.json
输出：docs/eval-questions-formal-full.json

策略：
  1. 保留所有 non-red 题目（green + yellow）
  2. 为 early-warning 的 title-only 题目补全为完整问题语句
  3. 标注 expected_output 是否可自动判分
  4. 输出分 set 的统计信息
"""

import json
import sys
from pathlib import Path

_MASTER = Path("docs/eval-questions-master.json")
_FORMAL = Path("docs/eval-questions-formal.json")
_OUTPUT = Path("docs/eval-questions-formal-full.json")


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def is_title_only(eval_item):
    """判断是否为 title-only 类型"""
    return eval_item.get('prompt_source') == 'title-only' or not eval_item.get('prompt')


def is_expected_placeholder(expected):
    """判断 expected_output 是否为占位符"""
    placeholder_phrases = [
        '见文档预期',
        '（占位：非原文',
        '见文档',
        'expected_output 待补全',
    ]
    return any(phrase in expected for phrase in placeholder_phrases)


def build_complete_prompt(eval_item, set_id):
    """
    为 title-only 题目构建完整问题语句

    策略：
    1. 如果是 data-governance-realdata-tests 的 T 系列题目，保留原 prompt（已完整）
    2. 如果是 early-warning 的 Q 系列 title-only，补全为完整问题
    3. 其他情况保留原 prompt
    """
    prompt = eval_item.get('prompt', '')
    name = eval_item.get('name', '')
    expected = eval_item.get('expected_output', '')

    # data-governance-realdata-tests 的 T 系列题目已完整
    if set_id == 'data-governance-realdata-tests':
        return prompt

    # 非 title-only 题目已完整
    if not is_title_only(eval_item):
        return prompt

    # early-warning title-only 题目：尝试从 expected_output 提取场景信息补全
    # 格式：场景：场景X；数据要求：XXX
    import re
    scene_match = re.search(r'场景：([^；]+)', expected)
    data_match = re.search(r'数据要求：([^；]+)', expected)

    scene = scene_match.group(1) if scene_match else ''
    data = data_match.group(1) if data_match else ''

    # 构建完整问题
    # 尝试提取问题意图（从 name 或 prompt）
    intent = prompt  # 使用原 prompt 作为意图关键词

    # 补全策略：根据意图关键词组合完整问题
    if '告警' in intent or '预警' in intent:
        complete = f"在{scene}场景下，{intent}。（{data}）"
    elif '水位' in intent or '降雨' in intent or '渗压' in intent or '渗流' in intent:
        complete = f"在{scene}场景下，{intent}。（{data}）"
    elif '设备' in intent or '测站' in intent:
        complete = f"在{scene}场景下，{intent}。（{data}）"
    elif '关联' in intent or '分析' in intent or '诊断' in intent:
        complete = f"在{scene}场景下，{intent}。（{data}）"
    elif '预测' in intent or '趋势' in intent or '未来' in intent:
        complete = f"在{scene}场景下，{intent}。（{data}）"
    elif '综合' in intent or '评估' in intent or '风险' in intent:
        complete = f"在{scene}场景下，{intent}。（{data}）"
    elif '处理' in intent or '建议' in intent or '预案' in intent:
        complete = f"在{scene}场景下，{intent}。（{data}）"
    else:
        complete = f"在{scene}场景下，{intent}。（{data}）"

    return complete


def generate_full_formal_set():
    """生成完整正式问题集"""
    print("[INFO] 加载数据...")
    master = load_json(_MASTER)
    formal = load_json(_FORMAL)

    # 建立 id → formal 的映射
    formal_map = {e['id']: e for e in formal['evals']}

    full_evals = []
    stats = {
        'green': 0,
        'yellow': 0,
        'red': 0,
        'by_set': {},
    }

    print(f"[INFO] 处理所有集合...")

    for set_data in master['sets']:
        set_id = set_data['set_id']
        evals = set_data.get('evals', [])

        set_stats = {'green': 0, 'yellow': 0, 'red': 0, 'total': len(evals)}

        for eval_item in evals:
            eid = eval_item['id']

            # 跳过 red 类型（title-only 且无法补全的）
            if is_title_only(eval_item):
                # 尝试补全
                complete_prompt = build_complete_prompt(eval_item, set_id)
                if not complete_prompt:
                    set_stats['red'] += 1
                    continue

                # 转换为完整问题
                formal_eval = {
                    'id': eid,
                    'set_id': set_id,
                    'name': eval_item['name'],
                    'prompt': complete_prompt,
                    'expected_output': eval_item.get('expected_output', ''),
                    'prompt_source': eval_item.get('prompt_source', 'title-only'),
                    'readiness': 'yellow' if is_expected_placeholder(eval_item.get('expected_output', '')) else 'green',
                }
            else:
                # 保留原 formal 记录
                if eid not in formal_map:
                    # 理论上不应该发生
                    continue
                formal_eval = formal_map[eid]

            # 统计
            readiness = formal_eval['readiness']
            stats[readiness] += 1
            set_stats[readiness] += 1
            full_evals.append(formal_eval)

        stats['by_set'][set_id] = set_stats
        print(f"  {set_id}: {len(full_evals)} 题（green={set_stats['green']}, yellow={set_stats['yellow']}, red={set_stats['red']}）")

    # 保存输出
    output = {
        'meta': {
            'source_master': str(_MASTER),
            'source_formal': str(_FORMAL),
            'description': '完整正式问题集（包含所有非 red 题目，title-only 已补全为完整问题）',
            'readiness_legend': {
                'green': 'prompt 完整 + expected_output 可自动判分',
                'yellow': 'prompt 完整 + expected_output 为占位符（需人工判分）',
                'red': 'prompt 不完整（已过滤）',
            },
            'usage': {
                'hermes_cli': 'hermes chat -s <skill> -q "<prompt>" -Q',
                'auto_eval': '仅 green 题目可直接用于自动判分',
                'yellow_eval': 'yellow 题目需人工核对 expected_output',
            }
        },
        'summary': {
            'total': len(full_evals),
            'by_readiness': {
                'green': stats['green'],
                'yellow': stats['yellow'],
            },
            'by_set': stats['by_set'],
        },
        'evals': full_evals,
    }

    with open(_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[SUCCESS] 生成完成：{_OUTPUT}")
    print(f"[SUMMARY]")
    print(f"  📊 正式问题总数：{len(full_evals)}")
    print(f"  ✅ green 可自动判分：{stats['green']} 题")
    print(f"  ⚠️  yellow prompt完整但expected占位：{stats['yellow']} 题")
    print(f"\n[SET BREAKDOWN]")
    for set_id, set_stats in stats['by_set'].items():
        print(f"  {set_id}:")
        print(f"    green={set_stats['green']}, yellow={set_stats['yellow']}, red={set_stats['red']}")
    print(f"\n[USAGE]")
    print(f"  查看完整问题集：less {_OUTPUT}")
    print(f"  按 readiness 过滤：jq '.evals[] | select(.readiness==\"green\")' {_OUTPUT}")
    print(f"  按 set 过滤：jq '.evals[] | select(.set_id==\"data-governance-routing-list\")' {_OUTPUT}")


if __name__ == '__main__':
    generate_full_formal_set()
