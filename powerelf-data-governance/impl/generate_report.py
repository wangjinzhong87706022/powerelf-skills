#!/usr/bin/env python3
"""
数据质量报告生成工具 — CLI 入口

用法:
    python3 impl/generate_report.py --date 2026-05-15
    python3 impl/generate_report.py --date 2026-05-15 --format json
    python3 impl/generate_report.py --date 2026-05-15 --format pdf --output /tmp/report.pdf

环境变量: POWERELF_DB_HOST, POWERELF_DB_PORT, POWERELF_DB_NAME, POWERELF_DB_USER, POWERELF_DB_PASSWORD
         或 SRM_DB_HOST, SRM_DB_PORT, SRM_DB_NAME, SRM_DB_USER, SRM_DB_PASSWORD (后备)
"""

import argparse
import sys
import os

# 确保能找到 lib/ 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))


def main():
    parser = argparse.ArgumentParser(description='数据质量报告生成工具')
    parser.add_argument('--date', '-d', type=str, default=None,
                        help='日期 (YYYY-MM-DD)，默认昨天')
    parser.add_argument('--format', '-f', type=str, default='markdown',
                        choices=['markdown', 'json', 'html', 'pdf'],
                        help='输出格式 (默认 markdown)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='输出文件路径 (默认 stdout)')
    parser.add_argument('--type', '-t', type=str, default='daily',
                        choices=['daily', 'anomaly', 'score'],
                        help='报告类型 (默认 daily)')

    args = parser.parse_args()

    # 默认日期 = 昨天
    if args.date is None:
        from datetime import datetime, timedelta
        args.date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    from report import generate_daily_report_from_db, generate_anomaly_report_from_db

    if args.type == 'daily':
        md = generate_daily_report_from_db(args.date)
    elif args.type == 'anomaly':
        md = generate_anomaly_report_from_db(args.date)
    else:
        print(f"错误: 暂不支持 {args.type} 类型的自动生成", file=sys.stderr)
        sys.exit(1)

    title_map = {'daily': '数据质量日报', 'anomaly': '数据异常分析报告', 'score': '设备质量评分报告'}

    if args.format == 'markdown':
        output = md
    elif args.format == 'json':
        from report import to_json
        output = to_json(md)
    elif args.format == 'html':
        from report import to_html
        output = to_html(md)
    elif args.format == 'pdf':
        from report import to_pdf
        output = to_pdf(md, title=f'{title_map.get(args.type, "数据质量报告")}-{args.date}',
                        output_path=args.output)
        if args.output:
            print(f"PDF 已保存到: {args.output}")
            return
        output = output.decode('latin-1') if isinstance(output, bytes) else output
    else:
        output = md

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"报告已保存到: {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
