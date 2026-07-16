#!/usr/bin/env python3
"""
告警查询脚本 - 预写常用查询，减少 LLM 推理轮次
用法: python3 query_early_warning.py --type <查询类型> [参数]

共享库: SmartTwinRes-skills/lib/db.py
标准文档: docs/db-credential-config.md
"""

import argparse
import json
import sys
import os

# 让脚本既能 `python3 scripts/query_early_warning.py` 又能被 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

# 从统一共享库导入 DB 查询功能
# 注意: execute_query_list() 返回 list[dict],与原代码兼容
from lib.db import execute_query_list, _require_env  # noqa: E402


def query_unconfirmed(days=7):
    """查询未确认告警"""
    sql = """
    SELECT COUNT(*) as count
    FROM ew_info_message
    WHERE message_confirm = 0 AND deleted = 0
      AND create_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
    """
    return execute_query_list(sql, (days,))

def query_by_level(days=30):
    """按级别统计告警"""
    sql = """
    SELECT
      level_r as level,
      CASE
        WHEN level_r = '1' THEN '红色(I级)'
        WHEN level_r = '2' THEN '橙色(II级)'
        WHEN level_r = '3' THEN '黄色(III级)'
        WHEN level_r = '4' THEN '蓝色(IV级)'
      END as level_name,
      COUNT(*) as count
    FROM ew_info_message
    WHERE deleted = 0
      AND create_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
    GROUP BY level_r
    ORDER BY level_r
    """
    return execute_query_list(sql, (days,))

def query_recent(days=3, limit=50):
    """查询最近告警"""
    sql = """
    SELECT id, ew_name, st_code, level_r, value, gather_time, message_confirm
    FROM ew_info_message
    WHERE deleted = 0
      AND create_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
    ORDER BY gather_time DESC
    LIMIT %s
    """
    return execute_query_list(sql, (days, limit))

def query_by_station(station_code, limit=50):
    """查询指定测站告警"""
    sql = """
    SELECT id, ew_name, level_r, value, gather_time, message_confirm
    FROM ew_info_message
    WHERE st_code = %s AND deleted = 0
    ORDER BY gather_time DESC
    LIMIT %s
    """
    return execute_query_list(sql, (station_code, limit))

def query_high_level(days=30):
    """查询高级别告警"""
    sql = """
    SELECT id, ew_name, st_code, value, gather_time
    FROM ew_info_message
    WHERE level_r IN ('1', '2') AND deleted = 0
      AND create_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
    ORDER BY gather_time DESC
    LIMIT 50
    """
    return execute_query_list(sql, (days,))

def query_rules():
    """查询告警规则"""
    sql = """
    SELECT id, name, ew_type, level_r, st_code, extend
    FROM ew_info_rules
    WHERE deleted = 0
    ORDER BY ew_type, level_r
    """
    return execute_query_list(sql)

def query_station_ranking(days=30, limit=10):
    """查询测站告警排名"""
    sql = """
    SELECT st_code, COUNT(*) as count
    FROM ew_info_message
    WHERE deleted = 0
      AND create_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
    GROUP BY st_code
    ORDER BY count DESC
    LIMIT %s
    """
    return execute_query_list(sql, (days, limit))

def query_hourly_distribution(days=30):
    """查询小时分布"""
    sql = """
    SELECT HOUR(gather_time) as hour, COUNT(*) as count
    FROM ew_info_message
    WHERE deleted = 0
      AND create_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
    GROUP BY HOUR(gather_time)
    ORDER BY count DESC
    """
    return execute_query_list(sql, (days,))

def query_device_offline(days=7):
    """查询设备离线告警"""
    sql = """
    SELECT id, st_code, level_r, gather_time
    FROM ew_info_message
    WHERE ew_name LIKE '%%离线%%' AND deleted = 0
      AND create_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
    ORDER BY gather_time DESC
    LIMIT 50
    """
    return execute_query_list(sql, (days,))

def query_alarm_trend(start_date, end_date):
    """查询告警趋势"""
    sql = """
    SELECT DATE(gather_time) as date, COUNT(*) as count
    FROM ew_info_message
    WHERE deleted = 0
      AND gather_time >= %s AND gather_time <= %s
    GROUP BY DATE(gather_time)
    ORDER BY date
    """
    return execute_query_list(sql, (start_date, end_date))

def query_rule_detail(rule_name):
    """查询规则详情"""
    sql = """
    SELECT name, ew_type, level_r, st_code, extend
    FROM ew_info_rules
    WHERE name LIKE %s AND deleted = 0
    """
    return execute_query_list(sql, (f'%{rule_name}%',))

def query_water_level(station_code):
    """查询当前水位"""
    sql = """
    SELECT rz as water_level, tm as time
    FROM st_rsvr_r
    WHERE eq_code = %s
    ORDER BY tm DESC
    LIMIT 1
    """
    return execute_query_list(sql, (station_code,))

def query_rainfall(station_code):
    """查询当前降雨"""
    sql = """
    SELECT p as rainfall, tm as time
    FROM st_pptn_r
    WHERE eq_code = %s
    ORDER BY tm DESC
    LIMIT 1
    """
    return execute_query_list(sql, (station_code,))

def query_alarm_storm():
    """查询告警风暴状态"""
    sql = """
    SELECT
      COUNT(*) as total,
      SUM(CASE WHEN create_time >= DATE_SUB(NOW(), INTERVAL 1 MINUTE) THEN 1 ELSE 0 END) as last_minute,
      SUM(CASE WHEN create_time >= DATE_SUB(NOW(), INTERVAL 1 HOUR) THEN 1 ELSE 0 END) as last_hour
    FROM ew_info_message
    WHERE deleted = 0
      AND create_time >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
    """
    return execute_query_list(sql)

def query_confirmation_rate(days=30):
    """查询确认率"""
    sql = """
    SELECT
      level_r as level,
      COUNT(*) as total,
      SUM(CASE WHEN message_confirm = 1 THEN 1 ELSE 0 END) as confirmed,
      ROUND(SUM(CASE WHEN message_confirm = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as rate
    FROM ew_info_message
    WHERE deleted = 0
      AND create_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
    GROUP BY level_r
    ORDER BY level_r
    """
    return execute_query_list(sql, (days,))

def query_weather_warning():
    """查询有效气象预警"""
    sql = """
    SELECT docid, docabstract, chnlname, model_type, docpubtime, docpuburl, warn_status
    FROM weather_warn
    WHERE warn_status = '1'
    ORDER BY docpubtime DESC
    LIMIT 20
    """
    return execute_query_list(sql)

def main():
    parser = argparse.ArgumentParser(description='告警查询脚本')
    parser.add_argument('--type', required=True, choices=[
        'unconfirmed', 'by_level', 'recent', 'by_station', 'high_level',
        'rules', 'station_ranking', 'hourly_distribution', 'device_offline',
        'alarm_trend', 'rule_detail', 'water_level', 'rainfall',
        'alarm_storm', 'confirmation_rate', 'weather_warning'
    ], help='查询类型')
    parser.add_argument('--days', type=int, default=7, help='查询天数')
    parser.add_argument('--limit', type=int, default=50, help='返回条数')
    parser.add_argument('--station', type=str, help='测站编码')
    parser.add_argument('--rule', type=str, help='规则名称')
    parser.add_argument('--start', type=str, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--format', choices=['json', 'table'], default='table', help='输出格式')

    args = parser.parse_args()

    # 执行查询
    result = None
    if args.type == 'unconfirmed':
        result = query_unconfirmed(args.days)
    elif args.type == 'by_level':
        result = query_by_level(args.days)
    elif args.type == 'recent':
        result = query_recent(args.days, args.limit)
    elif args.type == 'by_station':
        if not args.station:
            print("错误: --station 参数必填")
            sys.exit(1)
        result = query_by_station(args.station, args.limit)
    elif args.type == 'high_level':
        result = query_high_level(args.days)
    elif args.type == 'rules':
        result = query_rules()
    elif args.type == 'station_ranking':
        result = query_station_ranking(args.days, args.limit)
    elif args.type == 'hourly_distribution':
        result = query_hourly_distribution(args.days)
    elif args.type == 'device_offline':
        result = query_device_offline(args.days)
    elif args.type == 'alarm_trend':
        if not args.start or not args.end:
            print("错误: --start 和 --end 参数必填")
            sys.exit(1)
        result = query_alarm_trend(args.start, args.end)
    elif args.type == 'rule_detail':
        if not args.rule:
            print("错误: --rule 参数必填")
            sys.exit(1)
        result = query_rule_detail(args.rule)
    elif args.type == 'water_level':
        if not args.station:
            print("错误: --station 参数必填")
            sys.exit(1)
        result = query_water_level(args.station)
    elif args.type == 'rainfall':
        if not args.station:
            print("错误: --station 参数必填")
            sys.exit(1)
        result = query_rainfall(args.station)
    elif args.type == 'alarm_storm':
        result = query_alarm_storm()
    elif args.type == 'confirmation_rate':
        result = query_confirmation_rate(args.days)
    elif args.type == 'weather_warning':
        result = query_weather_warning()

    # 输出结果
    if result is not None:
        if args.format == 'json':
            print(json.dumps(result, ensure_ascii=False, default=str))
        else:
            if not result:
                print("无数据")
            else:
                # 表格格式输出
                headers = result[0].keys()
                print('\t'.join(headers))
                print('-' * 80)
                for row in result:
                    print('\t'.join(str(row.get(h, '')) for h in headers))

if __name__ == '__main__':
    main()
