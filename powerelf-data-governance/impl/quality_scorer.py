#!/usr/bin/env python3
"""
质量评分算子（基于 lib/scoring.py）
直接调用，Agent 不需要自己写 SQL 或理解算法细节。

用法:
  python3 quality_scorer.py \
    --missing-ratio 0.05 --anomaly-ratio 0.03 \
    --offline-date-ratio 0.10 --anomaly-date-ratio 0.05 \
    --offline-count 3 --anomaly-count 2 \
    --actual-records 22 --expected-records 24

输出: JSON 格式的四维度评分结果。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.scoring import compute_equil_score, compute_score_trend


def run_scoring(
    missing_ratio, anomaly_ratio,
    offline_date_ratio, anomaly_date_ratio,
    offline_count, anomaly_count,
    actual_records, expected_records,
    previous_total=None,
):
    """执行质量评分"""
    scores = compute_equil_score(
        missing_ratio, anomaly_ratio,
        offline_date_ratio, anomaly_date_ratio,
        offline_count, anomaly_count,
        actual_records, expected_records,
    )

    result = {
        "total": scores["total"],
        "quality": scores["quality"],
        "stability": scores["stability"],
        "fault": scores["fault"],
        "completeness": scores["completeness"],
    }

    if scores["total"] >= 90:
        result["grade"] = "A-优秀"
    elif scores["total"] >= 80:
        result["grade"] = "B-良好"
    elif scores["total"] >= 60:
        result["grade"] = "C-一般"
    else:
        result["grade"] = "D-较差"

    if previous_total is not None:
        result["trend"] = compute_score_trend(scores["total"], previous_total)
        result["previous_total"] = previous_total
        result["change"] = round(scores["total"] - previous_total, 2)

    return result


def main():
    parser = argparse.ArgumentParser(description="质量评分算子")
    parser.add_argument("--missing-ratio", type=float, required=True, help="缺失率 (0-1)")
    parser.add_argument("--anomaly-ratio", type=float, required=True, help="异常率 (0-1)")
    parser.add_argument("--offline-date-ratio", type=float, required=True, help="离线天数占比 (0-1)")
    parser.add_argument("--anomaly-date-ratio", type=float, required=True, help="异常天数占比 (0-1)")
    parser.add_argument("--offline-count", type=int, required=True, help="离线次数")
    parser.add_argument("--anomaly-count", type=int, required=True, help="异常次数")
    parser.add_argument("--actual-records", type=int, required=True, help="实际采集记录数")
    parser.add_argument("--expected-records", type=int, required=True, help="期望记录数")
    parser.add_argument("--previous-total", type=float, default=None, help="上期总分（可选，用于趋势分析）")
    args = parser.parse_args()

    result = run_scoring(
        args.missing_ratio, args.anomaly_ratio,
        args.offline_date_ratio, args.anomaly_date_ratio,
        args.offline_count, args.anomaly_count,
        args.actual_records, args.expected_records,
        args.previous_total,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
