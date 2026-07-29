# powerelf-inspection 评审 — 2026-07-29

## 0. 概览

| 项 | 值 |
|---|---|
| Skill | `powerelf-intelligent-inspection` |
| 评审版本 | HEAD `62c4d9c`（working tree clean for inspection/） |
| 文件统计 | impl/ 4 py (2274 LOC) + lib/ 8 py non-test (1254 LOC) + lib/ 4 test py (586 LOC) + impl/ 1 test py (215 LOC) + rules/ 13 md + algorithms/ 8 md + references/ 5 md + evolution/ 2 md + autoresearch/ 4 files + SKILL.md |
| 总 LOC (py) | ~4329（含 test） |
| 评审日期 | 2026-07-29 |
| 评审人 | Claude (sub-agent, Task 2/6) |

**摘要**：inspection 是仓库中第二大 skill（~4.3k LOC Python），架构上分为 `lib/`（纯函数内核）+ `impl/`（数据读取 + 分析引擎 + CLI）两层。近期经过密集开发（7/16 之前的 refactor → 7/16 之后的 lib 提取 + 测试补齐 + 文档完善），整体设计思路清晰——5 层异常判定体系、15 维度分析引擎、4 维度质量评分模型、数据源注册表机制。但存在一个 **Blocker 级编译错误**（`inspection_analyzer.py` 第 415 行 IndentationError，导致整个 15 维度引擎无法运行），以及多个 High 级问题：`read_sensor_data()` 全量传感器查询缺失 `deleted=0`、质量评分缺陷率分母字段用错（`real_checkobj` 而非 `real_objitem`）、3 处裸 `except:`、GNSS 表名在代码与白名单之间不一致。`lib/` 内核层质量较好（纯函数、类型提示齐全、有 78+ 单测），主要问题集中在 `impl/` 引擎层。

---

## 1. Blockers

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Blocker | 代码级 | `impl/inspection_analyzer.py:415-416` | **IndentationError: unexpected indent** — 第 415-416 行是第 413-414 行的残余重复片段（`"detail": "偏离历史分布，需人工确认"` + `})`），多了 8 空格缩进。`python3 -m py_compile` 直接报错。**整个 15 维度分析引擎无法导入、无法运行**，所有集成测试也会因此全部 skip/fail。 | 删除第 415-416 行（2 行残余代码）。这是 merge/edit 残留，修复后需立即跑一次 `py_compile` + 集成测试确认。 |

---

## 2. High

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| High | 代码级 | `impl/inspection_analyzer.py:121-131` | `read_sensor_data()` 是全部 15 维度分析的数据入口，其 SQL 拼接为 `f"SELECT {fields} FROM {table} WHERE {where} ORDER BY {time_field} DESC LIMIT :limit"` — **缺失 `deleted = 0` 过滤**。schema.md 铁律第 2 条："必须 `WHERE deleted = 0`"。该函数被 `analyze_water_level`、`analyze_rainfall`、`analyze_pressure`、`analyze_percolation`、`analyze_displacement`、`analyze_gate`、`analyze_pump`、`analyze_mad_anomaly`、`analyze_correlation` 等 9 个分析函数调用，**所有传感器数据查询都会包含已软删行**，导致异常检测基数虚高、统计结果不可靠。 | 在 `where_parts` 列表中追加 `"deleted = 0"` 条件。 |
| High | 代码级 | `impl/inspection_tool.py:247` | `calc_inspection_quality()` 计算缺陷率时使用 `real_checkobj`（实际检查对象数）作为分母，但 `quality-assessment.md`、`business_rules.md` §12、`data-model.md` §6 均明确规定分母为 `real_objitem`（实际检查项数）。`lib/quality.py` 的函数签名 `compute_defect_discovery_rate(defects_found, real_checkitems)` 参数名也是 `real_checkitems`。`real_checkobj` 是"检查了几个设备"，`real_objitem` 是"检查了几个检查项"，后者远大于前者。**用 `real_checkobj` 做分母会导致缺陷率被高估 3-10 倍**（一个设备通常有多个检查项），质量评分虚低。 | 将 `tasks['real_checkobj'].sum()` 改为 `tasks['real_objitem'].sum()`，并确保 SQL SELECT 中包含 `real_objitem` 列。 |
| High | 代码级 | `impl/inspection_tool.py:355,444,460` | 3 处裸 `except:`（无异常类型、无日志）。第 355 行在 `parse_percent()` 中吞掉所有异常返回 0；第 444 行在 `demo_collect()` 中吞掉巡检点查询失败；第 460 行在同一函数中吞掉检查项查询失败。commit `8c6f133` 已修复 governance 的裸 except，但 inspection_tool.py 遗漏。 | 改为 `except (ValueError, AttributeError):` 或 `except Exception as e: logger.debug(...)` |
| High | SQL/Schema | `impl/inspection_analyzer.py:479` + `impl/registry.py:29,85` + `impl/inspection_tool.py:44,111` | **GNSS 表名不一致**：`inspection_analyzer.py` 直接查询 `dsm_dfr_srvrds_srhrds`（schema.md 中存在的正确表名），但 `registry.py` 和 `inspection_tool.py` 的 `_ALLOWED_TABLES` 白名单以及 `get_builtin_registry()` 中使用 `srm_gnss_data_day`（schema.md 中 **不存在**）。两套 GNSS 表名同时存在于代码中：analyzer 走 `dsm_dfr_srvrds_srhrds`，registry 采集演示走 `srm_gnss_data_day`。后者在线上库可能不存在导致运行时报错，或 worse 命中非预期表。 | 统一为 `dsm_dfr_srvrds_srhrds`（schema.md 中的正确表名），或在白名单中标注 `srm_gnss_data_day` 为"SmartTwinRes 项目专用、本部署未启用"。 |
| High | 代码级 | `impl/inspection_analyzer.py:129` | `read_sensor_data()` 的 SQL 使用 f-string 内插 `{table}` 和 `{fields}`，虽然调用方均为硬编码字符串（非用户输入），但该函数**未做任何标识符白名单校验**——不同于 `registry.py:collect_from_source()` 会先调用 `_validate_identifiers()`。若有人通过 `read_sensor_data(engine, user_input_table, ...)` 调用则存在注入风险。`inspection_analyzer.py` 本身也没有 import 或定义 `_validate_identifiers`。 | 在 `read_sensor_data()` 入口添加白名单校验（复用 `registry.py` 的 `_ALLOWED_TABLES`）；或将硬编码表名提升为模块级常量。 |

---

## 3. Medium

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Medium | 文档-代码一致 | `impl/inspection_tool.py:247` + `references/business_rules.md:159` | 质量评分缺陷率分母：`business_rules.md` §12 明确列出优先级 `real_objitem > real_checkobj > plan_checkobj > real_checknum`，且 `lib/quality.py:compute_defect_discovery_rate()` 参数名为 `real_checkitems`。但 `inspection_tool.py:247` 使用 `real_checkobj`（检查对象数），违反了自身文档规定的优先级。这是 High #2 的文档侧佐证。 | 同 High #2 修复。 |
| Medium | 文档-代码一致 | `lib/anomaly.py:255-261` vs `lib/anomaly.py:280` | `_LAYER_WEIGHTS`（模块级常量）定义 `{1: 0.30, 2: 0.20, 3: 0.20, 4: 0.15, 5: 0.15}`，但 `composite_anomaly_judge()` 内部实际使用 `FACTOR_WEIGHT = {1: 0.30, 4: 0.20, 3: 0.20, 2: 0.20, 5: 0.10}`。两者在 L4（MAD）权重（0.15 vs 0.20）和 L2（变化率）权重（0.20 vs 0.20→实际映射为"历史"0.20）上不一致。`_LAYER_WEIGHTS` 从未被任何代码引用（dead code），但它的存在会误导开发者。`FACTOR_WEIGHT` 与 SKILL.md 的公式一致。 | 删除 `_LAYER_WEIGHTS`（dead code），或在注释中说明它已被 `FACTOR_WEIGHT` 取代。 |
| Medium | 代码级 | `impl/inspection_tool.py:39-54,69-83,86-164,167-174,177-217` | `inspection_tool.py` 完整复制了 `registry.py` 的全部函数：`_ALLOWED_TABLES`、`_validate_identifiers()`、`load_registry()`、`get_builtin_registry()`、`match_data_sources()`、`collect_from_source()`。虽然第 38 行有 `from registry import ...` 导入，但第 69-217 行又定义了本地版本（同名函数覆盖导入）。两处代码完全重复（约 150 行），且 `show_registry()` 在两文件中签名不同（`registry.py` 接受 `registry` 参数，`inspection_tool.py` 接受 `engine` 参数）。 | 删除 `inspection_tool.py` 中的重复定义，只保留 `from registry import ...`；统一 `show_registry()` 签名。 |
| Medium | 文档-代码一致 | `rules/anomaly-and-complex-conditions.md:204-208` vs `impl/inspection_analyzer.py:388,525` | **趋势检测阈值 doc-code 严重不一致**。规则文档声明：渗压连续上升 ≥ **12 次**（12 小时），GNSS 连续位移 ≥ **7 次**（7 天）。代码实际：渗压使用 7 点窗口/6 次连续上升（`wp_values[-7:]` + `min_consecutive=6`），GNSS 使用 5 点窗口/4 次连续上升（`speed_values[-5:]` + `min_consecutive=4`）。代码的窗口比规则文档要求的短一半以上，**会导致更多假阳性趋势告警**。SKILL.md 第 190-192 行声称的"渗压: 7 点窗口 / 6 次连续上升"与代码一致，但与规则文档矛盾。 | 统一三方（rules/、SKILL.md、code）的阈值。若以规则文档为准，代码应改为渗压 13 点窗口/12 次连续、GNSS 8 点窗口/7 次连续。 |
| Medium | 代码级 | `impl/inspection_tool.py:298-305` | `predict_defect_trend()` 使用 raw SQL 字符串（非 `text()` 包装）调用 `pd.read_sql()`，且 SQL 中包含 `DATE_FORMAT` 的 `%%Y-%%m`（PyMySQL 转义）。但 `pd.read_sql()` 使用 SQLAlchemy engine 时（本文件用 `create_engine`），`%%` 不会被 PyMySQL 转义——SQLAlchemy 使用 `text()` 的 `:param` 语法，不用 `%s` 占位符。`%%Y-%%m` 可能被 SQLAlchemy 原样传给 MySQL 导致 `DATE_FORMAT` 格式化错误。 | 改用 `text()` 包装 SQL，或确认 SQLAlchemy + PyMySQL 的 `%%` 转义行为。 |
| Medium | 代码级 | `impl/inspection_analyzer.py:456-467` | `analyze_percolation()` 的 MAD 异常检测直接内联实现了 MAD 计算（`np.median` + `np.abs` + `* 1.4826`），而非委托给 `lib/anomaly.mad_anomaly()`。这违反了 SKILL.md 声明的"5 层异常判定内核（lib/anomaly.py）"架构。同一文件中 `analyze_water_level()`、`analyze_pressure()`、`analyze_mad_anomaly()` 都正确委托了 `_anomaly.mad_anomaly()`，唯独 `analyze_percolation()` 内联。 | 改为调用 `_anomaly.mad_anomaly(perc_values.tolist(), threshold=3.0, min_samples=10)`。 |
| Medium | 架构 | `lib/anomaly.py` 全模块 | `composite_anomaly_judge()`、`layer1_threshold()`、`layer2_change_rate()`、`layer3_trend()`、`layer5_correlation()` 这 5 个函数**在 impl/ 中从未被调用**。只有 `mad_anomaly()` 和 `consecutive_monotonic()` 被 `inspection_analyzer.py` 实际使用。SKILL.md 宣传的"5 层异常判定体系"在 `lib/` 中有完整实现，但 `impl/` 引擎层用的是自己内联的简化逻辑（直接阈值比较 + `_anomaly.consecutive_monotonic` + `_anomaly.mad_anomaly`）。lib/ 的 5 层框架是"死代码"。 | 要么让 `impl/` 调用 `composite_anomaly_judge()` 实现真正的 5 层综合判定，要么将 `lib/anomaly.py` 中未使用的函数标记为"📌 roadmap / 概念实现"。 |
| Medium | 架构 | `impl/inspection_tool.py:291-296` | `predict_defect_trend()` 依赖 `scikit-learn`（`from sklearn.linear_model import LinearRegression`），但 `lib/defect_predict.py` 已有纯 Python 实现的 `linear_trend()` 函数（最小二乘回归，无外部依赖）。`inspection_tool.py` 未使用自己的 lib 内核，而是另起炉灶用 sklearn。这与"lib/ 是内核、impl/ 是接线层"的架构矛盾。 | 改用 `lib/defect_predict.linear_trend()`；若需 sklearn 的高级功能则在 lib/ 中封装。 |

---

## 4. Low

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Low | 架构 | `impl/registry.py:26-30` + `impl/inspection_tool.py:40-44` | `_ALLOWED_TABLES` 集合在两个文件中完全重复定义（14 个表名），且缺少 `wq_pcp_d`（水质表，`analyze_water_quality()` 实际使用）、`st_soil_moisture_r`（墒情表）、`st_termite_monitor_r`（白蚁表）、`business_check_task`、`business_check_error`、`business_check_route`、`business_check_result`、`ew_info_rules`、`ew_info_message`、`att_st_base`、`sys_data_source_registry` 等 inspection 实际查询的表。白名单与实际用表不一致。 | 提取为独立常量模块（如 `lib/constants.py`），统一管理白名单。 |
| Low | 代码级 | `impl/test_inspection.py:35-50` | 集成测试通过 `from inspection_analyzer import ...` 导入 15 个分析函数，但因 Blocker（`inspection_analyzer.py` IndentationError），导入会失败。`HAS_ANALYZER = False` 后所有 `@pytest.mark.skipif(not HAS_ANALYZER)` 标记的测试会 skip。**当前 CI 中 inspection 集成测试全部 skip**，不是因为有 DB 守卫，而是因为导入失败。 | 修复 Blocker 后重跑 CI 确认测试恢复。 |
| Low | 文档-代码一致 | `SKILL.md:3` frontmatter | description 字段为"水利工程智能巡检智能体 + 实时监测"（21 字符），根据 memory `hermes-skill-description-truncation.md`，前 57 字符影响路由。完整截断后仍为"水利工程智能巡检智能体 + 实时监测"（未达 57 字符上限），但丢失了核心路由词"异常检测""质量评分""缺陷预测""路线优化"。且"实时监测"已由 `powerelf-monitor` 负责，inspection 的 description 含"实时监测"可能造成路由误导。 | 重写 description 使前 57 字符包含"巡检""异常检测""质量评分""缺陷预测"等路由词，去掉"实时监测"。 |
| Low | 文档-代码一致 | `evolution/feedback-log.md:52` + `evolution/parameters.md:10-12` | `feedback-log.md` 条目为空（"暂无记录。首次运行后开始积累。"），`parameters.md` 开头声明"调整阈值请 UPDATE 数据库，不要只改本文档"——但参数表中所有"最后调整"日期均为 2026-05-31 或 2026-06-01（距今 60 天未更新）。自演化机制（rules/rule-evolution.md）虽然设计完善，但缺乏实际运行证据。 | 在 SKILL.md 中标注"自演化机制当前为 AI Agent 辅助流程，全自动闭环标记为 📌 roadmap"（已在 SKILL.md:319 标注，但未在 evolution/ 中同步）。 |
| Low | 文档-代码一致 | `algorithms/time-series-forecast.md` + `rules/intelligent-inspection.md:41` | `algorithms/time-series-forecast.md` 是指向 `_shared/algorithms/time-series-forecast.md` 的 stub（标注"已统一"），但该 stub 未标记"📌 roadmap"。同时 `rules/intelligent-inspection.md:41` 引用 `../../_shared/algorithms/time-series-forecast.md` 作为"水位变化趋势"的分析方法（指数平滑/ARIMA），但该算法在 `lib/` 和 `impl/` 中均**无实现**。SKILL.md:317 已标注 Holt-Winters/ARIMA 为 roadmap，但 rules/ 中未标注。 | 在 `rules/intelligent-inspection.md` 的"分析方法"表中标注"📌 roadmap"项。 |
| Low | 架构 | `impl/inspection_analyzer.py:1033-1124` | `analyze_correlation()` 实现了 3 种关联分析（水位-渗压、水位-流量、降雨-水位），但逻辑较简单（仅检查"同时上升"或"一方稳定另一方变化"），未使用 `lib/anomaly.layer5_correlation()` 的通用框架。且关联分析硬编码了 `st_rsvr_r`/`st_pressure_r`/`st_pptn_r` 表名，不具备可扩展性。 | 长期可考虑将关联规则参数化，通过 `sys_data_source_registry` 定义关联对。 |
| Low | 代码级 | `impl/inspection_tool.py:298` | `predict_defect_trend()` 的 SQL 使用 raw string 而非 `text()` 包装：`pd.read_sql("""SELECT DATE_FORMAT(...)...""", engine)`。虽然 SQLAlchemy engine 通常能处理 raw string，但项目纪律（`_shared/references/sql-discipline.md`）要求统一使用 `text()` 包装。 | 改用 `pd.read_sql(text("..."), engine)`。 |

---

## 5. 文档-代码一致性矩阵

| SKILL.md 声明 | 代码/文件实际状态 | 一致? | 备注 |
|---------------|------------------|-------|------|
| 15 维度传感器异常检测 | `inspection_analyzer.py` 有 15 个 `analyze_*` 函数 + `generate_report()` 调用 15 项 | ✅ | 完全匹配（需修复 Blocker 后才能运行） |
| 5 层异常判定体系 | `lib/anomaly.py` 实现 5 层函数 | ⚠️ | lib/ 有完整实现，但 impl/ 只用了 mad_anomaly + consecutive_monotonic（2/5 层） |
| 4 维度质量评分模型（完成率30+及时率25+缺陷率25+覆盖率20） | `lib/quality.py` 分段评分完全一致 | ✅ | `_score_*` 函数与 `quality-assessment.md` 逐行对齐 |
| 13 个规则文件 | `rules/` 目录下恰好 13 个 .md 文件 | ✅ | 完全匹配 |
| 8 个算法文档 | `algorithms/` 目录下 8 个 .md 文件 | ✅ | 但 3 个是 stub（指向 _shared），1 个标记 roadmap |
| 置信度公式: 0.3×阈值+0.2×数据质量+0.2×趋势+0.2×历史+0.1×上下文 | `composite_anomaly_judge()` FACTOR_WEIGHT 一致 | ✅ | 但该函数从未被 impl/ 调用 |
| `_LAYER_WEIGHTS` (0.30/0.20/0.20/0.15/0.15) | 与 FACTOR_WEIGHT 不一致 | ❌ | dead code，与 SKILL.md 公式矛盾 |
| `read_sensor_data()` 查询带 deleted=0 | 函数 SQL 无 deleted=0 | ❌ | 所有传感器查询受影响 |
| 缺陷率分母 = real_objitem | `inspection_tool.py` 用 real_checkobj | ❌ | 分母错误导致缺陷率虚高 |
| 趋势阈值: 渗压≥12次/GNSS≥7次 | 代码: 渗压≥6次/GNSS≥4次 | ❌ | 与 rules/ 不一致（与 SKILL.md 一致） |
| GNSS 表 = dsm_dfr_srvrds_srhrds | analyzer 正确；registry 白名单用 srm_gnss_data_day | ⚠️ | 两套表名并存 |
| 规则自演化（阈值适应/排除规则生成） | `evolution/feedback-log.md` 空 | ⚠️ | 机制设计完善但无运行记录 |
| Holt-Winters/ARIMA/LSTM 时序预测 | lib/ 和 impl/ 均无实现 | ⚠️ | SKILL.md 已标 📌 roadmap，rules/ 未标 |
| Mann-Kendall 趋势检测 | `_shared/rules/trend-detection.md` 描述但 impl/ 无实现 | ⚠️ | 概念文档，非代码承诺 |
| `lib/db.py` 转发 shim → `_shared/lib/db.py` | 实现正确（importlib.util 动态加载） | ✅ | 与 governance 一致 |

---

## 6. SQL/Schema 用表

| 代码中使用的表名 | schema.md 存在? | 操作类型 | 有 deleted=0? | 占位符风格 | 备注 |
|-----------------|----------------|---------|--------------|-----------|------|
| st_rsvr_r | ✅ | SELECT | ❌ (read_sensor_data) | `:days` (text) | |
| st_pptn_r | ✅ | SELECT | ❌ (read_sensor_data) | `:days` (text) | |
| st_pressure_r | ✅ | SELECT | ❌ (read_sensor_data) | `:days` (text) | |
| st_percolation_r | ✅ | SELECT | ❌ (read_sensor_data) | `:days` (text) | |
| dsm_dfr_srvrds_srhrds | ✅ | SELECT | ❌ (read_sensor_data) | `:days` (text) | GNSS 正确表名 |
| rei_gate_r | ✅ | SELECT | ❌ (read_sensor_data) | `:days` (text) | |
| rei_pump_r | ✅ | SELECT | ❌ (read_sensor_data) | `:days` (text) | varchar 字段需 CAST |
| wq_pcp_d | ✅ | SELECT | ❌ (无 deleted 列?) | `:days` (text) | 水质表，使用 `spt` 时间列 |
| st_soil_moisture_r | ✅ | SELECT | ❌ (无 deleted 列?) | `:days` (text) | 墒情表 |
| st_termite_monitor_r | ✅ | SELECT | ❌ (无 deleted 列?) | `:days` (text) | 白蚁表 |
| st_river_r | ✅ | 仅 rules/ 引用 | — | — | impl/ 未直接查询（用 st_rsvr_r 替代） |
| srm_gnss_data_day | ❌ | 白名单 + 内置注册表 | — | — | 幽灵表名（见 High #4） |
| srm_robot_data_day | ❌ | 白名单 + 内置注册表 | — | — | SmartTwinRes 专用，非本部署 |
| srm_illegal_acts | ❌ | 白名单 + 内置注册表 | — | — | SmartTwinRes 专用 |
| ew_camera_info | ✅ | 白名单 | — | — | |
| eq_equip_base | ✅ | SELECT | ✅ | `:param` (text) | |
| eq_equip_defect | ❌ | 白名单 + 内置注册表 | — | — | SmartTwinRes 专用 |
| ew_info_rules | ✅ | SELECT | ✅ | `:param` (text) | 阈值配置 |
| ew_info_message | ✅ | SELECT | ✅ | `:days` (text) | 告警记录 |
| att_st_base | ✅ | SELECT | ✅ | 无参数 | 测站信息 |
| business_check_task | ✅ | SELECT | ✅ | `:param` (text) | 巡检任务 |
| business_check_error | ✅ | SELECT | ✅ | `:days` (text) | 缺陷记录 |
| business_check_route | ✅ | SELECT | 部分 ✅ | `:param` (text) | 巡检路线 |
| business_check_point | ✅ | SELECT | — | `:param` (text) | 巡检点 |
| business_check_result | ✅ | SELECT | — | `:param` (text) | 巡检结果 |
| business_check_obj | ❌ | SELECT | — | `:param` (text) | 巡检对象 |
| business_check_obj_type | ❌ | SELECT | — | `:param` (text) | 对象类型 |
| business_check_obj_type_item | ❌ | SELECT | — | `:param` (text) | 检查项 |
| sys_data_source_registry | ✅ | SELECT | ✅ | 无参数 | 数据源注册表 |
| dsm_cz_info | ✅ (schema §五) | 仅 rules/ 引用 | — | — | GNSS 测点信息 |

---

## 7. untracked 处置建议

inspection/ 目录下所有文件均已 tracked（commit 历史显示最近一批 commit 到 `bf41737`）。无 untracked 文件需要处置。

> **注意**：`impl/__pycache__/` 和 `lib/__pycache__/` 目录存在但已被 `.gitignore` 忽略（预期行为）。`autoresearch/` 目录下的 4 个文件（`eval_criteria.md`、`results.json`、`results.tsv`、`SKILL.md.baseline`）已 tracked。

---

## 8. 正面发现

1. **lib/ 内核层质量高**：`anomaly.py`（379 LOC）、`quality.py`（311 LOC）、`defect_predict.py`（213 LOC）、`route_opt.py`（271 LOC）全部为纯函数设计，类型提示齐全（`Dict[str, Any]`、`List[float]` 等），无副作用，可独立单测。这在 5 个 skill 中独此一家。
2. **lib/ 单测覆盖完整**：4 个测试文件（`test_anomaly.py` 227 LOC、`test_quality.py` 140 LOC、`test_defect_predict.py` 112 LOC、`test_route_opt.py` 107 LOC）覆盖了全部 4 个 lib 内核模块，commit `80141b7` 报告 78 tests PASS。
3. **质量评分公式 doc-code 完美一致**：`lib/quality.py` 的 `_score_completion`/`_score_timeliness`/`_score_defect_rate`/`_score_coverage` 分段评分与 `quality-assessment.md` 逐行对齐（30/25/25/20 满分，A-E 等级阈值完全一致）。
4. **数据源注册表架构创新**：`sys_data_source_registry` + 关键词匹配机制实现了"新增数据源 = INSERT 一条记录，不改代码不改规则"的开闭原则。`registry.py` 有完善的白名单防注入（`_validate_identifiers`）。
5. **lib/db.py shim 设计合理**：通过 `importlib.util` 动态加载 `_shared/lib/db.py`，支持 `POWERELF_SKILLS_ROOT` 环境变量和相对路径双模式，与 governance 保持一致。
6. **SKILL.md 路由表完整**：适用场景 / When NOT to Use / Related Skills / 共享引用（_shared）四节齐全，路由指向明确。
7. **evolution/parameters.md 参数注册表**：所有可调参数（MAD 阈值、突变阈值、趋势阈值、距离阈值、质量权重、任务参数）集中管理，标注当前值、合理范围、对应数据库字段、最后调整日期。
8. **references/ 文档体系完善**：`pitfalls.md`（7 类高频陷阱含❌/✅对照）、`few_shots.md`（8 类 SQL 最佳实践）、`business_rules.md`（13 项状态码溯源字典）、`data-model.md`（11 个巡检业务实体 ER 模型）——文档深度和结构化程度在所有 skill 中最高。
9. **MAD 阈值 doc-code 一致**：`inspection_analyzer.py` 的 `analyze_mad_anomaly()` 使用的 MAD 阈值（水位 3.0、渗压 4.0、渗流 3.0、GNSS 3.5）与 `evolution/parameters.md` 和 `rules/anomaly-and-complex-conditions.md` 完全一致。
10. **lib/anomaly.mad_anomaly() 实现正确**：使用 `median + MAD * 1.4826` 的稳健统计方法，与 `_shared/algorithms/mad.md` 算法一致，含 `min_samples` 守卫和 `mad == 0` 退化处理。
