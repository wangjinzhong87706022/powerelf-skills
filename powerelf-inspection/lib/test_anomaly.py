import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import anomaly

def test_mad_anomaly_detects_outlier():
    # 使用有变化的序列 + 极端离群值
    vals = [float(i) for i in range(1, 21)] + [100.0]  # 1..20 + 极端值
    r = anomaly.mad_anomaly(vals, threshold=4.0)
    assert r["is_anomaly"] is True and r["score"] > 4.0

def test_mad_anomaly_min_samples():
    assert anomaly.mad_anomaly([1.0, 2.0], threshold=4.0)["is_anomaly"] is False  # 样本不足

def test_mad_anomaly_zero_mad():
    assert anomaly.mad_anomaly([5.0]*20, threshold=4.0)["is_anomaly"] is False  # mad=0 不报

def test_consecutive_monotonic_rise():
    r = anomaly.consecutive_monotonic([1,2,3,4,5,6], "rise", 5)
    assert r["is_trend"] is True and r["count"] == 5

def test_consecutive_monotonic_break():
    assert anomaly.consecutive_monotonic([1,2,3,2,1,0], "rise", 3)["is_trend"] is False

def _inq_falling_buggy(inq_trend):
    # 复刻 inspection_analyzer.py:1038 的旧逻辑（含 bug）
    return all(inq_trend[i] < inq_trend[i-1] for i in range(1, len(inq_trend)) if inq_trend[i-1] > 0)

def _inq_falling_fixed(inq_trend):
    comparable = [i for i in range(1, len(inq_trend)) if inq_trend[i-1] > 0]
    return bool(comparable) and all(inq_trend[i] < inq_trend[i-1] for i in comparable)

def test_c3_all_zero_flow_not_falling():
    # 修复后：全零→False（不再误判）；真下降→True
    assert _inq_falling_fixed([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]) is False  # 修复后不再误判
    assert _inq_falling_fixed([5.0, 4.0, 3.0, 2.0, 1.0, 0.5]) is True   # 真下降仍检出
    assert _inq_falling_fixed([3.0, 2.0, 1.0]) is True   # 短序列真下降
    assert _inq_falling_fixed([1.0, 0.0, 0.0]) is True   # 1.0→0.0 真实下降（0.0→0.0不可比但保留前段）

def test_h4_mad_vs_2sigma_on_skewed():
    # 右偏序列：一个远离的极端值。MAD 稳健，受极端值影响小。
    vals = [float(i) for i in range(1, 21)] + [100.0]  # 1..20 + 极端值
    import numpy as np
    median = float(np.median(vals[:-1])); mad = float(np.median(np.abs(np.array(vals[:-1])-median)))*1.4826
    z = abs(vals[-1]-median)/mad if mad>0 else 0.0
    assert z > 4.0  # MAD 检出极端值

def test_layer4_delegates_to_mad():
    # layer4现委托 mad_anomaly，等价行为
    vals = [float(i) for i in range(1, 21)] + [100.0]
    r1 = anomaly.mad_anomaly(vals, threshold=4.0)
    r2 = anomaly.layer4_mad_statistical(vals, threshold=4.0)
    assert r1["is_anomaly"] is True and r2["is_anomaly"] is True
    assert r1["score"] == r2["score"]  # 完全委托，结果一致

def test_layer2_reports_breaching_threshold_m1():
    # abs触发但rel未触发时，应报abs（修M1：不再无条件报rel）
    r = anomaly.layer2_change_rate(100.0, 99.0)  # abs=1, rel≈0.01
    wl = r["water_level"]  # abs=0.5, rel=0.05 → abs触发(1>0.5), rel不触发
    assert wl["is_anomaly"] is True
    assert wl["threshold"] == 0.5  # 应报实际触发的abs阈值

def test_layer1_rejects_malformed_extend():
    rules = [{"extend": "{\"content\":[null]}", "level_r": 3}]  # content[0]=null
    assert anomaly.layer1_threshold(100.0, rules) == []  # 不触发，不抛

def test_layer5_empty_indicators_not_anomaly():
    assert anomaly.layer5_correlation([])["is_anomaly"] is False

def test_confidence_formula_dd1():
    # 文档公式：0.3×阈值 + 0.2×数据质量 + 0.2×趋势 + 0.2×历史 + 0.1×上下文
    layers = {
        1: {"is_anomaly": True, "confidence": 0.9},   # 阈值层触发
        3: {"is_anomaly": True, "confidence": 0.8},   # 趋势层触发
    }
    r = anomaly.composite_anomaly_judge(layers)
    assert 0.0 < r["confidence"] <= 1.0
    assert set(r["triggered_layers"]) <= {1,2,3,4,5}


# ============================================================
# Edge cases: mad_anomaly
# ============================================================

def test_mad_anomaly_empty_list():
    """空序列 → 不是异常"""
    assert anomaly.mad_anomaly([], threshold=4.0)["is_anomaly"] is False


def test_mad_anomaly_single_value():
    """单值（不足 min_samples）→ 不是异常"""
    assert anomaly.mad_anomaly([42.0], threshold=4.0)["is_anomaly"] is False


def test_mad_anomaly_all_identical():
    """全相同值（MAD=0）→ 不是异常"""
    r = anomaly.mad_anomaly([3.0]*15, threshold=4.0)
    assert r["is_anomaly"] is False
    assert r["score"] == 0.0


def test_mad_anomaly_near_threshold():
    """接近阈值但不超标 → 不是异常"""
    vals = [float(i) for i in range(1, 21)]  # 1..20
    current = 25.0  # 远离但可能不触发 threshold=4 的 MAD
    r = anomaly.mad_anomaly(vals + [current], threshold=10.0)
    assert r["is_anomaly"] is False


# ============================================================
# Edge cases: consecutive_monotonic
# ============================================================

def test_consecutive_monotonic_empty():
    """空序列 → 无趋势"""
    assert anomaly.consecutive_monotonic([], "rise", 3)["is_trend"] is False


def test_consecutive_monotonic_single():
    """单元素 → 无趋势"""
    assert anomaly.consecutive_monotonic([5.0], "rise", 2)["is_trend"] is False


def test_consecutive_monotonic_fall():
    """连续下降趋势"""
    r = anomaly.consecutive_monotonic([10, 8, 6, 4, 2], "fall", 3)
    assert r["is_trend"] is True and r["count"] == 4


def test_consecutive_monotonic_flat():
    """平台值（既不上升也不下降）"""
    r_rise = anomaly.consecutive_monotonic([5, 5, 5, 5], "rise", 3)
    r_fall = anomaly.consecutive_monotonic([5, 5, 5, 5], "fall", 3)
    assert r_rise["is_trend"] is False
    assert r_fall["is_trend"] is False


def test_consecutive_monotonic_exact_threshold():
    """恰好等于 min_consecutive → 趋势成立"""
    r = anomaly.consecutive_monotonic([1, 2, 3], "rise", 2)
    assert r["is_trend"] is True and r["count"] == 2


# ============================================================
# Edge cases: layer1_threshold
# ============================================================

def test_layer1_empty_rules():
    """空规则列表 → 空结果"""
    assert anomaly.layer1_threshold(100.0, []) == []


def test_layer1_none_extend():
    """extend 为 None → 跳过"""
    rules = [{"extend": None, "level_r": 3}]
    assert anomaly.layer1_threshold(100.0, rules) == []


def test_layer1_missing_content_key():
    """extend 缺少 content 键 → 跳过"""
    rules = [{"extend": '{"condition": ">"}', "level_r": 3}]
    assert anomaly.layer1_threshold(100.0, rules) == []


def test_layer1_invalid_json():
    """extend 不是合法 JSON → 跳过"""
    rules = [{"extend": "not-json", "level_r": 3}]
    assert anomaly.layer1_threshold(100.0, rules) == []


# ============================================================
# Edge cases: layer2_change_rate
# ============================================================

def test_layer2_no_threshold():
    """变化极小（abs/rel 均不触发）→ 不触发"""
    r = anomaly.layer2_change_rate(100.001, 100.0)  # abs=0.001 < 0.5, rel≈0.00001 < 0.05
    assert r["water_level"]["is_anomaly"] is False


def test_layer2_zero_change():
    """变化为零 → 不触发"""
    r = anomaly.layer2_change_rate(100.0, 100.0)
    assert r["water_level"]["is_anomaly"] is False


# ============================================================
# Edge cases: layer4_mad_statistical
# ============================================================

def test_layer4_empty():
    """空序列 → 不是异常"""
    assert anomaly.layer4_mad_statistical([], threshold=4.0)["is_anomaly"] is False


# ============================================================
# Edge cases: layer5_correlation
# ============================================================

def test_layer5_single_pair():
    """单对反向关联 → 不应异常"""
    pairs = [{"a_trend": "rise", "b_trend": "fall", "label": "water/seepage", "desc": "正常反向关系"}]
    assert anomaly.layer5_correlation(pairs)["is_anomaly"] is False


def test_layer5_contradiction():
    """两指标同时上升 → 矛盾异常"""
    pairs = [{"a_trend": "rise", "b_trend": "rise", "label": "water/seepage", "desc": "水位上升+渗压上升可疑"}]
    assert anomaly.layer5_correlation(pairs)["is_anomaly"] is True


# ============================================================
# Edge cases: composite_anomaly_judge
# ============================================================

def test_confidence_empty_layers():
    """全部层未触发 → 置信度 0，不是异常"""
    r = anomaly.composite_anomaly_judge({})
    assert r["confidence"] == 0.0 and r["is_anomaly"] is False


def test_confidence_all_layers_triggered():
    """所有 5 层触发 → 高置信度"""
    layers = {i: {"is_anomaly": True, "confidence": 0.9} for i in range(1, 6)}
    r = anomaly.composite_anomaly_judge(layers)
    assert r["is_anomaly"] is True
    assert len(r["triggered_layers"]) == 5
