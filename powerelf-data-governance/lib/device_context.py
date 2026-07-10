"""
设备上下文关联模块 — 异常检测结果与设备知识库/运维记录关联

当检测到数据异常、离线、卡滞等问题时，自动查询：
1. 设备基础信息（厂商、型号、寿命、维保周期）
2. 历史缺陷记录（同类故障频率）
3. 维护保养记录（上次维修时间、是否超期）
4. 知识库相关文档（故障排除指南）

生成带上下文的智能运维建议。
"""

import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta


def get_device_context(conn, equipment_code: int) -> Dict:
    """获取设备完整上下文信息

    Args:
        conn: pymysql 连接
        equipment_code: 设备ID (eq_equip_base.id)

    Returns:
        dict: {
            device: {name, code, type, manufacturer, model, ...},
            defects: [{name, type, discovery_time, handle_status, ...}],
            maintenance: [{name, type, begin_time, end_time, result, ...}],
            ratings: [{rate_level, rate_time, ...}],
            overdue: {is_overdue, days_overdue, next_maintenance_date},
        }
    """
    cur = conn.cursor()

    # 1. 设备基础信息
    cur.execute("""
        SELECT id, name, code, type_flag, model, manufacturer,
               start_use_date, maintenance_cycle, service_life,
               next_maintenance_date, status, position, manage_unit
        FROM eq_equip_base
        WHERE id = %s AND deleted = 0
    """, (equipment_code,))
    device_row = cur.fetchone()
    if not device_row:
        return {"error": f"设备 {equipment_code} 不存在"}

    columns = [d[0] for d in cur.description]
    device = dict(zip(columns, device_row))

    # 2. 历史缺陷记录（最近10条）— 表可能不存在
    defects = []
    try:
        cur.execute("""
            SELECT id, name, description, type, discovery_time,
                   handle_status, handle_time, handle_description
            FROM eq_equip_defect
            WHERE equip_id = %s AND deleted = 0
            ORDER BY discovery_time DESC
            LIMIT 10
        """, (equipment_code,))
        for row in cur.fetchall():
            cols = [d[0] for d in cur.description]
            defects.append(dict(zip(cols, row)))
    except Exception:
        pass  # 表不存在时跳过

    # 3. 维护保养记录（最近10条）— 表可能不存在
    maintenance = []
    try:
        cur.execute("""
            SELECT r.id, r.name, r.type, r.begin_time, r.end_time,
                   r.result, r.status, r.content
            FROM eq_equip_record r
            WHERE r.equip_ids LIKE CONCAT('%%{', %s, '}%%')
              AND r.deleted = 0
            ORDER BY r.begin_time DESC
            LIMIT 10
        """, (equipment_code,))
        for row in cur.fetchall():
            cols = [d[0] for d in cur.description]
            maintenance.append(dict(zip(cols, row)))
    except Exception:
        pass

    # 4. 设备评级 — 表可能不存在
    ratings = []
    try:
        cur.execute("""
            SELECT rate_level, rate_time, sprate_level, sprate_time
            FROM eq_equip_rate
            WHERE equip_id = %s AND deleted = 0
            ORDER BY rate_time DESC
            LIMIT 3
        """, (equipment_code,))
        for row in cur.fetchall():
            cols = [d[0] for d in cur.description]
            ratings.append(dict(zip(cols, row)))
    except Exception:
        pass

    # 5. 维保到期检查
    overdue = _check_maintenance_overdue(device)

    # 6. 设备类型映射
    type_names = {
        1: '水位计', 2: '渗压计', 3: '闸门', 4: '泵站',
        5: 'GNSS', 6: '雨量计', 7: '流量计', 8: '水质计'
    }
    device['type_name'] = type_names.get(device.get('type_flag'), f"类型{device.get('type_flag')}")

    return {
        "device": device,
        "defects": defects,
        "maintenance": maintenance,
        "ratings": ratings,
        "overdue": overdue,
    }


def _check_maintenance_overdue(device: Dict) -> Dict:
    """检查设备是否超期未维护"""
    result = {
        "is_overdue": False,
        "days_overdue": 0,
        "next_maintenance_date": None,
        "message": "",
    }

    next_date = device.get("next_maintenance_date")
    if next_date:
        if isinstance(next_date, str):
            next_date = datetime.strptime(next_date, "%Y-%m-%d %H:%M:%S")
        result["next_maintenance_date"] = str(next_date)
        now = datetime.now()
        if now > next_date:
            days = (now - next_date).days
            result["is_overdue"] = True
            result["days_overdue"] = days
            result["message"] = f"维保已超期{days}天（应于{next_date.strftime('%Y-%m-%d')}维护）"

    # 检查是否超过使用寿命
    start_date = device.get("start_use_date")
    service_life = device.get("service_life")
    if start_date and service_life:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = start_date + timedelta(days=service_life)
        if datetime.now() > end_date:
            result["is_overdue"] = True
            result["message"] += f"；已超过设计寿命（{end_date.strftime('%Y-%m-%d')}）"

    return result


def get_similar_defects(conn, equipment_code: int, defect_type: str = None) -> List[Dict]:
    """查询同类型设备的相似缺陷

    Args:
        conn: pymysql 连接
        equipment_code: 设备ID
        defect_type: 缺陷类型（可选）

    Returns:
        list of dict: 相似缺陷列表
    """
    cur = conn.cursor()

    # 先获取设备类型
    cur.execute("SELECT type_flag FROM eq_equip_base WHERE id = %s AND deleted = 0", (equipment_code,))
    row = cur.fetchone()
    if not row:
        return []

    type_flag = row[0]

    # 查询同类型设备的缺陷
    sql = """
        SELECT d.name, d.description, d.type, d.discovery_time,
               d.handle_status, d.handle_description, e.name AS device_name
        FROM eq_equip_defect d
        JOIN eq_equip_base e ON d.equip_id = e.id AND e.deleted = 0
        WHERE e.type_flag = %s AND d.deleted = 0
    """
    params = [type_flag]

    if defect_type:
        sql += " AND d.type = %s"
        params.append(defect_type)

    sql += " ORDER BY d.discovery_time DESC LIMIT 20"

    cur.execute(sql, params)
    results = []
    for row in cur.fetchall():
        cols = [d[0] for d in cur.description]
        results.append(dict(zip(cols, row)))

    return results


def search_knowledge_base(conn, keywords: List[str], size: int = 5, provider: str = None) -> List[Dict]:
    """搜索知识库（通过统一知识检索框架）

    Args:
        conn: pymysql 连接
        keywords: 搜索关键词列表
        size: 返回数量
        provider: 知识库后端 (None=自动检测, "mysql", "ragflow", "elasticsearch", "chroma")

    Returns:
        list of dict: 知识库条目
    """
    from .knowledge import search_knowledge

    query = " ".join(keywords)
    results = search_knowledge(query, top_k=size, provider=provider, conn=conn)
    return [r.to_dict() for r in results]


def generate_maintenance_suggestion(
    anomaly_type: str,
    device_context: Dict,
    knowledge_results: List[Dict] = None,
) -> Dict:
    """根据异常类型和设备上下文生成智能运维建议

    Args:
        anomaly_type: 异常类型 (stagnation/drift/spike/offline/missing/correlation/extreme)
        device_context: get_device_context() 的输出
        knowledge_results: search_knowledge_base() 的输出（可选）

    Returns:
        dict: {
            priority: str,           # 紧急程度 (P0/P1/P2/P3)
            suggestion: str,         # 建议内容
            actions: list[str],      # 具体操作步骤
            knowledge_refs: list,    # 参考知识库条目
            similar_defects: list,   # 历史相似缺陷
        }
    """
    device = device_context.get("device", {})
    defects = device_context.get("defects", [])
    maintenance = device_context.get("maintenance", [])
    overdue = device_context.get("overdue", {})
    type_name = device.get("type_name", "未知设备")

    result = {
        "priority": "P2",
        "suggestion": "",
        "actions": [],
        "knowledge_refs": knowledge_results or [],
        "similar_defects": defects[:3],
    }

    # ===== 根据异常类型生成建议 =====

    if anomaly_type == "stagnation":
        result["priority"] = "P1"
        result["suggestion"] = f"{type_name}传感器疑似卡滞，连续输出相同值"
        result["actions"] = [
            f"1. 现场检查{type_name}传感器是否正常工作",
            "2. 检查传感器供电是否稳定",
            "3. 检查信号传输线路是否正常",
            "4. 尝试重启传感器设备",
            "5. 如重启无效，联系厂家更换",
        ]

    elif anomaly_type == "drift":
        result["priority"] = "P2"
        result["suggestion"] = f"{type_name}传感器存在渐进漂移，可能需要校准"
        result["actions"] = [
            f"1. 使用标准器对{type_name}传感器进行现场校准",
            "2. 检查传感器安装位置是否发生变化",
            "3. 检查环境因素（温度、湿度）是否影响测量",
            "4. 记录校准前后的偏差值",
        ]

    elif anomaly_type == "spike":
        result["priority"] = "P1"
        result["suggestion"] = f"{type_name}数据出现突变，可能是传感器故障或信号干扰"
        result["actions"] = [
            "1. 检查突变时间点是否有外部干扰（雷击、电磁干扰）",
            "2. 检查传感器接线是否松动",
            "3. 检查数据采集器是否正常",
            "4. 查看历史数据确认是否为偶发事件",
        ]

    elif anomaly_type == "offline":
        result["priority"] = "P0" if overdue.get("is_overdue") else "P1"
        result["suggestion"] = f"{type_name}设备离线"
        if overdue.get("is_overdue"):
            result["suggestion"] += f"，且维保已超期{overdue['days_overdue']}天"
        result["actions"] = [
            "1. 检查设备供电（电源、蓄电池）",
            "2. 检查通信链路（4G信号、网线、光纤）",
            "3. 检查设备是否在现场正常运行",
            "4. 如设备故障，启动维修流程",
        ]
        if overdue.get("is_overdue"):
            result["actions"].append(f"5. 【紧急】安排维保，已超期{overdue['days_overdue']}天")

    elif anomaly_type == "missing":
        result["priority"] = "P2"
        result["suggestion"] = f"{type_name}数据缺失"
        result["actions"] = [
            "1. 检查数据采集定时任务是否正常运行",
            "2. 检查数据库连接是否正常",
            "3. 确认设备在缺失时段是否在线",
            "4. 如设备在线但无数据，检查采集程序日志",
        ]

    elif anomaly_type == "correlation":
        result["priority"] = "P0"
        result["suggestion"] = f"多指标数据存在物理矛盾，可能是传感器故障"
        result["actions"] = [
            "1. 现场核查相关传感器的测量值",
            "2. 使用便携式仪器进行对比测量",
            "3. 检查数据传输过程中是否有错误",
            "4. 如确认传感器故障，立即更换",
        ]

    elif anomaly_type == "extreme":
        result["priority"] = "P1"
        result["suggestion"] = f"检测到极端数值，需确认是真实事件还是传感器故障"
        result["actions"] = [
            "1. 查看同期其他监测站数据是否一致",
            "2. 查看气象数据（降雨、气温）是否支撑",
            "3. 如确认为真实极端事件，记录备案",
            "4. 如确认为传感器故障，按spike处理",
        ]

    # ===== 结合维保状态补充建议 =====
    if overdue.get("is_overdue"):
        result["actions"].append(f"\n⚠️ 维保提醒：该设备{overdue['message']}")

    # ===== 结合历史缺陷补充建议 =====
    if defects:
        recent_defects = [d for d in defects if d.get("handle_status") in ("0", "1")]
        if recent_defects:
            result["actions"].append(f"\n⚠️ 该设备有{len(recent_defects)}个未处理缺陷：")
            for d in recent_defects[:3]:
                result["actions"].append(f"  - {d['name']}（发现于{d.get('discovery_time', 'N/A')}）")

    # ===== 结合知识库补充建议 =====
    if knowledge_results:
        result["actions"].append("\n📚 相关知识库文档：")
        for kb in knowledge_results[:3]:
            result["actions"].append(f"  - {kb.get('name', 'N/A')}: {kb.get('doc_name', 'N/A')}")

    return result


def analyze_with_context(
    conn,
    equipment_code: int,
    anomaly_type: str,
    anomaly_detail: str = "",
) -> Dict:
    """一键分析：异常检测 + 设备上下文 + 知识库 + 智能建议

    Args:
        conn: pymysql 连接
        equipment_code: 设备ID
        anomaly_type: 异常类型
        anomaly_detail: 异常详情

    Returns:
        dict: {device_context, knowledge, suggestion}
    """
    # 1. 获取设备上下文
    ctx = get_device_context(conn, equipment_code)

    # 2. 搜索知识库
    type_name = ctx.get("device", {}).get("type_name", "")
    keywords = [type_name, anomaly_type]
    if anomaly_detail:
        keywords.append(anomaly_detail)
    knowledge = search_knowledge_base(conn, keywords)

    # 3. 生成建议
    suggestion = generate_maintenance_suggestion(anomaly_type, ctx, knowledge)

    return {
        "device_context": ctx,
        "knowledge": knowledge,
        "suggestion": suggestion,
    }
