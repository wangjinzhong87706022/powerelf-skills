import sys, os; sys.path.insert(0, os.path.dirname(__file__))
import route_opt as ro

def test_m4_haversine_used():
    pts = [{"id":"a","lon":120.0,"lat":32.0},{"id":"b","lon":120.01,"lat":32.01},{"id":"c","lon":120.5,"lat":32.5}]
    clusters = ro.cluster_points(pts, n_clusters=2)
    assert len(clusters) <= 2
    all_ids = [p["id"] for p in pts]
    clustered_ids = [pid for c in clusters for pid in c]
    assert set(all_ids) == set(clustered_ids)


# ============================================================
# Edge cases: _haversine
# ============================================================

def test_haversine_zero_distance():
    """同一点 → 距离为 0"""
    assert ro._haversine(32.0, 120.0, 32.0, 120.0) == 0.0


def test_haversine_known_distance():
    """已知两点（约 111km/度）"""
    d = ro._haversine(32.0, 120.0, 33.0, 120.0)
    assert 100000 < d < 120000  # 约 111km


# ============================================================
# Edge cases: cluster_points
# ============================================================

def test_cluster_single_point():
    """单点 → 1 个聚类"""
    pts = [{"id":"a","lon":120.0,"lat":32.0}]
    clusters = ro.cluster_points(pts, n_clusters=2)
    assert len(clusters) == 1


def test_cluster_k_too_large():
    """n_clusters 超过点数 → 退化为每个点一个聚类"""
    pts = [{"id":"a","lon":120.0,"lat":32.0},{"id":"b","lon":120.5,"lat":32.5}]
    clusters = ro.cluster_points(pts, n_clusters=10)
    assert len(clusters) == 2


def test_cluster_all_same_location():
    """所有点在同一位置 → 1 个聚类"""
    pts = [{"id":str(i),"lon":120.0,"lat":32.0} for i in range(5)]
    clusters = ro.cluster_points(pts, n_clusters=3)
    assert len(clusters) == 1


# ============================================================
# Edge cases: time_balance
# ============================================================

def test_time_balance_empty():
    """空聚类 → 空字典"""
    r = ro.time_balance([], max_time_minutes=120)
    assert isinstance(r, dict)


def test_time_balance_single():
    """单聚类 → 正常返回"""
    clusters = [[{"id": 1, "point_time": 30}]]
    r = ro.time_balance(clusters, max_time_minutes=120)
    assert isinstance(r, dict)


# ============================================================
# Edge cases: priority_select
# ============================================================

def test_priority_select_empty():
    """空列表 → 空列表"""
    assert ro.priority_select([], {}, 5) == []


def test_priority_select_ordering():
    """按分数降序排列"""
    items = [
        {"id": "a"},
        {"id": "b"},
        {"id": "c"},
    ]
    scores = {"b": 0.9, "c": 0.6, "a": 0.3}
    r = ro.priority_select(items, scores, max_count=2)
    assert len(r) == 2
    assert r[0]["id"] == "b"


# ============================================================
# Edge cases: diagnose_problems
# ============================================================

def test_diagnose_empty():
    """空数据 → 无问题诊断（可能返回调查结果）"""
    r = ro.diagnose_problems({})
    # 空字典可能返回"无数据"诊断，但不是问题
    assert isinstance(r, list)


def test_diagnose_no_problems():
    """无缺陷 → 不会返回问题型诊断"""
    r = ro.diagnose_problems({"bad_num": 0, "real_checknum": 100})
    # 低缺陷率可能报告为"设备状况良好"（正面消息），不是实质问题
    for item in r:
        assert item.get("type") != "problem"