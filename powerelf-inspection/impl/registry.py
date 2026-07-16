#!/usr/bin/env python3
"""
数据源注册表与采集模块（registry）

职责：
  - 加载 sys_data_source_registry（或回退内置默认）
  - 根据文本匹配数据源
  - 从注册表定义采集数据（含 SQL 注入防护）

S4 最小分离：将采集层从 inspection_tool.py 抽离。
"""

import re
import logging

try:
    import pandas as pd
    from sqlalchemy import create_engine, text
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

logger = logging.getLogger("inspection.registry")

# 标识符白名单（防 SQL 注入：table/fields/time_field 来自 sys_data_source_registry，DB 可写）
_ALLOWED_TABLES = {
    "st_river_r","st_rsvr_r","st_pressure_r","st_percolation_r","st_pptn_r",
    "rei_gate_r","rei_pump_r","eq_equip_base","eq_equip_defect","ew_camera_info",
    "srm_gnss_data_day","srm_robot_data_day","srm_illegal_acts",
}
_ALLOWED_TIME_FIELDS = {"tm", "create_time", "discovery_time", None}


def _validate_identifiers(table, fields, time_field):
    """校验标识符白名单（防 SQL 注入）"""
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table}")
    if time_field is not None and time_field not in _ALLOWED_TIME_FIELDS:
        raise ValueError(f"非法时间列: {time_field}")
    if not re.fullmatch(r"[A-Za-z0-9_]+(,[A-Za-z0-9_]+)*", fields or ""):
        raise ValueError(f"非法字段列表: {fields}")


def load_registry(engine):
    """从 sys_data_source_registry 表加载数据源定义"""
    try:
        registry = pd.read_sql("""
            SELECT id, name, source_table, keywords, station_type,
                   max_distance, query_fields, time_field, default_hours,
                   judge_rules, sort_order
            FROM sys_data_source_registry
            WHERE status = 1 AND deleted = 0
            ORDER BY sort_order
        """, engine)
        return registry
    except Exception:
        # 注册表不存在时回退到内置默认
        return get_builtin_registry()


def get_builtin_registry():
    """内置默认注册表（兼容无注册表场景）"""
    data = [
        {"name": "水位监测", "source_table": "st_river_r",
         "keywords": "水位,库水位,上游水位,下游水位,河道水位,汛限水位",
         "station_type": "1", "max_distance": 500,
         "query_fields": "z,q,tm", "time_field": "tm", "default_hours": 24,
         "judge_rules": None, "sort_order": 10},
        {"name": "流量监测", "source_table": "st_river_r",
         "keywords": "流量,入库流量,出库流量,泄洪流量,过闸流量",
         "station_type": "1", "max_distance": 500,
         "query_fields": "q,tm", "time_field": "tm", "default_hours": 24,
         "judge_rules": None, "sort_order": 11},
        {"name": "渗压监测", "source_table": "st_pressure_r",
         "keywords": "渗压,扬压力,孔隙水压力,坝体渗压,渗透压力",
         "station_type": None, "max_distance": 50,
         "query_fields": "water_pressure,ext_pressure,ext_temperature,tm",
         "time_field": "tm", "default_hours": 720,
         "judge_rules": None, "sort_order": 20},
        {"name": "渗流监测", "source_table": "st_percolation_r",
         "keywords": "渗流,渗漏,渗流量,坝脚渗水,渗水",
         "station_type": None, "max_distance": 50,
         "query_fields": "percolation,tm", "time_field": "tm", "default_hours": 720,
         "judge_rules": None, "sort_order": 21},
        {"name": "GNSS位移", "source_table": "srm_gnss_data_day",
         "keywords": "位移,变形,沉降,GNSS,大坝位移,坝体变形,水平位移,垂直位移",
         "station_type": "2", "max_distance": 100,
         "query_fields": "wgs84_delta_h,wgs84_delta_x,wgs84_delta_y,speed_gh,speed_gx,speed_gy,tm",
         "time_field": "tm", "default_hours": 2160,
         "judge_rules": None, "sort_order": 30},
        {"name": "测量机器人", "source_table": "srm_robot_data_day",
         "keywords": "机器人,全站仪,精密测量,机器人位移,大坝变形监测",
         "station_type": None, "max_distance": None,
         "query_fields": "tm,wgs84_delta_h,wgs84_delta_x,wgs84_delta_y,speed_gh,speed_gx,speed_gy,timely_change_north,timely_change_east,timely_change_height,dot_address",
         "time_field": "tm", "default_hours": 120,
         "judge_rules": None, "sort_order": 31},
        {"name": "雨量监测", "source_table": "st_pptn_r",
         "keywords": "雨量,降雨,降水,暴雨,日雨量",
         "station_type": None, "max_distance": 5000,
         "query_fields": "p,dr,tm", "time_field": "tm", "default_hours": 24,
         "judge_rules": None, "sort_order": 40},
        {"name": "闸门状态", "source_table": "rei_gate_r",
         "keywords": "闸门,开度,启闭,闸门开度,过闸,闸门运行",
         "station_type": None, "max_distance": 200,
         "query_fields": "gtophgt,gtopnum,gtq,status,tm",
         "time_field": "tm", "default_hours": 24,
         "judge_rules": None, "sort_order": 50},
        {"name": "泵站参数", "source_table": "rei_pump_r",
         "keywords": "泵站,电压,电流,功率,频率,三相,水泵,电机",
         "station_type": None, "max_distance": 200,
         "query_fields": "uab,ubc,uca,ia,ib,ic,p,q,cos,freq,status,tm",
         "time_field": "tm", "default_hours": 24,
         "judge_rules": None, "sort_order": 51},
        {"name": "设备状态", "source_table": "eq_equip_base",
         "keywords": "设备状态,在线,离线,设备故障,设备运行,设备异常",
         "station_type": None, "max_distance": None,
         "query_fields": "id,name,code,status,position,category",
         "time_field": None, "default_hours": None,
         "judge_rules": None, "sort_order": 60},
        {"name": "设备缺陷", "source_table": "eq_equip_defect",
         "keywords": "缺陷,设备缺陷,故障,事故缺陷,重大缺陷",
         "station_type": None, "max_distance": None,
         "query_fields": "equip_id,name,description,type,handle_status,discovery_time",
         "time_field": "discovery_time", "default_hours": None,
         "judge_rules": None, "sort_order": 65},
        {"name": "摄像头", "source_table": "ew_camera_info",
         "keywords": "外观,裂缝,锈蚀,渗水,表面,破损,视频,监控",
         "station_type": None, "max_distance": None,
         "query_fields": "device_id,channel_id,alarm_code,alarm_stat,confirm",
         "time_field": None, "default_hours": None,
         "judge_rules": None, "sort_order": 70},
        {"name": "违法行为", "source_table": "srm_illegal_acts",
         "keywords": "违法,违规,非法,钓鱼,采砂,倾倒,闯入",
         "station_type": None, "max_distance": None,
         "query_fields": "id,illegal,file_path,processing_time,status",
         "time_field": "create_time", "default_hours": None,
         "judge_rules": None, "sort_order": 72},
    ]
    return pd.DataFrame(data)


def match_data_sources(required_text, registry):
    """根据检查项文本匹配数据源"""
    matched = []
    for _, source in registry.iterrows():
        keywords = [kw.strip() for kw in str(source['keywords']).split(',')]
        if any(kw in required_text for kw in keywords):
            matched.append(source)
    return matched


def collect_from_source(engine, source, st_id=None, project_id=None):
    """从注册表定义的数据源采集数据"""
    table = source['source_table']
    fields = source['query_fields']
    hours = source.get('default_hours')
    time_field = source.get('time_field', 'tm')

    # 标识符白名单校验（防 SQL 注入）
    _validate_identifiers(table, fields, time_field)

    try:
        if st_id and hours:
            sql = (f"SELECT {fields} FROM {table} "
                   f"WHERE st_id=:st_id AND {time_field} >= NOW()-INTERVAL :hours HOUR "
                   f"ORDER BY {time_field} DESC LIMIT 100")
            rows = pd.read_sql(sql, engine, params={"st_id": st_id, "hours": int(hours)})
        elif st_id:
            sql = f"SELECT {fields} FROM {table} WHERE st_id=:st_id ORDER BY {time_field} DESC LIMIT 100"
            rows = pd.read_sql(sql, engine, params={"st_id": st_id})
        elif project_id and hours:
            sql = (f"SELECT {fields} FROM {table} "
                   f"WHERE project_id=:pid AND deleted=0 "
                   f"AND {time_field} >= NOW()-INTERVAL :hours HOUR "
                   f"ORDER BY {time_field} DESC LIMIT 100")
            rows = pd.read_sql(sql, engine, params={"pid": project_id, "hours": int(hours)})
        elif project_id:
            sql = f"SELECT {fields} FROM {table} WHERE project_id=:pid AND deleted=0"
            rows = pd.read_sql(sql, engine, params={"pid": project_id})
        else:
            return {"error": "缺少 st_id 或 project_id"}

        return {
            "source": source['name'],
            "table": table,
            "row_count": len(rows),
            "latest": rows.iloc[0].to_dict() if not rows.empty else None,
            "data": rows.head(10).to_dict('records'),
        }
    except Exception as e:
        return {"source": source['name'], "table": table, "error": str(e)}


def show_registry(registry):
    """打印注册表摘要"""
    print(f"数据源注册表（共 {len(registry)} 项）：")
    for _, row in registry.iterrows():
        print(f"  {row.get('sort_order', '?'):3d}. {row.get('name', '?'):12s} → {row.get('source_table', '?')}")


def demo_collect(engine, registry, source_name="水位监测"):
    """演示采集指定数据源"""
    sources = registry[registry['name'] == source_name]
    if sources.empty:
        print(f"未找到数据源：{source_name}")
        return
    source = sources.iloc[0]
    result = collect_from_source(engine, source, st_id=1)
    print(f"\n采集结果：{result.get('source')} ({result.get('table')})")
    print(f"  行数：{result.get('row_count', 0)}")
    if 'error' in result:
        print(f"  错误：{result['error']}")
    elif result.get('latest'):
        print(f"  最新：{result['latest']}")
