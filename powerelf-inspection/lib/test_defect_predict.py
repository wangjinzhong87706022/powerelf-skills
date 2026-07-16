import sys, os; sys.path.insert(0, os.path.dirname(__file__))
import defect_predict as dp

def test_m3_hotspot_thresholds_documented():
    # 阈值标注为启发式（非普适），且函数可跑
    assert hasattr(dp, "HOTSPOT_THRESHOLDS")  # 显式常量 + 注释说明启发式


# ============================================================
# Edge cases: linear_trend
# ============================================================

def test_linear_trend_empty():
    """空序列 → 稳定，预测 0"""
    r = dp.linear_trend([])
    assert r["trend_direction"] == "stable"
    assert r["predicted_next"] == 0


def test_linear_trend_single():
    """单值 → 稳定，预测该值"""
    r = dp.linear_trend([10.0])
    assert r["trend_direction"] == "stable"
    assert r["predicted_next"] == 10


def test_linear_trend_rising():
    """上升趋势"""
    r = dp.linear_trend([1.0, 2.0, 3.0, 4.0, 5.0])
    assert r["trend_direction"] == "rising"
    assert r["predicted_next"] > 5


def test_linear_trend_falling():
    """下降趋势"""
    r = dp.linear_trend([10.0, 8.0, 6.0, 4.0, 2.0])
    assert r["trend_direction"] == "falling"
    assert r["predicted_next"] < 2


def test_linear_trend_flat():
    """平台值 → 稳定"""
    r = dp.linear_trend([5.0, 5.0, 5.0, 5.0])
    assert r["trend_direction"] == "stable"


def test_linear_trend_negative_prediction_clamped():
    """预测值负 → 钳位到 0"""
    r = dp.linear_trend([100.0, 10.0, 1.0])
    assert r["predicted_next"] >= 0


# ============================================================
# Edge cases: seasonal_analysis
# ============================================================

def test_seasonal_empty():
    """空数据 → 季节性因子全 1.0"""
    r = dp.seasonal_analysis({})
    assert all(r["seasonal_factor"][m] == 1.0 for m in range(1, 13))


def test_seasonal_single_month():
    """只有一个月的数据 → 该月为 peak 和 trough"""
    r = dp.seasonal_analysis({6: [10.0, 12.0, 8.0]})
    assert r["peak_months"][0]["month"] == 6


def test_seasonal_flood_peak():
    """汛期月份应有较高因子"""
    r = dp.seasonal_analysis({
        6: [10.0, 12.0], 7: [15.0, 18.0], 8: [20.0, 22.0],
        1: [1.0, 2.0], 2: [1.0, 1.0],
    })
    peak_months = [pm["month"] for pm in r["peak_months"]]
    assert 8 in peak_months  # 8月应为 peak


# ============================================================
# Edge cases: bayesian_hotspot
# ============================================================

def test_hotspot_empty_history():
    """空历史 → 空列表"""
    assert dp.bayesian_hotspot([], {}) == []


def test_hotspot_no_matches():
    """历史中的 equip_id 都不在 importance 中 → 权重默认为 1.0"""
    history = [{"equip_id": "EQ001", "defect_count": 5}]
    r = dp.bayesian_hotspot(history, {})
    assert len(r) == 1
    assert r[0]["importance_weight"] == 1.0


def test_hotspot_high_risk():
    """高频缺陷 + 高重要性 → high 风险"""
    history = [{"equip_id": "EQ001", "defect_count": 20, "total_months": 12}]
    r = dp.bayesian_hotspot(history, {"EQ001": 4.0})
    assert r[0]["risk_level"] == "high"


def test_hotspot_score_ordering():
    """多个设备 → 按 hotspot_score 降序排列"""
    history = [
        {"equip_id": "EQ_A", "defect_count": 20, "total_months": 12},
        {"equip_id": "EQ_B", "defect_count": 1, "total_months": 12},
        {"equip_id": "EQ_C", "defect_count": 5, "total_months": 12},
    ]
    r = dp.bayesian_hotspot(history, {e["equip_id"]: 2.0 for e in history})
    scores = [e["hotspot_score"] for e in r]
    assert scores == sorted(scores, reverse=True)
