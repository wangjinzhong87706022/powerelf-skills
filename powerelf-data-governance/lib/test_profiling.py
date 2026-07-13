#!/usr/bin/env python3
"""
profiling.py 单元测试。
用法: cd /home/scada/powerelf-worktree-A && python3 powerelf-data-governance/lib/test_profiling.py
不依赖数据库。仅 numpy/pandas 可选。
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))            # .../lib
_SKILL_ROOT = os.path.dirname(_HERE)                            # .../powerelf-data-governance
sys.path.insert(0, _HERE)                                       # -> from profiling import ...
sys.path.insert(0, _SKILL_ROOT)                                 # -> from lib.profiling import ...

# ============================================================
# 导入目标模块（profiling.py 尚不存在时会在 Step 2 报 ModuleNotFoundError）
# ============================================================

from profiling import (
    classify_column,
    profile_numeric,
    profile_temporal,
    completeness_tier,
    detect_accuracy_flags,
    profile_table,
)


# ============================================================
# classify_column
# ============================================================

def test_classify_identifier():
    """eq_id / stcd → identifier。"""
    assert classify_column("eq_id") == "identifier"
    assert classify_column("stcd") == "identifier"


def test_classify_temporal():
    """*_time / create_time → temporal。"""
    assert classify_column("create_time") == "temporal"
    assert classify_column("measurement_time") == "temporal"


def test_classify_metric():
    """water_pressure / rz / rainfall → metric。"""
    assert classify_column("water_pressure") == "metric"
    assert classify_column("rz") == "metric"
    assert classify_column("rainfall") == "metric"


def test_classify_boolean():
    """含 switch / status → boolean。"""
    assert classify_column("switch") == "boolean"
    assert classify_column("device_status") == "boolean"


def test_classify_unrecognized_falls_to_text():
    """无法识别的列 → text。"""
    assert classify_column("notes") == "text"
    assert classify_column("unknown_col") == "text"


# ============================================================
# profile_numeric
# ============================================================

def test_profile_numeric_basic():
    """基础统计量正确。"""
    vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    r = profile_numeric(vals)
    assert r["count"] == 10, r
    assert r["null_rate"] == 0.0, r
    assert r["min"] == 1.0, r
    assert r["max"] == 10.0, r
    assert r["mean"] == 5.5, r
    assert r["median"] == 5.5, r
    assert r["distinct"] == 10, r
    assert r["zero_rate"] == 0.0, r
    assert r["negative_rate"] == 0.0, r
    assert r["p1"] == 1.09, r   # np.percentile 线性插值
    assert r["p99"] == 9.91, r


def test_profile_numeric_nulls():
    """含 None → null_rate 正确。"""
    vals = [1.0, None, 3.0, None, 5.0]
    r = profile_numeric(vals)
    assert r["count"] == 5, r
    assert r["null_rate"] == 0.4, r
    assert r["min"] == 1.0, r
    assert r["max"] == 5.0, r


def test_profile_numeric_zeros():
    """含零值 → zero_rate 正确。"""
    vals = [0.0, 1.0, 0.0, 3.0, 0.0]
    r = profile_numeric(vals)
    assert r["zero_rate"] == 0.6, r
    assert r["negative_rate"] == 0.0, r


def test_profile_numeric_negatives():
    """含负值 → negative_rate 正确。"""
    vals = [-1.0, 2.0, -3.0, 4.0, 5.0]
    r = profile_numeric(vals)
    assert r["negative_rate"] == 0.4, r
    assert r["zero_rate"] == 0.0, r


def test_profile_numeric_distinct():
    """distinct 去重统计正确。"""
    vals = [1.0, 2.0, 2.0, 3.0, 3.0, 3.0]
    r = profile_numeric(vals)
    assert r["distinct"] == 3, r


# ============================================================
# profile_temporal
# ============================================================

def test_profile_temporal_basic():
    """时间跨度 / gap 正确。"""
    import pandas as pd
    vals = pd.to_datetime([
        "2024-01-01 00:00:00",
        "2024-01-01 01:00:00",
        "2024-01-01 03:00:00",   # 2h gap
        "2024-01-01 06:00:00",   # 3h gap
    ])
    r = profile_temporal(vals)
    assert r["min"] == pd.Timestamp("2024-01-01 00:00:00"), r
    assert r["max"] == pd.Timestamp("2024-01-01 06:00:00"), r
    assert r["span"] == pd.Timedelta(hours=6), r
    assert r["median_gap"] == pd.Timedelta(hours=2), r
    assert r["max_gap"] == pd.Timedelta(hours=3), r
    assert r["null_rate"] == 0.0, r


def test_profile_temporal_future_count():
    """未来时间戳被计入。"""
    import pandas as pd
    now = pd.Timestamp("2024-06-01 00:00:00")
    vals = pd.to_datetime([
        "2024-01-01 00:00:00",
        "2024-12-31 23:59:59",   # 未来
    ])
    r = profile_temporal(vals, now=now)
    assert r["future_count"] == 1, r


def test_profile_temporal_empty():
    """空序列 → 全 None + 0 值。"""
    r = profile_temporal([])
    assert r["min"] is None, r
    assert r["max"] is None, r
    assert r["span"] is None, r
    assert r["null_rate"] == 0.0, r


# ============================================================
# completeness_tier
# ============================================================

def test_completeness_tier_green():
    assert completeness_tier(0.995) == "绿"
    assert completeness_tier(1.0) == "绿"


def test_completeness_tier_yellow():
    assert completeness_tier(0.95) == "黄"
    assert completeness_tier(0.99) == "黄"


def test_completeness_tier_orange():
    assert completeness_tier(0.90) == "橙"
    assert completeness_tier(0.80) == "橙"


def test_completeness_tier_red():
    assert completeness_tier(0.79) == "红"
    assert completeness_tier(0.0) == "红"


# ============================================================
# detect_accuracy_flags
# ============================================================

def test_detect_accuracy_placeholder_999999():
    """植入 999999 占位符应被检出。"""
    col_profile = {
        "type": "numeric",
        "min": 0.0,
        "max": 999999.0,
        "mean": 999000.0,
        "distinct": 5,
        "null_rate": 0.0,
    }
    flags = detect_accuracy_flags(col_profile)
    assert "placeholder_999999" in flags, flags


def test_detect_accuracy_bimodal():
    """双峰分布 hint → 标记 bimodal。"""
    col_profile = {
        "type": "numeric",
        "distribution_hint": "双峰",
        "min": 0.0,
        "max": 100.0,
        "null_rate": 0.0,
    }
    flags = detect_accuracy_flags(col_profile)
    assert "bimodal_distribution" in flags, flags


def test_detect_accuracy_no_flags():
    """干净列 → 空 flags。"""
    col_profile = {
        "type": "numeric",
        "distribution_hint": "正态",
        "min": 10.0,
        "max": 100.0,
        "null_rate": 0.01,
    }
    flags = detect_accuracy_flags(col_profile)
    assert flags == [], flags


# ============================================================
# profile_table
# ============================================================

def test_profile_table_integration():
    """rows → 每列分类 + numeric profile + table-level completeness_tier + flags。"""
    rows = [
        {"eq_id": "E01", "create_time": "2024-01-01T00:00:00", "water_pressure": 1.5, "switch": 1},
        {"eq_id": "E02", "create_time": "2024-01-01T01:00:00", "water_pressure": 2.5, "switch": 0},
        {"eq_id": None, "create_time": None, "water_pressure": None, "switch": None},
    ]
    r = profile_table(rows)
    assert "columns" in r, r
    assert "completeness_tier" in r, r
    assert "flags" in r, r
    assert r["row_count"] == 3, r
    # eq_id 含 1 个 null → 有效值率 2/3 = 0.667 → 红
    assert r["completeness_tier"] == "红", r
    col_names = [c["name"] for c in r["columns"]]
    assert "eq_id" in col_names, r
    assert "water_pressure" in col_names, r


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
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_run())
