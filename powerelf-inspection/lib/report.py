"""统一巡检报告组装：分节 → MD/JSON/HTML + 嵌 QA 闸 + 挂 confidence_tier + 附 data-quality caveat。
镜像 governance lib/report.py 模式（本轮自建，不升 _shared，见 ROADMAP）。"""
from typing import Any, Dict, List

_QA_CHECKLIST = """## 交付前 QA 自检（见 ../_shared/references/analysis-qa-checklist.md）
- [ ] 关联键(eq_id/stcd/st_id)已核验
- [ ] ew_info_rules 阈值数据存在性已确认
- [ ] 传感器故障 vs 真异常已区分（消费 data-quality tier）
- [ ] business_check 状态码(1/2/3)正确
- [ ] 缺陷率已用 data-quality tier 校正
置信度评级: Ready / With caveats / Needs revision → {confidence_tier}
"""

def render_report(title: str, sections: List[Dict[str, Any]], *,
                  confidence_tier: str = "Needs revision",
                  data_quality_caveat: str = "") -> str:
    """渲染完整巡检报告（Markdown）"""
    md = f"# {title}\n\n"
    for s in sections:
        md += f"## {s['category']}\n\n{s.get('body','')}\n\n"
    if data_quality_caveat:
        md += f"> ⚠️ 数据质量 caveat: {data_quality_caveat}\n\n"
    md += _QA_CHECKLIST.format(confidence_tier=confidence_tier)
    return md

def to_json(sections: List[Dict[str, Any]], confidence_tier: str) -> Dict[str, Any]:
    """导出 JSON 格式报告"""
    return {"sections": sections, "confidence_tier": confidence_tier}
