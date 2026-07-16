import sys, os
sys.path.insert(0, os.path.dirname(__file__))

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
