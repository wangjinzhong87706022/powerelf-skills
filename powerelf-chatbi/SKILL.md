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
  env_vars: [POWERELF_API_BASE, POWERELF_API_TOKEN, POWERELF_DB_READONLY_USER, POWERELF_DB_READONLY_PASSWORD]
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

## 数据访问

chatbi 走 **agent 自主 NL2SQL 直连库**（弃后端 Vanna）：

```bash
source ../_shared/bootstrap.sh   # 导出 RO_DB_URL（只读账号 chatbi_ro）
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
