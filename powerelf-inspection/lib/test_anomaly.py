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
    assert _inq_falling_fixed([3.0, 2.0, 1.0]) is True  # 短序列真下降
    assert _inq_falling_fixed([1.0, 0.0, 0.0]) is False  # 部分零值（0.0→0.0不可比）

def test_h4_mad_vs_2sigma_on_skewed():
    # 右偏序列：一个远离的极端值。MAD 稳健，受极端值影响小。
    vals = [float(i) for i in range(1, 21)] + [100.0]  # 1..20 + 极端值
    import numpy as np
    median = float(np.median(vals[:-1])); mad = float(np.median(np.abs(np.array(vals[:-1])-median)))*1.4826
    z = abs(vals[-1]-median)/mad if mad>0 else 0.0
    assert z > 4.0  # MAD 检出极端值
