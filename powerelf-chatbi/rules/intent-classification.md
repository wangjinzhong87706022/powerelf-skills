# 意图分类规则

## 意图类型

| IntentType | 说明 | 关键词 | 状态 |
|------------|------|--------|------|
| TEXT_TO_SQL | 自然语言转SQL | "查"、"查询"、"多少"、"几个" | 已实现 |
| VISUALIZATION | 数据可视化 | "图表"、"曲线"、"柱状图"、"饼图" | 已实现 |
| INTERPRETATION | 数据分析解读 | "分析"、"解读"、"说明"、"总结" | 已实现 |
| KNOWLEDGE_QUERY | 知识库检索 | "知识"、"文档"、"规范"、"标准" | 未实现 |
| SUGGESTION | 基于数据的建议 | "建议"、"应该"、"怎么处理" | 未实现 |
| CLARIFICATION | 澄清模糊问题 | 问题过于模糊时 | 未实现 |
| WEB_SEARCH | 联网搜索 | "搜索"、"最新"、"新闻" | 未实现 |
| DATA_ASSISTANCE | 数据操作支持 | "导出"、"下载"、"备份" | 未实现 |
| ANALYSIS | 深度分析 | "深入"、"详细"、"对比" | 未实现 |

## 分类逻辑

```
输入: 用户自然语言问题

1. 提取关键词
2. 匹配意图类型
3. if 匹配到已实现的意图:
     → 执行对应流水线
   else:
     → 返回"暂不支持该类型问题"的提示

默认行为:
  首次提问 → TEXT_TO_SQL + VISUALIZATION + INTERPRETATION 三步流水线
  后续提问 → 通过意图分类决定执行步骤
```

## 流水线组合（hermes agent 编排，弃后端 Vanna）

```
TEXT_TO_SQL 流水线:
  意图分类 → agent 生成 SQL（用 sql-discipline.md/schema.md/few_shots.md）
           → chatbi/impl/query_exec.py 只读执行（7 层护栏）→ 数据表格

VISUALIZATION 流水线:
  数据 → agent 按 chart-selection.md 选图 → 生成 ECharts option

INTERPRETATION 流水线:
  数据 → agent 解读（过 analysis-qa-checklist.md / statistical-caution.md）→ 分析文本

完整流水线 (首次):
  意图分类 → 生成SQL → query_exec 执行 → 图表决策 → 图表生成 → 数据解读
```
