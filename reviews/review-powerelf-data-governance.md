# powerelf-data-governance 评审 — 2026-07-29

## 0. 概览

| 项 | 值 |
|---|---|
| Skill | `powerelf-data-governance` |
| 评审版本 | HEAD `e99d2ed` + working tree dirty（`SKILL.md` modified、`rules/offline-detection.md` modified） |
| 文件统计 | impl/ 6 py (1061 LOC) + lib/ 17 py 非测试 (5046 LOC) + lib/ 8 test py (902 LOC) + tests/ 11 文件 (2 py 478 LOC + 5 md + 4 sh, untracked) + rules/ 5 md + algorithms/ 5 md + SKILL.md + evolution/ 2 md + scripts/ 1 py (untracked) + references/ 13 文件 (untracked) |
| 总 LOC (py) | ~7009（含 test）+ ~236 scripts/ |
| 评审日期 | 2026-07-29 |
| 评审人 | Claude (sub-agent, Task 1/6) |

**摘要**：governance 是仓库中最大的 skill（~7k LOC Python），近期经过 3 连修改（8c6f133/44715ea/5fce818），整体质量较好——py_compile 全过、无裸 except、无硬编码密钥、评分公式 doc-code 完全一致。主要问题集中在：**SQL f-string 注入面**（虽然 impl/ 有白名单防护，lib/ 没有）、**10 个幽灵表名**出现在 ALLOWED_TABLES 中但 schema.md 不存在、**report.py UNION ALL 漏写 `deleted=0`**、**SKILL.md "禁止 conn.execute" 与 lib/ 实际使用 raw pymysql 自相矛盾**、以及**测试覆盖严重不足**（report.py 884 LOC / writeback.py 317 LOC / interpolation.py 642 LOC 均无测试）。

---

## 1. Blockers

无 Blocker 级发现。

---

## 2. High

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| High | 代码级 | `lib/report.py:386` | UNION ALL 查询 `SELECT '{tbl}' AS tbl, COUNT(DISTINCT st_id) AS cnt FROM {tbl}` 无 `WHERE deleted = 0` 过滤。SKILL.md 明确要求"每条 SQL 必须带 deleted = 0"，且其他 SQL（overview.py、writeback.py）都遵守了。此处会多计已软删行，导致日报"测站数"虚高。 | 在 f-string 拼接处追加 `WHERE deleted = 0`。 |
| High | 代码级 | `impl/anomaly_detector.py:109` `impl/missing_detector.py:64` `impl/offline_detector.py:67` `impl/profiler.py:108` `lib/overview.py:57-58` `lib/report.py:386,399,407,415` | SQL f-string 内插表名/列名。impl/ 有 ALLOWED_TABLES/ALLOWED_FIELDS 白名单防护（安全），但 lib/overview.py 的 `_table_overview()` 直接用 MONITOR_TABLES 字典 key 拼接、lib/report.py 的 monitor_tables 字典 key 拼接，均无运行时校验。若有人向字典添加恶意 key 或 dict 来源不可信，即可注入。 | 统一使用 SQLAlchemy `text()` + 参数化；表名至少做 `if table not in KNOWN_TABLES: raise` 守卫。 |
| High | 代码级 | 全 `lib/` 目录 | 测试覆盖严重不足：report.py (884 LOC)、writeback.py (317 LOC)、interpolation.py (642 LOC)、knowledge.py (453 LOC)、device_context.py (388 LOC)、extreme_event.py (239 LOC)、correlation.py (221 LOC)、overview.py (276 LOC) 均无对应测试文件。lib/ 测试只覆盖了 7/17 模块（mad/missing/offline/outliers/profiling/scoring/stagnation），产线代码 5046 LOC vs 测试 902 LOC，覆盖率 ~18%。 | 优先补 report.py 和 writeback.py 的测试（写操作 + 金额计算最易出错）。 |
| High | SQL/Schema | `impl/anomaly_detector.py:79-85` `impl/missing_detector.py:21-27` `impl/offline_detector.py:21-27` `impl/profiler.py:54-60` | ALLOWED_TABLES 白名单包含 10 个**幽灵表名**（st_deformation_r, st_gnss_r, st_seepage_r, st_rain_r, st_wind_r, st_temp_r, st_strlevel_r, st_strain_r, st_tilt_r, st_environment_r），在 `_shared/references/schema.md` 中均 **0 次出现**。用户传入这些表名会通过白名单校验，但实际执行时表不存在报错（或 worse，命中同名非预期表）。 | 与 schema.md 对齐，删除不存在的表名；或在 ALLOWED_TABLES 注释中标注"预留/未部署"。 |

---

## 3. Medium

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Medium | 文档-代码一致 | `SKILL.md:94` vs `lib/overview.py` 全文件、`lib/writeback.py` 全文件 | SKILL.md 明确"🚫 禁止：conn.execute(、cursor().execute(...).fetchall()、pymysql.connect("，要求只用 `query()`。但 overview.py 全程使用 `conn.cursor()` + `cur.execute()`（raw pymysql），writeback.py 同理（7 处 `cur = conn.cursor()`）。虽然 overview.py 通过 `from db import get_connection` 获取连接（不是 pymysql.connect），但仍违反了"只用 query()"的明文规定。 | 要么修改 SKILL.md 承认 lib/ 模块需要 raw connection（概览/回写场景 query() 不够用），要么将 overview.py/writeback.py 重构为使用 query()/query_multi()。 |
| Medium | 文档-代码一致 | `algorithms/mad-algorithm.md` 全文件 | 该文件仅 11 行，是一个指向 `_shared/algorithms/mad.md` 的 stub，标注"不再维护"。但 `rules/anomaly-detection.md:21` 仍引用 `algorithms/mad-algorithm.md`，SKILL.md 也未提及 `_shared/algorithms/mad.md` 的存在。形成断裂引用链。 | 更新 rules/anomaly-detection.md 直接引用 `_shared/algorithms/mad.md`；或在 SKILL.md 中说明 MAD 算法的单一事实源位置。 |
| Medium | 文档-代码一致 | `algorithms/multivariate-anomaly.md` 全文件 + `algorithms/spatial-interpolation.md` 全文件 | 两份算法文档（246 + 278 行）描述了孤立森林、DBSCAN、自编码器、Kriging、高斯过程、IDW 等 6 种算法的伪代码和参数，但 **全仓库无任何 Python 实现**。文档标题未标注"规划中"或"概念设计"，容易误导 Agent 认为已实现。 | 在文件顶部添加 `> ⚠️ 概念设计，尚未实现` 标注；或移至 `evolution/` 目录。 |
| Medium | SQL/Schema | `lib/report.py:372-381` | report.py 的 monitor_tables 字典包含 `rei_gate_r` 和 `rei_pump_r`（闸门/泵站工情表）。这两张表在 schema.md 中存在，但属于"设备工情"类（1.2 节），不是"监测数据"表。且它们的 `st_id` 列语义可能不同（闸门/泵站没有传统意义上的"测站"）。UNION ALL `COUNT(DISTINCT st_id)` 可能返回错误结果。 | 确认 rei_gate_r/rei_pump_r 是否确有 st_id 列及其语义；若不适合日报统计则从 monitor_tables 中移除。 |
| Medium | SQL/Schema | 全 impl/ + 全 lib/ | 占位符风格混用：impl/ 使用 SQLAlchemy `:param` 命名占位符（如 `:days`, `:st_id`），lib/report.py 和 lib/writeback.py 使用 PyMySQL `%s` 位置占位符。虽然各自与所用 driver 一致（impl/ 用 SQLAlchemy `text()`，lib/ 用 raw pymysql），但跨模块不一致增加了维护心智负担。 | 长期统一为一种 driver/占位符风格；短期在 SKILL.md 中说明两种风格的使用场景。 |
| Medium | 架构 | `powerelf-data-governance/references/` 全目录（13 文件，全 untracked） | SKILL.md 多处引用 `references/quick-reference.md`、`references/analysis-guide.md`、`references/best-practices.md`，但这 3 个文件 + 整个 references/ 目录均为 **untracked**（未 commit）。若其他人 clone 仓库或 Agent 在新会话中运行，这些文件不存在，SKILL.md 中的链接全部 404。 | 尽快 `git add` references/ 目录并 commit。这是 SKILL.md 正常工作的必要条件。 |
| Medium | 架构 | `powerelf-data-governance/scripts/classify_offline_by_duration.py`（untracked） | SKILL.md 的"强制指令"和"工具命令"两节均以最高优先级指向 `scripts/classify_offline_by_duration.py`，但该文件为 **untracked**。若文件丢失，SKILL.md 的核心工作流即断裂。 | 立即 commit 该文件。 |
| Medium | 代码级 | `lib/overview.py:57` | `_table_overview()` 中 `f"FROM \`{table}\`"` 使用反引号包裹表名，但 MONITOR_TABLES 的 key `dsm_dfr_srvrds_srhrds` 是一个非标准表名（无 st_ 前缀、含连续下划线），反引号虽可保护但不如在 SQL 层用白名单安全。且 `_table_overview()` 接受任意 `table: str` 参数，未做输入验证。 | 在函数入口添加 `if table not in MONITOR_TABLES: raise ValueError` 守卫。 |
| Medium | 代码级 | `lib/report.py:389` | `cur.execute(f"""{union_parts}""")` 中 union_parts 由 Python f-string 拼接而成，直接传给 `cur.execute()` 无参数化。虽然表名来自硬编码字典（不是用户输入），但此模式若被复制到其他上下文则危险。 | 添加注释 `# SAFE: table names from hardcoded dict, not user input`；长期改为参数化。 |
| Medium | 代码级 | `impl/offline_detector.py:91` | `DEFAULT_THRESHOLDS` 使用 st_type 代码（如 `"SP": 360`）作为 key，但 `run_detection()` 中 `threshold = DEFAULT_THRESHOLDS.get(table, 60)` 用表名（如 `st_pressure_r`）查找 — key 类型不匹配（SP vs st_pressure_r），永远 fallback 到默认 60 分钟。SP 类型设备（水位站）应有 360 分钟阈值，但实际使用 60 分钟，导致**假离线告警频率高 6 倍**。这是一个静默功能 bug，不影响程序运行但产出错误结果。 | 确认是否真有 SP 类型设备在生产中运行；若有则升 High。最小修复：键从 st_type 改为表名，或加一个归一化层（table→st_type→threshold）。 |

---

## 4. Low

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Low | 文档-代码一致 | `SKILL.md:1` frontmatter | SKILL.md frontmatter 的 `description` 字段（57 字符后被 hermes 截断）为"监测数据（水库水位/雨量/渗压/渗流/GNSS）有没有异常值、缺失、离线、卡滞？→数据质量治理：MAD/缺失/离线检测、评分、插值、报告。" — 根据 memory `hermes-skill-description-truncation.md`，只有前 57 字符影响路由。截断后为"监测数据（水库水位/雨量/渗压/渗流/GNSS）有没有异常值、缺"，丢失了关键路由词"MAD""评分""插值"。 | 重写 description 使前 57 字符包含核心路由词。 |
| Low | 文档-代码一致 | `evolution/parameters.md` 全文件 | parameters.md 所有参数的"最后调整"日期均为 2026-05-30，距今已 60 天未更新。虽然参数值与代码一致（验证过 DEFAULT_THRESHOLDS），但缺乏维护活跃度信号。 | 在 SKILL.md 或 evolution/ 中添加"参数审阅周期"提醒。 |
| Low | 架构 | `lib/test_*.py`（8 文件） | 测试文件与生产代码混放在 `lib/` 目录中（如 `lib/test_mad.py` 与 `lib/mad.py` 并列），而非独立的 `tests/` 目录。untracked 的 `tests/` 目录有 2 个 e2e 测试但未 commit。这种混放模式在 5 个 skill 中独此一家。 | 统一移至 `tests/` 目录；或至少在 SKILL.md 中说明约定。 |
| Low | 代码级 | `lib/writeback.py:260` | `batch_fix_anomalies()` 和 `batch_fill_missing()` 在循环体内 `import logging`（延迟导入），且 `logging.warning()` 未配置 handler，默认输出到 stderr。 | 将 `import logging` 移至文件顶部；配置 logger 或改用 `print(..., file=sys.stderr)`。 |
| Low | 代码级 | `impl/anomaly_detector.py:113-114` | `load_data()` 的 except 块 `except Exception as e: return pd.DataFrame()` 吞掉了所有异常（含连接错误、权限错误），返回空 DataFrame。调用方只看到 "NO_DATA"，不知道是表不存在还是网络问题。 | 至少记录 `print(f"[WARN] load_data failed: {e}", file=sys.stderr)` 再返回空。 |
| Low | 架构 | `algorithms/` 目录 | SKILL.md 未直接引用 algorithms/ 目录中的任何文件（0 次 grep 命中）。algorithms/ 的 5 个文件仅被 rules/*.md 间接引用。Agent 的按需加载流程中可能永远不会读到 algorithms/，使其成为"死文档"。 | 在 SKILL.md 的"快速查找"表中添加 algorithms/ 入口。 |
| Low | 文档-代码一致 | `SKILL.md` 全文 | SKILL.md 声明 `version: 2.0.0` 但无 changelog 或版本历史。结合 SKILL_OPTIMIZATION_PLAN.md 提到的"当前 731 行 → 目标 < 15KB"优化计划（untracked），版本号与实际内容的对应关系不明。 | 添加 changelog 段或在 evolution/ 中维护版本历史。 |
| Low | SQL/Schema | `lib/writeback.py:117` | `create_offline_record()` INSERT 语句硬编码 `tenant_id = 1`。这是多租户框架的租户隔离列，硬编码意味着所有离线记录都归属 tenant 1，若实际部署有多租户则数据错乱。 | 从连接上下文或配置中读取 tenant_id；或添加注释说明"单租户部署，tenant_id 恒为 1"。 |

---

## 5. 文档-代码一致性矩阵

| SKILL.md 声明 | 代码/文件实际状态 | 一致? | 备注 |
|---------------|------------------|-------|------|
| 5 个规则文件（离线/异常/缺失/插值/评分） | rules/ 下恰好 5 个 .md 文件 | ✅ | 完全匹配 |
| 3 个算法（MAD/插值/评分） | algorithms/ 下 5 个 .md 文件 | ⚠️ | 多出 multivariate-anomaly.md 和 spatial-interpolation.md（无实现）；mad-algorithm.md 是 stub |
| "禁止 conn.execute(" | overview.py + writeback.py 全程 raw pymysql | ❌ | SKILL.md 规定与实际 lib/ 实现矛盾 |
| "每条 SQL 必须带 deleted = 0" | report.py:386 UNION ALL 无 deleted=0 | ❌ | 日报测站数虚高 |
| MAD 阈值: 水位 3.0 / 雨量 5.0 / 渗压 4.0 / GNSS 3.5 / 流量 4.0 | anomaly_detector.py DEFAULT_THRESHOLDS 完全一致 | ✅ | |
| 离线阈值: SP=360, 其他=60 | offline_detector.py DEFAULT_THRESHOLDS 一致（但 key 不匹配，见 Medium #10） | ⚠️ | key 用 st_type 而非 table name |
| 评分四维度 35%+10%+40%+15% | scoring.py compute_equil_score 完全一致 | ✅ | 公式逐行对齐 |
| 变化率阈值: 水位 5% / 渗压 3% / GNSS 2% / 流量 10% | anomaly_detector.py CHANGE_RATE_THRESHOLDS 完全一致 | ✅ | |
| `scripts/classify_offline_by_duration.py` 为强制入口 | 文件存在但 untracked | ⚠️ | 功能正常，但未 commit |
| `references/quick-reference.md` 等被 SKILL.md 引用 | 文件存在但全目录 untracked | ⚠️ | 13 文件均未 commit |
| algorithms/mad-algorithm.md 引用 | stub 指向 _shared/algorithms/mad.md | ⚠️ | rules/ 仍引用旧路径 |

---

## 6. SQL/Schema 用表

| 代码中使用的表名 | schema.md 存在? | 操作类型 | 有 deleted=0? | 占位符风格 | 备注 |
|-----------------|----------------|---------|--------------|-----------|------|
| st_rsvr_r | ✅ | SELECT | ✅ (overview) / ❌ (report UNION) | `:days` (impl) / 无 (report) | |
| st_river_r | ✅（0 行空表） | SELECT | 同上 | 同上 | schema.md 标注"本部署未启用" |
| st_pptn_r | ✅ | SELECT | 同上 | 同上 | |
| st_pressure_r | ✅ | SELECT | 同上 | 同上 | |
| st_percolation_r | ✅ | SELECT | 同上 | 同上 | |
| dsm_dfr_srvrds_srhrds | ✅ | SELECT | 同上 | 同上 | GNSS 表 |
| rei_gate_r | ✅ | SELECT (report) | ❌ | 无 | 闸门工情，非传统监测表 |
| rei_pump_r | ✅ | SELECT (report) | ❌ | 无 | 泵站工情 |
| st_deformation_r | ❌ | ALLOWED 白名单 | — | — | 幽灵表名 |
| st_gnss_r | ❌ | ALLOWED 白名单 | — | — | 幽灵表名（实际用 dsm_dfr_srvrds_srhrds） |
| st_seepage_r | ❌ | ALLOWED 白名单 | — | — | 幽灵表名 |
| st_rain_r | ❌ | ALLOWED 白名单 | — | — | 幽灵表名（实际用 st_pptn_r） |
| st_wind_r / st_temp_r / st_strlevel_r / st_strain_r / st_tilt_r / st_environment_r | ❌ | ALLOWED 白名单 | — | — | 6 个幽灵表名 |
| eq_equip_base | ✅ | SELECT + UPDATE | ✅ | `%s` (writeback) | writeback 用 raw pymysql |
| eq_business_equip_relation | ✅ | SELECT | — | 无 WHERE | overview.py JOIN |
| eq_equip_offline_record | ✅ | SELECT + INSERT + UPDATE | — | `%s` | 无 deleted 列（设计如此） |
| eq_data_anomaly_record | ✅ | SELECT + INSERT + UPDATE | — | `%s` | |
| eq_data_missing_record | ✅ | SELECT + INSERT + UPDATE | — | `%s` | |
| stats_data_collection_daily | ✅ | SELECT | — | `%s` | report.py 日报统计 |
| stats_data_missing_daily | ✅ | SELECT | — | `%s` | |
| stats_data_anomaly_daily | ✅ | SELECT | — | `%s` | |
| dg_equip_offline | ✅ | 仅文档引用 | — | — | 离线阈值配置表 |

---

## 7. untracked 处置建议

| 文件/目录 | 内容摘要（前 30 行） | 处置 | 理由 |
|-----------|---------------------|------|------|
| `references/README.md` | references/ 目录索引，列出 quick-ref / analysis-guide / best-practices 的用途 | **保留 + commit** | SKILL.md 多处引用 references/ 文件，不 commit 则链接 404 |
| `references/analysis-guide.md` | 12 种分析方法 API 说明（~3KB） | **保留 + commit** | 被 SKILL.md "快速查找"表引用 |
| `references/best-practices.md` | Pitfalls + QA 闸 + 边界规则汇总（~2.5KB） | **保留 + commit** | 被 SKILL.md "Pitfalls" 和 "Validation Gate" 引用 |
| `references/quick-reference.md` | DB 连接、核心表、常用 SQL、阈值速查（~3KB） | **保留 + commit** | 被 SKILL.md "快速查找"表引用，最高频参考文件 |
| `references/actual_schema.md` | 实际 schema 备注（~0.5KB） | **保留 + commit** | 补充 schema 信息 |
| `references/algorithm.md` | 算法详细说明（~20KB） | **保留 + commit** | 大文件但与 algorithms/ 互补 |
| `references/business_rules.md` | 业务规则文档（~8KB） | **保留 + commit** | 与 rules/ 互补 |
| `references/comprehensive-detection.md` | 综合检测流程（~4.7KB） | **保留 + commit** | 工作流文档 |
| `references/drift-analysis-template.md` | 漂移分析模板（~2.4KB） | **保留 + commit** | 模板文档 |
| `references/missing-data-workflow.md` | 缺失数据处理工作流（~3.5KB） | **保留 + commit** | 工作流文档 |
| `references/pitfalls.md` | 详细 pitfalls（~6.6KB） | **保留 + commit** | 与 SKILL.md pitfalls 段互补 |
| `references/pymysql-query-template.md` | PyMySQL 查询模板（~0.5KB） | **保留 + commit** | 开发辅助 |
| `references/schema.md` | skill-local schema 副本（~0.4KB） | **评估后决定** | 与 `_shared/references/schema.md` 可能重复；若为子集则删除 |
| `scripts/classify_offline_by_duration.py` | 批量离线设备分级脚本（236 行，8.3KB） | **保留 + commit** | SKILL.md 强制指令指向此文件，是核心功能入口 |
| `tests/e2e_benchmark.py` | 端到端性能基准测试（198 行） | **保留 + commit** | 有用的性能回归测试 |
| `tests/verify_classify_offline.py` | 离线分级验证脚本（280 行） | **保留 + commit** | 功能验证测试 |
| `tests/HERMES_TESTING_GUIDE.md` | Hermes 测试指南（~9.6KB） | **保留 + commit** | 测试文档 |
| `tests/QUICK_START.md` | 快速开始指南（~7.3KB） | **保留 + commit** | 入门文档 |
| `tests/README_HERMES_TEST.md` | Hermes 测试 README（~4.7KB） | **保留 + commit** | 测试文档 |
| `tests/monitoring_and_adjustment.md` | 监控与调整指南（~7.7KB） | **保留 + commit** | 运维文档 |
| `tests/monitor_session.sh` | 监控会话脚本（~1.9KB） | **保留 + commit** | 运维工具 |
| `tests/quick_test.sh` | 快速测试 shell 脚本（~4.6KB） | **保留 + commit** | 测试工具 |
| `tests/real_world_test.sh` | 真实场景测试脚本（~1.5KB） | **保留 + commit** | 测试工具 |
| `tests/run_hermes_test.sh` | Hermes 测试运行脚本（~7.2KB） | **保留 + commit** | 测试工具 |
| `tests/test_on_hermes.sh` | Hermes 测试脚本（~5.5KB） | **保留 + commit** | 测试工具 |
| `SKILL_OPTIMIZATION_PLAN.md` | SKILL.md 瘦身方案（731行→<15KB） | **保留（不 commit）** | 内部规划文档，完成后归档 |
| `SKILL_OPTIMIZATION_SUMMARY.md` | 优化摘要 | **保留（不 commit）** | 同上 |

---

## 8. 正面发现

1. **py_compile 全过**：impl/ 6 文件 + lib/ 25 文件（含 test）全部编译通过，无语法错误。
2. **无裸 except**：commit 8c6f133 修复后，全 skill 无 `except:` 裸捕获。所有 except 块都捕获具体异常类型或 `Exception as e`。
3. **评分公式 doc-code 完美一致**：scoring.py 的四维度公式（35%+10%+40%+15%）与 rules/quality-scoring.md + algorithms/scoring-formulas.md 逐行对齐，包括时间衰减 λ=0.05 和趋势阈值 ±5 分。
4. **MAD 阈值 doc-code 完美一致**：anomaly_detector.py 的 DEFAULT_THRESHOLDS 和 CHANGE_RATE_THRESHOLDS 与 rules/anomaly-detection.md 及 evolution/parameters.md 完全一致。
5. **impl/ SQL 注入防护到位**：所有 impl/ 文件使用 ALLOWED_TABLES + ALLOWED_FIELDS 白名单验证用户输入后才拼接 SQL，且使用 SQLAlchemy `text()` + 命名参数。
6. **writeback.py 事务管理规范**：所有写操作都有 try/except/rollback + finally: cur.close()，批量操作有 failed_ids 追踪。
7. **SKILL.md 路由表完整**：When to Use / When NOT to Use / Related Skills 三节齐全，路由指向明确。
8. **evolution/parameters.md 参数注册表**：所有可调参数集中管理，含当前值、合理范围、说明、最后调整日期。这在 5 个 skill 中独此一家。
9. **offline-detection.md 文档质量高**：330 行的详细文档，含三态判定、渐进式告警、MTTR、批量分级、SQL 示例、FAQ、性能对比，是所有 rules/ 中最完善的。
10. **overview.py 设计合理**：`build_overview()` 纯函数返回 dict（可单测、可复用），`render_text()` 负责展示，职责分离清晰。红旗系统（red_flags）有 severity 分级。
