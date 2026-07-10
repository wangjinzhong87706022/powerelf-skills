---
name: powerelf-chatbi
description: "ChatBI智能分析：意图分类规则、图表选择规则、SQL生成规则。规则内嵌，可独立判断。"
version: 2.0.0
author: Powerelf Team
license: MIT
platforms: [linux, windows, macos]
metadata:
  hermes:
    tags: [water-conservancy, chatbi, nl2sql, visualization, knowledge-base]
    related_skills: [powerelf-data-governance, powerelf-monitor]
prerequisites:
  env_vars: [POWERELF_API_BASE, POWERELF_API_TOKEN]
---

# ChatBI Skill v2

NL2SQL 智能数据分析引擎。规则内嵌。

## 能力概览

| 子模块 | 文件 | 功能 |
|--------|------|------|
| 意图分类 | `rules/intent-classification.md` | 用户问题→意图类型分类 |
| 图表选择 | `rules/chart-selection.md` | 数据特征→图表类型选择 |
| SQL生成 | `rules/sql-generation.md` | NL2SQL提示词和规则 |

## 按需加载指令

```
"意图"/"分类"/"理解"     → rules/intent-classification.md
"图表"/"可视化"/"ECharts" → rules/chart-selection.md
"SQL"/"查询"/"NL2SQL"    → rules/sql-generation.md
```

## 自我进化

- 可调参数：`evolution/parameters.md`
- 反馈日志：`evolution/feedback-log.md`

---

## API 附录

| 端点 | 说明 |
|------|------|
| `GET /chatbi/aiReporter/newSession?userId=` | 创建会话 |
| `GET /chatbi/aiReporter/{chatId}/message?question=` | 发送问题(SSE) |
| `POST /chatbi/aiReporter/{chatId}/cancel` | 取消操作 |
| `GET /knowledge/base/search?content=&size=` | 知识库检索 |
| `GET /knowledge/neo4j-graph/graphEcharts?fileName=` | 知识图谱 |
| `GET /llm-api/streamChat?message=&promptType=` | LLM对话 |
| `GET /aiMenu/search-menus?question=&prefix=` | 菜单导航 |

通用头与鉴权约定：见 [`../_shared/api-auth.md`](../_shared/api-auth.md)（`Authorization: Bearer ${POWERELF_API_TOKEN}` + `tenant-id: 1`）
