#!/usr/bin/env python3
"""
extract_hermes_ready_questions.py — 提取可直接在 hermes CLI 使用的完整问题列表

输出格式：
  set_id | id | name | skill | prompt | expected_output | readiness

skill 映射：根据 set_id 推断对应 hermes skill
  - early-warning-v3-matrix → powerelf-early-warning
  - data-governance-routing-list → powerelf-data-governance
  - data-governance-realdata-tests → powerelf-data-governance
  - routing-evals-v1 → powerelf-chatbi（路由测试）
  - routing-evals-v2 → powerelf-chatbi（路由测试）
  - inspection-eval-criteria → powerelf-inspection
  - inspection-eval-cases → powerelf-inspection
"""

import json
from pathlib import Path

_FORMAL_FULL = Path("docs/eval-questions-formal-full.json")
_OUTPUT_MD = Path("docs/hermes-ready-questions.md")
_OUTPUT_JSON = Path("docs/hermes-ready-questions.json")

SET_TO_SKILL = {
    'early-warning-v3-matrix': 'powerelf-early-warning',
    'data-governance-routing-list': 'powerelf-data-governance',
    'data-governance-realdata-tests': 'powerelf-data-governance',
    'routing-evals-v1': 'powerelf-chatbi',
    'routing-evals-v2': 'powerelf-chatbi',
    'inspection-eval-criteria': 'powerelf-inspection',
    'inspection-eval-cases': 'powerelf-inspection',
}


def load_formal():
    with open(_FORMAL_FULL, encoding='utf-8') as f:
        return json.load(f)


def generate_hermes_ready():
    data = load_formal()
    evals = data['evals']

    # 按 readiness 分组
    green = [e for e in evals if e['readiness'] == 'green']
    yellow = [e for e in evals if e['readiness'] == 'yellow']

    # 生成 Markdown
    md_lines = [
        "# Hermes CLI 直接可用问题集",
        "",
        f"> 生成时间：{data['meta'].get('generated_at', 'N/A')}",
        f"> 总计：{data['summary']['total']} 题",
        f"> ✅ green（可直接判分）：{data['summary']['by_readiness']['green']} 题",
        f"> ⚠️  yellow（需人工判分）：{data['summary']['by_readiness']['yellow']} 题",
        "",
        "## 使用说明",
        "",
        "### 1. 在 Hermes CLI 中直接提问",
        "",
        "```bash",
        "# 基本语法",
        "hermes chat -s <skill> -q \"<问题>\" -Q",
        "",
        "# 示例：查询水位异常",
        "hermes chat -s powerelf-data-governance -q \"帮我检查一下最近24小时水库水位数据有没有异常值，用MAD算法检测一下\" -Q",
        "",
        "# 示例：巡检分析",
        "hermes chat -s powerelf-inspection -q \"渗压计416在5月20日有10kPa突变，工具是否检出？\" -Q",
        "```",
        "",
        "### 2. 按 Skill 分类",
        "",
    ]

    # 按 skill 分组
    by_skill = {}
    for e in green + yellow:
        skill = SET_TO_SKILL.get(e['set_id'], 'unknown')
        if skill not in by_skill:
            by_skill[skill] = {'green': [], 'yellow': []}
        by_skill[skill][e['readiness']].append(e)

    for skill in sorted(by_skill.keys()):
        questions = by_skill[skill]
        green_q = questions['green']
        yellow_q = questions['yellow']

        md_lines.extend([
            f"#### {skill}（{len(green_q) + len(yellow_q)} 题）",
            "",
        ])

        if green_q:
            md_lines.append("**✅ 可直接判分的问题**")
            md_lines.append("")
            for i, e in enumerate(green_q, 1):
                md_lines.extend([
                    f"{i}. **{e['id']}** ({e['name']})",
                    f"   ```bash",
                    f"   hermes chat -s {skill} -q \"{e['prompt']}\" -Q",
                    f"   ```",
                    f"   *预期：{e['expected_output'][:80]}{'...' if len(e['expected_output']) > 80 else ''}*",
                    "",
                ])

        if yellow_q:
            md_lines.append("**⚠️  需人工判分的问题**")
            md_lines.append("")
            for i, e in enumerate(yellow_q, 1):
                md_lines.extend([
                    f"{i}. **{e['id']}** ({e['name']})",
                    f"   ```bash",
                    f"   hermes chat -s {skill} -q \"{e['prompt']}\" -Q",
                    f"   ```",
                    f"   *注意：expected_output 为占位符，需人工核对*",
                    "",
                ])

    # 生成 JSON
    json_output = {
        'meta': data['meta'],
        'summary': data['summary'],
        'by_skill': {
            skill: {
                'green': [e['id'] for e in questions['green']],
                'yellow': [e['id'] for e in questions['yellow']],
            }
            for skill, questions in by_skill.items()
        },
        'evals': evals,
    }

    # 保存文件
    with open(_OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))

    with open(_OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] 生成完成")
    print(f"  Markdown：{_OUTPUT_MD}")
    print(f"  JSON：{_OUTPUT_JSON}")
    print(f"\n[SUMMARY]")
    print(f"  Skill 数量：{len(by_skill)}")
    for skill in sorted(by_skill.keys()):
        g = len(by_skill[skill]['green'])
        y = len(by_skill[skill]['yellow'])
        print(f"  {skill}: {g + y} 题（green={g}, yellow={y}）")


if __name__ == '__main__':
    generate_hermes_ready()
