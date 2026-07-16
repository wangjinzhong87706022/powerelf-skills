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
