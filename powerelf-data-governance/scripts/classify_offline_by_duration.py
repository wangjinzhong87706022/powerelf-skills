#!/usr/bin/env python3
"""
批量离线设备分级脚本（一步到位）
用法: python3 classify_offline_by_duration.py --db "$DB_URL"

功能:
  - 查询所有离线设备（eq_equip_base.status = 0）
  - JOIN 三张表获取完整信息（离线时长、业务表、阈值）
  - 按离线时长分级（INFO/WARNING/ERROR/CRITICAL）
  - 输出 Markdown 表格（agent 可直接展示）

优化效果:
  - 替代逐站检测（17次工具调用 → 1次）
  - 耗时从 222 秒降至 10-30 秒
"""

import argparse
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

# 复用 lib/offline.py 的分级逻辑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.offline import classify_offline_duration


def classify_offline_by_duration(engine):
    """一步查询所有离线设备并按离线时长分级

    SQL 逻辑:
      1. 从 eq_equip_base 筛选所有离线设备（status = 0）
      2. LEFT JOIN eq_equip_offline_record 获取离线时长
      3. LEFT JOIN eq_business_equip_relation 获取业务表和阈值
      4. 在 Python 层复用 lib/offline.py 的分级逻辑
    """
    sql = """
    SELECT
        e.id,
        e.name,
        e.code,
        e.type_flag,
        e.st_base_id,
        r.total_offline_duration,
        r.offline_start_date,
        r.offline_start_time,
        r.offline_end_time,
        b.business_table,
        b.offline_threshold,
        b.frequency
    FROM eq_equip_base e
    LEFT JOIN eq_equip_offline_record r
        ON e.id = r.equipment_code  -- ⚠️ id (bigint) ↔ equipment_code (bigint)
    LEFT JOIN eq_business_equip_relation b
        ON e.id = b.eq_id
    WHERE e.status = 0
      AND e.deleted = 0
    ORDER BY r.total_offline_duration DESC
    """

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        devices = []

        for row in result:
            # SQLAlchemy 2.0 Row 对象转 dict
            device = dict(row._mapping)

            # 分级逻辑（复用 lib/offline.py，保持阈值一致）
            if device['total_offline_duration'] is None:
                # 无离线记录，可能是状态刚变，设为 INFO
                device['offline_hours'] = 0.0
                device['severity'] = 'INFO'
            else:
                offline_hours = device['total_offline_duration'] / 3600.0
                device['offline_hours'] = round(offline_hours, 2)
                device['severity'] = classify_offline_duration(offline_hours)

            # 计算离线开始时间
            if device['offline_start_date'] and device['offline_start_time']:
                start_dt = device['offline_start_time'] if isinstance(device['offline_start_time'], datetime) else datetime.combine(device['offline_start_date'], datetime.min.time())
                device['offline_start'] = start_dt.strftime('%Y-%m-%d %H:%M')
            elif device['offline_start_date']:
                device['offline_start'] = device['offline_start_date'].strftime('%Y-%m-%d')
            else:
                device['offline_start'] = '未知'

            # 格式化业务表名
            device['business_table_display'] = device['business_table'] or '未知'
            device['threshold_display'] = f"{device['offline_threshold']}min" if device['offline_threshold'] else '未配置'
            device['freq_display'] = f"{device['frequency']}min" if device['frequency'] else '未知'

            devices.append(device)

    return devices


def format_markdown(devices, limit=20):
    """格式化为 Markdown 表格（直接展示用）

    Args:
        devices: 设备列表
        limit: 详细列表最大显示行数（默认 20，避免输出过大）
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f"## 离线设备分级分析结果",
        f"",
        f"**统计时间**: {now}",
        f"**离线设备总数**: {len(devices)} 台",
        f"",
    ]

    # 按严重级别分组统计
    by_severity = {}
    for d in devices:
        sev = d['severity']
        by_severity.setdefault(sev, []).append(d)

    # 分级汇总
    lines.append("### 分级汇总")
    lines.append("")
    severity_order = ['CRITICAL', 'ERROR', 'WARNING', 'INFO']
    severity_desc = {
        'CRITICAL': '严重离线（>24 小时）',
        'ERROR': '长期离线（4-24 小时）',
        'WARNING': '短期离线（1-4 小时）',
        'INFO': '轻度离线（<1 小时）',
    }
    for sev in severity_order:
        count = len(by_severity.get(sev, []))
        if count > 0:
            lines.append(f"- **{sev}**（{severity_desc[sev]}）: {count} 台")
    lines.append("")

    # 详细列表（限制行数）
    if limit is None or len(devices) <= limit:
        lines.append("### 详细列表（全部）")
        display_devices = devices
    else:
        lines.append(f"### 详细列表（前 {limit} 台，共 {len(devices)} 台）")
        display_devices = devices[:limit]

    lines.append("")
    lines.append("| 严重级别 | 设备名称 | 设备编码 | 类型 | 离线时长(h) | 开始时间 | 业务表 | 阈值 | 采集频率 |")
    lines.append("|---------|---------|---------|------|-----------|---------|-------|------|---------|")

    for d in display_devices:
        lines.append(
            f"| {d['severity']} | {d['name']} | {d['code']} "
            f"| {d['type_flag']} | {d['offline_hours']}h "
            f"| {d['offline_start']} | {d['business_table_display']} "
            f"| {d['threshold_display']} | {d['freq_display']} |"
        )

    if limit is not None and len(devices) > limit:
        lines.append(f"\n... 还有 {len(devices) - limit} 台设备，使用 `--full` 参数查看完整列表")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*数据来源: eq_equip_base + eq_equip_offline_record + eq_business_equip_relation*")

    return "\n".join(lines)


def format_csv(devices):
    """格式化为 CSV（用于人工复核）"""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # 表头
    writer.writerow([
        'severity', 'device_name', 'device_code', 'type_flag',
        'offline_hours', 'offline_start', 'business_table',
        'offline_threshold_min', 'frequency_min', 'total_offline_duration_sec'
    ])

    # 数据行
    for d in devices:
        writer.writerow([
            d['severity'],
            d['name'],
            d['code'],
            d['type_flag'],
            d['offline_hours'],
            d['offline_start'],
            d['business_table'] or '',
            d['offline_threshold'] or '',
            d['frequency'] or '',
            d['total_offline_duration'] or ''
        ])

    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description="批量离线设备分级脚本")
    parser.add_argument("--db", required=True, help="数据库连接（SQLAlchemy URL）")
    parser.add_argument("--format", choices=['markdown', 'csv', 'json'], default='markdown',
                        help="输出格式（默认: markdown）")
    parser.add_argument("--output", help="输出文件（默认: stdout）")
    parser.add_argument("--limit", type=int, default=20,
                        help="Markdown 输出详细列表的最大行数（默认 20）")
    parser.add_argument("--full", action='store_true',
                        help="输出完整列表（覆盖 --limit）")
    args = parser.parse_args()

    engine = create_engine(args.db)
    devices = classify_offline_by_duration(engine)

    # 按格式输出
    if args.format == 'markdown':
        limit = None if args.full else args.limit
        output = format_markdown(devices, limit=limit)
    elif args.format == 'csv':
        output = format_csv(devices)
    elif args.format == 'json':
        import json
        output = json.dumps(devices, ensure_ascii=False, indent=2, default=str)

    # 写文件或 stdout
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 已输出 {len(devices)} 条记录到 {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
