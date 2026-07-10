"""
数据治理报告生成模块 — 支持 Markdown / JSON / HTML / PDF 格式

功能:
- 数据质量日报
- 异常分析报告
- 设备评分报告
- 趋势分析报告

输出格式:
- markdown: 终端/消息推送
- json: API 返回
- html: 网页展示
- pdf: 存档/打印
"""

import json
import os
from datetime import datetime, date
from io import BytesIO


# ====== 报告模板 ======

DAILY_REPORT_TEMPLATE = """# 数据质量日报 — {date}

## 一、概览

| 指标 | 数值 |
|------|------|
| 监测设备总数 | {device_count} 台 |
| 在线设备 | {online_count} 台 |
| 离线设备 | {offline_count} 台 |
| 异常设备 | {anomaly_count} 台 |
| 综合采集率 | {collection_rate} |
| 综合质量评分 | {total_score} 分 ({grade}) |

## 二、分表采集率

| 数据表 | 期望(条) | 实际(条) | 采集率 |
|--------|----------|----------|--------|
{collection_rate_detail}

## 三、数据采集情况

| 数据表 | 采集条数 | 缺失条数 | 异常条数 |
|--------|----------|----------|----------|
{collection_table}

## 四、异常发现

{anomaly_section}

## 五、离线设备

{offline_section}

## 六、评分详情

| 维度 | 权重 | 得分 |
|------|------|------|
| 数据质量 | 35% | {quality_score} |
| 运行稳定性 | 10% | {stability_score} |
| 故障频率 | 40% | {fault_score} |
| 数据完整性 | 15% | {completeness_score} |
| **总分** | | **{total_score}** |

## 七、处理建议

{suggestions}

---
*报告生成时间: {generated_at}*
*分析时间窗口: {start_time} ~ {end_time}*
"""

ANOMALY_REPORT_TEMPLATE = """# 数据异常分析报告 — {date}

## 一、异常概览

| 指标 | 数值 |
|------|------|
| 异常记录总数 | {total_anomalies} |
| 已修复 | {fixed_count} |
| 未修复 | {unfixed_count} |
| 修复率 | {fix_rate}% |

## 二、异常明细

{anomaly_table}

## 三、异常分布

### 按设备
{by_device}

### 按数据表
{by_table}

### 按时间
{by_time}

## 四、处理建议

{suggestions}

---
*报告生成时间: {generated_at}*
"""

SCORE_REPORT_TEMPLATE = """# 设备质量评分报告 — {date}

## 一、评分概览

| 指标 | 数值 |
|------|------|
| 评估设备数 | {device_count} |
| 平均分 | {avg_score} |
| 最高分 | {max_score} |
| 最低分 | {min_score} |
| 优秀(≥90) | {grade_a} 台 |
| 良好(80-89) | {grade_b} 台 |
| 一般(70-79) | {grade_c} 台 |
| 较差(60-69) | {grade_d} 台 |
| 严重不足(<60) | {grade_e} 台 |

## 二、设备评分排名

{ranking_table}

## 三、评分趋势

{trend_section}

## 四、改进建议

{suggestions}

---
*报告生成时间: {generated_at}*
"""


def _render_template(template, data):
    """渲染模板"""
    try:
        return template.format(**data)
    except KeyError as e:
        return f"模板渲染错误: 缺少字段 {e}"


def _anomaly_to_table(anomalies):
    """异常记录转表格"""
    if not anomalies:
        return "无异常记录\n"
    lines = ["| 设备 | 数据表 | 异常时间 | 是否已修复 |", "|------|--------|----------|-----------|"]
    for a in anomalies:
        status = "[已修复]" if a.get('whether_fix') == 1 else "[未修复]"
        lines.append(f"| {a.get('equipment_code', 'N/A')} | {a.get('table_name', 'N/A')} | {a.get('data_anomaly_datetime', 'N/A')} | {status} |")
    return '\n'.join(lines)


def _offline_to_table(records):
    """离线记录转表格"""
    if not records:
        return "无离线设备\n"
    lines = ["| 设备 | 离线开始 | 离线结束 | 离线时长 |", "|------|----------|----------|----------|"]
    for r in records:
        hours = r.get('total_offline_duration', 0) / 3600
        end = r.get('offline_end_time', '仍在离线')
        lines.append(f"| {r.get('equipment_code', 'N/A')} | {r.get('offline_start_time', 'N/A')} | {end} | {hours:.1f}h |")
    return '\n'.join(lines)


def _score_to_ranking(scores):
    """评分转排名表"""
    if not scores:
        return "无评分数据\n"
    lines = ["| 排名 | 设备 | 评分 | 等级 |", "|------|------|------|------|"]
    sorted_scores = sorted(scores, key=lambda x: x.get('score', 0), reverse=True)
    for i, s in enumerate(sorted_scores, 1):
        score = s.get('score', 0)
        if score >= 90: grade = 'A-优秀'
        elif score >= 80: grade = 'B-良好'
        elif score >= 60: grade = 'C-一般'
        else: grade = 'D-较差'
        lines.append(f"| {i} | {s.get('device_name', s.get('device_id', 'N/A'))} | {score:.1f} | {grade} |")
    return '\n'.join(lines)


# ====== 报告生成函数 ======

def generate_daily_report(date_str, overview, collection_data, anomalies, offline_records, score_result, suggestions=None):
    """生成数据质量日报

    Args:
        date_str: 日期字符串 (YYYY-MM-DD)
        overview: dict {device_count, online_count, offline_count, anomaly_count, collection_rate}
        collection_data: list of dict {table_name, collected, missing, anomaly}
        anomalies: list of dict {equipment_code, table_name, data_anomaly_datetime, whether_fix}
        offline_records: list of dict {equipment_code, offline_start_time, offline_end_time, total_offline_duration}
        score_result: dict {total, quality, stability, fault, completeness}
        suggestions: list of str (处理建议)

    Returns:
        str: Markdown 格式日报
    """
    collection_table = ""
    for c in collection_data:
        collection_table += f"| {c.get('table_name', '')} | {c.get('collected', 0)} | {c.get('missing', 0)} | {c.get('anomaly', 0)} |\n"
    if not collection_table:
        collection_table = "| - | - | - | - |\n"

    # 分表采集率明细
    collection_rate_detail = ""
    coll_details = overview.get('collection_details', [])
    if coll_details:
        for d in coll_details:
            rate_str = f"{d['rate']:.1f}%" if isinstance(d.get('rate'), (int, float)) else str(d.get('rate', '-'))
            collection_rate_detail += f"| {d['table']} | {d['expected']} | {d['actual']} | {rate_str} |\n"
    else:
        # 向后兼容：没有明细时显示总采集率
        total_rate = overview.get('collection_rate', '-')
        collection_rate_detail = f"| - | - | - | {total_rate} |\n"

    anomaly_section = _anomaly_to_table(anomalies) if anomalies else "今日无异常发现\n"
    offline_section = _offline_to_table(offline_records) if offline_records else "所有设备在线\n"

    total_score = float(score_result.get('total', 0))
    if total_score >= 90: grade = 'A-优秀'
    elif total_score >= 80: grade = 'B-良好'
    elif total_score >= 60: grade = 'C-一般'
    else: grade = 'D-较差'

    # 综合采集率字符串
    coll_rate_str = overview.get('collection_rate', '-')
    if isinstance(coll_rate_str, (int, float)):
        coll_rate_str = f"{coll_rate_str:.1f}%"

    if suggestions is None:
        suggestions = []
        if overview.get('offline_count', 0) > 0:
            suggestions.append(f"- {overview['offline_count']} 台设备离线，建议检查通信和电源")
        if overview.get('anomaly_count', 0) > 0:
            suggestions.append(f"- 发现 {overview['anomaly_count']} 台设备数据异常，建议现场核查")
        if total_score < 60:
            suggestions.append("- 综合评分低于60分，需要全面排查设备状态")
        if not suggestions:
            suggestions.append("- 数据质量良好，无需特别处理")

    data = {
        'date': date_str,
        'device_count': overview.get('device_count', 0),
        'online_count': overview.get('online_count', 0),
        'offline_count': overview.get('offline_count', 0),
        'anomaly_count': overview.get('anomaly_count', 0),
        'collection_rate': coll_rate_str,
        'collection_rate_detail': collection_rate_detail,
        # collection_data_number 按"时间槽覆盖"统计,非总行数;见 actual_schema.md
        'total_score': f"{total_score:.1f}",
        'grade': grade,
        'collection_table': collection_table,
        'anomaly_section': anomaly_section,
        'offline_section': offline_section,
        'quality_score': f"{float(score_result.get('quality', 0)):.1f}",
        'stability_score': f"{float(score_result.get('stability', 0)):.1f}",
        'fault_score': f"{float(score_result.get('fault', 0)):.1f}",
        'completeness_score': f"{float(score_result.get('completeness', 0)):.1f}",
        'suggestions': '\n'.join(suggestions),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'start_time': f"{date_str} 00:00:00",
        'end_time': f"{date_str} 23:59:59",
    }
    return _render_template(DAILY_REPORT_TEMPLATE, data)


def generate_daily_report_from_db(date_str, conn=None, suggestions=None):
    """从数据库自动查询数据并生成数据质量日报

    自动查询 stats_data_collection_daily、stats_data_missing_daily、
    stats_data_anomaly_daily、eq_data_anomaly_record、eq_equip_offline_record、
    eq_equip_base 等表，计算采集率和评分，生成完整日报。

    Args:
        date_str: 日期字符串 (YYYY-MM-DD)
        conn: 数据库连接（可选，None 时自动创建并关闭）
        suggestions: 自定义建议列表（可选）

    Returns:
        str: Markdown 格式日报
    """
    from db import get_connection

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        cur = conn.cursor()

        # ── 1. 设备概况 ──
        cur.execute('SELECT status, COUNT(*) AS cnt FROM eq_equip_base GROUP BY status')
        status_counts = {r['status']: r['cnt'] for r in cur.fetchall()}
        device_count = sum(status_counts.values())
        online = status_counts.get(1, 0)
        offline = status_counts.get(0, 0)
        anomaly_count = status_counts.get(2, 0)

        # ── 2. 各表采集率 ──
        # 表名 -> 采集频率(min)
        monitor_tables = {
            'st_rsvr_r': 60,
            'st_pressure_r': 60,
            'st_pptn_r': 60,
            'st_river_r': 60,
            'st_percolation_r': 60,
            'dsm_dfr_srvrds_srhrds': 60,
            'rei_gate_r': 60,
            'rei_pump_r': 60,
        }

        # ── 批量查询优化:32次串行→4次 ──────────────────────────────
        # ① 所有表的测站数 一次UNION ALL查
        union_parts = '\n    UNION ALL '.join(
            f"SELECT '{tbl}' AS tbl, COUNT(DISTINCT st_id) AS cnt FROM {tbl}"
            for tbl in monitor_tables
        )
        cur.execute(f"""
            {union_parts}
        """)
        station_counts = {r['tbl']: r['cnt'] for r in cur.fetchall()}

        # ② ③ ④ 三张统计表 用 IN 子句一次查所有表
        tbl_list = list(monitor_tables.keys())
        in_clause = ', '.join(['%s'] * len(tbl_list))

        cur.execute(
            f"SELECT table_name, collection_data_number"
            f"  FROM stats_data_collection_daily"
            f"  WHERE tm = %s AND table_name IN ({in_clause})",
            [date_str] + tbl_list
        )
        collection_map = {r['table_name']: r['collection_data_number'] for r in cur.fetchall()}

        cur.execute(
            f"SELECT table_name, missing_data_number"
            f"  FROM stats_data_missing_daily"
            f"  WHERE tm = %s AND table_name IN ({in_clause})",
            [date_str] + tbl_list
        )
        missing_map = {r['table_name']: r['missing_data_number'] for r in cur.fetchall()}

        cur.execute(
            f"SELECT table_name, anomaly_data_number"
            f"  FROM stats_data_anomaly_daily"
            f"  WHERE tm = %s AND table_name IN ({in_clause})",
            [date_str] + tbl_list
        )
        anomaly_map = {r['table_name']: r['anomaly_data_number'] for r in cur.fetchall()}

        # ── 内存中组装结果 ──────────────────────────────────────
        coll_details = []
        collection_data = []
        total_actual = 0
        total_expected = 0

        for tbl, freq in monitor_tables.items():
            stations = station_counts.get(tbl, 0)
            if stations == 0:
                continue
            expected = stations * (24 * 60 // freq)
            actual = collection_map.get(tbl, 0)
            missing = missing_map.get(tbl, 0)
            anomaly = anomaly_map.get(tbl, 0)
            rate = round(actual / expected * 100, 1) if expected > 0 else 0
            coll_details.append({
                'table': tbl, 'expected': expected,
                'actual': actual, 'rate': rate,
            })
            collection_data.append({
                'table_name': tbl, 'collected': actual,
                'missing': missing, 'anomaly': anomaly,
            })
            total_actual += actual
            total_expected += expected

        overall_rate = round(total_actual / total_expected * 100, 1) if total_expected > 0 else 0

        # ── 3. 异常记录 ──
        cur.execute(
            'SELECT equipment_code, table_name, data_anomaly_datetime, whether_fix '
            'FROM eq_data_anomaly_record WHERE DATE(data_anomaly_datetime) = %s',
            (date_str,)
        )
        anomalies = [dict(r) for r in cur.fetchall()]

        # ── 4. 离线记录（当日活跃的） ──
        cur.execute(
            'SELECT equipment_code, offline_start_time, offline_end_time, total_offline_duration '
            'FROM eq_equip_offline_record '
            'WHERE DATE(offline_start_time) <= %s '
            'AND (offline_end_time IS NULL OR DATE(offline_end_time) >= %s) '
            'LIMIT 20',
            (date_str, date_str)
        )
        offline_records = [dict(r) for r in cur.fetchall()]

        # ── 5. 评分计算 ──
        collection_ratio = min(total_actual / max(total_expected, 1), 1.0)
        quality = round(35 * collection_ratio, 1)
        stability = round(max(0, 10 * (1 - len(offline_records) / max(device_count, 1))), 1)
        fault = round(max(0, 40 - min(
            len(offline_records) * 2 + len(anomalies) * 5, 40
        )), 1)
        completeness = round(15 * collection_ratio, 1)
        total_score = round(quality + stability + fault + completeness, 1)

        score_result = {
            'total': total_score, 'quality': quality,
            'stability': stability, 'fault': fault,
            'completeness': completeness,
        }

        # ── 6. 组装 overview ──
        overview = {
            'device_count': device_count,
            'online_count': online,
            'offline_count': offline,
            'anomaly_count': anomaly_count,
            'collection_rate': overall_rate,
            'collection_details': coll_details,
        }

        # ── 7. 生成报告 ──
        if suggestions is None:
            suggestions = []
            if offline > 0:
                suggestions.append(f"- {offline} 台设备离线，建议检查通信链路和供电情况")
            if anomaly_count > 0:
                suggestions.append(f"- 发现 {anomaly_count} 台设备数据异常，建议现场核查")
            if overall_rate < 50:
                suggestions.append(f"- 综合采集率仅 {overall_rate}%，需排查通信链路")
            if total_score < 60:
                suggestions.append("- 综合评分低于60分，需要全面排查设备状态")
            if not suggestions:
                suggestions.append("- 数据质量良好，无需特别处理")

        return generate_daily_report(
            date_str, overview, collection_data,
            anomalies, offline_records, score_result, suggestions
        )

    finally:
        if own_conn:
            conn.close()


def generate_anomaly_report(date_str, anomalies, suggestions=None):
    """生成异常分析报告"""
    total = len(anomalies)
    fixed = sum(1 for a in anomalies if a.get('whether_fix') == 1)
    unfixed = total - fixed
    fix_rate = (fixed / total * 100) if total > 0 else 0

    anomaly_table = _anomaly_to_table(anomalies)

    # 按设备分组
    by_device = {}
    for a in anomalies:
        eq = a.get('equipment_code', 'N/A')
        by_device.setdefault(eq, []).append(a)
    device_lines = ["| 设备 | 异常数 | 已修复 |", "|------|--------|--------|"]
    for eq, items in by_device.items():
        device_lines.append(f"| {eq} | {len(items)} | {sum(1 for i in items if i.get('whether_fix')==1)} |")

    # 按表分组
    by_table = {}
    for a in anomalies:
        tbl = a.get('table_name', 'N/A')
        by_table.setdefault(tbl, []).append(a)
    table_lines = ["| 数据表 | 异常数 |", "|--------|--------|"]
    for tbl, items in by_table.items():
        table_lines.append(f"| {tbl} | {len(items)} |")

    data = {
        'date': date_str,
        'total_anomalies': total,
        'fixed_count': fixed,
        'unfixed_count': unfixed,
        'fix_rate': f"{fix_rate:.1f}",
        'anomaly_table': anomaly_table,
        'by_device': '\n'.join(device_lines),
        'by_table': '\n'.join(table_lines),
        'by_time': "（按时间分布图需配合可视化工具）",
        'suggestions': '\n'.join(suggestions or ["- 建议优先处理未修复的异常记录"]),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return _render_template(ANOMALY_REPORT_TEMPLATE, data)


def generate_anomaly_report_from_db(date_str, conn=None, suggestions=None):
    """从数据库自动查询异常数据并生成异常分析报告

    Args:
        date_str: 日期范围 (YYYY-MM-DD 或 YYYY-MM)
        conn: 数据库连接（可选）
        suggestions: 自定义建议列表（可选）

    Returns:
        str: Markdown 格式异常分析报告
    """
    from db import get_connection
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        cur = conn.cursor()

        # 支持月度或单日查询
        if len(date_str) == 7:  # YYYY-MM
            where = 'DATE_FORMAT(data_anomaly_datetime, %s) = %s'
            params = ('%Y-%m', date_str)
        else:  # YYYY-MM-DD
            where = 'DATE(data_anomaly_datetime) = %s'
            params = (date_str,)

        cur.execute(
            f'SELECT equipment_code, table_name, data_anomaly_datetime, whether_fix, fix_data_content '
            f'FROM eq_data_anomaly_record WHERE {where}',
            params
        )
        anomalies = [dict(r) for r in cur.fetchall()]

        if suggestions is None:
            suggestions = []
            unfixed = sum(1 for a in anomalies if a.get('whether_fix') == 0)
            if unfixed > 0:
                suggestions.append(f"- 有 {unfixed} 条异常未修复，建议优先处理")
            if not anomalies:
                suggestions.append("- 该时间段内无异常记录，数据质量良好")
            else:
                suggestions.append("- 建议对异常设备进行现场核查")

        return generate_anomaly_report(date_str, anomalies, suggestions)

    finally:
        if own_conn:
            conn.close()


def generate_score_report(date_str, scores, suggestions=None):
    """生成设备评分报告"""
    if not scores:
        return "无评分数据\n"

    score_values = [s.get('score', 0) for s in scores]
    avg_score = sum(score_values) / len(score_values)

    grade_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0}
    for s in score_values:
        if s >= 90: grade_counts['A'] += 1
        elif s >= 80: grade_counts['B'] += 1
        elif s >= 70: grade_counts['C'] += 1
        elif s >= 60: grade_counts['D'] += 1
        else: grade_counts['E'] += 1

    data = {
        'date': date_str,
        'device_count': len(scores),
        'avg_score': f"{avg_score:.1f}",
        'max_score': f"{max(score_values):.1f}",
        'min_score': f"{min(score_values):.1f}",
        'grade_a': grade_counts['A'],
        'grade_b': grade_counts['B'],
        'grade_c': grade_counts['C'],
        'grade_d': grade_counts['D'],
        'grade_e': grade_counts['E'],
        'ranking_table': _score_to_ranking(scores),
        'trend_section': "（趋势分析需历史数据对比）",
        'suggestions': '\n'.join(suggestions or ["- 建议对评分低于60分的设备进行重点维护"]),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return _render_template(SCORE_REPORT_TEMPLATE, data)


# ====== 格式转换 ======

def to_json(report_md, metadata=None):
    """将 Markdown 报告转为 JSON 格式"""
    return json.dumps({
        'format': 'markdown',
        'content': report_md,
        'metadata': metadata or {},
        'generated_at': datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2)


def to_html(report_md, title="数据治理报告"):
    """将 Markdown 报告转为 HTML 格式"""
    # 简单 Markdown → HTML 转换
    html = report_md
    # 标题
    html = html.replace('# ', '<h1>').replace('\n<h1>', '\n<h1>')
    lines = html.split('\n')
    result = []
    for line in lines:
        if line.startswith('# '):
            result.append(f'<h1>{line[2:]}</h1>')
        elif line.startswith('## '):
            result.append(f'<h2>{line[3:]}</h2>')
        elif line.startswith('### '):
            result.append(f'<h3>{line[4:]}</h3>')
        elif line.startswith('---'):
            result.append('<hr>')
        elif line.startswith('| ') and '---|' not in line:
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if cells:
                row = ''.join(f'<td>{c}</td>' for c in cells)
                result.append(f'<tr>{row}</tr>')
        elif line.startswith('- '):
            result.append(f'<li>{line[2:]}</li>')
        elif line.strip() == '':
            result.append('<br>')
        else:
            result.append(f'<p>{line}</p>')

    body = '\n'.join(result)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif; margin: 40px; line-height: 1.6; }}
h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
h2 {{ color: #34495e; margin-top: 30px; }}
table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #3498db; color: white; }}
tr:nth-child(even) {{ background-color: #f2f2f2; }}
li {{ margin: 5px 0; }}
hr {{ border: 1px solid #eee; margin: 20px 0; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def to_pdf(report_md, title="数据治理报告", output_path=None):
    """将 Markdown 报告转为 PDF 格式

    Args:
        report_md: Markdown 格式报告内容
        title: 报告标题
        output_path: 输出文件路径 (可选，不指定则返回 bytes)

    Returns:
        bytes 或 str: PDF 内容(bytes) 或 文件路径(str)
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError(
            "PDF 生成需要安装 fpdf2: pip install 'fpdf2>=2.7.5,<3'"
        )

    # 查找中文字体
    font_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/arphic/uming.ttc',
        '/usr/share/fonts/truetype/arphic/ukai.ttc',
    ]
    font_path = None
    for fp in font_paths:
        if os.path.exists(fp):
            font_path = fp
            break

    if font_path is None:
        raise RuntimeError("未找到中文字体，无法生成PDF")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # 添加中文字体
    pdf.add_font('CJK', '', font_path, uni=True)
    pdf.add_font('CJK', 'B', font_path, uni=True)

    # 标题
    pdf.set_font('CJK', 'B', 16)
    pdf.cell(0, 12, title, ln=True, align='C')
    pdf.ln(5)

    # 解析 Markdown 内容
    lines = report_md.split('\n')
    in_table = False
    table_rows = []

    for line in lines:
        line = line.strip()
        if not line:
            if in_table and table_rows:
                _render_table_pdf(pdf, table_rows)
                table_rows = []
                in_table = False
            pdf.ln(3)
            continue

        # 标题
        if line.startswith('# '):
            if in_table and table_rows:
                _render_table_pdf(pdf, table_rows)
                table_rows = []
                in_table = False
            pdf.set_font('CJK', 'B', 14)
            pdf.cell(0, 10, line[2:], ln=True)
            pdf.ln(2)
        elif line.startswith('## '):
            if in_table and table_rows:
                _render_table_pdf(pdf, table_rows)
                table_rows = []
                in_table = False
            pdf.set_font('CJK', 'B', 12)
            pdf.cell(0, 8, line[3:], ln=True)
            pdf.ln(2)
        elif line.startswith('### '):
            if in_table and table_rows:
                _render_table_pdf(pdf, table_rows)
                table_rows = []
                in_table = False
            pdf.set_font('CJK', 'B', 11)
            pdf.cell(0, 7, line[4:], ln=True)
            pdf.ln(1)
        elif line.startswith('---'):
            if in_table and table_rows:
                _render_table_pdf(pdf, table_rows)
                table_rows = []
                in_table = False
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
        elif line.startswith('| '):
            in_table = True
            if '---|' not in line:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                table_rows.append(cells)
        elif line.startswith('- '):
            if in_table and table_rows:
                _render_table_pdf(pdf, table_rows)
                table_rows = []
                in_table = False
            pdf.set_font('CJK', '', 10)
            pdf.cell(5)
            pdf.cell(0, 6, f"• {line[2:]}", ln=True)
        elif line.startswith('*') and line.endswith('*'):
            if in_table and table_rows:
                _render_table_pdf(pdf, table_rows)
                table_rows = []
                in_table = False
            pdf.set_font('CJK', '', 9)
            pdf.cell(0, 5, line.strip('*'), ln=True)
        else:
            if in_table and table_rows:
                _render_table_pdf(pdf, table_rows)
                table_rows = []
                in_table = False
            pdf.set_font('CJK', '', 10)
            # 处理长文本换行
            pdf.multi_cell(0, 6, line)

    # 处理最后的表格
    if in_table and table_rows:
        _render_table_pdf(pdf, table_rows)

    if output_path:
        pdf.output(output_path)
        return output_path
    else:
        return pdf.output(dest='S').encode('latin-1')


def _render_table_pdf(pdf, rows):
    """在 PDF 中渲染表格"""
    if not rows:
        return

    # 计算列宽
    num_cols = len(rows[0])
    col_width = (190 - 10) / num_cols  # 页面宽度减去边距

    pdf.set_font('CJK', '', 9)

    for i, row in enumerate(rows):
        if i == 0:  # 表头
            pdf.set_font('CJK', 'B', 9)
            pdf.set_fill_color(52, 152, 219)
            pdf.set_text_color(255, 255, 255)
        else:
            pdf.set_font('CJK', '', 9)
            pdf.set_fill_color(245, 245, 245) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(0, 0, 0)

        for cell in row:
            # 截断过长内容
            display = cell[:20] + '...' if len(cell) > 20 else cell
            pdf.cell(col_width, 6, display, border=1, fill=True)
        pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)
