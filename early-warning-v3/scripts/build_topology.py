#!/usr/bin/env python3
"""
build_topology.py — 水利对象知识图谱建图脚本

把散落在 att_st_base / eq_equip_base / att_dam_base / att_dam_section /
att_st_point / att_st_dot 等十余张表里的隐式拓扑关系，抽取为统一的
topo_node + topo_edge 两张表，供 compute_blast_radius /
find_fault_cluster 做 BFS 查询，供 rank_root_causes 做根因排序。

用法:
    python3 build_topology.py              # 全量重建
    python3 build_topology.py --incremental # 增量更新（软删旧记录再重插）

依赖:
    pymysql 1.x  (已验证 1.4.6 可用)
    Python 3.11+

数据来源对照 (节点):
    station  ← att_st_base (id, code, name, longitude, latitude, status, project_id, type)
    device   ← eq_equip_base (id, code, name, type_flag, status, st_base_id)
    project  ← att_st_base.project_id 聚合
    dam      ← att_dam_base (id, dam_code, dam_name, start_long, start_lat, end_long, end_lat, if_main_dam, dam_max_heig, dam_top_elev, tenant_id)
    section  ← att_dam_section (id, dam_code, code, name, type, location, point_ids JSON, percolation_st_id)
    point    ← att_st_point (id, name, code, st_id, eq_id, lgtd, lttd, stel, type, ch)
             + att_st_dot (id, st_id, eq_id, point_id, name, indicator_type, table_name, address, unit, k, b)

数据来源对照 (边):
    belongs_to device→station   ← eq_equip_base.st_base_id
    belongs_to station→project  ← att_st_base.project_id
    belongs_to section→dam      ← att_dam_section.dam_code ↔ att_dam_base.dam_code
    belongs_to point→section    ← att_dam_section.point_ids JSON 数组包含 point_id
    belongs_to point→station    ← att_st_point.st_id (若 st_id 非空)
    belongs_to dam→project      ← att_dam_base.dam_code 同水库 att_st_base.project_id 的桥接
    upstream_of station→station ← att_st_base 经纬度空间推断 (haversine < 10km, 雨量→水库)
    causes     *→*              ← causal-rules.json 规则匹配
    near       point↔point      ← 同 section_id 的 point 两两组合
    near       station↔station  ← 经纬度 haversine < 1km

作者: Powerelf Team
版本: 1.0
日期: 2026-08-05
"""

import json
import os
import sys
from datetime import datetime
from math import radians, sin, cos, asin, sqrt
from typing import Any, Dict, List, Optional, Set, Tuple

import pymysql

# ============================================================
# 1. 配置
# ============================================================
# 数据库连接（复用 early-warning-v3/db-config.md 配置，支持环境变量覆盖）
DB_CONFIG: Dict[str, Any] = {
    "host": os.getenv("POWERELF_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("POWERELF_DB_PORT", "3306")),
    "user": os.getenv("POWERELF_DB_USER", "root"),
    "password": os.getenv("POWERELF_DB_PASSWORD", "123456aA."),
    "database": os.getenv("POWERELF_DB_NAME", "powerelf_srm_yml"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# causal-rules.json 的路径（相对于本脚本所在目录）
CAUSAL_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "analysis", "causal-rules.json")

# 空间推断参数
UPSTREAM_MAX_DISTANCE_KM = 10.0  # 雨量站→水库站上游推断的最大距离
NEAR_STATION_MAX_DISTANCE_KM = 1.0  # 测站 near 边的最大距离

# ============================================================
# 2. 数据库连接
# ============================================================
def get_connection() -> pymysql.connections.Connection:
    """获取 MySQL 连接"""
    return pymysql.connect(**DB_CONFIG)


# ============================================================
# 3. 工具函数
# ============================================================
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两个经纬度点之间的球面距离(km)"""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * asin(sqrt(a))


def safe_float(v: Any) -> Optional[float]:
    """安全转 float，None/空字符串返回 None"""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def safe_str(v: Any) -> Optional[str]:
    """安全转 str，None/空字符串返回 None"""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def parse_json_field(v: Any) -> Any:
    """解析 JSON 字段。MySQL 返回的 JSON 可能是 str 或已解析的对象"""
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


# ============================================================
# 4. 子类型推断函数
# ============================================================
# SL651 测站类型代码 → subtype 映射 (水利行业 SL651 规范)
# 参考: _shared/references/schema.md 中 att_st_base.type 字段注释
# 代码含义:
#   PP = 雨量站        → rain
#   ZH = 综合站(雨量+水位+流量) → reservoir (含水位监测)
#   RR = 溢洪道/流量站  → reservoir (流量监测, 多为水库出库)
#   MM = 气象站        → weather
#   SS = 墒情站        → soil_moisture
#   WQ = 水质站        → water_quality
#   SP = 视频站        → camera_station
#   ZL/ZZ = 水位站     → water_level
#   其他 → unknown
STATION_TYPE_CODE_MAP: Dict[str, str] = {
    "PP": "rain",
    "ZH": "reservoir",
    "RR": "reservoir",
    "MM": "weather",
    "SS": "soil_moisture",
    "WQ": "water_quality",
    "SP": "camera_station",
    "ZL": "water_level",
    "ZZ": "water_level",
    "DP": "pump_station",
    "DD": "gate_station",
}


def infer_station_subtype(station_row: Dict[str, Any]) -> str:
    """
    推断测站子类型。

    判定优先级:
        1. att_st_base.type 字段 SL651 代码映射 (PP/ZH/RR/MM/SS/WQ/SP 等)
        2. 测站名 name 中文关键词 fallback (雨/水位/河/气/墒/潮)
        3. 默认 "unknown"

    返回值用于 causal-rules.json 的 from_subtype / to_subtype 匹配。

    示例:
        type='PP' → rain
        type='ZH', name='主坝（右）雨水情综合测站' → reservoir (ZH 优先)
        type=None, name='徐家湾雨量测站' → rain (name 关键词 fallback)
    """
    type_str = safe_str(station_row.get("type")) or ""
    name_str = safe_str(station_row.get("name")) or ""

    # 1. SL651 代码映射 (优先)
    if type_str in STATION_TYPE_CODE_MAP:
        return STATION_TYPE_CODE_MAP[type_str]

    # 2. name 中文关键词 fallback
    if "雨" in name_str:
        return "rain"
    if "水位" in name_str or "水库" in name_str:
        return "reservoir"
    if "河" in name_str:
        return "river"
    if "气" in name_str:
        return "weather"
    if "墒" in name_str:
        return "soil_moisture"
    if "潮" in name_str:
        return "tide"

    return "unknown"


def infer_device_subtype(device_row: Dict[str, Any]) -> str:
    """
    推断设备子类型。

    判定依据:
        1. type_flag 字段（设备类型字典）
        2. 设备名 name

    type_flag 映射（基于项目 _shared/lib/db.py 的设备类型字典）:
        1  → rain         (雨量计)
        3  → water_level  (水位计)
        7  → pressure     (渗压计)
        8  → percolation  (渗流计)
        9  → gnss         (GNSS 位移)
        11 → gate         (闸门)
        13 → pump         (泵)
        14 → camera       (摄像头)
        20 → soil_moisture (墒情)
        其他 → unknown
    """
    type_flag = safe_str(device_row.get("type_flag")) or ""
    name_str = safe_str(device_row.get("name")) or ""

    # type_flag 关键词匹配
    if type_flag in ("1", "01"):
        return "rain"
    if type_flag in ("3", "03"):
        return "water_level"
    if type_flag in ("7", "07"):
        return "pressure"
    if type_flag in ("8", "08"):
        return "percolation"
    if type_flag in ("9", "09"):
        return "gnss"
    if type_flag in ("11", "011"):
        return "gate"
    if type_flag in ("13", "013"):
        return "pump"
    if type_flag in ("14", "014"):
        return "camera"
    if type_flag in ("20", "020"):
        return "soil_moisture"

    # name 关键词 fallback
    if "雨" in name_str or "rain" in name_str.lower():
        return "rain"
    if "水位" in name_str or "water" in name_str.lower():
        return "water_level"
    if "渗压" in name_str or "pressure" in name_str.lower():
        return "pressure"
    if "渗流" in name_str or "percolation" in name_str.lower():
        return "percolation"
    if "闸" in name_str or "gate" in name_str.lower():
        return "gate"
    if "泵" in name_str or "pump" in name_str.lower():
        return "pump"
    return "unknown"


def infer_point_subtype(point_row: Dict[str, Any], source_table: str = "att_st_point") -> str:
    """
    推断测点子类型。

    判定依据:
        1. source_table: att_st_point / att_st_dot / st_pressure_r / dsm_dfr_srvrds_srhrds
        2. indicator_type 字段（att_st_dot 表）
        3. name 字段关键词

    返回值用于 causal-rules.json 的 to_subtype 匹配:
        pressure     (渗压)
        percolation  (渗流)
        gnss         (GNSS 位移)
        displacement (垂直/水平位移日数据)
        seepage      (浸润线)
        unknown
    """
    name_str = safe_str(point_row.get("name")) or ""
    indicator = safe_str(point_row.get("indicator_type")) or ""

    if source_table == "st_pressure_r":
        return "pressure"
    if source_table == "dsm_dfr_srvrds_srhrds":
        return "gnss"
    if source_table == "st_percolation_r":
        return "percolation"

    # 基于 att_st_dot.indicator_type
    if "渗压" in indicator or "pressure" in indicator.lower():
        return "pressure"
    if "渗流" in indicator or "percolation" in indicator.lower():
        return "percolation"
    if "位移" in indicator or "displacement" in indicator.lower():
        return "displacement"
    if "gnss" in indicator.lower():
        return "gnss"

    # 基于 name 关键词
    if "渗压" in name_str or "孔隙水压力" in name_str:
        return "pressure"
    if "渗流" in name_str or "浸润线" in name_str:
        return "percolation" if "渗流" in name_str else "seepage"
    if "位移" in name_str or "沉降" in name_str or "垂直" in name_str:
        return "displacement"
    if "gnss" in name_str.lower():
        return "gnss"

    return "unknown"


# ============================================================
# 5. 节点抽取
# ============================================================
def extract_station_nodes(conn: pymysql.connections.Connection) -> List[Dict[str, Any]]:
    """从 att_st_base 抽取测站节点"""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, code, name, longitude, latitude, status, project_id, type,
                   cat_area, location, tenant_id
            FROM att_st_base
            WHERE deleted = 0
            """
        )
        rows = cursor.fetchall()

    nodes = []
    for row in rows:
        node_id = f"station:{row['id']}"
        properties = {
            "code": safe_str(row.get("code")),
            "longitude": safe_float(row.get("longitude")),
            "latitude": safe_float(row.get("latitude")),
            "status": row.get("status"),
            "type": safe_str(row.get("type")),
            "cat_area": safe_float(row.get("cat_area")),
            "location": safe_str(row.get("location")),
            "subtype": infer_station_subtype(row),
        }
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "station",
                "ref_id": row["id"],
                "name": safe_str(row.get("name")) or node_id,
                "project_id": row.get("project_id"),
                "tenant_id": row.get("tenant_id", 1),
                "properties": json.dumps(properties, ensure_ascii=False),
            }
        )
    return nodes


def extract_device_nodes(conn: pymysql.connections.Connection) -> List[Dict[str, Any]]:
    """从 eq_equip_base 抽取设备节点"""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, code, name, type_flag, status, st_base_id,
                   manufacturer, position, project_id, tenant_id
            FROM eq_equip_base
            WHERE deleted = 0
            """
        )
        rows = cursor.fetchall()

    nodes = []
    for row in rows:
        node_id = f"device:{row['id']}"
        properties = {
            "code": safe_str(row.get("code")),
            "type_flag": safe_str(row.get("type_flag")),
            "status": row.get("status"),
            "manufacturer": safe_str(row.get("manufacturer")),
            "position": safe_str(row.get("position")),
            "st_base_id": row.get("st_base_id"),
            "subtype": infer_device_subtype(row),
        }
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "device",
                "ref_id": row["id"],
                "name": safe_str(row.get("name")) or node_id,
                "project_id": row.get("project_id"),
                "tenant_id": row.get("tenant_id", 1),
                "properties": json.dumps(properties, ensure_ascii=False),
            }
        )
    return nodes


def extract_project_nodes(conn: pymysql.connections.Connection) -> List[Dict[str, Any]]:
    """从 att_st_base.project_id 聚合工程节点"""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT project_id, COUNT(*) AS station_count, MIN(tenant_id) AS tenant_id
            FROM att_st_base
            WHERE deleted = 0 AND project_id IS NOT NULL
            GROUP BY project_id
            """
        )
        rows = cursor.fetchall()

    nodes = []
    for row in rows:
        node_id = f"project:{row['project_id']}"
        properties = {
            "source": "att_st_base.project_id 聚合",
            "station_count": row["station_count"],
        }
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "project",
                "ref_id": row["project_id"],
                "name": f"工程-{row['project_id']}",
                "project_id": row["project_id"],
                "tenant_id": row.get("tenant_id", 1),
                "properties": json.dumps(properties, ensure_ascii=False),
            }
        )
    return nodes


def extract_dam_nodes(conn: pymysql.connections.Connection) -> List[Dict[str, Any]]:
    """从 att_dam_base 抽取大坝节点"""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, dam_code, dam_name, start_long, start_lat, end_long, end_lat,
                   if_main_dam, dam_max_heig, dam_top_elev, dam_loc, tenant_id
            FROM att_dam_base
            WHERE deleted = 0
            """
        )
        rows = cursor.fetchall()

    nodes = []
    for row in rows:
        node_id = f"dam:{row['id']}"
        properties = {
            "dam_code": safe_str(row.get("dam_code")),
            "if_main_dam": safe_str(row.get("if_main_dam")),
            "dam_max_heig": safe_float(row.get("dam_max_heig")),
            "dam_top_elev": safe_float(row.get("dam_top_elev")),
            "start_long": safe_float(row.get("start_long")),
            "start_lat": safe_float(row.get("start_lat")),
            "end_long": safe_float(row.get("end_long")),
            "end_lat": safe_float(row.get("end_lat")),
            "dam_loc": safe_str(row.get("dam_loc")),
        }
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "dam",
                "ref_id": row["id"],
                "name": safe_str(row.get("dam_name")) or node_id,
                "project_id": None,  # att_dam_base 无 project_id，需通过 att_st_base 桥接
                "tenant_id": row.get("tenant_id", 1),
                "properties": json.dumps(properties, ensure_ascii=False),
            }
        )
    return nodes


def extract_section_nodes(conn: pymysql.connections.Connection) -> List[Dict[str, Any]]:
    """从 att_dam_section 抽取断面节点"""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, dam_code, code, type, name, location,
                   percolation_st_id, point_ids, tenant_id
            FROM att_dam_section
            WHERE deleted = 0
            """
        )
        rows = cursor.fetchall()

    nodes = []
    for row in rows:
        node_id = f"section:{row['id']}"
        point_ids_list = parse_json_field(row.get("point_ids")) or []
        properties = {
            "dam_code": safe_str(row.get("dam_code")),
            "code": safe_str(row.get("code")),
            "type": safe_str(row.get("type")),
            "location": safe_str(row.get("location")),
            "percolation_st_id": row.get("percolation_st_id"),
            "point_ids": [int(p) for p in point_ids_list if p is not None],
        }
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "section",
                "ref_id": row["id"],
                "name": safe_str(row.get("name")) or node_id,
                "project_id": None,  # 通过 dam_code → att_dam_base → att_st_base 桥接
                "tenant_id": row.get("tenant_id", 1),
                "properties": json.dumps(properties, ensure_ascii=False),
            }
        )
    return nodes


def extract_point_nodes(
    conn: pymysql.connections.Connection,
) -> Tuple[List[Dict[str, Any]], Dict[int, int], Dict[int, int]]:
    """
    从 att_st_point + att_st_dot 抽取测点节点。

    att_st_point: 大坝监测测点（渗压/位移/GNSS 等），含 st_id, eq_id, 经纬度, 高程
    att_st_dot:   采集测点，含 st_id, eq_id, point_id, indicator_type, 数据表名

    返回:
        nodes: 测点节点列表
        point_to_section: point_id → section_id 映射（来自 att_dam_section.point_ids）
        point_to_station: point_id → station_id 映射（来自 att_st_point.st_id）
    """
    nodes = []
    seen_ref_ids: Set[int] = set()

    # 5.1 从 att_st_point 抽取
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, st_id, eq_id, name, code, type, point_address,
                   lgtd, lttd, stel, ch, status, tenant_id
            FROM att_st_point
            WHERE deleted = 0
            """
        )
        rows = cursor.fetchall()

    point_to_station: Dict[int, int] = {}
    for row in rows:
        if row["id"] in seen_ref_ids:
            continue
        seen_ref_ids.add(row["id"])
        node_id = f"point:{row['id']}"
        properties = {
            "source_table": "att_st_point",
            "code": safe_str(row.get("code")),
            "type": safe_str(row.get("type")),
            "point_address": safe_str(row.get("point_address")),
            "lgtd": safe_float(row.get("lgtd")),
            "lttd": safe_float(row.get("lttd")),
            "stel": safe_float(row.get("stel")),
            "ch": safe_str(row.get("ch")),
            "status": safe_str(row.get("status")),
            "st_id": row.get("st_id"),
            "eq_id": row.get("eq_id"),
            "subtype": infer_point_subtype(row, "att_st_point"),
        }
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "point",
                "ref_id": row["id"],
                "name": safe_str(row.get("name")) or node_id,
                "project_id": None,
                "tenant_id": row.get("tenant_id", 1),
                "properties": json.dumps(properties, ensure_ascii=False),
            }
        )
        if row.get("st_id"):
            point_to_station[row["id"]] = row["st_id"]

    # 5.2 从 att_st_dot 抽取（补充 att_st_point 没有的测点）
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, st_id, eq_id, point_id, name, indicator_type,
                   table_name, address, unit, k, b, type, tenant_id
            FROM att_st_dot
            WHERE deleted = 0
            """
        )
        rows = cursor.fetchall()

    for row in rows:
        if row["id"] in seen_ref_ids:
            continue
        seen_ref_ids.add(row["id"])
        node_id = f"point:{row['id']}"
        properties = {
            "source_table": "att_st_dot",
            "name": safe_str(row.get("name")),
            "indicator_type": safe_str(row.get("indicator_type")),
            "table_name": safe_str(row.get("table_name")),
            "address": safe_str(row.get("address")),
            "unit": safe_str(row.get("unit")),
            "k": safe_float(row.get("k")),
            "b": safe_float(row.get("b")),
            "type": safe_str(row.get("type")),
            "st_id": row.get("st_id"),
            "eq_id": row.get("eq_id"),
            "point_id": row.get("point_id"),
            "subtype": infer_point_subtype(row, "att_st_dot"),
        }
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "point",
                "ref_id": row["id"],
                "name": safe_str(row.get("name")) or node_id,
                "project_id": None,
                "tenant_id": row.get("tenant_id", 1),
                "properties": json.dumps(properties, ensure_ascii=False),
            }
        )
        if row.get("st_id"):
            point_to_station[row["id"]] = row["st_id"]

    # 5.3 构建 point_id → section_id 映射（来自 att_dam_section.point_ids JSON）
    point_to_section: Dict[int, int] = {}
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, point_ids FROM att_dam_section
            WHERE deleted = 0 AND point_ids IS NOT NULL
            """
        )
        section_rows = cursor.fetchall()

    for srow in section_rows:
        section_id = srow["id"]
        pid_list = parse_json_field(srow.get("point_ids")) or []
        for pid in pid_list:
            try:
                point_to_section[int(pid)] = section_id
            except (TypeError, ValueError):
                continue

    return nodes, point_to_section, point_to_station


# ============================================================
# 6. 边抽取
# ============================================================
def extract_belongs_to_edges(
    conn: pymysql.connections.Connection,
    point_to_section: Dict[int, int],
    point_to_station: Dict[int, int],
) -> List[Dict[str, Any]]:
    """
    生成 belongs_to 边:
        device   → station   (eq_equip_base.st_base_id)
        station  → project   (att_st_base.project_id)
        point    → section   (att_dam_section.point_ids JSON 包含 point_id)
        point    → station   (att_st_point.st_id)
        section  → dam       (att_dam_section.dam_code ↔ att_dam_base.dam_code)
        dam      → project   (通过同 tenant_id 的 att_st_base.project_id 桥接)
    """
    edges: List[Dict[str, Any]] = []

    with conn.cursor() as cursor:
        # 6.1 device → station
        cursor.execute(
            """
            SELECT id, st_base_id, tenant_id FROM eq_equip_base
            WHERE deleted = 0 AND st_base_id IS NOT NULL
            """
        )
        for row in cursor.fetchall():
            edges.append(
                {
                    "from_node": f"device:{row['id']}",
                    "to_node": f"station:{row['st_base_id']}",
                    "edge_type": "belongs_to",
                    "weight": 1.0,
                    "lag_min": None,
                    "evidence": "eq_equip_base.st_base_id",
                    "rule_id": None,
                    "tenant_id": row.get("tenant_id", 1),
                }
            )

        # 6.2 station → project
        cursor.execute(
            """
            SELECT id, project_id, tenant_id FROM att_st_base
            WHERE deleted = 0 AND project_id IS NOT NULL
            """
        )
        for row in cursor.fetchall():
            edges.append(
                {
                    "from_node": f"station:{row['id']}",
                    "to_node": f"project:{row['project_id']}",
                    "edge_type": "belongs_to",
                    "weight": 1.0,
                    "lag_min": None,
                    "evidence": "att_st_base.project_id",
                    "rule_id": None,
                    "tenant_id": row.get("tenant_id", 1),
                }
            )

        # 6.3 point → section（基于 att_dam_section.point_ids JSON）
        for point_id, section_id in point_to_section.items():
            edges.append(
                {
                    "from_node": f"point:{point_id}",
                    "to_node": f"section:{section_id}",
                    "edge_type": "belongs_to",
                    "weight": 1.0,
                    "lag_min": None,
                    "evidence": "att_dam_section.point_ids JSON 包含 point_id",
                    "rule_id": None,
                    "tenant_id": 1,
                }
            )

        # 6.4 point → station（基于 att_st_point.st_id）
        for point_id, station_id in point_to_station.items():
            edges.append(
                {
                    "from_node": f"point:{point_id}",
                    "to_node": f"station:{station_id}",
                    "edge_type": "belongs_to",
                    "weight": 1.0,
                    "lag_min": None,
                    "evidence": "att_st_point.st_id",
                    "rule_id": None,
                    "tenant_id": 1,
                }
            )

        # 6.5 section → dam（基于 att_dam_section.dam_code ↔ att_dam_base.dam_code）
        cursor.execute(
            """
            SELECT ds.id AS section_id, ds.dam_code, db.id AS dam_id,
                   ds.tenant_id
            FROM att_dam_section ds
            JOIN att_dam_base db ON ds.dam_code = db.dam_code AND db.deleted = 0
            WHERE ds.deleted = 0 AND ds.dam_code IS NOT NULL
            """
        )
        for row in cursor.fetchall():
            edges.append(
                {
                    "from_node": f"section:{row['section_id']}",
                    "to_node": f"dam:{row['dam_id']}",
                    "edge_type": "belongs_to",
                    "weight": 1.0,
                    "lag_min": None,
                    "evidence": f"att_dam_section.dam_code={row['dam_code']} ↔ att_dam_base.dam_code",
                    "rule_id": None,
                    "tenant_id": row.get("tenant_id", 1),
                }
            )

        # 6.6 dam → project（桥接：同 tenant_id 下 att_st_base.project_id）
        # 策略: 找到与该 dam 同 tenant_id 的任意一个 station 的 project_id
        cursor.execute(
            """
            SELECT db.id AS dam_id, db.tenant_id, db.dam_code,
                   (SELECT MIN(s.project_id) FROM att_st_base s
                    WHERE s.deleted = 0 AND s.tenant_id = db.tenant_id
                      AND s.project_id IS NOT NULL) AS project_id
            FROM att_dam_base db
            WHERE db.deleted = 0
            """
        )
        for row in cursor.fetchall():
            project_id = row.get("project_id")
            if project_id is not None:
                edges.append(
                    {
                        "from_node": f"dam:{row['dam_id']}",
                        "to_node": f"project:{project_id}",
                        "edge_type": "belongs_to",
                        "weight": 0.7,  # 桥接关系，权重降低
                        "lag_min": None,
                        "evidence": f"桥接: att_dam_base.tenant_id={row['tenant_id']} → att_st_base.project_id={project_id}",
                        "rule_id": None,
                        "tenant_id": row.get("tenant_id", 1),
                    }
                )

    return edges


def infer_upstream_downstream_edges(
    conn: pymysql.connections.Connection,
) -> List[Dict[str, Any]]:
    """
    选项 B: 用空间推断生成 upstream_of 边。

    规则:
        1. 同一 project_id 内推断，不跨 project
        2. 雨量站 (subtype=rain) → 水库站 (subtype=reservoir)
        3. haversine 距离 < UPSTREAM_MAX_DISTANCE_KM (10km)
        4. weight = 1 - distance / max_distance (距离越近权重越高)
        5. lag_min 默认 60 (汇流延迟)，具体由 causal-rules.json 的 CR-001 覆盖
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, code, name, longitude, latitude, type, project_id, tenant_id
            FROM att_st_base
            WHERE deleted = 0
              AND longitude IS NOT NULL AND latitude IS NOT NULL
            """
        )
        stations = cursor.fetchall()

    # 按 project_id 分组
    by_project: Dict[Any, List[Dict[str, Any]]] = {}
    for s in stations:
        by_project.setdefault(s.get("project_id"), []).append(s)

    edges: List[Dict[str, Any]] = []
    for project_id, sts in by_project.items():
        if project_id is None:
            continue
        # 区分雨量站和水库站
        rain_stations = [s for s in sts if infer_station_subtype(s) == "rain"]
        reservoir_stations = [s for s in sts if infer_station_subtype(s) == "reservoir"]

        for r in reservoir_stations:
            r_lat = safe_float(r.get("latitude"))
            r_lon = safe_float(r.get("longitude"))
            if r_lat is None or r_lon is None:
                continue
            for p in rain_stations:
                p_lat = safe_float(p.get("latitude"))
                p_lon = safe_float(p.get("longitude"))
                if p_lat is None or p_lon is None:
                    continue
                dist = haversine_km(p_lat, p_lon, r_lat, r_lon)
                if dist < UPSTREAM_MAX_DISTANCE_KM:
                    edges.append(
                        {
                            "from_node": f"station:{p['id']}",
                            "to_node": f"station:{r['id']}",
                            "edge_type": "upstream_of",
                            "weight": round(1.0 - dist / UPSTREAM_MAX_DISTANCE_KM, 3),
                            "lag_min": 60,
                            "evidence": f"空间推断: haversine {dist:.2f}km < {UPSTREAM_MAX_DISTANCE_KM}km",
                            "rule_id": None,
                            "tenant_id": r.get("tenant_id", 1),
                        }
                    )

    return edges


def extract_causes_edges(
    conn: pymysql.connections.Connection,
    causal_rules_path: str,
) -> List[Dict[str, Any]]:
    """
    从 causal-rules.json 加载因果规则，匹配 topo_node 表中已存在的节点对，
    生成 causes 边。

    匹配逻辑:
        1. 加载 causal-rules.json
        2. 对每条规则，查询 properties->>'$.subtype' = from_subtype 且 node_type=from_type 的节点
        3. 同理查询 to 节点
        4. 若 applies_within_project=true，只匹配同 project_id 的 from→to 对
        5. 若 bidirectional=true，额外生成 to→from 边
        6. lag_min / weight / evidence / rule_id 从规则文件读取
    """
    # 加载 causal-rules.json
    with open(causal_rules_path, "r", encoding="utf-8") as f:
        rules_data = json.load(f)
    rules = rules_data.get("rules", [])

    edges: List[Dict[str, Any]] = []
    with conn.cursor() as cursor:
        for rule in rules:
            from_type = rule["from_type"]
            from_subtype = rule["from_subtype"]
            to_type = rule["to_type"]
            to_subtype = rule["to_subtype"]

            # 查询 from 节点
            cursor.execute(
                """
                SELECT node_id, project_id, tenant_id
                FROM topo_node
                WHERE node_type = %s
                  AND JSON_UNQUOTE(JSON_EXTRACT(properties, '$.subtype')) = %s
                  AND deleted = 0
                """,
                (from_type, from_subtype),
            )
            from_nodes = cursor.fetchall()

            # 查询 to 节点
            cursor.execute(
                """
                SELECT node_id, project_id, tenant_id
                FROM topo_node
                WHERE node_type = %s
                  AND JSON_UNQUOTE(JSON_EXTRACT(properties, '$.subtype')) = %s
                  AND deleted = 0
                """,
                (to_type, to_subtype),
            )
            to_nodes = cursor.fetchall()

            # 匹配节点对
            applies_within = rule.get("applies_within_project", True)
            bidirectional = rule.get("bidirectional", False)
            lag_min = rule.get("lag_min")
            weight = rule.get("weight", 0.85)
            evidence = rule.get("evidence", "")
            rule_id = rule.get("rule_id", "")

            for fn in from_nodes:
                for tn in to_nodes:
                    if fn["node_id"] == tn["node_id"]:
                        continue
                    # 同 project 过滤
                    if applies_within and fn.get("project_id") != tn.get("project_id"):
                        continue
                    # tenant 过滤
                    if fn.get("tenant_id") != tn.get("tenant_id"):
                        continue

                    edges.append(
                        {
                            "from_node": fn["node_id"],
                            "to_node": tn["node_id"],
                            "edge_type": "causes",
                            "weight": weight,
                            "lag_min": lag_min,
                            "evidence": evidence,
                            "rule_id": rule_id,
                            "tenant_id": fn.get("tenant_id", 1),
                        }
                    )

                    # 双向因果
                    if bidirectional:
                        edges.append(
                            {
                                "from_node": tn["node_id"],
                                "to_node": fn["node_id"],
                                "edge_type": "causes",
                                "weight": weight,
                                "lag_min": lag_min,
                                "evidence": evidence,
                                "rule_id": rule_id,
                                "tenant_id": tn.get("tenant_id", 1),
                            }
                        )

    return edges


def extract_near_edges(
    conn: pymysql.connections.Connection,
    point_to_section: Dict[int, int],
) -> List[Dict[str, Any]]:
    """
    生成 near 边:
        1. 同 section_id 的 point 两两连边 (weight=0.8)
        2. 经纬度 haversine < 1km 的 station 两两连边 (weight=0.6)
    """
    edges: List[Dict[str, Any]] = []

    # 7.1 同 section 的 point 两两连边
    section_points: Dict[int, List[int]] = {}
    for point_id, section_id in point_to_section.items():
        section_points.setdefault(section_id, []).append(point_id)

    for section_id, point_ids in section_points.items():
        if len(point_ids) < 2:
            continue
        for i in range(len(point_ids)):
            for j in range(i + 1, len(point_ids)):
                edges.append(
                    {
                        "from_node": f"point:{point_ids[i]}",
                        "to_node": f"point:{point_ids[j]}",
                        "edge_type": "near",
                        "weight": 0.8,
                        "lag_min": None,
                        "evidence": f"同 section:{section_id}",
                        "rule_id": None,
                        "tenant_id": 1,
                    }
                )

    # 7.2 经纬度 haversine < 1km 的 station 两两连边
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, latitude, longitude, project_id, tenant_id
            FROM att_st_base
            WHERE deleted = 0
              AND latitude IS NOT NULL AND longitude IS NOT NULL
            """
        )
        stations = cursor.fetchall()

    # 按 project_id 分组，避免跨工程连 near 边
    by_project: Dict[Any, List[Dict[str, Any]]] = {}
    for s in stations:
        by_project.setdefault(s.get("project_id"), []).append(s)

    for project_id, sts in by_project.items():
        n = len(sts)
        for i in range(n):
            lat_i = safe_float(sts[i].get("latitude"))
            lon_i = safe_float(sts[i].get("longitude"))
            if lat_i is None or lon_i is None:
                continue
            for j in range(i + 1, n):
                lat_j = safe_float(sts[j].get("latitude"))
                lon_j = safe_float(sts[j].get("longitude"))
                if lat_j is None or lon_j is None:
                    continue
                dist = haversine_km(lat_i, lon_i, lat_j, lon_j)
                if dist < NEAR_STATION_MAX_DISTANCE_KM:
                    edges.append(
                        {
                            "from_node": f"station:{sts[i]['id']}",
                            "to_node": f"station:{sts[j]['id']}",
                            "edge_type": "near",
                            "weight": round(0.6 * (1 - dist / NEAR_STATION_MAX_DISTANCE_KM), 3),
                            "lag_min": None,
                            "evidence": f"空间邻近: haversine {dist:.3f}km < {NEAR_STATION_MAX_DISTANCE_KM}km",
                            "rule_id": None,
                            "tenant_id": sts[i].get("tenant_id", 1),
                        }
                    )

    return edges


# ============================================================
# 7. 写入数据库
# ============================================================
def clear_topology_tables(conn: pymysql.connections.Connection) -> None:
    """全量重建前清空 topo_node / topo_edge（topo_alarm_event 保留历史）"""
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM topo_edge")
        cursor.execute("DELETE FROM topo_node")
    conn.commit()


def upsert_nodes(conn: pymysql.connections.Connection, nodes: List[Dict[str, Any]]) -> int:
    """批量 upsert 节点（已存在则更新 properties/name/project_id）"""
    if not nodes:
        return 0
    sql = """
        INSERT INTO topo_node (node_id, node_type, ref_id, name, project_id,
                               properties, tenant_id, deleted)
        VALUES (%s, %s, %s, %s, %s, %s, %s, b'0')
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            project_id = VALUES(project_id),
            properties = VALUES(properties),
            tenant_id = VALUES(tenant_id),
            deleted = b'0',
            updated_at = NOW()
    """
    batch = [
        (
            n["node_id"],
            n["node_type"],
            n["ref_id"],
            n["name"],
            n["project_id"],
            n["properties"],
            n["tenant_id"],
        )
        for n in nodes
    ]
    with conn.cursor() as cursor:
        cursor.executemany(sql, batch)
    conn.commit()
    return len(batch)


def upsert_edges(conn: pymysql.connections.Connection, edges: List[Dict[str, Any]]) -> int:
    """批量 upsert 边（唯一键 from_node+to_node+edge_type 去重）"""
    if not edges:
        return 0
    sql = """
        INSERT INTO topo_edge (from_node, to_node, edge_type, weight,
                               lag_min, evidence, rule_id, tenant_id, deleted)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, b'0')
        ON DUPLICATE KEY UPDATE
            weight = VALUES(weight),
            lag_min = VALUES(lag_min),
            evidence = VALUES(evidence),
            rule_id = VALUES(rule_id),
            tenant_id = VALUES(tenant_id),
            deleted = b'0',
            updated_at = NOW()
    """
    batch = [
        (
            e["from_node"],
            e["to_node"],
            e["edge_type"],
            e["weight"],
            e.get("lag_min"),
            e.get("evidence", ""),
            e.get("rule_id"),
            e.get("tenant_id", 1),
        )
        for e in edges
    ]
    with conn.cursor() as cursor:
        cursor.executemany(sql, batch)
    conn.commit()
    return len(batch)


# ============================================================
# 8. 主流程
# ============================================================
def main(incremental: bool = False) -> int:
    """建图主流程"""
    print("=" * 60)
    print("水利对象知识图谱建图脚本")
    print(f"模式: {'增量更新' if incremental else '全量重建'}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    conn = get_connection()

    # Step 1: 抽取节点
    print("\n[Step 1] 抽取节点...")
    stations = extract_station_nodes(conn)
    devices = extract_device_nodes(conn)
    projects = extract_project_nodes(conn)
    dams = extract_dam_nodes(conn)
    sections = extract_section_nodes(conn)
    points, point_to_section, point_to_station = extract_point_nodes(conn)

    all_nodes = stations + devices + projects + dams + sections + points
    print(f"  测站 station: {len(stations)}")
    print(f"  设备 device:  {len(devices)}")
    print(f"  工程 project: {len(projects)}")
    print(f"  大坝 dam:     {len(dams)}")
    print(f"  断面 section: {len(sections)}")
    print(f"  测点 point:   {len(points)}")
    print(f"  节点总数:     {len(all_nodes)}")

    # Step 2: 抽取边
    print("\n[Step 2] 抽取边...")
    belongs_to = extract_belongs_to_edges(conn, point_to_section, point_to_station)
    upstream_of = infer_upstream_downstream_edges(conn)
    causes = extract_causes_edges(conn, CAUSAL_RULES_PATH)
    near = extract_near_edges(conn, point_to_section)

    all_edges = belongs_to + upstream_of + causes + near
    print(f"  belongs_to: {len(belongs_to)}")
    print(f"  upstream_of: {len(upstream_of)}")
    print(f"  causes:     {len(causes)}")
    print(f"  near:       {len(near)}")
    print(f"  边总数:     {len(all_edges)}")

    # Step 3: 写入数据库
    print("\n[Step 3] 写入数据库...")
    if not incremental:
        clear_topology_tables(conn)
        print("  已清空 topo_node / topo_edge（全量重建）")

    n_nodes = upsert_nodes(conn, all_nodes)
    n_edges = upsert_edges(conn, all_edges)
    print(f"  节点写入: {n_nodes}")
    print(f"  边写入:   {n_edges}")

    # Step 4: 验证
    print("\n[Step 4] 验证数据完整性...")
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS c FROM topo_node WHERE deleted = 0")
        node_count = cursor.fetchone()["c"]
        cursor.execute("SELECT COUNT(*) AS c FROM topo_edge WHERE deleted = 0")
        edge_count = cursor.fetchone()["c"]
        cursor.execute(
            """
            SELECT edge_type, COUNT(*) AS c
            FROM topo_edge WHERE deleted = 0
            GROUP BY edge_type ORDER BY edge_type
            """
        )
        edge_type_stats = cursor.fetchall()
        cursor.execute(
            """
            SELECT node_type, COUNT(*) AS c
            FROM topo_node WHERE deleted = 0
            GROUP BY node_type ORDER BY node_type
            """
        )
        node_type_stats = cursor.fetchall()

    print(f"  topo_node 行数: {node_count}")
    print(f"  topo_edge 行数: {edge_count}")
    print("  节点类型分布:")
    for row in node_type_stats:
        print(f"    {row['node_type']:15s}: {row['c']}")
    print("  边类型分布:")
    for row in edge_type_stats:
        print(f"    {row['edge_type']:15s}: {row['c']}")

    # 检查孤立节点（没有任何边连接的节点）
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS c FROM topo_node n
            WHERE n.deleted = 0
              AND NOT EXISTS (SELECT 1 FROM topo_edge e
                              WHERE e.deleted = 0
                                AND (e.from_node = n.node_id OR e.to_node = n.node_id))
            """
        )
        isolated_count = cursor.fetchone()["c"]
    print(f"  孤立节点数: {isolated_count}")

    print("\n建图完成。")
    conn.close()
    return 0


if __name__ == "__main__":
    incremental_mode = "--incremental" in sys.argv
    sys.exit(main(incremental=incremental_mode))
