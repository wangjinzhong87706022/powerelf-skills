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
    related_skills: [powerelf-data-governance, powerelf-monitor, powerelf-inspection, powerelf-early-warning]
prerequisites:
  env_vars: [POWERELF_API_BASE, POWERELF_API_TOKEN, POWERELF_DB_READONLY_USER, POWERELF_DB_READONLY_PASSWORD]
---

# ChatBI Skill v2

NL2SQL 智能数据分析引擎。规则内嵌。

## 适用场景

本 skill 适用于：
- 自然语言 → SQL 查询水利监测数据
- 数据可视化（ECharts 图表生成）
- 数据分析解读（趋势/异常/对比）
- 知识库检索

## When NOT to Use

| 你想要的 | 应使用 |
|---|---|
| **昨日/本周**离线巡检回顾、日报、复合工况、质量评分 | `powerelf-inspection` |
| 数据质量（异常/缺失/离线/卡滞检测、评分、插值） | `powerelf-data-governance` |
| 阈值/告警判定与分发 | `powerelf-early-warning` |
| 实时当前值/趋势看盘 | `powerelf-monitor` |

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

## 数据访问

chatbi 走 **agent 自主 NL2SQL 直连库**（弃后端 Vanna）：

```bash
source ../_shared/bootstrap.sh   # 导出 RO_DB_URL（只读账号 chatbi_ro）
# 部署环境：可设置 POWERELF_SKILLS_ROOT 指向 powerelf-skills 根目录替代相对路径
python3 impl/query_exec.py --sql "SELECT ..." --db "$RO_DB_URL" [--limit 2000] [--display 20] [--format json|table]
```

`query_exec.py` 7 层安全护栏（只读账号/sqlparse/单语句/系统库黑名单/强制 LIMIT/超时 120s/只读事务），详见 [`rules/sql-generation.md`](rules/sql-generation.md)。

## API 附录（非 NL2SQL 能力，平台端点）

| 端点 | 说明 |
|------|------|
| `GET /knowledge/base/search?content=&size=` | 知识库检索 |
| `GET /knowledge/neo4j-graph/graphEcharts?fileName=` | 知识图谱 |
| `GET /llm-api/streamChat?message=&promptType=` | LLM对话 |
| `GET /aiMenu/search-menus?question=&prefix=` | 菜单导航 |

通用头与鉴权约定：见 [`../_shared/api-auth.md`](../_shared/api-auth.md)（`Authorization: Bearer ${POWERELF_API_TOKEN}` + `tenant-id: 1`）

## 共享引用（_shared）

本 skill 生成 SQL 时依赖以下 `_shared/` 文档：

| 文档 | 用途 |
|------|------|
| `_shared/references/schema.md` | DDL、关联键铁律、类型定义 |
| `_shared/references/sql-discipline.md` | SQL 写作 6 维解析 + 7 条纪律 |
| `_shared/references/analysis-qa-checklist.md` | 数据解读交付前 QA 闸 |
| `_shared/references/statistical-caution.md` | 统计措辞护栏（避免过度推断） |
| `_shared/references/api-auth.md` | REST API 鉴权约定 |
| `_shared/references/data-profiling.md` | 数据画像方法论 |
