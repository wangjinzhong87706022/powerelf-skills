#!/usr/bin/env python3
"""
outliers.py 单元测试 + anomaly_detector.detect_by_method 分派测试。
用法: cd powerelf-data-governance && python3 lib/test_outliers.py
不依赖数据库。仅 numpy 必需；detect_by_method 测试需 pandas+sqlalchemy（缺失则跳过）。
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))            # .../lib
_SKILL_ROOT = os.path.dirname(_HERE)                            # .../powerelf-data-governance
sys.path.insert(0, _HERE)                                       # -> from outliers import ...
sys.path.insert(0, _SKILL_ROOT)                                 # -> from impl.anomaly_detector import ...

from outliers import detect_iqr, detect_percentile

# detect_by_method 测试可选（需 anomaly_detector 的重依赖）
try:
    import pandas  # noqa: F401
    import sqlalchemy  # noqa: F401
    from impl.anomaly_detector import detect_by_method
    HAS_DETECTOR = True
except ImportError:
    HAS_DETECTOR = False


# ============================================================
# detect_iqr
# ============================================================

def test_iqr_finds_injected_outlier():
    """11 点序列 [1..10, 100]，100 应被检出，边界可手算。"""
    vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100]
    r = detect_iqr(vals, k=1.5)
    # numpy 线性插值：p25=3.5, p75=8.5, IQR=5.0, lower=-4.0, upper=16.0
    assert r["q1"] == 3.5, r
    assert r["q3"] == 8.5, r
    assert r["iqr"] == 5.0, r
    assert r["lower_bound"] == -4.0, r
    assert r["upper_bound"] == 16.0, r
    assert r["anomaly_indices"] == [10], r
    assert r["anomaly_count"] == 1, r
    assert r["total_points"] == 11, r


def test_iqr_degenerate_all_equal():
    """所有值相同 → IQR=0，无离群，不报错。"""
    r = detect_iqr([5, 5, 5, 5, 5], k=1.5)
    assert r["iqr"] == 0.0, r
    assert r["anomaly_count"] == 0, r
    assert r["anomaly_indices"] == [], r


def test_iqr_clean_array_no_outliers():
    """平稳序列无离群。"""
    vals = [10.0, 10.1, 9.9, 10.2, 9.8, 10.0, 10.1, 9.9, 10.0, 10.1]
    r = detect_iqr(vals, k=1.5)
    assert r["anomaly_count"] == 0, r


def test_iqr_invalid_k_falls_back():
    """k <= 0 回退到 1.5。"""
    r = detect_iqr([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], k=-1)
    assert r["anomaly_count"] == 1, r
    assert r["anomaly_indices"] == [10], r


def test_iqr_empty():
    r = detect_iqr([], k=1.5)
    assert r["anomaly_count"] == 0, r
    assert r["total_points"] == 0, r


# ============================================================
# detect_percentile
# ============================================================

def test_percentile_finds_injected_outlier():
    """50 个 10 + 一个 999；p99 落在 10 与 999 之间，999 被检出。"""
    vals = [10.0] * 50 + [999.0]
    r = detect_percentile(vals, low=1, high=99)
    # p1=10.0, p99=504.5 (线性插值)
    assert r["low_bound"] == 10.0, r
    assert r["high_bound"] == 504.5, r
    assert r["anomaly_indices"] == [50], r
    assert r["anomaly_count"] == 1, r
    assert r["total_points"] == 51, r


def test_percentile_uniform_tails():
    """[1..100] 均匀序列，p1/p99 边界外仅首尾两点。"""
    vals = list(range(1, 101))
    r = detect_percentile(vals, low=1, high=99)
    assert r["anomaly_indices"] == [0, 99], r
    assert r["anomaly_count"] == 2, r


def test_percentile_invalid_low_high_swaps():
    """low >= high 时回退到 1/99。"""
    r = detect_percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], low=80, high=20)
    # 不报错，且仍返回合法结构
    assert "anomaly_count" in r and "anomaly_indices" in r, r


def test_percentile_empty():
    r = detect_percentile([], low=1, high=99)
    assert r["anomaly_count"] == 0, r
    assert r["total_points"] == 0, r


# ============================================================
# detect_by_method（仅当重依赖可用）
# ============================================================

if HAS_DETECTOR:
    def test_dispatch_mad_default():
        r = detect_by_method("mad", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], threshold=None)
        assert r["method"] == "mad", r
        assert r["analysis_key"] == "mad_analysis", r
        assert 10 in r["result"]["anomaly_indices"], r
        assert r["score_label"] == "z_score", r

    def test_dispatch_iqr_default_threshold():
        r = detect_by_method("iqr", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], threshold=None)
        assert r["method"] == "iqr", r
        assert r["threshold"] == 1.5, r
        assert r["analysis_key"] == "iqr_analysis", r
        assert 10 in r["result"]["anomaly_indices"], r
        assert r["score_label"] is None, r

    def test_dispatch_iqr_explicit_k():
        r = detect_by_method("iqr", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], threshold=3.0)
        assert r["threshold"] == 3.0, r

    def test_dispatch_iqr_invalid_k_falls_back():
        r = detect_by_method("iqr", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], threshold=-2)
        assert r["threshold"] == 1.5, r

    def test_dispatch_percentile_default():
        r = detect_by_method("percentile", [10.0] * 50 + [999.0], threshold=None)
        assert r["method"] == "percentile", r
        assert r["threshold"] == 1, r
        assert r["analysis_key"] == "percentile_analysis", r
        assert 50 in r["result"]["anomaly_indices"], r
        assert r["score_label"] is None, r

    def test_dispatch_percentile_invalid_p_falls_back():
        r = detect_by_method("percentile", [10.0] * 50 + [999.0], threshold=60)
        assert r["threshold"] == 1, r

    def test_dispatch_unknown_method_raises():
        try:
            detect_by_method("zscore", [1, 2, 3], threshold=None)
            assert False, "应抛 ValueError"
        except ValueError:
            pass


# ============================================================
# 运行器
# ============================================================

def _run():
    g = globals()
    tests = [(n, f) for n, f in g.items() if n.startswith("test_") and callable(f)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ FAIL  {name}: {e}")
            failed += 1
    total = passed + failed
    print(f"\n总计 {total} 项: 通过 {passed}, 失败 {failed}")
    if not HAS_DETECTOR:
        print("(pandas/sqlalchemy 缺失，detect_by_method 测试已跳过)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_run())
