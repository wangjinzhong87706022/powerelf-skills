"""Tests for validate_report_consistency — 报告一致性断言闸（T1）。

复现评审 N1：带 5 处矛盾的报告被判 Ready to share。本闸在渲染前校验：
1. severity 汇总 ≡ findings 明细（口径漂移）
2. "N 维全部成功" 与 "无数据维度" 不得同现
3. "变化率 N 次" 与 "正常" 自相矛盾检测
4. MAD 统计只允许一个来源（防跨工具混装）
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "impl"))
import inspection_analyzer as ia


def _mk_analyses(findings_by_dim=None, statuses=None):
    """构造 analyses 列表：{category, status, findings:[{level,message,detail}]}"""
    findings_by_dim = findings_by_dim or {}
    statuses = statuses or {}
    out = []
    for cat, fnds in findings_by_dim.items():
        out.append({"category": cat, "status": statuses.get(cat, "ok"),
                    "findings": [{"level": f["level"], "message": f.get("message", ""),
                                  "detail": f.get("detail", "")} for f in fnds]})
    return out


def test_severity_mismatch_detected():
    """明细 2 CRITICAL / 1 WARNING，传入 critical=1/warnings=1 → 违规。"""
    analyses = _mk_analyses({
        "维度A": [{"level": "CRITICAL", "message": "a"}, {"level": "CRITICAL", "message": "b"}],
        "维度B": [{"level": "WARNING", "message": "c"}],
    })
    passed, viols = ia.validate_report_consistency(analyses, critical=1, warnings=1)
    assert not passed
    assert any("severity 汇总与明细不符" in v for v in viols)


def test_severity_match_passes():
    """明细与传入一致 → 通过。"""
    analyses = _mk_analyses({
        "维度A": [{"level": "CRITICAL", "message": "a"}],
        "维度B": [{"level": "WARNING", "message": "c"}],
    })
    passed, viols = ia.validate_report_consistency(analyses, critical=1, warnings=1)
    assert passed
    assert viols == []


def test_no_data_with_claims_detected():
    """声明 2 维全覆盖，但 1 维无数据 → 违规。"""
    analyses = _mk_analyses({
        "维度A": [{"level": "OK", "message": "正常"}],
        "维度B": [],
    }, statuses={"维度B": "无数据"})
    passed, viols = ia.validate_report_consistency(analyses, critical=0, warnings=0)
    assert not passed
    assert any("无数据/不足" in v for v in viols)


def test_all_no_data_passes():
    """全部维度都无数据 → 不触发"部分无数据"违规。"""
    analyses = _mk_analyses({"维度A": [], "维度B": []},
                            statuses={"维度A": "无数据", "维度B": "无数据"})
    passed, viols = ia.validate_report_consistency(analyses, critical=0, warnings=0)
    assert passed


def test_rate_vs_normal_contradiction_detected():
    """findings 同时含"变化率 5 次"与"分布正常" → 违规（问题③）。"""
    analyses = _mk_analyses({
        "渗压监测": [{"level": "WARNING", "message": "变化率超限 5 次",
                    "detail": "数据分布正常"}],
    })
    passed, viols = ia.validate_report_consistency(analyses, critical=0, warnings=1)
    assert not passed
    assert any("自相矛盾" in v for v in viols)


def test_mad_multi_source_detected():
    """MAD 统计出现 2 个来源 → 违规（防跨工具混装）。"""
    analyses = _mk_analyses({
        "MAD统计异常": [{"level": "OK", "message": "正常"}],
        "MAD统计异常": [{"level": "OK", "message": "正常"}],
    })
    # dict 键重复会覆盖，需手动构造
    analyses = [
        {"category": "MAD统计异常", "findings": [{"level": "OK", "message": "正常"}], "status": "ok"},
        {"category": "MAD统计异常", "findings": [{"level": "OK", "message": "正常"}], "status": "ok"},
    ]
    passed, viols = ia.validate_report_consistency(analyses, critical=0, warnings=0)
    assert not passed
    assert any("MAD 统计出现 2 个来源" in v for v in viols)
