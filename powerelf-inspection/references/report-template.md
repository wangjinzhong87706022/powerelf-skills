# 智能巡检报告

**生成时间**: {generated_at}
**run_id**: {run_id}
**分析周期**: 近{days}天
**分析维度**: {dim_count}项

---

## 巡检概览

| 级别 | 数量 | 说明 |
|------|------|------|
| 🔴 CRITICAL | {critical} | 需立即处理 |
| 🟡 WARNING | {warnings} | 需关注 |
| 🟢 OK | {ok_count} | 正常 |

---

{sections}

{charts}

## 设备状态（三口径分层）

{offline_overview}

## 巡检建议

{recommendations}

## Data Notes（无数据/数据质量维度说明）

{data_notes}

## 附录：数据覆盖清单（近{days}天各表行数）

{coverage}

## 最终结论（三问）

1. **多严重**：CRITICAL {critical} 项 / WARNING {warnings} 项
2. **最可能根因**：见各异常条目 detail（含数据源锚点）
3. **下一步谁做什么**：见巡检建议；CRITICAL 项须人工现场确认后处置

---
*报告由智能巡检系统自动生成（模板：references/report-template.md）*

{qa_checklist}
