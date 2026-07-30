#!/usr/bin/env python3
"""
端到端（E2E）验证：模拟 agent 执行"离线设备分级"任务

对比两种方案：
1. 优化前：逐站循环调用 offline_detector.py（模拟 5 台设备）
2. 优化后：调用 classify_offline_by_duration.py（一次批量查询）

测量指标：
- 工具调用次数
- SQL 查询耗时
- 输出 token 数（估算）
- 总耗时

用法:
  python3 e2e_benchmark.py --db "$DB_URL" --stations 5
"""

import time
import sys
import os
import subprocess
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.offline import classify_offline_duration


def simulate_old_approach(engine, station_ids):
    """模拟旧方案：逐站循环调用 offline_detector.py"""
    print(f"\n{'='*80}")
    print(f"旧方案：逐站循环调用 offline_detector.py（{len(station_ids)} 台设备）")
    print(f"{'='*80}\n")

    results = []
    start_time = time.time()

    for i, st_id in enumerate(station_ids, 1):
        print(f"  [{i}/{len(station_ids)}] 检测设备 st_id={st_id}...", end=" ", flush=True)

        # 模拟单站检测（查最新时间 + 判定）
        sql = "SELECT MAX(tm) as latest FROM st_pressure_r WHERE st_id = :st_id AND deleted = 0"

        step_start = time.time()
        with engine.connect() as conn:
            result = conn.execute(text(sql), {"st_id": st_id})
            latest = result.scalar()

        if latest:
            from datetime import datetime
            now = datetime.now()
            threshold = 60  # 渗压站默认阈值 60 分钟
            offline_status = "OFFLINE" if (latest + timezone(timedelta(minutes=threshold))) < now else "ONLINE"
            offline_hours = (now - latest).total_seconds() / 3600
            severity = classify_offline_duration(offline_hours) if offline_status == "OFFLINE" else "ONLINE"
            results.append({"st_id": st_id, "status": offline_status, "severity": severity, "latest": str(latest)})
        else:
            results.append({"st_id": st_id, "status": "NO_DATA", "severity": "INFO", "latest": None})

        step_time = time.time() - step_start
        print(f"{results[-1]['status']} ({step_time:.3f}s)")

    total_time = time.time() - start_time

    print(f"\n旧方案完成:")
    print(f"  - 工具调用次数: {len(station_ids)} 次")
    print(f"  - SQL 查询耗时: {total_time:.3f} 秒")
    print(f"  - 平均每站: {total_time/len(station_ids):.3f} 秒")
    print(f"  - 估算 token 数: {len(station_ids) * 200} tokens（每站 ~200 tokens）")

    return total_time, results


def simulate_new_approach(engine):
    """新方案：调用 classify_offline_by_duration.py（批量查询）"""
    print(f"\n{'='*80}")
    print(f"新方案：批量查询 classify_offline_by_duration.py")
    print(f"{'='*80}\n")

    start_time = time.time()

    sql = """
    SELECT
        e.id,
        e.name,
        e.code,
        e.type_flag,
        r.total_offline_duration,
        r.offline_start_date,
        r.offline_start_time,
        b.business_table,
        b.offline_threshold
    FROM eq_equip_base e
    LEFT JOIN eq_equip_offline_record r ON e.id = r.equipment_code
    LEFT JOIN eq_business_equip_relation b ON e.id = b.eq_id
    WHERE e.status = 0
      AND e.deleted = 0
    ORDER BY r.total_offline_duration DESC
    """

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        devices = [dict(row._mapping) for row in result]

    # 格式化输出
    output_lines = [f"## 离线设备分级分析结果\n"]
    output_lines.append(f"**离线设备总数**: {len(devices)}\n")

    by_severity = {}
    for d in devices:
        if d['total_offline_duration'] is None:
            sev = 'INFO'
            hours = 0.0
        else:
            hours = d['total_offline_duration'] / 3600.0
            sev = classify_offline_duration(hours)
        by_severity.setdefault(sev, []).append(d)

    for sev in ['CRITICAL', 'ERROR', 'WARNING', 'INFO']:
        count = len(by_severity.get(sev, []))
        if count > 0:
            output_lines.append(f"- **{sev}**: {count} 台")

    output_lines.append(f"\n| 严重级别 | 设备名称 | 设备编码 | 离线时长(h) |")
    output_lines.append(f"|---------|---------|---------|-----------|")

    for d in devices:
        if d['total_offline_duration'] is None:
            sev, hours = 'INFO', 0.0
        else:
            hours = d['total_offline_duration'] / 3600.0
            sev = classify_offline_duration(hours)
        output_lines.append(f"| {sev} | {d['name']} | {d['code']} | {hours:.1f}h |")

    output = "\n".join(output_lines)
    total_time = time.time() - start_time

    print(f"新方案完成:")
    print(f"  - 工具调用次数: 1 次")
    print(f"  - SQL 查询耗时: {total_time:.3f} 秒")
    print(f"  - 处理设备数: {len(devices)} 台")
    print(f"  - 输出行数: {len(output_lines)} 行")
    print(f"  - 估算 token 数: {len(output)} tokens（约 {len(output)//4} tokens）")

    return total_time, len(devices)


def main():
    import argparse
    from datetime import timedelta, timezone

    parser = argparse.ArgumentParser(description="端到端性能基准测试")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--stations", type=int, default=5, help="模拟设备数（旧方案）")
    args = parser.parse_args()

    engine = create_engine(args.db)

    print(f"\n{'#'*80}")
    print(f"# 端到端性能基准测试")
    print(f"# 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*80}\n")

    # 获取离线设备 ID 列表（用于旧方案）
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT id FROM eq_equip_base WHERE status = 0 AND deleted = 0 LIMIT :limit"
        ), {"limit": args.stations})
        station_ids = [row[0] for row in result]

    print(f"测试设备: {len(station_ids)} 台（ID: {station_ids}）")

    # 运行两种方案
    old_time, old_results = simulate_old_approach(engine, station_ids)
    new_time, new_count = simulate_new_approach(engine)

    # 对比总结
    print(f"\n{'='*80}")
    print(f"性能对比总结")
    print(f"{'='*80}\n")

    print(f"| 指标 | 旧方案（{args.stations} 台） | 新方案（全部） | 提升 |")
    print(f"|------|---------------------|---------------|------|")
    print(f"| 工具调用次数 | {args.stations} 次 | 1 次 | {100*(args.stations-1)/args.stations:.0f}% ↓ |")
    print(f"| SQL 查询耗时 | {old_time:.3f} 秒 | {new_time:.3f} 秒 | {old_time/new_time:.1f}× |")
    print(f"| 处理设备数 | {args.stations} 台 | {new_count} 台 | {new_count/args.stations:.1f}× |")
    print(f"| 输出 token 数 | ~{args.stations*200} | ~{new_count*20} | {args.stations*200//(new_count*20 or 1)}× |")

    print(f"\n总加速比: {old_time/new_time:.1f}×")
    print(f"总调用次数减少: {args.stations} → 1 ({100*(args.stations-1)/args.stations:.0f}%)")

    print(f"\n{'='*80}")
    print(f"✅ 基准测试完成")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
