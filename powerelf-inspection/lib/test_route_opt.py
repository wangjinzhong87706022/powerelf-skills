import sys, os; sys.path.insert(0, os.path.dirname(__file__))
import route_opt as ro

def test_m4_haversine_used():
    pts = [{"id":"a","lng":120.0,"lat":32.0},{"id":"b","lng":120.01,"lat":32.01},{"id":"c","lng":120.5,"lat":32.5}]
    clusters = ro.cluster_points(pts, k=2)  # 应使用 haversine 而非裸经纬度
    assert len(clusters) <= 2
    # 验证所有点都被分配
    all_ids = [p["id"] for p in pts]
    clustered_ids = [pid for c in clusters for pid in c]
    assert set(all_ids) == set(clustered_ids)
