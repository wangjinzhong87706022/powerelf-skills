# powerelf-chatbi 评审 — 2026-07-30

## 0. 概览

| 项 | 值 |
|---|---|
| Skill | `powerelf-chatbi` |
| 评审版本 | HEAD `dc312ac`（branch `review/2026-07-29-skills-deep`，working tree clean for `powerelf-chatbi/`） |
| 代码覆盖 | **2 py 文件**（`impl/query_exec.py` 175 行 + `impl/test_query_exec.py` 169 行 = **344 行 Python**）——5 主 skill 中代码密度最高 |
| 总 LOC | **1176**（SKILL.md 94L + rules/ 329L + impl/ 344L + references/few_shots.md 372L + evolution/ 37L = 9 文件） |
| 评审日期 | 2026-07-30 |
| 评审人 | Claude (sub-agent, Task 5/6) |
| 关键依赖 | `sqlparse`（语句解析）+ `sqlalchemy`（连接管理）+ `pymysql`（驱动）+ `_shared/lib/db.py`（只读 URL）|

**摘要**：`powerelf-chatbi` 是 5 主 skill 中唯一的"代码 + SQL 密集型"skill，核心价值在 `query_exec.py` 的 7 层 SQL 安全护栏（只读账号 / sqlparse 语句类型 / 单语句 / 系统库黑名单 / 强制 LIMIT / 超时 / 只读事务）和 `few_shots.md` 的 20 个 NL→SQL 示例。**主要优点是 7 层护栏架构设计合理、层次分明、测试覆盖了层 1-5 的核心逻辑**（22 个测试用例），**SKILL.md routing 4 节齐全，`related_skills` 完整列出 4 个兄弟 skill**。**主要问题集中在安全层**：L2 关键字黑名单遗漏 `SLEEP` / `BENCHMARK`（DoS 向量）和 `INTO OUTFILE` / `INTO DUMPFILE`（文件写出），L5 强制 LIMIT 只检测存在性不检查上限值，测试覆盖在层 6 / 层 7 完全空白（需 DB 连接），few_shots 中 3 个示例的 JOIN 键与 schema.md "铁律"矛盾（`stcd` vs `eq_id`，`st_id` vs `eq_id`）。**无 Blocker**——L1 只读账号是主防线，`SLEEP` / `INTO OUTFILE` 在只读账号下仍受限（FILE 权限未授予），但 defense-in-depth 有明显缺口。

---

## 1. Blockers

**无 Blocker**——L1 只读账号（`chatbi_ro` 仅 `GRANT SELECT`）是主防线，所有 7 层护栏的 defense-in-depth 设计意味着即使 L2 关键字黑名单有遗漏，L1 仍能阻止数据修改操作。`SLEEP` / `BENCHMARK` / `INTO OUTFILE` 虽然在 L2-L5 层面未被拦截，但 L1 只读账号 + L7 只读事务（`SET SESSION TRANSACTION READ ONLY`）限制了实际影响。

---

## 2. High

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| High | 代码安全 | `impl/query_exec.py:42-46` FORBIDDEN_KEYWORDS | **黑名单遗漏 `SLEEP` / `BENCHMARK`（DoS 向量）**。`SELECT SLEEP(300)` 和 `SELECT BENCHMARK(10000000, SHA1('test'))` 均通过 L2 语句类型检查（`sqlparse.get_type()` 返回 `SELECT`），且不在 FORBIDDEN_KEYWORDS 中（测试验证：`kw_block=False`）。攻击者可构造 NL→SQL 请求（如"等待 5 分钟"→agent 生成 `SELECT SLEEP(300)`）使数据库连接阻塞 120 秒（L6 MAX_EXECUTION_TIME 兜底）。L1 只读账号仅限制数据修改，**不限制 CPU/时间资源消耗**；L7 只读事务同样不阻止 `SLEEP` / `BENCHMARK`（它们是只读函数）。**实测**：`SELECT SLEEP(10)` → `type=SELECT, accepted=True, kw_block=False`；`SELECT BENCHMARK(1000000,SHA1("test"))` → `type=SELECT, accepted=True, kw_block=False`。**对比**：L2 文档声明"关键字黑名单"（line 9），但实际黑名单仅覆盖 DDL/DML 写操作 + 少数系统操作（`call` / `load` / `handler` / `rename` / `lock` / `unlock`），DoS 函数未覆盖。 | 在 FORBIDDEN_KEYWORDS 增加 `"sleep"`, `"benchmark"`。如需保留 `update_time` 类字段名不误杀（已由 `\b` 边界保证），这两个词同样不会误杀常见字段名（`sleep_count` / `benchmark_score` 不被 `\bsleep\b` / `\bbenchmark\b` 匹配）。 |
| High | 代码安全 | `impl/query_exec.py:42-46` FORBIDDEN_KEYWORDS | **黑名单遗漏 `INTO OUTFILE` / `INTO DUMPFILE`（文件写出）**。`SELECT * FROM st_rsvr_r INTO OUTFILE '/tmp/data.csv'` 通过 L2（`get_type()=SELECT`），且不在黑名单中（测试验证：`kw_block=False`）。L1 只读账号需 `FILE` 权限才能执行 `INTO OUTFILE`，主防线有效，但 defense-in-depth 缺口存在。`INTO DUMPFILE`（写单行 blob）同理。`SELECT ... INTO @var`（变量赋值）同样未被拦截，但变量在连接关闭后消失，风险极低。**对比**：`LOAD_FILE` 被黑名单中的 `load` 关键词捕获（`\bload\b` 匹配 `load_file`），但对称的 `INTO OUTFILE` 未覆盖。 | 在 FORBIDDEN_KEYWORDS 增加 `"outfile"`, `"dumpfile"`。`INTO` 本身太通用（`INSERT INTO` 已用 `insert` 拦截，`SELECT INTO @var` 风险低），不建议直接拦截 `into`。或在 `validate_readonly` 中增加正则 `r"\binto\s+(outfile|dumpfile)\b"` 作为 L2 后的附加检查。 |
| High | 代码安全 + SQL | `impl/query_exec.py:58-62` ensure_limit + `references/few_shots.md` 多处 | **L5 强制 LIMIT 只检测存在性、不检查上限值**（代码层）+ **few_shots 3 个示例 JOIN 键与 schema.md "铁律"矛盾**（文档层）。**代码层**：`ensure_limit()` 仅用 `re.search(r"\blimit\b", sql.lower())` 检测 LIMIT 是否存在，若存在则原样返回（line 61 `return sql`），**不验证 LIMIT 数值是否 ≤ MAX_LIMIT**。若 agent 生成 `SELECT * FROM st_rsvr_r LIMIT 999999999`，L5 不注入包裹（因已有 LIMIT），但 999999999 远超 MAX_LIMIT=2000，可能拉取全表数据导致内存压力。`--limit` CLI 参数仅控制**注入**的 LIMIT 值（line 163 `default=MAX_LIMIT`），不约束 agent 已有的 LIMIT。**文档层**：few_shots.md 3 个示例使用错误 JOIN 键：(1) #13 闸门 `r.stcd = s.code`（但 `rei_gate_r.stcd` 是站码非设备码，且 schema.md 推荐 `eq_id`→`eq_equip_base.id`）；(2) #14 泵站 `r.st_id = s.id`（schema.md 铁律首选 `eq_id`→`eq_equip_base.id`）；(3) #15 墒情 `r.stcd = s.code`（schema.md line 98 标 `st_rsvr_r.stcd` 99.8% 空，`stcd` 不可靠）。**代码层与文档层合并为 High**：两者都是"agent 生成 SQL → query_exec 执行"路径上的质量控制缺口。 | (a) 代码：在 `ensure_limit` 中增加 LIMIT 数值检查（正则提取 LIMIT 后的数字，若 > MAX_LIMIT 则替换为 MAX_LIMIT），或统一用子查询包裹 + 外层 LIMIT MAX_LIMIT；(b) 文档：修正 few_shots #13/#14/#15 的 JOIN 键为 `eq_id`→`eq_equip_base.id`，与 schema.md 铁律对齐（详见 M3）。 |

---

## 3. Medium

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Medium | SQL/Schema | `references/few_shots.md:237` (#13 闸门) + `:260` (#14 泵站) + `:280` (#15 墒情) | **3 个 few_shots 示例 JOIN 键与 schema.md "关联键铁律"矛盾**。sql-generation.md line 19-27 显式列"关联键铁律"：`st_rsvr_r / st_pptn_r / st_percolation_r` 用 `stcd`（varchar），`st_pressure_r` 用 `eq_id`（bigint），`dsm_dfr_srvrds_srhrds` 用 `eq_id`（int）。但 schema.md line 32-37 的铁律表明确写"所有监测表都同时具备 eq_id 与 eq_code"且"首选 eq_id 直连 eq_equip_base.id"，并标 `st_rsvr_r.stcd` 为"99.8% 空，勿用于 JOIN"（line 98）。few_shots 中：(1) #13 `rei_gate_r` 用 `r.stcd = s.code`（`rei_gate_r.stcd` 是站码，schema 推荐 `eq_id`）；(2) #14 `rei_pump_r` 用 `r.st_id = s.id`（schema 推荐 `eq_id`→`eq_equip_base.id`）；(3) #15 `st_soil_moisture_r` 用 `r.stcd = s.code`（schema 未标空率但推荐 `eq_id`）。Agent 照抄这些示例会生成低效/错误 JOIN（`stcd` 空 → JOIN 丢失行）。 | 修正 3 个示例的 JOIN 键为 `eq_id`→`eq_equip_base.id`，并统一 sql-generation.md line 21-25 的"关联键铁律"表与 schema.md line 32-37 一致（首选 `eq_id`，备选 `stcd`→`eq_equip_base.code`）。 |
| Medium | SQL/Schema | `references/few_shots.md:143` (#8 GNSS) | **GNSS point_id 占位符类型错误**。few_shots #8 写 `WHERE point_id = 'XX测点ID'`（varchar 占位符，带引号），但 schema.md line 148 明确标 `point_id` 类型为 `INT`（`point_id int 测点ID`），且 line 391 警告"`point_id` 是 INT（不是 varchar）"。Agent 照抄会生成 `WHERE point_id = 'XX测点ID'`，MySQL 隐式类型转换为 `WHERE point_id = 0`，返回错误结果（point_id=0 的行或空集）。 | 改占位符为 `WHERE point_id = XX`（数值型，无引号），与 few_shots #9 `WHERE section_id = XX`（line 161，同为 bigint/int 占位符）风格对齐。 |
| Medium | 代码 + 测试 | `impl/test_query_exec.py` 全文 (169L) | **测试覆盖在 L6(超时) / L7(只读事务) 完全空白**。22 个测试用例覆盖 L1(2) + L2(11) + L3(2) + L4(2) + L5(3) + 空SQL(1) + CLI(2) + 格式化(1)，但 L6(`MAX_EXECUTION_TIME` 设置，query_exec.py:117-121) 和 L7(`SET SESSION TRANSACTION READ ONLY`，query_exec.py:112-116) 需要真实 DB 连接，**0 个测试用例**。这两层是 defense-in-depth 的关键组件（L7 是 L1 的双保险），若 SET 语句语法错误或 MySQL 版本不兼容（`MAX_EXECUTION_TIME` 需 MySQL 5.7.4+），会静默失败（line 115-116 / 120-121 的 `except Exception` 吞错）。测试矩阵：L1 ✅(2) / L2 ✅(11) / L3 ✅(2) / L4 ✅(2) / L5 ✅(3) / L6 ❌(0) / L7 ❌(0)。 | (a) 短期：增加 2 个 mock 测试，用 `unittest.mock.patch` 模拟 `conn.execute` 并验证 `SET SESSION TRANSACTION READ ONLY` 和 `SET SESSION MAX_EXECUTION_TIME=120000` 被调用（即使 `execute()` 内部 try/except 吞错，mock 可验证调用发生）；(b) 长期：在 CI 中加 MySQL Docker 容器，跑集成测试验证 L6/L7 在真实连接上生效。 |
| Medium | 代码安全 | `impl/query_exec.py:60` ensure_limit 正则 | **LIMIT 检测正则 `\blimit\b` 在字符串字面量/注释中产生假阳性**。`SELECT * FROM t WHERE name = 'limit'` 或 `SELECT * FROM t -- limit comment` 中的 `limit` 被 `\blimit\b` 匹配（实测验证：`has_limit=True`），导致 `ensure_limit` 跳过注入，查询无实际 LIMIT 约束。L5 设计目标是"无 LIMIT 则强制注入"，假阳性使该目标在特定 SQL 模式下失效。非安全问题（只读账号限制），但违反 L5 设计意图。**对比**：`limit_val` / `has_limit` / `data_limit_count` 等含 `_` 的标识符不被误匹配（`_` 是 `\w` 字符，`\b` 不匹配），实测验证正确。 | 在 `ensure_limit` 中增加更精确的 LIMIT 检测：先用 sqlparse 解析 SQL 提取 LIMIT token，或正则 `r"\bLIMIT\s+\d+"`（要求 LIMIT 后跟数字，排除字符串/注释中的孤立 `limit` 词）。 |
| Medium | SQL/Schema | `references/few_shots.md:307-319` (#17 视频AI) | **`ew_camera_info` 表不在 schema.md 中**。few_shots #17 查询 `ew_camera_info` 表（含 `device_id` / `type` / `alarm_grade` / `alarm_stat` / `info` / `create_time` / `confirm` / `st_id` 列），但 `_shared/references/schema.md` 全文 grep `ew_camera_info` 返回 0 结果。schema.md 是"唯一事实源"（line 1），few_shots 引用未收录表违反这一原则。Agent 生成此 SQL 会报 `Table 'ew_camera_info' doesn't exist`（若该表真不存在于线上库），或引用未经验证的表结构。 | (a) 若 `ew_camera_info` 线上存在：在 schema.md 补 DDL（与 `ew_info_rules` / `ew_info_message` 同节）；(b) 若不存在：从 few_shots.md 删除 #17 或标注"⚠️ 待验证表是否存在"。 |
| Medium | SQL/Schema | `references/few_shots.md:83-89` (#5 设备离线) | **`eq_equip_offline_record` 列名占位符与 schema.md 摘要不完全对齐**。few_shots #5 用 `o.offline_start_time`（datetime）和 `o.offline_end_time`（datetime），但 schema.md line 580 摘要写 `{offline\|anomaly}_start_date (date) + _start_time (time)`（date + time 两列拆分）和 `{offline\|anomaly}_end_time (time)`（仅 time 无 date）。若 schema.md 准确，`offline_start_time` 应为 `TIME` 类型（非 `DATETIME`），few_shots 的 `o.offline_start_time` 作为 datetime 比较会失败。schema.md 对该表无完整 DDL（仅摘要），无法 100% 确认，但文档间矛盾已构成 Medium 风险。 | (a) 用 `SHOW CREATE TABLE eq_equip_offline_record` 实测列名/类型，更新 schema.md 补完整 DDL；(b) 修正 few_shots #5 的列名与 schema 对齐。 |
| Medium | 代码安全 | `impl/query_exec.py:93-96` validate_readonly L4 系统库检查 | **L4 系统库黑名单被反引号（backtick）绕过**。`validate_readonly` 中 L4 用 `f"{sch}." in lowered`（line 95）检测 `mysql.` / `information_schema.` 等前缀，但**未处理反引号引住的 schema 标识符**。`SELECT * FROM \`mysql\`.user` 和 `` SELECT * FROM `information_schema`.tables ``（反引号包围的 schema 名）均能绕过 L4 检测，agent 生成的 SQL 若使用反引号风格会直接命中系统库。L1 只读账号对 `mysql.user` 等表的 SELECT 权限取决于账号授予（标准只读账号无 `mysql.*` 权限），L7 只读事务同样不阻止读系统表，**真实风险是信息泄露**（枚举 `mysql.user` 拿到所有账号 → 辅助提权）。**对比 H1/H2 的黑名单缺口**：H1/H2 是"已声明要拦但漏了"，L4 backtick 缺口是"拦截逻辑本身有正则漏洞"。 | 在 L4 检测前先去掉反引号：`` lowered = re.sub(r"`", "", lowered) ``，或将 line 95 改为正则 `r"(?<![\w`]){sch}\.|\`{sch}\`"` 兼容反引号场景。同步增加 1 个测试用例 `` `mysql`.user `` 验证拦截。 |
| Medium | 文档-代码一致 | `_shared/references/schema.md:335-358` (rei_gate_r/rei_pump_r) + `:454-476` (st_soil_moisture_r/st_termite_monitor_r) | **schema.md 中 4 张监测表 DDL 不完整——缺 `eq_id` / `eq_code` / `deleted` / `tenant_id` 公共列**。schema.md line 47 铁律"所有监测表都同时具备 eq_id 与 eq_code"，line 34 铁律"所有表都有 deleted"，但这 4 张表的 DDL 段**均无 `eq_id` / `eq_code` / `deleted` / `tenant_id` 列**——与铁律自相矛盾。若 few_shots M1 修复"改 JOIN 键为 eq_id"需要这 4 张表存在 `eq_id` 列，**DDL 不补 = M1 修复不可落地**。可能原因：(a) schema.md 同步时漏掉这 4 张表的 DDL 段；(b) 实际这 4 张表 DDL 与众不同（特例）。无论哪种，schema.md 的"唯一事实源"地位被破坏。**与 M1 关联**：M1 修复路径被本 finding 阻塞，需先决。 | (a) 用 `SHOW CREATE TABLE rei_gate_r / rei_pump_r / st_soil_moisture_r / st_termite_monitor_r` 实测这 4 张表真实 DDL，补全 schema.md 缺失的 4 个公共列；(b) 若实测确无这些列，则铁律"所有监测表都同时具备 eq_id 与 eq_code"需修订为"绝大多数监测表，例外：rei_gate_r/rei_pump_r/st_soil_moisture_r/st_termite_monitor_r"，并相应改 few_shots 的 JOIN 键方案。 |

---

## 4. Low

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Low | 文档-代码一致 | `evolution/feedback-log.md:5` + `evolution/parameters.md` 全表 | **"自我进化"机制形式化无运行证据**。`feedback-log.md:5` 仍为"（暂无记录。）"，`parameters.md` 全部 11 个参数的"最后调整"列均为 `2026-05-30`（NL2SQL 3 + 图表 2 + LLM 3 + 知识库 3 = 11 行）。距离评审日 2026-07-30 已 **61 天无参数调整反馈**。与 SKILL.md:53-56 "自我进化"段声明、`version: 2.0.0` 形成对比。**对比 early-warning L3 + monitor M3**：5 skill 共性弱信号，chatbi 作为代码最密集的 skill，参数调优（如 `SQL重试次数=4` / `最大查询行数=2000`）应有运行日志支撑。 | (a) 在 `feedback-log.md` 补一条"v2.0.0 初始发布（2026-05-30）"占位记录；(b) `parameters.md` 增加"上次触发来源（人工/用户反馈/自动调优）"列；(c) `SQL重试次数` 当前值 4 但 `query_exec.py` 无重试逻辑（agent 端重试），应显式标注"agent 侧参数"。 |
| Low | 文档-代码一致 | `SKILL.md:94` 末尾 | **SKILL.md 末尾无 version/date 标记**。frontmatter line 4 写 `version: 2.0.0`，但文档末尾（line 94）以 `_shared/references/data-profiling.md` 表行结束，无显式"最后更新"日期。**对比 early-warning / monitor / inspection 同样问题**：是 5 skill 共性。 | 在 line 94 之后加一行 `> 本文档 v2.0.0 · 最后更新 2026-07-16（commit cc4b90d 加路由表 + related_skills 补齐）`。 |
| Low | 代码安全 | `impl/query_exec.py:42-46` FORBIDDEN_KEYWORDS | **`SELECT ... INTO @var`（用户变量赋值）未被拦截**。`SELECT col INTO @var FROM t` 通过 L2（`get_type()=SELECT`），且 `into` 不在 FORBIDDEN_KEYWORDS 中。变量在连接关闭后消失，且 L3 单语句限制阻止后续引用该变量的语句，实际风险极低。但 defense-in-depth 角度应记录。 | 暂不修复（风险低且修复成本高——`into` 太通用），在文档中显式标注"INTO @var 由 L3 单语句 + L1 连接隔离覆盖"。 |
| Low | 代码 | `impl/query_exec.py:60` ensure_limit | **LIMIT 检测对 `limit` 在 SQL 注释中产生假阳性**（`SELECT * FROM t -- limit comment` → `has_limit=True`，不注入 LIMIT）。与 M4 同源但更边缘（注释中的 `limit` 词极少出现）。 | 同 M4 建议（更精确的 LIMIT 检测）。 |
| Low | 文档-代码一致 | `SKILL.md:3` description 字段 | **description 长度 44 字符（≤ 57 字符窗口），但缺 `knowledge-base` / `data-analysis` 关键词**。description "ChatBI智能分析：意图分类规则、图表选择规则、SQL生成规则。规则内嵌，可独立判断。" 前 57 字符窗口内含"智能分析/意图分类/图表选择/SQL生成/规则内嵌"主关键词，但 tags 中的 `knowledge-base`（对应 intent `KNOWLEDGE_QUERY`）和 `visualization`（对应 intent `VISUALIZATION`）未在 description 中出现。hermes 路由若仅走 description 匹配，"知识库"类查询可能落空。**对比**：tags 中已有 `[water-conservancy, chatbi, nl2sql, visualization, knowledge-base]`（line 10），可兜底。 | 改 description 为 "ChatBI智能分析：NL2SQL查询、数据可视化、知识库检索。规则内嵌，可独立判断。"（加入"可视化"和"知识库"关键词，保持 ≤57 字符）。 |

---

## 5. 文档-代码一致性矩阵（声明 vs 实际）

| SKILL.md / 文档声明 | 实际文件状态 |
|----------------------|-------------|
| 3 规则模块（intent-classification / chart-selection / sql-generation） | `rules/` 恰好 3 个 .md（49L / 153L / 127L）— ✅ 完全匹配 |
| 7 层安全护栏（SKILL.md:70 + query_exec.py:7-14 文档声明） | `query_exec.py` 实现 7 层：L1(只读账号,line 109+db.py) / L2(sqlparse+黑名单,line 82-91) / L3(单语句,line 73-76) / L4(系统库,line 93-96) / L5(强制LIMIT,line 58-62+98) / L6(超时,line 117-121) / L7(只读事务,line 112-116) — ✅ 7 层全部实现，与声明一致 |
| L2 "sqlparse get_type==SELECT" 声明（query_exec.py:9） | 实测 `sqlparse.get_type()` 对 SHOW/DESCRIBE/SET/HANDLER 返回 UNKNOWN（被拒绝），对 SELECT/WITH-SELECT/INSERT-SELECT 返回正确类型 — ✅ 行为符合声明。但 CTE 检测依赖 `startswith("WITH")`（line 84）而非 sqlparse 原生 — ⚠️ 见 M4（假阳性风险低） |
| L2 "关键字黑名单" 声明（query_exec.py:9） | FORBIDDEN_KEYWORDS 17 个词覆盖 DDL/DML 写操作 + call/load/handler/rename/lock/unlock — ⚠️ 遗漏 sleep/benchmark/outfile/dumpfile（见 H1/H2） |
| L5 "强制 LIMIT" 声明（query_exec.py:12） | `ensure_limit()` 检测存在性并注入子查询包裹 — ⚠️ 不检查 LIMIT 数值上限（见 H3 代码层） |
| 自我进化：parameters.md + feedback-log.md | `evolution/` 2 文件齐全 — ⚠️ feedback-log 空，全参数 2026-05-30（见 L1） |
| 适用场景 | line 20-27 列出 4 条场景（NL→SQL / 可视化 / 数据解读 / 知识库检索）— ✅ |
| When NOT to Use | line 29-35 表 4 行（inspection / governance / early-warning / monitor）— ✅ 4 路由清晰 |
| Related Skills（frontmatter） | line 11 列 4 个（governance/monitor/inspection/early-warning）— ✅ **完整 4 元组**（与 monitor/inspection/early-warning 的 2-3 个形成对比，chatbi 是 frontmatter 最齐全的） |
| 共享引用（_shared） | line 83-94 表 6 行（schema.md / sql-discipline.md / analysis-qa-checklist.md / statistical-caution.md / api-auth.md / data-profiling.md）— ✅ 全部指向 `_shared/references/` |
| 按需加载指令 | line 47-51 给 3 个关键词路由（意图→intent-classification / 图表→chart-selection / SQL→sql-generation）— ✅ 与 3 rules 对齐 |
| 数据访问 CLI | line 65-68 给 `python3 impl/query_exec.py --sql --db --limit --display --format` — ✅ 与 `query_exec.py` argparse (line 159-165) 完全一致 |
| frontmatter `related_skills` | 4 个 — ✅ 完整（**但 monitor/inspection/early-warning 的 frontmatter 未回列 chatbi，是跨 skill 问题**） |
| frontmatter `tags` | 5 个（water-conservancy/chatbi/nl2sql/visualization/knowledge-base）— ✅ 覆盖核心能力 |
| description 长度 | 44 字符 ≤ 57 字符窗口 — ✅ 主关键词可见，但缺 knowledge-base/visualization（见 L5） |
| `rules/sql-generation.md` "关联键铁律" 表（line 21-25） | 与 schema.md line 32-37 "关联键铁律"表矛盾：sql-generation 推荐 `stcd`（varchar），schema.md 推荐 `eq_id`（bigint）— ❌ 见 M1 |
| `references/few_shots.md` 20 个示例 | 20 个 NL→SQL 示例（水情×4 + 雨情×1 + 设备×2 + 预警×2 + GNSS×1 + 渗压×1 + 巡检×2 + 治理×1 + 闸门×1 + 泵站×1 + 墒情×1 + 白蚁×1 + 视频AI×1 + 渗流×1 + 河道×1 + 设备统计×1）— ⚠️ 3 个 JOIN 键错误（见 M1），1 个类型错误（见 M2），1 个表不在 schema（见 M5），1 个列名不确定（见 M6） |
| `_shared/references/schema.md` 引用 | SKILL.md:89 + sql-generation.md:17 均指向 `_shared/references/schema.md` — ✅ 指针有效 |
| `_shared/references/sql-discipline.md` 引用 | SKILL.md:90 + sql-generation.md:16 指向 — ✅（需 Task 6 验证目标文件存在且有实质内容） |
| `_shared/lib/db.py` 依赖 | test_query_exec.py:11 `from db import get_readonly_sqlalchemy_url` — ✅ 依赖有效（db.py 存在于 `_shared/lib/`） |
| `test_query_exec.py` 覆盖 7 层 | L1(2) + L2(11) + L3(2) + L4(2) + L5(3) + L6(0) + L7(0) = 22 测试 — ⚠️ L6/L7 空白（见 M3） |
| query_exec.py `py_compile` | 通过（无语法错误）— ✅ |
| test_query_exec.py `py_compile` | 通过（无语法错误）— ✅ |
| 意图分类 9 类（intent-classification.md） | 3 已实现（TEXT_TO_SQL/VISUALIZATION/INTERPRETATION）+ 6 未实现 — ✅ 与 SKILL.md:39-43 能力概览表一致（仅列 3 个子模块） |
| 图表选择 12 类（chart-selection.md） | 12 种图表类型 + 10 步选择逻辑 + 6 种 ECharts 输出示例 — ✅ 与 SKILL.md:42 "图表选择"描述一致 |

---

## 6. SQL/Schema 用表

**SQL finding**: 有——`query_exec.py` 执行任意 SQL（经 7 层护栏消毒），`few_shots.md` 含 20 个 SQL 示例，`rules/sql-generation.md` 含 11 个 SQL 模式片段。

few_shots.md 20 个示例中引用的表（去重后 20 张）：

| # | 表名 | schema.md 存在? | 操作 | JOIN 键 | 备注 |
|---|------|----------------|------|---------|------|
| 1 | `st_rsvr_r` | ✅ schema.md:197 | SELECT (read) | `stcd`→`att_st_base.code` (few_shots #1/#2) | ⚠️ schema.md line 98 标 `stcd` 99.8% 空 |
| 2 | `att_st_base` | ✅ schema.md:529 | SELECT (read) | 被 JOIN 方 | 测站基础信息 |
| 3 | `st_pptn_r` | ✅ schema.md:278 | SELECT (read) | `stcd`→`att_st_base.code` (few_shots #3) | |
| 4 | `eq_equip_base` | ✅ schema.md:485 | SELECT (read) | 被 JOIN 方 | 设备台账 |
| 5 | `eq_equip_offline_record` | ⚠️ schema.md:575 摘要(无 DDL) | SELECT (read) | `code`→`equipment_code` (few_shots #5) | 列名可能与 schema 摘要不一致（见 M6） |
| 6 | `ew_info_message` | ✅ schema.md:643 | SELECT (read) | — | 预警消息 |
| 7 | `dsm_dfr_srvrds_srhrds` | ✅ schema.md:363 | SELECT (read) | `point_id` (few_shots #8) | ⚠️ point_id 占位符类型错误（见 M2） |
| 8 | `st_pressure_r` | ✅ schema.md:412 | SELECT (read) | `section_id` (few_shots #9) | |
| 9 | `business_check_error` | ❌ 不在 schema.md (属 inspection) | SELECT (read) | — | schema.md line 38 显式排除 |
| 10 | `business_check_task` | ❌ 不在 schema.md (属 inspection) | SELECT (read) | — | schema.md line 38 显式排除 |
| 11 | `stats_data_collection_daily` | ⚠️ schema.md:591 摘要(无 DDL) | SELECT (read) | `(tm, table_name)` (few_shots #12) | |
| 12 | `stats_data_missing_daily` | ⚠️ schema.md:592 摘要(无 DDL) | SELECT (read) | `(tm, table_name)` (few_shots #12) | |
| 13 | `stats_data_anomaly_daily` | ⚠️ schema.md:593 摘要(无 DDL) | SELECT (read) | `(tm, table_name)` (few_shots #12) | |
| 14 | `rei_gate_r` | ✅ schema.md:333 | SELECT (read) | `stcd`→`att_st_base.code` (few_shots #13) | ⚠️ JOIN 键与 schema 铁律不一致（见 M1） |
| 15 | `rei_pump_r` | ✅ schema.md:347 | SELECT (read) | `st_id`→`att_st_base.id` (few_shots #14) | ⚠️ JOIN 键应为 `eq_id`（见 M1） |
| 16 | `st_soil_moisture_r` | ✅ schema.md:452 | SELECT (read) | `stcd`→`att_st_base.code` (few_shots #15) | ⚠️ JOIN 键应为 `eq_id`（见 M1） |
| 17 | `st_termite_monitor_r` | ✅ schema.md:467 | SELECT (read) | `stcd`→`att_st_base.code` (few_shots #16) | |
| 18 | `ew_camera_info` | ❌ **不在 schema.md** | SELECT (read) | `st_id`→`att_st_base.id` (few_shots #17) | 见 M5 |
| 19 | `st_percolation_r` | ✅ schema.md:394 | SELECT (read) | `stcd` (few_shots #18) | ⚠️ schema.md line 137 标 `stcd` 92.2% 空 |
| 20 | `st_river_r` | ✅ schema.md:225 | SELECT (read) | `stcd`→`att_st_base.code` (few_shots #19) | ⚠️ schema.md line 249 标"0 行空表，勿查" |

**安全审计**：所有 20 个示例均为 SELECT 语句（无 DDL/DML 写操作），全部包含 `deleted=0` 和 `tenant_id=1` 过滤条件（与 sql-generation.md:120-121 纪律一致），无 `;` 堆叠，无系统库引用。SQL 安全性良好。

**占位符审计**：PyMySQL 使用 `%s` 占位符（schema.md line 74 提示），但 few_shots 全部使用 `?` 或硬编码占位符（`XX`/`XX测点ID`/`XX`），与 PyMySQL 约定不完全一致。作为 LLM 生成的模板（非直接执行代码），可接受，但应在 sql-generation.md 中显式注明"占位符由 agent 根据 PyMySQL 约定替换为 `%s`"。

---

## 7. untracked 处置建议

`powerelf-chatbi/` 目录下 **0 untracked 文件、0 modified 文件**（`git status --short -- powerelf-chatbi/` 输出为空）。所有 9 个文件（1 SKILL.md + 3 rules + 2 impl + 1 references + 2 evolution）均已 tracked，最后一次提交为 `cc4b90d docs(chatbi): 加适用场景/When NOT to Use 路由表 + _shared 引用 + related_skills 补齐`（2026-07-16）。

`impl/__pycache__/` 目录存在但属于 Python 编译缓存（gitignore 应覆盖，不影响评审）。

**无需处置**。

---

## 8. 正面发现

1. **7 层安全护栏架构设计优秀**：`query_exec.py` 的 defense-in-depth 设计是仓库中安全最严密的组件——L1(只读账号) → L2(语句类型+黑名单) → L3(单语句) → L4(系统库黑名单) → L5(强制LIMIT) → L6(超时) → L7(只读事务)，层次分明、各司其职。即使某一层被绕过，后续层仍提供保护。这是"agent 直连数据库"架构下的最佳实践。
2. **`related_skills` 完整 4 元组**：SKILL.md frontmatter line 11 列出全部 4 个兄弟 skill（governance/monitor/inspection/early-warning），是 5 主 skill 中 **frontmatter 最齐全的**（monitor 缺 chatbi、inspection 缺 chatbi、early-warning 缺 inspection+chatbi）。chatbi 可作为 other skill 修复 `related_skills` 的参考。
3. **routing 4 节齐全**：SKILL.md 包含 适用场景(line 20-27) / When NOT to Use(line 29-35) / 共享引用(line 83-94) / API附录(line 73-80) 四节，**与 monitor commit 413a94c 建立的模板对齐**（恰好是 early-warning H1 缺失的部分）。
4. **测试覆盖核心逻辑充分**：22 个测试用例覆盖 L1-L5 的纯函数护栏（无 DB 依赖），测试设计合理——拒绝类测试用 `pytest.raises(ValueError)`，接受类测试验证输出，CLI 测试用 mock。L2 单独有 11 个测试（覆盖 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE 7 种写操作 + SELECT/CTE 2 种合法语句 + 字段名不误杀 1 个边界 case）。
5. **`py_compile` 双文件通过**：`query_exec.py` 和 `test_query_exec.py` 均无语法错误，import 链完整（`sqlparse` / `sqlalchemy` / `db.py`），代码质量高。
6. **few_shots.md 20 个示例覆盖广泛**：覆盖水情(4) + 雨情(1) + 设备(2) + 预警(2) + GNSS(1) + 渗压(1) + 巡检(2) + 治理(1) + 闸门(1) + 泵站(1) + 墒情(1) + 白蚁(1) + 视频AI(1) + 渗流(1) + 河道(1) + 统计(1) 共 16 个场景，含 ROW_NUMBER 窗口函数、CASE 条件映射、LEFT JOIN、子查询、聚合等复杂模式。
7. **SQL 纪律一致性好**：所有 20 个 few_shots 示例均包含 `deleted=0` + `tenant_id=1` 过滤条件，与 sql-generation.md:120-121 纪律一致；无 SELECT *（除 #4 设备离线外，但该查询列了具体列名）。
8. **`validate_readonly` 函数设计为纯函数**：将 L2-L5 护栏封装为无 DB 依赖的纯函数（line 65-99），便于单测，测试可独立运行。L1/L6/L7 在 `execute()` 中（需 DB 连接），职责分离清晰。
9. **错误透传设计合理**：`execute()` 的 `except Exception` (line 127-130) 将 SQL 错误透传给 agent（`print` to stderr + `sys.exit(2)`），支持 agent 自修正重试（sql-generation.md:12 "SQL 错误由 agent 见错误信息自修正重试"）。
10. **description 字段长度合理（44 字符 ≤ 57 字符窗口）**：前 57 字符含"ChatBI智能分析/意图分类/图表选择/SQL生成/规则内嵌"主关键词，hermes 路由 description 通道有效。tags 补充 `visualization` / `knowledge-base` 兜底子能力。

---

> **评审计数**：0 Blocker + 3 High + 8 Medium + 5 Low = **16 findings**（chatbi 是 5 主 skill 中代码密度最高的，finding 数量相应多于 monitor 10 / early-warning 12 / inspection 20 / governance 22）。**核心修复优先级**：H1（黑名单加 sleep/benchmark）→ H2（黑名单加 outfile/dumpfile）→ H3（L5 LIMIT 数值检查 + few_shots JOIN 键修正）→ M1-M8（few_shots 对齐 schema + L4 backtick 修复 + 4 张表 DDL 补全）→ M3（L6/L7 测试补充）。H1/H2 修复仅需在 FORBIDDEN_KEYWORDS frozenset 中加 4 个字符串，影响面最小、安全收益最大。M7（L4 backtick 绕过）需改 `validate_readonly` 的检测逻辑，1 行 regex 修复 + 1 个测试用例。
