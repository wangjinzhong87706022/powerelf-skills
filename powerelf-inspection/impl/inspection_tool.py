#!/usr/bin/env python3
"""
巡检结果分析工具（inspection_tool）
职责：分析巡检任务结果数据，输出质量评分、缺陷趋势、路线效率。

模式：
  quality  — 巡检质量评分（分段制）
  defects  — 缺陷趋势预测（线性回归）
  routes   — 路线效率分析（遗漏率/超时率）
  full     — 综合报告
  registry — 数据源注册表查看
  collect  — 数据采集演示

用法:
  python inspection_tool.py --mode quality --db "$DB_URL"
  python inspection_tool.py --mode full --db "..." --start 2026-01-01 --end 2026-12-31
  python inspection_tool.py --mode registry --db "..."
  python inspection_tool.py --mode collect --db "..." --route-id 1

注意：传感器数据巡检分析（水情/雨量/渗压/位移/闸门/泵站/水质/墒情/白蚁）由 inspection_analyzer.py 负责。
"""

import argparse
import json
import logging
import re
import sys as _sys
import os as _os
from datetime import datetime

logger = logging.getLogger("inspection_tool")

# 导入 lib/quality（P2-T5 接线）
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib"))
import quality as _quality

# 标识符白名单（防 SQL 注入：table/fields/time_field 来自 sys_data_source_registry，DB 可写）
_ALLOWED_TABLES = {
    "st_river_r","st_rsvr_r","st_pressure_r","st_percolation_r","st_pptn_r",
    "rei_gate_r","rei_pump_r","eq_equip_base","eq_equip_defect","ew_camera_info",
    "srm_gnss_data_day","srm_robot_data_day","srm_illegal_acts",
}
_ALLOWED_TIME_FIELDS = {"tm", "create_time", "discovery_time", None}

def _validate_identifiers(table, fields, time_field):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table}")
    if time_field is not None and time_field not in _ALLOWED_TIME_FIELDS:
        raise ValueError(f"非法时间列: {time_field}")
    # fields 仅允许 [A-Za-z0-9_,]
    if not re.fullmatch(r"[A-Za-z0-9_]+(,[A-Za-z0-9_]+)*", fields or ""):
        raise ValueError(f"非法字段列表: {fields}")

try:
    import pandas as pd
    import numpy as np
    from sqlalchemy import create_engine, text
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


# ============================================================
# 0. 数据源注册表
# ============================================================

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


# ============================================================
# 1. 巡检质量评分
# ============================================================

def calc_inspection_quality(engine, start_date, end_date):
    """计算巡检质量评分（与 quality-assessment.md 分段评分模型一致）"""
    tasks = pd.read_sql(text("""
        SELECT id, name, status, plan_checknum, real_checknum,
               plan_checkobj, real_checkobj, bad_num, check_percent,
               plan_time, begin_time, end_time, exceed_time
        FROM business_check_task
        WHERE create_time BETWEEN :start AND :end
          AND deleted = 0
    """), engine, params={"start": start_date, "end": end_date})

    if tasks.empty:
        return {"score": 0, "detail": "无巡检数据"}

    total = len(tasks)
    completed = len(tasks[tasks['status'] == '3'])
    overtime = len(tasks[tasks['exceed_time'] == '1'])

    completion_rate = completed / total if total > 0 else 0
    timeliness_rate = 1 - (overtime / total) if total > 0 else 0

    # 缺陷率使用 real_checkobj 作为分母（C2 修复）
    total_defects = tasks['bad_num'].sum()
    real_items = tasks['real_checkobj'].sum() if 'real_checkobj' in tasks.columns else 0
    defect_rate = _quality.compute_defect_discovery_rate(int(total_defects), int(real_items))

    def parse_percent(p):
        try:
            return float(str(p).replace('%', '')) / 100
        except (ValueError, AttributeError):
            return 0

    avg_omission = tasks['check_percent'].apply(parse_percent).mean()
    coverage_rate = 1 - avg_omission

    # 调用 lib/quality 统一评分（D4 删除内联副本）
    qs = _quality.compute_quality_score(completion_rate, timeliness_rate, defect_rate, coverage_rate)
    score_completion = qs["dimension_scores"]["completion"]["score"]
    score_timeliness = qs["dimension_scores"]["timeliness"]["score"]
    score_defect = qs["dimension_scores"]["defect_rate"]["score"]
    score_coverage = qs["dimension_scores"]["coverage"]["score"]
    score = qs["total_score"]

    return {
        "score": round(score, 1),
        "grade": "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "E",
        "score_breakdown": {
            "completion": score_completion,
            "timeliness": score_timeliness,
            "defect": score_defect,
            "coverage": score_coverage
        },
        "completion_rate": f"{completion_rate:.1%}",
        "timeliness_rate": f"{timeliness_rate:.1%}",
        "defect_rate": f"{defect_rate:.1%}",
        "coverage_rate": f"{coverage_rate:.1%}",
        "total_tasks": total,
        "completed_tasks": completed,
        "overtime_tasks": overtime,
        "total_defects": int(total_defects)
    }


# ============================================================
# 2. 缺陷趋势预测
# ============================================================

def predict_defect_trend(engine, months=6):
    """基于历史数据预测缺陷趋势"""
    try:
        from sklearn.linear_model import LinearRegression
    except ImportError:
        return {"error": "需要安装 scikit-learn: pip install scikit-learn"}

    df = pd.read_sql("""
        SELECT DATE_FORMAT(create_time, '%%Y-%%m') AS month,
               COUNT(*) AS defect_count
        FROM business_check_error
        WHERE deleted = 0
        GROUP BY DATE_FORMAT(create_time, '%%Y-%%m')
        ORDER BY month
    """, engine)

    if len(df) < 3:
        return {"prediction": "数据不足，至少需要3个月数据"}

    X = np.arange(len(df)).reshape(-1, 1)
    y = df['defect_count'].values

    model = LinearRegression()
    model.fit(X, y)

    future_X = np.arange(len(df), len(df) + months).reshape(-1, 1)
    predictions = model.predict(future_X)
    predictions = np.maximum(predictions, 0)

    slope = model.coef_[0]
    trend = "上升" if slope > 0.5 else "下降" if slope < -0.5 else "平稳"

    return {
        "historical": df.to_dict('records'),
        "trend": trend,
        "slope": round(slope, 2),
        "predictions": [
            {"month": f"未来第{i+1}月", "predicted_defects": round(max(0, float(p)))}
            for i, p in enumerate(predictions)
        ]
    }


# ============================================================
# 3. 路线优化分析
# ============================================================

def analyze_route_efficiency(engine):
    """分析巡检路线效率"""
    tasks = pd.read_sql("""
        SELECT t.id, t.name, t.route_id, t.check_percent, t.exceed_time,
               t.plan_checknum, t.real_checknum, t.bad_num,
               r.name AS route_name, r.max_time
        FROM business_check_task t
        LEFT JOIN business_check_route r ON t.route_id = r.id
        WHERE t.deleted = 0 AND t.status = '3'
    """, engine)

    if tasks.empty:
        return {"suggestion": "无已完成的巡检任务数据"}

    def parse_percent(p):
        try:
            return float(str(p).replace('%', '')) / 100
        except:
            return 0

    tasks['omission_rate'] = tasks['check_percent'].apply(parse_percent)

    route_stats = tasks.groupby(['route_id', 'route_name']).agg({
        'omission_rate': 'mean',
        'exceed_time': lambda x: (x == '1').sum(),
        'bad_num': 'sum',
        'id': 'count'
    }).rename(columns={'id': 'task_count', 'exceed_time': 'overtime_count'}).reset_index()

    suggestions = []
    for _, stats in route_stats.iterrows():
        issues = []
        if stats['omission_rate'] > 0.2:
            issues.append(f"遗漏率过高({stats['omission_rate']:.1%})")
        if stats['overtime_count'] > stats['task_count'] * 0.3:
            issues.append(f"频繁超时({int(stats['overtime_count'])}/{int(stats['task_count'])})")

        if issues:
            suggestions.append({
                "route_id": int(stats['route_id']),
                "route_name": stats['route_name'],
                "issues": issues,
                "suggestion": "建议拆分路线或增加巡检时间" if stats['omission_rate'] > 0.2 else "建议延长计划时间"
            })

    return {
        "route_stats": route_stats.to_dict('records'),
        "suggestions": suggestions
    }


# ============================================================
# 4. 注册表查询与数据采集
# ============================================================

def show_registry(engine):
    """展示数据源注册表内容"""
    registry = load_registry(engine)
    if registry.empty:
        print("注册表为空，使用内置默认数据源")
        registry = get_builtin_registry()

    print(f"\n数据源注册表 (共 {len(registry)} 条):\n")
    print(f"{'序号':<4} {'名称':<12} {'数据表':<25} {'关键词':<40} {'测站类型':<8} {'距离m':<8}")
    print("-" * 120)
    for i, row in registry.iterrows():
        st = str(row.get('station_type', '')) if pd.notna(row.get('station_type')) else '-'
        dist = str(int(row['max_distance'])) if pd.notna(row.get('max_distance')) else '-'
        kw = str(row['keywords'])[:38]
        print(f"{i+1:<4} {row['name']:<12} {row['source_table']:<25} {kw:<40} {st:<8} {dist:<8}")

    print(f"\n扩展方式: INSERT INTO sys_data_source_registry ... (详见 docs/18-数据源动态注册机制.md)")


def demo_collect(engine, route_id):
    """演示基于注册表的数据采集"""
    registry = load_registry(engine)
    if registry.empty:
        registry = get_builtin_registry()

    print(f"\n=== 巡检路线 {route_id} 数据采集演示 ===\n")

    try:
        route = pd.read_sql(
            "SELECT * FROM business_check_route WHERE id=:id", engine,
            params={"id": route_id}
        )
    except Exception as e:
        print(f"查询路线失败: {e}")
        return

    if route.empty:
        print(f"路线 {route_id} 不存在")
        return

    route = route.iloc[0]
    print(f"路线: {route['name']}")
    point_ids = str(route['select_id']).rstrip(',').split(',')
    print(f"巡检点: {point_ids}\n")

    for point_id in point_ids:
        try:
            point = pd.read_sql(
                "SELECT * FROM business_check_point WHERE id=:id", engine,
                params={"id": int(point_id)}
            )
        except:
            continue
        if point.empty:
            continue
        point = point.iloc[0]
        print(f"  巡检点 [{point_id}] {point['point_name']}")

        # 遍历检查项
        try:
            items = pd.read_sql("""
                SELECT i.id, i.required, o.obj_name
                FROM business_check_obj_type_item i
                JOIN business_check_obj_type t ON i.check_obj_type_id = t.id
                JOIN business_check_obj o ON o.type_id = t.id
                WHERE o.point_id = :pid AND i.deleted = 0
            """, engine, params={"pid": int(point_id)})
        except:
            continue

        for _, item in items.iterrows():
            required = str(item['required'])
            matched = match_data_sources(required, registry)
            if matched:
                sources = ", ".join([s['name'] for s in matched])
                print(f"    检查项: {required[:40]}... → 采集: {sources}")
            else:
                print(f"    检查项: {required[:40]}... → 无匹配数据源(需人工)")
        print()


# ============================================================
# 5. 完整报告
# ============================================================

def generate_report(engine, start_date, end_date):
    """生成完整巡检分析报告"""
    quality = calc_inspection_quality(engine, start_date, end_date)
    defects = predict_defect_trend(engine)
    routes = analyze_route_efficiency(engine)

    breakdown = quality.get('score_breakdown', {})
    report = f"""
# 巡检分析报告 ({start_date} ~ {end_date})

## 一、质量评分: {quality['score']}/100 ({quality.get('grade', 'N/A')})

| 指标 | 数值 | 得分 |
|------|------|------|
| 完成率 | {quality['completion_rate']} | {breakdown.get('completion', 'N/A')}/30 |
| 及时率 | {quality['timeliness_rate']} | {breakdown.get('timeliness', 'N/A')}/25 |
| 缺陷发现率 | {quality['defect_rate']} | {breakdown.get('defect', 'N/A')}/25 |
| 路线覆盖率 | {quality['coverage_rate']} | {breakdown.get('coverage', 'N/A')}/20 |
| 总任务数 | {quality['total_tasks']} | — |
| 总缺陷数 | {quality['total_defects']} | — |

## 二、缺陷趋势

- 趋势方向: {defects.get('trend', 'N/A')}
- 月均变化: {defects.get('slope', 'N/A')} 个/月

## 三、路线优化建议
"""
    for s in routes.get('suggestions', []):
        report += f"- **{s.get('route_name', s['route_id'])}**: {', '.join(s['issues'])} → {s['suggestion']}\n"

    if not routes.get('suggestions'):
        report += "- 所有路线运行正常，无需调整\n"

    return report


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="巡检智能分析工具")
    parser.add_argument("--mode",
                        choices=["quality", "defects", "routes", "full",
                                 "registry", "collect"],
                        default="full", help="分析模式")
    parser.add_argument("--db", help="数据库连接 (mysql+pymysql://user:pass@host:3306/powerelf)")
    parser.add_argument("--start", default="2026-01-01", help="开始日期")
    parser.add_argument("--end", default="2026-12-31", help="结束日期")
    parser.add_argument("--route-id", type=int, help="巡检路线ID(collect模式用)")
    parser.add_argument("--output", help="输出JSON文件路径")

    args = parser.parse_args()

    # 所有模式需要数据库连接
    if not args.db:
        print("错误: 需要 --db 参数指定数据库连接")
        sys.exit(1)

    if not HAS_DEPS:
        print("错误: 需要安装依赖: pip install pandas numpy sqlalchemy pymysql scikit-learn")
        sys.exit(1)

    engine = create_engine(args.db)

    if args.mode == "registry":
        show_registry(engine)
    elif args.mode == "collect":
        if not args.route_id:
            print("错误: collect 模式需要 --route-id 参数")
            sys.exit(1)
        demo_collect(engine, args.route_id)
    elif args.mode == "quality":
        result = calc_inspection_quality(engine, args.start, args.end)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.mode == "defects":
        result = predict_defect_trend(engine)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.mode == "routes":
        result = analyze_route_efficiency(engine)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        report = generate_report(engine, args.start, args.end)
        print(report)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n报告已保存到: {args.output}")
        return

    if args.output and args.mode not in ("registry", "collect"):
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
