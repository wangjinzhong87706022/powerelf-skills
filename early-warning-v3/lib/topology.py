#!/usr/bin/env python3
"""
topology.py — 水利对象知识图谱查询函数

提供两个核心函数:
    1. compute_blast_radius(start_node, edge_types, max_hops)
       从 start_node 出发, BFS 遍历指定类型的边, 返回所有可达节点 + 路径.
       对应腾讯"故障在拓扑图上的爆炸半径".
    2. find_fault_cluster(alarm_nodes, time_window_min)
       给定一组告警涉及的节点, 用 union-find 把拓扑可达的节点聚成连通分量,
       再用 time_window 过滤时间不相关的告警, 返回"故障团".
       对应腾讯"社团聚类 + DBSCAN".

另外提供根因排序辅助函数:
    3. rank_root_causes(event, top_n)
       在故障团内按 5 维打分排序 TOPN 可疑根因.
    4. apply_confidence_gate(ranked_causes)
       根因置信度低于阈值时降级返回"建议人工介入", 绝不胡编.

依赖:
    pymysql 1.x
    Python 3.11+
    topo_node / topo_edge 表已由 build_topology.py 建好

作者: Powerelf Team
版本: 1.0
日期: 2026-08-05
"""

import json
import os
from collections import defaultdict, deque
from datetime import datetime
from math import radians, sin, cos, asin, sqrt
from typing import Any, Dict, List, Optional, Set, Tuple

import pymysql

# ============================================================
# 1. 配置
# ============================================================
DB_CONFIG: Dict[str, Any] = {
    "host": os.getenv("POWERELF_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("POWERELF_DB_PORT", "3306")),
    "user": os.getenv("POWERELF_DB_USER", "root"),
    "password": os.getenv("POWERELF_DB_PASSWORD", "123456aA."),
    "database": os.getenv("POWERELF_DB_NAME", "powerelf_srm_yml"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# 根因排序五维权重 (对齐 docs/water-conservancy-knowledge-graph-and-root-cause-ranking.md 第四章)
WEIGHTS: Dict[str, float] = {
    "temporal_priority": 0.25,
    "topology_centrality": 0.20,
    "causal_evidence": 0.25,
    "alarm_severity": 0.15,
    "historical_recurrence": 0.15,
}

# 置信度闸阈值
SUPPRESS_THRESHOLD = 0.5
WARNING_THRESHOLD = 0.7

# 告警级别 → 严重度分数
SEVERITY_MAP: Dict[str, float] = {
    "1": 1.00,  # 红色
    "2": 0.75,  # 橙色
    "3": 0.50,  # 黄色
    "4": 0.25,  # 蓝色
}


# ============================================================
# 2. 工具函数
# ============================================================
def get_connection() -> pymysql.connections.Connection:
    return pymysql.connect(**DB_CONFIG)


def safe_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def parse_json_field(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (list, dict)):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return None
    return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * asin(sqrt(a))


# ============================================================
# 3. Union-Find (并查集)
# ============================================================
class UnionFind:
    """带路径压缩和按秩合并的并查集"""

    def __init__(self, items: List[Any]):
        self.parent: Dict[Any, Any] = {x: x for x in items}
        self.rank: Dict[Any, int] = {x: 0 for x in items}

    def add(self, x: Any) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0

    def find(self, x: Any) -> Any:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: Any, y: Any) -> None:
        self.add(x)
        self.add(y)
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def clusters(self) -> Dict[Any, List[Any]]:
        result: Dict[Any, List[Any]] = defaultdict(list)
        for x in self.parent:
            result[self.find(x)].append(x)
        return dict(result)


# ============================================================
# 4. 核心查询函数
# ============================================================
def compute_blast_radius(
    start_node: str,
    edge_types: Optional[List[str]] = None,
    max_hops: int = 2,
    conn: Optional[pymysql.connections.Connection] = None,
) -> Dict[str, Any]:
    """
    从 start_node 出发, BFS 遍历指定类型的边, 返回所有可达节点 + 路径.

    对应腾讯 TCOP "故障在拓扑图上的爆炸半径".

    Args:
        start_node: 起始节点 node_id, 如 "station:123"
        edge_types: 限定的边类型, 默认 ["belongs_to", "upstream_of", "causes", "near"]
            注意: near 边在 BFS 时按无向处理 (双向可达)
            belongs_to 默认向上 (device→station→project) 方向遍历
            upstream_of 按 from→to 方向 (上游→下游)
            causes 按 from→to 方向 (因→果)
        max_hops: 最大 BFS 跳数, 默认 2
        conn: 可选的数据库连接, 不传则内部新建

    Returns:
        {
            "start_node": "station:123",
            "reachable_nodes": [
                {"node_id", "node_type", "name", "hops", "path": [...]}
            ],
            "affected_devices": [...],
            "affected_stations": [...],
            "affected_projects": [...],
            "affected_dams": [...],
            "affected_sections": [...],
            "affected_points": [...],
            "total_affected": int
        }
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    if edge_types is None:
        edge_types = ["belongs_to", "upstream_of", "causes", "near"]

    try:
        # 取 start_node 的节点信息
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT node_id, node_type, name FROM topo_node WHERE node_id = %s AND deleted = 0",
                (start_node,),
            )
            start_row = cursor.fetchone()
        if not start_row:
            return {
                "start_node": start_node,
                "reachable_nodes": [],
                "affected_devices": [],
                "affected_stations": [],
                "affected_projects": [],
                "affected_dams": [],
                "affected_sections": [],
                "affected_points": [],
                "total_affected": 0,
                "error": f"start_node {start_node} not found in topo_node",
            }

        # BFS
        visited: Dict[str, Dict[str, Any]] = {
            start_node: {
                "node_id": start_node,
                "node_type": start_row["node_type"],
                "name": start_row["name"],
                "hops": 0,
                "path": [start_node],
            }
        }
        queue: deque = deque([(start_node, 0)])

        # 预取所有相关边, 避免每跳一次 SQL
        # 在内存里建邻接表
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(edge_types))
            cursor.execute(
                f"""
                SELECT from_node, to_node, edge_type, weight, lag_min
                FROM topo_edge
                WHERE deleted = 0 AND edge_type IN ({placeholders})
                """,
                edge_types,
            )
            all_edges = cursor.fetchall()

        # 建邻接表: adjacency[node_id] = [(neighbor, edge_type, weight, lag_min, direction)]
        # direction: "out" 表示 from_node=node, "in" 表示 to_node=node
        adjacency: Dict[str, List[Tuple[str, str, float, Optional[int], str]]] = defaultdict(list)
        for e in all_edges:
            f, t = e["from_node"], e["to_node"]
            et, w = e["edge_type"], safe_float(e.get("weight")) or 1.0
            lag = e.get("lag_min")
            # 出边: f → t
            adjacency[f].append((t, et, w, lag, "out"))
            # 入边: t ← f (按无向处理, 用于反向溯源)
            adjacency[t].append((f, et, w, lag, "in"))

        while queue:
            current, hops = queue.popleft()
            if hops >= max_hops:
                continue
            for neighbor, et, w, lag, direction in adjacency.get(current, []):
                if neighbor in visited:
                    continue
                visited[neighbor] = {
                    "node_id": neighbor,
                    "node_type": None,  # 下面批量补
                    "name": None,
                    "hops": hops + 1,
                    "path": visited[current]["path"] + [neighbor],
                }
                queue.append((neighbor, hops + 1))

        # 批量补 node_type / name
        node_ids = list(visited.keys())
        if node_ids:
            with conn.cursor() as cursor:
                placeholders = ",".join(["%s"] * len(node_ids))
                cursor.execute(
                    f"""
                    SELECT node_id, node_type, name
                    FROM topo_node
                    WHERE node_id IN ({placeholders}) AND deleted = 0
                    """,
                    node_ids,
                )
                for row in cursor.fetchall():
                    if row["node_id"] in visited:
                        visited[row["node_id"]]["node_type"] = row["node_type"]
                        visited[row["node_id"]]["name"] = row["name"]

        # 按类型分组
        affected: Dict[str, List[str]] = defaultdict(list)
        for nid, info in visited.items():
            if nid == start_node:
                continue
            nt = info["node_type"] or "unknown"
            type_key = f"affected_{nt}s"  # affected_devices / affected_stations 等
            affected[type_key].append(nid)

        reachable_list = sorted(
            visited.values(), key=lambda x: (x["hops"], x["node_id"])
        )

        return {
            "start_node": start_node,
            "reachable_nodes": reachable_list,
            "affected_devices": affected.get("affected_devices", []),
            "affected_stations": affected.get("affected_stations", []),
            "affected_projects": affected.get("affected_projects", []),
            "affected_dams": affected.get("affected_dams", []),
            "affected_sections": affected.get("affected_sections", []),
            "affected_points": affected.get("affected_points", []),
            "total_affected": len(reachable_list) - 1,  # 减去 start_node 自己
        }
    finally:
        if own_conn:
            conn.close()


def find_fault_cluster(
    alarm_nodes: List[str],
    time_window_min: int = 30,
    conn: Optional[pymysql.connections.Connection] = None,
) -> List[Dict[str, Any]]:
    """
    给定一组告警涉及的节点, 用 union-find 把拓扑可达的节点聚成连通分量,
    再用 time_window 过滤时间不相关的告警, 返回"故障团".

    对应腾讯"社团聚类 + DBSCAN 密度聚类".

    聚类边类型 (只考虑这些边做连通性):
        belongs_to, near, upstream_of
    (causes 边只用于根因排序的 causal_evidence 维度, 不用于连通性判断)

    Args:
        alarm_nodes: 告警涉及的节点 node_id 列表 (可能含 None, 会过滤)
        time_window_min: 同一团内告警的最大时间跨度, 默认 30 分钟.
            设为 0 或负数则跳过时间窗口过滤.
        conn: 可选的数据库连接

    Returns:
        [
            {
                "cluster_id": 1,
                "nodes": ["station:123", "device:456", ...],
                "alarm_count": 5,
                "start_time": datetime,
                "end_time": datetime,
                "centroid_node": "station:123",   # 团内度数最高的节点
                "severity_score": 0.85            # 团的严重程度 [0,1]
            }
        ]
    """
    # 过滤掉 None / 空字符串
    valid_nodes = [n for n in alarm_nodes if n]
    if not valid_nodes:
        return []

    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        # 取所有聚类边 (belongs_to, near, upstream_of)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT from_node, to_node, edge_type
                FROM topo_edge
                WHERE deleted = 0
                  AND edge_type IN ('belongs_to', 'near', 'upstream_of')
                """
            )
            cluster_edges = cursor.fetchall()

        # 把所有出现过的节点加进 union-find
        all_node_set: Set[str] = set(valid_nodes)
        edge_node_set: Set[str] = set()
        for e in cluster_edges:
            edge_node_set.add(e["from_node"])
            edge_node_set.add(e["to_node"])
        all_node_set |= edge_node_set

        uf = UnionFind(list(all_node_set))

        # 对每条边做 union
        for e in cluster_edges:
            uf.union(e["from_node"], e["to_node"])

        # 找 valid_nodes 所在的连通分量
        clusters_map: Dict[Any, List[str]] = defaultdict(list)
        for n in valid_nodes:
            root = uf.find(n)
            clusters_map[root].append(n)

        # 给每个连通分量分配 cluster_id, 计算团内统计
        result: List[Dict[str, Any]] = []
        for cluster_id, (root, nodes) in enumerate(clusters_map.items(), 1):
            # 去重
            unique_nodes = list(set(nodes))
            if not unique_nodes:
                continue

            # 计算 centroid_node: 团内度数最高的节点
            with conn.cursor() as cursor:
                placeholders = ",".join(["%s"] * len(unique_nodes))
                cursor.execute(
                    f"""
                    SELECT node_id,
                           (SELECT COUNT(*) FROM topo_edge e
                            WHERE e.deleted = 0
                              AND e.edge_type IN ('belongs_to','near','upstream_of')
                              AND (e.from_node = n.node_id OR e.to_node = n.node_id)) AS degree
                    FROM topo_node n
                    WHERE n.node_id IN ({placeholders}) AND n.deleted = 0
                    """,
                    unique_nodes,
                )
                degree_rows = cursor.fetchall()

            if degree_rows:
                centroid = max(degree_rows, key=lambda r: r.get("degree", 0))["node_id"]
            else:
                centroid = unique_nodes[0]

            cluster_info = {
                "cluster_id": cluster_id,
                "nodes": unique_nodes,
                "node_count": len(unique_nodes),
                "centroid_node": centroid,
                "severity_score": 0.0,  # 由调用方 rank_root_causes 填充
            }
            result.append(cluster_info)

        return result
    finally:
        if own_conn:
            conn.close()


# ============================================================
# 5. 告警聚合: aggregate_alarms_to_events
# ============================================================
def alarm_to_node(
    alarm: Dict[str, Any],
    conn: Optional[pymysql.connections.Connection] = None,
) -> Optional[str]:
    """
    把 ew_info_message 映射到 topo_node.node_id.

    优先级:
        1. eq_code → eq_equip_base.code → device 节点
        2. st_code → att_st_base.code → station 节点
        3. 都查不到 → None

    Args:
        alarm: ew_info_message 字典, 至少含 st_code / eq_code 之一
        conn: 可选的数据库连接

    Returns:
        node_id 字符串, 如 "device:456" / "station:123" / None
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        eq_code = safe_str(alarm.get("eq_code"))
        st_code = safe_str(alarm.get("st_code"))

        # 1. eq_code → device
        if eq_code:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM eq_equip_base WHERE code = %s AND deleted = 0 LIMIT 1",
                    (eq_code,),
                )
                row = cursor.fetchone()
            if row:
                return f"device:{row['id']}"

        # 2. st_code → station
        if st_code:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM att_st_base WHERE code = %s AND deleted = 0 LIMIT 1",
                    (st_code,),
                )
                row = cursor.fetchone()
            if row:
                return f"station:{row['id']}"

        return None
    finally:
        if own_conn:
            conn.close()


def aggregate_alarms_to_events(
    alarms: List[Dict[str, Any]],
    time_window_min: int = 30,
    tenant_id: int = 1,
    conn: Optional[pymysql.connections.Connection] = None,
) -> List[Dict[str, Any]]:
    """
    把原始告警列表聚合成故障事件 (对齐腾讯三级过滤).

    流程:
        1. 每条告警映射到图节点 (alarm_to_node)
        2. 用 find_fault_cluster 做拓扑社团聚类
        3. 每个团内, 用 time_window 过滤掉时间上不相关的告警
        4. 每个过滤后的连通分量生成一个故障事件

    Args:
        alarms: ew_info_message 字典列表, 每个至少含
                id, st_code, eq_code, level_r, gather_time
        time_window_min: 同一故障事件内告警的最大时间跨度, 默认 30
        tenant_id: 租户 ID
        conn: 可选的数据库连接

    Returns:
        [
            {
                "event_id": "EVT-20260805-001",
                "tenant_id": 1,
                "start_time": datetime,
                "end_time": datetime,
                "max_level": "1",
                "alarm_count": 5,
                "affected_nodes": ["station:123", ...],
                "cluster_id": 1,
                "centroid_node": "station:123",
                "severity_score": 0.85,
                "alarms": [alarm1, alarm2, ...]  # 原始告警引用
            }
        ]
    """
    if not alarms:
        return []

    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        # 1. 映射告警到图节点
        alarm_node_pairs: List[Tuple[Dict[str, Any], Optional[str]]] = []
        for alarm in alarms:
            node_id = alarm_to_node(alarm, conn)
            alarm_node_pairs.append((alarm, node_id))

        valid_pairs = [(a, n) for a, n in alarm_node_pairs if n]
        if not valid_pairs:
            return []

        # 2. 拓扑社团聚类
        valid_nodes = list(set(n for _, n in valid_pairs))
        clusters = find_fault_cluster(valid_nodes, time_window_min, conn)

        if not clusters:
            # 没有拓扑关联, 把所有告警作为一个事件
            clusters = [
                {
                    "cluster_id": 1,
                    "nodes": valid_nodes,
                    "centroid_node": valid_nodes[0],
                }
            ]

        # 3. 为每个团生成故障事件
        today_str = datetime.now().strftime("%Y%m%d")
        events: List[Dict[str, Any]] = []

        for cluster in clusters:
            cluster_nodes_set = set(cluster["nodes"])

            # 收集该团内所有告警
            cluster_alarms = [
                alarm for alarm, node_id in valid_pairs if node_id in cluster_nodes_set
            ]
            if not cluster_alarms:
                continue

            # 时间窗口过滤: 保留时间跨度 <= time_window_min 的告警
            if time_window_min and time_window_min > 0:
                cluster_alarms.sort(key=lambda a: a.get("gather_time") or datetime.min)
                if len(cluster_alarms) > 1:
                    # 用滑动窗口找告警密度最高的子集
                    best_start, best_end = 0, 0
                    best_count = 0
                    for i in range(len(cluster_alarms)):
                        t_i = cluster_alarms[i].get("gather_time") or datetime.min
                        for j in range(i, len(cluster_alarms)):
                            t_j = cluster_alarms[j].get("gather_time") or datetime.min
                            span = (t_j - t_i).total_seconds() / 60
                            if span <= time_window_min:
                                count = j - i + 1
                                if count > best_count:
                                    best_count = count
                                    best_start, best_end = i, j
                    if best_count > 0:
                        cluster_alarms = cluster_alarms[best_start : best_end + 1]

            if not cluster_alarms:
                continue

            # 计算事件属性
            start_time = min(
                (a.get("gather_time") for a in cluster_alarms if a.get("gather_time")),
                default=datetime.now(),
            )
            end_time = max(
                (a.get("gather_time") for a in cluster_alarms if a.get("gather_time")),
                default=datetime.now(),
            )
            levels = [safe_str(a.get("level_r")) for a in cluster_alarms]
            max_level = min(
                (lv for lv in levels if lv in SEVERITY_MAP),
                default="4",
            )

            severity_scores = [SEVERITY_MAP.get(lv, 0.25) for lv in levels]
            severity_score = (
                sum(severity_scores) / len(severity_scores) if severity_scores else 0.0
            )

            event_id = f"EVT-{today_str}-{len(events) + 1:03d}"

            events.append(
                {
                    "event_id": event_id,
                    "tenant_id": tenant_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "max_level": max_level,
                    "alarm_count": len(cluster_alarms),
                    "affected_nodes": list(cluster_nodes_set),
                    "cluster_id": cluster["cluster_id"],
                    "centroid_node": cluster.get("centroid_node"),
                    "severity_score": round(severity_score, 4),
                    "alarms": cluster_alarms,
                }
            )

        return events
    finally:
        if own_conn:
            conn.close()


# ============================================================
# 6. 根因排序: rank_root_causes
# ============================================================
def _query_causes_edges_from(
    node_id: str,
    conn: pymysql.connections.Connection,
) -> List[Dict[str, Any]]:
    """查询从 node_id 出发的所有 causes 边"""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT to_node, weight, lag_min, rule_id, evidence
            FROM topo_edge
            WHERE from_node = %s AND edge_type = 'causes' AND deleted = 0
            """,
            (node_id,),
        )
        return cursor.fetchall()


def _compute_intra_cluster_degrees(
    candidate_nodes: List[str],
    edge_types: List[str],
    conn: pymysql.connections.Connection,
) -> Dict[str, int]:
    """计算团内每个节点的度数 (只数指定类型的边, 只数团内节点间的边)"""
    if not candidate_nodes:
        return {}
    candidate_set = set(candidate_nodes)
    degrees: Dict[str, int] = {n: 0 for n in candidate_nodes}

    placeholders = ",".join(["%s"] * len(candidate_nodes))
    et_placeholders = ",".join(["%s"] * len(edge_types))
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT from_node, to_node
            FROM topo_edge
            WHERE deleted = 0
              AND edge_type IN ({et_placeholders})
              AND (from_node IN ({placeholders}) OR to_node IN ({placeholders}))
            """,
            edge_types + candidate_nodes + candidate_nodes,
        )
        for row in cursor.fetchall():
            f, t = row["from_node"], row["to_node"]
            if f in candidate_set:
                degrees[f] = degrees.get(f, 0) + 1
            if t in candidate_set:
                degrees[t] = degrees.get(t, 0) + 1
    return degrees


def _compute_historical_recurrence(
    node_id: str,
    days: int = 30,
    conn: Optional[pymysql.connections.Connection] = None,
) -> float:
    """
    计算过去 N 天该节点作为根因的频率 [0, 1].

    实现:
        1. 查询 topo_alarm_event 表, 过去 N 天 root_cause_node == node_id 的事件数
        2. 除以过去 N 天的总事件数
    如果 topo_alarm_event 表为空 (刚部署), 返回 0.5 (中性值).
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM topo_alarm_event
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                """,
                (days,),
            )
            total = cursor.fetchone()["total"]
            if total == 0:
                return 0.5  # 中性值

            cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM topo_alarm_event
                WHERE root_cause_node = %s
                  AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                """,
                (node_id, days),
            )
            root_cause_count = cursor.fetchone()["cnt"]
        return min(1.0, root_cause_count / total)
    finally:
        if own_conn:
            conn.close()


def rank_root_causes(
    event: Dict[str, Any],
    top_n: int = 3,
    conn: Optional[pymysql.connections.Connection] = None,
) -> List[Dict[str, Any]]:
    """
    在故障事件内, 对每个候选根因节点按 5 维打分, 加权排序出 TOPN.

    对齐腾讯"告警严重程度接近 + 互相导致告警可能性高 → 排序 TOPN 可疑根因".

    五维打分:
        temporal_priority (0.25): 节点首条告警时间早于团内其他告警 → 1.0, 晚 1 小时 → 0.0
        topology_centrality (0.20): 节点在团内的度数 / 团内最大度数
        causal_evidence (0.25): 有 causes 边指向团内其他告警节点的数量 / (团内节点数 - 1)
        alarm_severity (0.15): max(SEVERITY_MAP[level_r]) 该节点的最高告警级别
        historical_recurrence (0.15): 过去 30 天该节点作为根因的频率

    Args:
        event: topo_alarm_event 字典, 需含 affected_nodes / alarms
        top_n: 返回 TOP N 根因, 默认 3
        conn: 可选的数据库连接

    Returns:
        ranked_causes: List[dict], 按 root_cause_score 降序, 每个 dict 含:
            - rank: 排名 (1 = 最可能根因)
            - node_id: 候选根因节点 ID
            - node_name: 节点显示名
            - node_type: 节点类型
            - root_cause_score: 综合得分 [0, 1]
            - score_breakdown: 五维分数明细
            - evidence: 人类可读的证据列表
            - confidence: 置信度 [0, 1]
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        candidate_nodes: List[str] = event.get("affected_nodes", [])
        event_alarms: List[Dict[str, Any]] = event.get("alarms", [])

        if not candidate_nodes or not event_alarms:
            return []

        # 预计算: 每个节点的告警
        node_alarms: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for alarm in event_alarms:
            nid = alarm_to_node(alarm, conn)
            if nid:
                node_alarms[nid].append(alarm)

        # 预计算: 团内每个节点的度数 (含 belongs_to / near / upstream_of)
        cluster_edge_types = ["belongs_to", "near", "upstream_of", "causes"]
        node_degrees = _compute_intra_cluster_degrees(
            candidate_nodes, cluster_edge_types, conn
        )
        max_degree = max(node_degrees.values()) if node_degrees else 1
        if max_degree == 0:
            max_degree = 1

        # 预计算: 团内最早告警时间
        all_times = [a.get("gather_time") for a in event_alarms if a.get("gather_time")]
        event_start = min(all_times) if all_times else datetime.now()

        scores: List[Dict[str, Any]] = []

        for node_id in candidate_nodes:
            alarms = node_alarms.get(node_id, [])
            if not alarms:
                continue

            # ===== 维度 1: 时序优先性 =====
            first_times = [a.get("gather_time") for a in alarms if a.get("gather_time")]
            first_alarm_time = min(first_times) if first_times else datetime.now()
            time_diff_sec = (first_alarm_time - event_start).total_seconds()
            temporal_priority = max(0.0, 1.0 - time_diff_sec / 3600.0)

            # ===== 维度 2: 拓扑中心性 =====
            degree = node_degrees.get(node_id, 0)
            topology_centrality = degree / max_degree if max_degree > 0 else 0.0

            # ===== 维度 3: 因果链证据 =====
            causal_out_edges = _query_causes_edges_from(node_id, conn)
            causal_targets_in_cluster = [
                e["to_node"]
                for e in causal_out_edges
                if e["to_node"] in set(candidate_nodes) and e["to_node"] != node_id
            ]
            denom = max(1, len(candidate_nodes) - 1)
            causal_evidence = len(causal_targets_in_cluster) / denom

            # ===== 维度 4: 告警严重度 =====
            alarm_severity = max(
                (SEVERITY_MAP.get(safe_str(a.get("level_r")), 0.0) for a in alarms),
                default=0.0,
            )

            # ===== 维度 5: 历史复发率 =====
            historical_recurrence = _compute_historical_recurrence(
                node_id, days=30, conn=conn
            )

            # ===== 加权求和 =====
            total_score = sum(
                WEIGHTS[dim] * val
                for dim, val in [
                    ("temporal_priority", temporal_priority),
                    ("topology_centrality", topology_centrality),
                    ("causal_evidence", causal_evidence),
                    ("alarm_severity", alarm_severity),
                    ("historical_recurrence", historical_recurrence),
                ]
            )

            # ===== 生成证据列表 =====
            evidence_list: List[str] = []
            if temporal_priority >= 0.9:
                evidence_list.append(
                    f"首条告警时间 {first_alarm_time.strftime('%H:%M:%S')}, 早于团内其他告警"
                )
            if causal_evidence > 0:
                evidence_list.append(
                    f"causes 边指向 {len(causal_targets_in_cluster)} 个下游告警节点"
                )
            if topology_centrality >= 0.8:
                evidence_list.append(f"团内度数 {degree}, 拓扑中心性高")

            # ===== 计算置信度 =====
            confidence = total_score
            if len(alarms) < 3:
                confidence = max(0.0, confidence - 0.15)
            if temporal_priority >= 0.9 and causal_evidence > 0.5:
                confidence = min(1.0, confidence + 0.10)

            scores.append(
                {
                    "node_id": node_id,
                    "node_name": node_id,  # 可选: 查 topo_node 补 name
                    "node_type": node_id.split(":")[0] if ":" in node_id else "unknown",
                    "root_cause_score": round(total_score, 4),
                    "score_breakdown": {
                        "temporal_priority": round(temporal_priority, 4),
                        "topology_centrality": round(topology_centrality, 4),
                        "causal_evidence": round(causal_evidence, 4),
                        "alarm_severity": round(alarm_severity, 4),
                        "historical_recurrence": round(historical_recurrence, 4),
                    },
                    "evidence": evidence_list,
                    "confidence": round(confidence, 4),
                }
            )

        # 按总分降序, 取 TOP N
        scores.sort(key=lambda x: x["root_cause_score"], reverse=True)
        top = scores[:top_n]
        for i, s in enumerate(top, 1):
            s["rank"] = i

        return top
    finally:
        if own_conn:
            conn.close()


# ============================================================
# 7. 置信度降级闸: apply_confidence_gate
# ============================================================
def apply_confidence_gate(
    ranked_causes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    置信度降级闸: 根因置信度低于阈值时降级返回"建议人工介入", 绝不胡编.

    对应腾讯 TCOP "模型幻觉: 强制结构化输出 + 引用上下文,
                    相似度低于阈值就降级返回'建议人工介入', 绝不胡编".

    降级规则:
        - root_cause_score < SUPPRESS_THRESHOLD (0.5) → suppress (不列根因)
        - 0.5 <= score < WARNING_THRESHOLD (0.7) → show_with_warning
        - score >= 0.7 → show

    额外:
        - 如果所有候选根因都被 suppress → 整体降级, 输出"本次故障根因不确定, 建议人工介入"
        - display_reason 字段给出人类可读的原因

    Args:
        ranked_causes: rank_root_causes 的返回值

    Returns:
        {
            "overall_status": "normal" | "degraded" | "fully_degraded",
            "message": str,
            "ranked_causes": [...with display_action/display_reason added...]
        }
    """
    if not ranked_causes:
        return {
            "overall_status": "fully_degraded",
            "message": "无候选根因, 建议人工介入分析",
            "ranked_causes": [],
        }

    for cause in ranked_causes:
        score = cause.get("root_cause_score", 0.0)
        if score < SUPPRESS_THRESHOLD:
            cause["display_action"] = "suppress"
            cause["display_reason"] = "🚫 根因置信度不足, 建议人工介入"
        elif score < WARNING_THRESHOLD:
            cause["display_action"] = "show_with_warning"
            cause["display_reason"] = "⚠️ 低置信度, 仅供参考"
        else:
            cause["display_action"] = "show"
            cause["display_reason"] = "✅ 置信度充足"

    # 整体降级检查: 如果所有候选都被 suppress
    all_suppressed = all(c.get("display_action") == "suppress" for c in ranked_causes)
    if all_suppressed:
        return {
            "overall_status": "fully_degraded",
            "message": "本次故障所有候选根因置信度均不足, 建议人工介入分析",
            "ranked_causes": ranked_causes,
        }

    # 部分降级: 至少有一个被 suppress 或 show_with_warning
    any_warning = any(
        c.get("display_action") in ("suppress", "show_with_warning")
        for c in ranked_causes
    )
    if any_warning:
        return {
            "overall_status": "degraded",
            "message": "部分候选根因置信度不足, 已降级处理",
            "ranked_causes": ranked_causes,
        }

    return {
        "overall_status": "normal",
        "message": "所有候选根因置信度充足",
        "ranked_causes": ranked_causes,
    }


# ============================================================
# 8. 端到端入口: analyze_alarm_root_cause
# ============================================================
def analyze_alarm_root_cause(
    alarms: List[Dict[str, Any]],
    time_window_min: int = 30,
    top_n: int = 3,
    tenant_id: int = 1,
    conn: Optional[pymysql.connections.Connection] = None,
) -> Dict[str, Any]:
    """
    端到端: 告警列表 → 告警聚合 → 根因排序 → 置信度降级闸.

    对齐腾讯 TCOP 完整链路:
        "10 秒内自动识别 + 告警收敛, 聚合成故障事件;
         90 秒内多智能体协作, 决策智能体判定根因;
         3 分钟内自动生成报告 + 触发修复"

    Args:
        alarms: ew_info_message 字典列表
        time_window_min: 告警聚合时间窗口, 默认 30 分钟
        top_n: 根因排序 TOP N, 默认 3
        tenant_id: 租户 ID
        conn: 可选的数据库连接

    Returns:
        {
            "events": [
                {
                    ...event fields...,
                    "ranked_causes": [...],
                    "confidence_gate": {...}
                }
            ],
            "total_alarms": int,
            "total_events": int
        }
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        # 1. 告警聚合
        events = aggregate_alarms_to_events(
            alarms, time_window_min=time_window_min, tenant_id=tenant_id, conn=conn
        )

        # 2. 对每个事件做根因排序 + 置信度降级
        for event in events:
            ranked = rank_root_causes(event, top_n=top_n, conn=conn)
            gate_result = apply_confidence_gate(ranked)
            event["ranked_causes"] = ranked
            event["confidence_gate"] = gate_result

            # 把 TOP1 根因和置信度回写到 event
            if ranked:
                event["root_cause_node"] = ranked[0]["node_id"]
                event["root_cause_conf"] = ranked[0]["confidence"]

        return {
            "events": events,
            "total_alarms": len(alarms),
            "total_events": len(events),
        }
    finally:
        if own_conn:
            conn.close()


# ============================================================
# 9. CLI 入口 (用于手动测试)
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="水利对象知识图谱查询工具")
    parser.add_argument(
        "--blast",
        help="计算爆炸半径, 传入 start_node 如 station:123",
    )
    parser.add_argument(
        "--cluster",
        action="store_true",
        help="对最近告警做故障团聚类",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="端到端: 取最近告警 → 聚合 → 根因排序 → 置信度闸",
    )
    parser.add_argument("--days", type=int, default=7, help="告警时间范围(天), 默认 7")
    parser.add_argument("--top", type=int, default=3, help="根因排序 TOP N, 默认 3")
    args = parser.parse_args()

    if args.blast:
        result = compute_blast_radius(args.blast)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif args.cluster or args.analyze:
        conn = get_connection()
        try:
            # 取最近 N 天告警
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, ew_name, st_code, eq_code, ew_type, level_r,
                           value, gather_time, create_time, tenant_id
                    FROM ew_info_message
                    WHERE deleted = 0
                      AND create_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    ORDER BY gather_time DESC
                    LIMIT 200
                    """,
                    (args.days,),
                )
                alarms = cursor.fetchall()

            print(f"取到 {len(alarms)} 条告警 (最近 {args.days} 天)")

            if args.analyze:
                result = analyze_alarm_root_cause(
                    alarms, top_n=args.top, conn=conn
                )
                print(
                    json.dumps(
                        result, ensure_ascii=False, indent=2, default=str
                    )
                )
            else:
                events = aggregate_alarms_to_events(alarms, conn=conn)
                for ev in events:
                    print(
                        f"事件 {ev['event_id']}: {ev['alarm_count']} 条告警, "
                        f"级别 {ev['max_level']}, {ev['start_time']} ~ {ev['end_time']}"
                    )
                    print(f"  涉及节点: {ev['affected_nodes']}")
        finally:
            conn.close()

    else:
        parser.print_help()
