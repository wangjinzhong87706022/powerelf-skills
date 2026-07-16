"""Tests for mad.py — MAD anomaly detection module."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import mad


def test_detect_anomalies_empty():
    assert mad.detect_anomalies([]) == []


def test_detect_anomalies_normal():
    vals = [1.0, 2.0, 1.5, 2.5, 1.8, 2.2, 1.3, 2.7, 1.6, 2.4]
    r = mad.detect_anomalies(vals, threshold=4.0)
    anomalies = [x for x in r if x["is_anomaly"]]
    assert len(anomalies) == 0


def test_detect_anomalies_clear_outlier():
    vals = [1.0] * 10 + [100.0]
    r = mad.detect_anomalies(vals, threshold=4.0)
    anomalies = [x for x in r if x["is_anomaly"]]
    assert len(anomalies) > 0


def test_detect_anomalies_all_identical():
    vals = [5.0] * 20
    r = mad.detect_anomalies(vals, threshold=4.0)
    anomalies = [x for x in r if x["is_anomaly"]]
    assert len(anomalies) == 0


def test_detect_change_rate_empty():
    assert mad.detect_change_rate([]) == []


def test_detect_change_rate_normal():
    """微小变化 → 不触发"""
    vals = [1.0, 1.01, 1.02, 1.015]  # 变化率 0.01/0.01/0.005 < 0.05
    r = mad.detect_change_rate(vals)
    suspicious = [x for x in r if x["is_suspicious"]]
    assert len(suspicious) == 0


def test_detect_change_rate_spike():
    vals = [1.0, 1.0, 1.0, 100.0]
    r = mad.detect_change_rate(vals)
    # 最后一点变化率 99/1=99 >> 0.05
    assert r[-1]["is_suspicious"] is True


def test_detect_change_rate_zero_division():
    """前值=0 时变化率=0，不触发"""
    vals = [0.0, 100.0]
    r = mad.detect_change_rate(vals)
    assert r[1]["change_rate"] == 0.0
    assert r[1]["is_suspicious"] is False


def test_composite_judge_high():
    mad_r = [{"index": 0, "value": 100, "is_anomaly": True, "score": 8.0}]
    cr_r = [{"index": 0, "value": 100, "is_suspicious": True, "change_rate": 0.5}]
    r = mad.composite_judge(mad_r, cr_r)
    assert r[0]["confidence"] == "high"


def test_composite_judge_medium():
    mad_r = [{"index": 0, "value": 100, "is_anomaly": True, "score": 8.0}]
    cr_r = [{"index": 0, "value": 100, "is_suspicious": False, "change_rate": 0.0}]
    r = mad.composite_judge(mad_r, cr_r)
    assert r[0]["confidence"] == "medium"


def test_composite_judge_low():
    mad_r = [{"index": 0, "value": 100, "is_anomaly": False, "score": 1.0}]
    cr_r = [{"index": 0, "value": 100, "is_suspicious": True, "change_rate": 0.5}]
    r = mad.composite_judge(mad_r, cr_r)
    assert r[0]["confidence"] == "low"


def test_composite_judge_normal():
    mad_r = [{"index": 0, "value": 100, "is_anomaly": False, "score": 1.0}]
    cr_r = [{"index": 0, "value": 100, "is_suspicious": False, "change_rate": 0.0}]
    r = mad.composite_judge(mad_r, cr_r)
    assert r[0]["is_anomaly"] is False