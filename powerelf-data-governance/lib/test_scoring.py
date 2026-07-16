"""Tests for scoring.py — quality scoring module."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import scoring


def test_quality_normal():
    """正常缺失率+异常率 → 非零分"""
    s = scoring.compute_quality_score(0.05, 0.03)
    assert 25 < s < 35  # 约 30


def test_quality_zero_when_sum_ge_30pct():
    """missing + anomaly >= 30% → 0"""
    assert scoring.compute_quality_score(0.2, 0.2) == 0.0
    assert scoring.compute_quality_score(0.3, 0.0) == 0.0
    assert scoring.compute_quality_score(0.0, 0.3) == 0.0


def test_quality_both_zero():
    """无缺失无异常 → 满分"""
    s = scoring.compute_quality_score(0.0, 0.0)
    assert s == 35.0


def test_quality_all_missing():
    """全缺失 → 0"""
    s = scoring.compute_quality_score(1.0, 0.0)
    assert s == 0.0


def test_stability_normal():
    """正常在线率"""
    s = scoring.compute_stability_score(0.1, 0.05)
    assert 8 < s < 10


def test_stability_all_offline():
    """全离线"""
    s = scoring.compute_stability_score(1.0, 1.0)
    assert s == 0.0


def test_stability_perfect():
    """无离线无异常"""
    s = scoring.compute_stability_score(0.0, 0.0)
    assert s == 10.0


def test_fault_normal():
    s = scoring.compute_fault_score(3, 2)
    assert 25 < s < 35


def test_fault_too_many():
    """超过 20 次事件 → 0"""
    assert scoring.compute_fault_score(15, 10) == 0.0
    assert scoring.compute_fault_score(0, 21) == 0.0


def test_fault_zero():
    assert scoring.compute_fault_score(0, 0) == 40.0


def test_completeness_full():
    assert scoring.compute_completeness_score(24, 24) == 15.0


def test_completeness_partial():
    s = scoring.compute_completeness_score(18, 24)
    assert s == 7.5  # 18/24=0.75, 低于 80% 用 penalty 系数 10 → 7.5


def test_completeness_below_80pct():
    """低于 80% → penalty 系数 10 而非 15"""
    s = scoring.compute_completeness_score(10, 24)
    assert s < 10  # 10/24 * 10 ≈ 4.17


def test_completeness_zero_expected():
    assert scoring.compute_completeness_score(10, 0) == 0.0


def test_total_normal():
    t = scoring.compute_total_score(30, 8, 30, 13)
    assert 70 < t < 90


def test_total_max():
    assert scoring.compute_total_score(35, 10, 40, 15) == 100.0


def test_time_decay_today():
    assert scoring.time_decay_weight(0) == 1.0


def test_time_decay_old():
    w = scoring.time_decay_weight(30)
    assert 0 < w < 0.3


def test_trend_improving():
    assert scoring.compute_score_trend(90, 80) == "improving"


def test_trend_declining():
    assert scoring.compute_score_trend(75, 85) == "declining"


def test_trend_stable():
    assert scoring.compute_score_trend(82, 80) == "stable"


def test_equil_score_returns_all_dims():
    r = scoring.compute_equil_score(0.05, 0.03, 0.1, 0.05, 3, 2, 22, 24)
    assert set(r.keys()) == {"total", "quality", "stability", "fault", "completeness"}
    assert 0 <= r["total"] <= 100