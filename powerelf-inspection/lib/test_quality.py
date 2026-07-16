import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import quality

def test_c1_custom_weights_coherent():
    # 自定义权重下 total 仍落在 0-100 且与权重一致
    r = quality.compute_quality_score(0.97, 0.97, 0.03, 0.97,
            weights={"completion":0.4,"timeliness":0.2,"defect_rate":0.2,"coverage":0.2})
    assert 0 <= r["total_score"] <= 100
    # 默认权重满分场景
    r2 = quality.compute_quality_score(0.97, 0.97, 0.03, 0.97)
    assert r2["total_score"] >= 90 and r2["grade"] == "A"

def test_c2_defect_rate_denominator():
    # 缺陷发现率 = bad_num / real_objitem（非 plan_checkobj）
    rate = quality.compute_defect_discovery_rate(defects_found=5, real_checkitems=500)
    assert abs(rate - 0.01) < 1e-9

def test_h1_check_percent_documented():
    # 敲定：check_percent 语义=完成率（默认处置），文档/代码/schema 对齐
    assert quality.CHECK_PERCENT_SEMANTICS == "completion"

def test_adjusted_defect_count_removes_faults():
    # 原始缺陷 10，其中 3 个是传感器故障 → 调整后 7
    assert quality.adjusted_defect_count(10, [True, False, True, False, True]) == 7
    # 全故障 → 0（不降到负数）
    assert quality.adjusted_defect_count(3, [True, True, True]) == 0
    # 无故障 → 原值
    assert quality.adjusted_defect_count(5, [False, False]) == 5


# ============================================================
# Edge cases: compute_completion_rate
# ============================================================

def test_completion_rate_zero_plan():
    """计划为 0 → 0"""
    assert quality.compute_completion_rate(0, 10) == 0.0


def test_completion_rate_exceeds():
    """实际超过计划 → 不超过 1.0"""
    assert quality.compute_completion_rate(5, 10) == 1.0


def test_completion_rate_partial():
    """部分完成"""
    assert quality.compute_completion_rate(10, 7) == 0.7


# ============================================================
# Edge cases: compute_timeliness_rate
# ============================================================

def test_timeliness_rate_zero_total():
    """总数为 0 → 0"""
    assert quality.compute_timeliness_rate(0, 0) == 0.0


def test_timeliness_rate_all_late():
    """全部超时"""
    assert quality.compute_timeliness_rate(0, 10) == 0.0


def test_timeliness_rate_all_on_time():
    """全部准时"""
    assert quality.compute_timeliness_rate(10, 10) == 1.0


# ============================================================
# Edge cases: compute_route_coverage
# ============================================================

def test_route_coverage_zero_total():
    """总点数为 0 → 0"""
    assert quality.compute_route_coverage(0, 0) == 0.0


def test_route_coverage_full():
    """全覆盖"""
    assert quality.compute_route_coverage(10, 10) == 1.0


def test_route_coverage_partial():
    """部分覆盖"""
    assert quality.compute_route_coverage(5, 10) == 0.5


# ============================================================
# Edge cases: compute_quality_score
# ============================================================

def test_quality_score_all_zero():
    """全 0 → E 级"""
    r = quality.compute_quality_score(0.0, 0.0, 0.0, 0.0)
    assert r["grade"] == "E" and r["total_score"] < 60


def test_quality_score_boundary_b():
    """接近 B 级边界"""
    r = quality.compute_quality_score(0.80, 0.90, 0.03, 0.90)
    assert 70 <= r["total_score"] <= 89
    assert r["grade"] in ("B", "C")


# ============================================================
# Edge cases: check_quality_alerts
# ============================================================

def test_quality_alerts_empty():
    """空数据 → 无告警"""
    assert quality.check_quality_alerts({}) == []


def test_quality_alerts_overtime():
    """超时率 > 30% → 触发 overtime 告警"""
    alerts = quality.check_quality_alerts({"overtime": 10, "total": 20})
    types = [a["type"] for a in alerts]
    assert "overtime" in types


def test_quality_alerts_omission():
    """遗漏率 > 20% → 触发 omission 告警"""
    alerts = quality.check_quality_alerts({"plan_points": 100, "actual_points": 50})
    types = [a["type"] for a in alerts]
    assert "omission" in types


def test_quality_alerts_defect_backlog():
    """缺陷率 > 20% → 触发 defect_backlog 告警"""
    alerts = quality.check_quality_alerts({"defects_found": 30, "total_checks": 100})
    types = [a["type"] for a in alerts]
    assert "defect_backlog" in types


def test_quality_alerts_consecutive_defects():
    """连续 3+ 有缺陷的任务 → 触发 consecutive_defects 告警"""
    alerts = quality.check_quality_alerts({"consecutive_defect_tasks": [1, 2, 3]})
    types = [a["type"] for a in alerts]
    assert "consecutive_defects" in types
