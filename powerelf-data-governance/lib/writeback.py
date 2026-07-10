"""
数据治理回写模块 — 将分析结果写回数据库

功能:
- 异常修复: 将插值结果写入 eq_data_anomaly_record.fix_data_content
- 缺失填补: 将插值结果写入 eq_data_missing_record.filled_data_content
- 设备状态: 更新 eq_equip_base.status
- 离线记录: 创建/更新 eq_equip_offline_record
- 异常记录: 创建 eq_data_anomaly_record
"""

import json
from datetime import datetime


def fix_anomaly(conn, anomaly_id, fix_data, whether_fix=1):
    """修复异常记录，将修复数据写入 fix_data_content

    Args:
        conn: pymysql 连接对象
        anomaly_id: 异常记录ID
        fix_data: 修复数据 (dict/list)，将序列化为 JSON
        whether_fix: 是否已修复 (0=否, 1=是)

    Returns:
        bool: 是否成功
    """
    sql = """
        UPDATE eq_data_anomaly_record
        SET fix_data_content = %s, whether_fix = %s
        WHERE id = %s
    """
    cur = conn.cursor()
    try:
        cur.execute(sql, (json.dumps(fix_data, ensure_ascii=False, default=str), whether_fix, anomaly_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"修复异常记录失败: {e}")
    finally:
        cur.close()


def fill_missing(conn, missing_id, filled_data, whether_add=1):
    """填补缺失记录，将填补数据写入 filled_data_content

    Args:
        conn: pymysql 连接对象
        missing_id: 缺失记录ID
        filled_data: 填补数据 (dict/list)，将序列化为 JSON
        whether_add: 是否已补录 (0=否, 1=是)

    Returns:
        bool: 是否成功
    """
    sql = """
        UPDATE eq_data_missing_record
        SET filled_data_content = %s, whether_add = %s
        WHERE id = %s
    """
    cur = conn.cursor()
    try:
        cur.execute(sql, (json.dumps(filled_data, ensure_ascii=False, default=str), whether_add, missing_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"填补缺失记录失败: {e}")
    finally:
        cur.close()


def update_device_status(conn, device_id, status):
    """更新设备状态

    Args:
        conn: pymysql 连接对象
        device_id: 设备ID (eq_equip_base.id)
        status: 新状态 (0=离线, 1=在线, 2=异常)

    Returns:
        bool: 是否成功
    """
    sql = "UPDATE eq_equip_base SET status = %s WHERE id = %s AND deleted = 0"
    cur = conn.cursor()
    try:
        cur.execute(sql, (status, device_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"更新设备状态失败: {e}")
    finally:
        cur.close()


def create_offline_record(conn, equipment_code, offline_start, offline_end=None, duration_seconds=None):
    """创建设备离线记录

    Args:
        conn: pymysql 连接对象
        equipment_code: 设备ID
        offline_start: 离线开始时间 (datetime)
        offline_end: 离线结束时间 (datetime, 可选)
        duration_seconds: 离线时长(秒, 可选)

    Returns:
        int: 新记录ID
    """
    if duration_seconds is None and offline_end is not None:
        duration_seconds = int((offline_end - offline_start).total_seconds())

    sql = """
        INSERT INTO eq_equip_offline_record
        (equipment_code, offline_start_date, offline_start_time, offline_end_time, total_offline_duration, tenant_id)
        VALUES (%s, %s, %s, %s, %s, 1)
    """
    cur = conn.cursor()
    try:
        cur.execute(sql, (
            equipment_code,
            offline_start.date(),
            offline_start,
            offline_end,
            duration_seconds or 0
        ))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"创建离线记录失败: {e}")
    finally:
        cur.close()


def update_offline_record(conn, record_id, offline_end, duration_seconds):
    """更新离线记录（设备恢复时）

    Args:
        conn: pymysql 连接对象
        record_id: 离线记录ID
        offline_end: 离线结束时间 (datetime)
        duration_seconds: 总离线时长(秒)

    Returns:
        bool: 是否成功
    """
    sql = """
        UPDATE eq_equip_offline_record
        SET offline_end_time = %s, total_offline_duration = %s
        WHERE id = %s
    """
    cur = conn.cursor()
    try:
        cur.execute(sql, (offline_end, duration_seconds, record_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"更新离线记录失败: {e}")
    finally:
        cur.close()


def create_anomaly_record(conn, equipment_code, anomaly_time, table_name, fix_data=None):
    """创建数据异常记录

    Args:
        conn: pymysql 连接对象
        equipment_code: 设备ID
        anomaly_time: 异常时间 (datetime)
        table_name: 数据来源表名
        fix_data: 修复数据 (可选)

    Returns:
        int: 新记录ID
    """
    sql = """
        INSERT INTO eq_data_anomaly_record
        (equipment_code, data_anomaly_datetime, data_anomaly_date, whether_fix, table_name, fix_data_content, tenant_id)
        VALUES (%s, %s, %s, %s, %s, %s, 1)
    """
    cur = conn.cursor()
    try:
        fix_json = json.dumps(fix_data, ensure_ascii=False, default=str) if fix_data else None
        whether_fix = 1 if fix_data else 0
        cur.execute(sql, (equipment_code, anomaly_time, anomaly_time.date(), whether_fix, table_name, fix_json))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"创建异常记录失败: {e}")
    finally:
        cur.close()


def create_missing_record(conn, equipment_code, missing_time, table_name, missing_count=1, filled_data=None):
    """创建数据缺失记录

    Args:
        conn: pymysql 连接对象
        equipment_code: 设备ID
        missing_time: 缺失时间 (datetime)
        table_name: 数据来源表名
        missing_count: 缺失条数
        filled_data: 填补数据 (可选)

    Returns:
        int: 新记录ID
    """
    sql = """
        INSERT INTO eq_data_missing_record
        (equipment_code, data_missing_datetime, data_missing_date, data_missing_count,
         whether_add, table_name, filled_data_content, tenant_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
    """
    cur = conn.cursor()
    try:
        filled_json = json.dumps(filled_data, ensure_ascii=False, default=str) if filled_data else None
        whether_add = 1 if filled_data else 0
        cur.execute(sql, (equipment_code, missing_time, missing_time.date(), missing_count, whether_add, table_name, filled_json))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"创建缺失记录失败: {e}")
    finally:
        cur.close()


def batch_fix_anomalies(conn, fixes):
    """批量修复异常记录

    Args:
        conn: pymysql 连接对象
        fixes: list of dict, 每个包含 {anomaly_id, fix_data, whether_fix}

    Returns:
        dict: {success_count, total_count, failed_ids: [...]}
    """
    sql = """
        UPDATE eq_data_anomaly_record
        SET fix_data_content = %s, whether_fix = %s
        WHERE id = %s
    """
    cur = conn.cursor()
    success = 0
    failed_ids = []
    for fix in fixes:
        try:
            cur.execute(sql, (
                json.dumps(fix['fix_data'], ensure_ascii=False, default=str),
                fix.get('whether_fix', 1),
                fix['anomaly_id']
            ))
            success += cur.rowcount
        except Exception as e:
            failed_ids.append(fix.get('anomaly_id'))
            import logging
            logging.warning("修复异常记录 %s 失败: %s", fix.get('anomaly_id'), e)
    try:
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"批量修复提交失败: {e}")
    finally:
        cur.close()
    return {
        "success_count": success,
        "total_count": len(fixes),
        "failed_ids": failed_ids,
    }


def batch_fill_missing(conn, fills):
    """批量填补缺失记录

    Args:
        conn: pymysql 连接对象
        fills: list of dict, 每个包含 {missing_id, filled_data, whether_add}

    Returns:
        dict: {success_count, total_count, failed_ids: [...]}
    """
    sql = """
        UPDATE eq_data_missing_record
        SET filled_data_content = %s, whether_add = %s
        WHERE id = %s
    """
    cur = conn.cursor()
    success = 0
    failed_ids = []
    for fill in fills:
        try:
            cur.execute(sql, (
                json.dumps(fill['filled_data'], ensure_ascii=False, default=str),
                fill.get('whether_add', 1),
                fill['missing_id']
            ))
            success += cur.rowcount
        except Exception as e:
            failed_ids.append(fill.get('missing_id'))
            import logging
            logging.warning("填补缺失记录 %s 失败: %s", fill.get('missing_id'), e)
    try:
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"批量填补提交失败: {e}")
    finally:
        cur.close()
    return {
        "success_count": success,
        "total_count": len(fills),
        "failed_ids": failed_ids,
    }
