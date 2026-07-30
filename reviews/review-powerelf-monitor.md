# powerelf-monitor 评审 — 2026-07-30

## 0. 概览

| 项 | 值 |
|---|---|
| Skill | `powerelf-monitor` |
| 评审版本 | HEAD `12abfd5`（branch `review/2026-07-29-skills-deep`，working tree clean for `powerelf-monitor/`） |
| 代码覆盖 | **0 py 文件 / 0 sql 文件**（纯文档 skill：1 SKILL.md 138 行 + 5 rules/*.md 29 行 + 3 algorithms/*.md 23 行 + 2 evolution/*.md 45 行 = 11 md，~235 LOC；所有逻辑下沉到 `_shared/rules/` 和 `_shared/algorithms/`） |
| 总 LOC | ~235（md only，文件数 5+3+2+1=11，与 SKILL.md 声明 "5 规则 + 3 算法 + 自我进化" 一致） |
| 评审日期 | 2026-07-30 |
| 评审人 | Claude (sub-agent, Task 4/6) |

**摘要**：`powerelf-monitor` 是仓库 5 个主 skill 中体量最小的之一（0.2k LOC 纯文档），设计上"规则内嵌、按需加载、自我进化"三件套与 governance / early-warning / inspection 同源。**主要优点是 routing 4 节（适用场景/When NOT to Use/Related Skills/共享引用 _shared）齐全**（这一点恰好是 early-warning H1 缺失的部分，monitor 在 commit `413a94c` "加适用场景/When NOT to Use 路由表 + _shared 引用节" 已显式补齐）；与 `powerelf-inspection` 的"实时/离线"分工段（line 135-137）写得清晰且对偶；5 个 rules 指针全部指向 `_shared/` 内有实质内容的目标文件（最早 1.3k、最新 4.3k 字节），`413a94c` 的重构无"断链"。**主要问题集中在 SKILL.md 内表层不一致（"12类监测" vs 实际 14 行；frontmatter `related_skills` 缺 chatbi 但 body "When NOT to Use" 有）以及"自我进化"机制形式化（feedback-log 仍为空、parameters.md 全 2026-05-30 无运行证据）**。无 Blocker，无代码安全问题（无代码可评），无 SQL 注入面（无 SQL）。**与 early-warning H1（路由表缺失）对称的是，本 skill 路由表结构本身是好的，但 frontmatter ↔ body 之间存在小不一致**。

---

## 1. Blockers

**无 Blocker**（无 Python 代码可评，无 SQL 可评，无运行时可触发严重故障；所有 logic 已下沉到 `_shared/`，由 Task 6 重点评审）。

---

## 2. High

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| High | 架构 | `SKILL.md:11` frontmatter `metadata.hermes.related_skills` vs `:30-35` body "When NOT to Use" 表 | **frontmatter `related_skills` 缺 `powerelf-chatbi`**。frontmatter line 11 声明 `related_skills: [powerelf-data-governance, powerelf-early-warning, powerelf-inspection]`（3 个），但 body "When NOT to Use" 表 line 30-35 显式列出 inspection / governance / early-warning / **chatbi**（4 个）。这是一处 frontmatter ↔ body 不一致：`powerelf-chatbi` 在"5 主 skill 生态"中是事实存在的伙伴（与 monitor 同样消费 st_* 表 + REST API），monitor 的"实时看盘"↔ chatbi 的"纯查询"是天然的分工边界，但 frontmatter 漏写会导致 hermes routing 在"依赖元数据"通道错过这一指针。**对比 early-warning sub-report H1 + §5 行 72**：early-warning 的 frontmatter `related_skills` 也只列 2 个（governance + monitor），同样漏 inspection + chatbi——这是一个跨 skill 的系统性问题，monitor 与 early-warning 是同病相怜。 | 在 frontmatter `related_skills` 追加 `powerelf-chatbi`（形成完整 4 元组：`[powerelf-data-governance, powerelf-early-warning, powerelf-inspection, powerelf-chatbi]`），与 body "When NOT to Use" 表对齐。这是 hermes 路由的关键元数据，不应漏。 |

---

## 3. Medium

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Medium | 文档-代码一致 | `SKILL.md:25, 37, 39, 51, 59, 67, 73, 81-94` | **"12类监测"与"12大监测类型"声明 vs 实际 14 行**。SKILL.md line 25（"适用场景"第 3 条）"实时 12 类监测分析"、line 37 "## 12大监测类型" 标题、line 73-76 "趋势异常检测 / 水位变化率算法 / 位移速率算法 / 时序预测算法" 4 个跨表引用。但实际行计数：水文气象 7（水库/河道/闸站/潮汐/雨情/分区雨情/防洪区）+ 设备工情 2（闸门/泵站）+ 大坝安全 3（GNSS/渗流/渗压）+ 其他 2（墒情/白蚁）= **14 行**，且 line 81-94 "按需加载指令" 也有 14 个关键词组（不含"趋势"和"预测"这两个横切算法）。doc-doc 不一致：Agent 看到 "12 类" 可能漏处理 河道水情/潮汐水情/防洪区水情/渗流量/渗压/白蚁 这 6 个未在 frontmatter 路由中的类别。 | 改 "12 类" 为 "14 类"（或在 12 类之下标 "核心 12 + 扩展 2"，与 line 47-49 防洪区水情、line 64 渗压、line 71 白蚁 等次要类别显式区分）。 |
| Medium | 架构 | `SKILL.md:124-133` "## 共享引用（_shared）" 段 | **"共享引用" 段未列 `reservoir-analysis`**。line 132 写 `_shared/rules/ 闸门/泵站/GNSS/雨情/趋势规则（单一事实源）`，**5 个 rules 中只提了 4 个**（漏 "水库"）。`rules/reservoir-analysis.md`（line 1-7）明确声明 "monitor / inspection 原各自一份，逐字相同，已合并为跨 skill 单一事实源"，与 line 43 表 "水库水情 \| st_rsvr_r \| ... \| `rules/reservoir-analysis.md`" 形成 SKILL.md 自身内的引用闭环。**当前 line 132 的描述对 reservoir 是"漏挂"**——若按"按需加载"逻辑，Agent 读 line 132 会以为"水库"规则不在 `_shared/` 里，可能回退到 `monitor/rules/reservoir-analysis.md`（只是一个 7 行指针），浪费一次跳转。 | line 132 改为 `闸门/泵站/GNSS/雨情/水库/趋势规则（单一事实源）`，保持 5 类齐全；或在段头加一句"完整 5 类规则见 `powerelf-monitor/rules/` 目录树"。 |
| Medium | 架构 | `evolution/feedback-log.md:9` + `evolution/parameters.md` 全表 | **"自我进化"机制形式化无运行证据**。`feedback-log.md:9` 仍为 "（暂无记录。）"，所有 15 个数据行参数的"最后调整"列都是 `2026-05-30`（水库 4 / 雨情 4 / GNSS 3 / 闸门泵站 4 = 15 行数据行，4 个分组标题 + 4 个表头 + 7 个空行 + 1 个文档标题 = 36 行文件）。**距离评审日 2026-07-30 已 61 天无任何参数调整反馈**。这与 SKILL.md:97-100 "自我进化"段、`:9 frontmatter version: 2.0.0"、README 强调的"按需加载 + 自我进化"形成对比：机制存在但 0 次触发。**对比 early-warning sub-report L3**（同样问题：feedback-log 空、parameters 全 2026-05-30），这是 5 skill 的共性弱信号，但 monitor 是 0.2k LOC 小 skill，影响面相对小，标 Medium。 | (a) 在 `feedback-log.md` 补一条"v2.0.0 初始发布（2026-05-30）"占位记录；(b) `parameters.md` 增加一列"上次触发来源（人工 / 用户反馈 / 自动调优）"以建立可观测性；(c) 长期：在 `algorithms/time-series-forecast.md` 加"自动参数寻优"段，给"自我进化"一个具体触发点。 |
| Medium | 架构 | `SKILL.md:10` `metadata.hermes.tags` | **tags 缺 `rainfall` / `gate` / `pump` / `trend` / `forecast` 5 个关键词**。当前 tags：`[water-conservancy, real-time-monitoring, sensor, reservoir, dam, gnss]`（6 个）。`rules/` + `algorithms/` 共 8 个文件中，tags 仅覆盖 reservoir / dam / gnss 3 个，**漏**：`rainfall`（rainfall-analysis）/ `gate` 或 `pump`（gate-pump-status）/ `trend`（trend-detection）/ `forecast`（time-series-forecast）。**description 字段实际 52 字符**（"水利工程实时监控：12类监测数据分析规则、趋势异常检测、水位变化率、位移速率计算。规则内嵌，可独立分析。"），前 57 字符窗口内已含"实时监控/监测数据规则/趋势异常/水位变化率/位移速率"，主关键词"趋势"和"位移"在 description 中可被兜底，但 `rainfall`（雨量）/ `gate`（闸门）/ `pump`（泵站）在 description 中**完全没有出现**——若 hermes 走纯 tags 匹配，"今天闸门开启高度多少"会落空。**对比 early-warning L4**（同样 tags 覆盖不足）：monitor 的 tags 缺漏面更大（5/8 = 62.5% 类别未覆盖），影响"按需加载"机制的实际可达性。 | 在 tags 中追加 `rainfall` / `gate-pump` / `trend` / `forecast`（合并为 4 个 tag 字符串），与 description 形成"description 抓主类 + tags 兜子类"双通道路由。 |

---

## 4. Low

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Low | 文档-代码一致 | `evolution/parameters.md:10` | **"库容平衡偏差阈值" 值=待校准 (orphan param)**。水库水情参数表第 4 行 "库容平衡偏差阈值 \| 待校准 \| - \| 需根据具体水库校准 \| 2026-05-30"，值是字符串"待校准"而非数值，**"合理范围"列也填 `-`**，无具体调参依据。与 reservoir-analysis.md 指针所指的 `_shared/rules/reservoir-analysis.md` 内容耦合度未知（Task 6 重点），但作为参数注册表的一行，应有数值或显式"未启用"。 | (a) 短期：把"待校准"改为 `null` 或在"当前值"列加 "(未启用)" 后缀，注明"此参数需配合具体水库校准，通用 v2.0.0 不预设"；(b) 长期：把水库专属参数从通用注册表抽离，做成 `evolution/parameters-reservoir.md` 子表（每个水库一个值）。 |
| Low | 文档-代码一致 | `SKILL.md:73-76` 跨表引用 vs `evolution/parameters.md` 全表 | **`time-series-forecast` 算法在 `parameters.md` 无对应参数**。SKILL.md:76 显式列 `algorithms/time-series-forecast.md` 为 4 个跨表引用之一（指数平滑/ARIMA/LSTM），但 `evolution/parameters.md` 16 个数据行中**没有任何"预测"或"时序"参数**（分组为：水库 4 + 雨情 4 + GNSS 3 + 闸门泵站 4 = 15 行，加上"库容平衡"待校准 = 16 行，无 forecast）。对比 SKILL.md:75-76 提到 "α / β / γ 系数"（在 `_shared/algorithms/time-series-forecast.md` 中是核心超参），parameters.md 完全缺位。Agent 拿到"预测 ARIMA 参数"调优需求时无落脚点。 | 在 `evolution/parameters.md` 增加 "## 时序预测参数" 分组，至少补 3 个：(a) Holt-Winters α (默认 0.3, 范围 0.1-0.5); (b) ARIMA (p,d,q) 默认 (1,1,1); (c) LSTM epochs/batch_size 默认 (50/32)。 |
| Low | 文档-代码一致 | `SKILL.md:25` 描述 vs `SKILL.md:81-94` 按需加载指令 | **"12 类"声明 vs 14 个按需加载关键词**。line 25 写"实时 12 类监测分析"，但 line 81-94 的"按需加载指令"段实际有 14 个关键词组（"水位"/"水库"/"水情"、"河道"/"河流"、"闸站"/"水闸"、"潮汐"/"潮位"、"雨量"/"降雨"、"分区雨情"/"区域降雨"、"闸门"/"泵站"、"GNSS"/"位移"/"变形"、"渗流"/"渗流量"、"渗压"/"压力"、"墒情"/"土壤"、"白蚁"/"蚁害"、"趋势"/"异常趋势"、"预测"/"预报"/"ARIMA"/"LSTM"），其中"趋势"和"预测"是跨切算法而非 12 类中的某一类。**14 vs 12 的矛盾与 M1 同源**——两个数字差 = 2，正好对应"防洪区水情 + 渗压"两个"12 大表"里的次要类别（line 49 + line 64）+ 1 个 "潮汐水情"（line 46）= 3 个...实际再数：水库水情、河道水情、闸站水情、潮汐水情、测站雨情、分区雨情、防洪区水情、闸门工情、泵站工情、GNSS变形、渗流量、渗压、墒情、白蚁 = 14 类。 | 修法同 M1（"12 类" → "14 类"）。 |
| Low | 文档-代码一致 | `SKILL.md:124-133` 段 | **"共享引用"段 `_shared/rules/` 是复数但未指明子文件**。line 130 写 `_shared/rules/`（目录级引用），与 line 132 `_shared/algorithms/` 对偶，但 SKILL.md 全文其他处（如 line 43 `rules/reservoir-analysis.md`、line 47 `rules/rainfall-analysis.md`、line 62 `rules/gnss-deformation.md`）都是精确到子文件。Agent 读 line 130 可能不知道要打开哪个文件。**虽然 line 132 给出了"5 类规则名（闸门/泵站/GNSS/雨情/水库/趋势）"的人话描述，但 line 130 表格中"用途"列写"闸门/泵站/GNSS/雨情/趋势规则（单一事实源）"**——没给具体路径。 | line 130/132 改为列举子文件：`\| _shared/rules/reservoir-analysis.md \| 水库水情分析 \|` 等，与 SKILL.md 正文其他处精度对齐。 |
| Low | 文档-代码一致 | `SKILL.md:138` | **末尾无 version/date 标记**。line 138 文档末尾以"离线巡检回顾/日报/巡检质量考核 → 用 `powerelf-inspection`"段结束，**无显式版本号或最后修改日期**。frontmatter line 4 写了 `version: 2.0.0`，但没有对应"最后更新：2026-XX-XX"作为文档级元信息。**对比 early-warning 同样问题**，是 SKILL.md 普遍共性。 | 在 line 138 之后加一行 `> 本文档 v2.0.0 · 最后更新 2026-07-16（commit 413a94c 加路由表）`，与 frontmatter 双向印证。 |

---

## 5. 文档-代码一致性矩阵（声明 vs 实际）

| SKILL.md / README 声明 | 实际文件状态 |
|----------------------|-------------|
| 5 规则模块（reservoir / rainfall / gate-pump / gnss / trend） | `rules/` 恰好 5 个 .md（reservoir 7L / rainfall 7L / gate-pump 3L / gnss 3L / trend 9L） — ✅ 完全匹配（与 early-warning 5 规则对称） |
| 3 算法模块（water-level-change / displacement-rate / time-series-forecast） | `algorithms/` 恰好 3 个 .md（7L / 7L / 9L） — ✅ 完全匹配（与 early-warning 3 策略对称） |
| 自我进化：parameters.md + feedback-log.md | `evolution/` 2 文件齐全 — ⚠️ 但 feedback-log 空，全参数 2026-05-30（见 Medium M3） |
| 12类监测分析 | 实际"12大监测类型"表 14 行（7+2+3+2） — ❌ 见 Medium M1 |
| 适用场景 | line 20-26 列出 4 条场景（含"实时值/趋势看盘/REST API/12 类监测分析/趋势异常"）— ✅ |
| When NOT to Use | line 28-35 表 4 行（inspection / governance / early-warning / chatbi）— ✅ 4 路由清晰 |
| Related Skills | frontmatter line 11 列 3 个（governance/early-warning/inspection），body 无独立 Related Skills 段 — ⚠️ frontmatter 漏 chatbi（见 High H1）；line 135-137 "与 powerelf-inspection 的分工" 是 inspection-only 的非通用 Related Skills 段 |
| 共享引用（_shared） | line 124-133 表 4 行（schema.md / api-auth.md / rules/ / algorithms/）— ⚠️ `_shared/rules/` 未列 reservoir（见 Medium M2） |
| 5 规则 + 3 算法 = 8 子模块 | `rules/` 5 + `algorithms/` 3 = 8 — ✅ 完全匹配 |
| frontmatter `related_skills` | 3 个（缺 chatbi）— ❌ 见 High H1 |
| frontmatter `tags` | 6 个（缺 rainfall / gate / pump / trend / forecast）— ⚠️ 见 Medium M4 |
| description 长度 52 字符 | 实测 52 字符，57 字符窗口内全主类（实时监控/监测数据/趋势异常/水位变化率/位移速率），但 rainfall/gate/pump 缺位 — ⚠️ 见 Medium M4 |
| `related_skills` 双向闭环 | body "When NOT to Use" 列 4 个 ↔ frontmatter 3 个 — ❌ 见 High H1（4 vs 3 不一致） |
| `_shared/rules/*.md` 指针 | 5 个本地指针 → 5 个 `_shared` 目标（reservoir 1.3k / rainfall 3.0k / gate-pump 4.3k / gnss 3.3k / trend 1.4k bytes），全部有实质内容 — ✅ 无断链 |
| `_shared/algorithms/*.md` 指针 | 3 个本地指针 → 3 个 `_shared` 目标（water-level 0.8k / displacement 0.8k / time-series 6.4k bytes），全部有实质内容 — ✅ 无断链 |
| parameters.md 与 rules/algorithms 引用对齐 | water-level-change / reservoir / rainfall / gate-pump / gnss / displacement 6 个模块有对应参数；time-series-forecast / trend-detection 2 个模块无对应参数 — ⚠️ 见 Low L2 |
| `与 powerelf-inspection 的分工` 段 | line 135-137 显式写"monitor=实时，inspection=离线"分工 | ✅ | 是本 skill 独有的对偶段，inspection 报告中应也有镜像 |
| API 附录 13 个端点 | line 106-120 列 13 个端点（monitor/overview、srm/*、att/dot-user/concern） | ✅ | 与 SKILL.md 表 11 类监测类型 + 2 个特殊端点（关注/水位预警）匹配 |

---

## 6. SQL/Schema 用表

**SQL finding: 无**（无 Python 实现，无 .sql 文件，无 `--db` 直连入口；本 skill 全部走 REST API 通过 `_shared/api-auth.md` 鉴权）。

文档中提及的表（仅在 `SKILL.md` "12大监测类型" 段 14 行表中显式列出，11 张 st_* / rei_* / dsm_* 表名）：

| 文档中提及的表 | schema.md 存在? | 操作 | 占位符 | 备注 |
|---------------|----------------|------|--------|------|
| `st_rsvr_r` | ✅ schema.md:152 附近 | REST API 读 | — | 水库水情核心表 |
| `st_river_r` | ✅ schema.md | REST API 读 | — | 河道水情 |
| `st_was_r` | ✅ schema.md | REST API 读 | — | 闸站水情 |
| `st_tide_r` | ✅ schema.md | REST API 读 | — | 潮汐水情 |
| `st_pptn_r` | ✅ schema.md | REST API 读 | — | 测站雨情 |
| `st_pptn_region_r` | ✅ schema.md | REST API 读 | — | 分区雨情 |
| `st_flood_r` | ✅ schema.md | REST API 读 | — | 防洪区水情 |
| `rei_gate_r` | ✅ schema.md:333 | REST API 读 | — | 闸门工情（schema.md line 139 标 ⚠️`eq_id 是 int 非 bigint`） |
| `rei_pump_r` | ✅ schema.md:347 | REST API 读 | — | 泵站工情 |
| `dsm_dfr_srvrds_srhrds` | ✅ schema.md:363 | REST API 读 | — | GNSS 位移（schema.md line 139 ⚠️**无 stcd 列，eq_id 是 int**） |
| `st_percolation_r` | ✅ schema.md | REST API 读 | — | 渗流量 |
| `st_pressure_r` | ✅ schema.md | REST API 读 | — | 渗压 |
| `st_soil_moisture_r` | ✅ schema.md | REST API 读 | — | 墒情 |
| `st_termite_monitor_r` | ✅ schema.md:467 | REST API 读 | — | 白蚁监测 |

> **说明**：本 skill 是纯 REST API 消费者（13 个端点，line 106-120），**无任何直接 DB 访问**。schema.md 中 `dsm_dfr_srvrds_srhrds` 的 ⚠️ 提示（无 stcd 列、eq_id 是 int）是 schema 真实状态，SKILL.md:62 表格中正确列 `point_id(测点ID)` 而非 `stcd(站码)`，**与 schema 实际一致**，是 doc ↔ schema 正确对齐的范例（值得 governance/chatbi 学习）。Task 6 评审 `_shared/references/schema.md` 时可顺带确认 `st_soil_moisture_r` / `st_pptn_region_r` / `st_flood_r` 等"次要表"是否同样有 2026-07-28 之后的实测数据。

---

## 7. untracked 处置建议

`powerelf-monitor/` 目录下 **0 untracked 文件、0 modified 文件**（`git status --short -- powerelf-monitor/` 输出为空）。所有 11 个文件（1 SKILL.md + 5 rules + 3 algorithms + 2 evolution）均已 tracked，最后一次提交为 `413a94c docs(monitor): 加适用场景/When NOT to Use 路由表 + _shared 引用节`（2026-07-16），中间 `440b29b docs(monitor): related_skills 加 inspection + 对称分工段` 加了 inspection 但**未加 chatbi**（即 High H1 的根因——`440b29b` commit message 显式说"加 inspection"，但漏了 chatbi）。

**无需处置**。但建议在 High H1 修复时把 `440b29b` 那个 commit 也"补"成 `related_skills: [governance, early-warning, inspection, chatbi]`，commit message 加 "(... + chatbi)" 显式追溯。

---

## 8. 正面发现

1. **routing 4 节齐全（与 early-warning H1 对照）**：commit `413a94c` 显式补了 适用场景（line 20-26）/ When NOT to Use（line 28-35 表）/ 共享引用（line 124-133 表）/ 与 powerelf-inspection 的分工（line 135-137）四节，**正是 early-warning H1 缺失的部分**。monitor 是 5 skill 中路由表最完整的（governance / inspection / chatbi 应当也对齐到这个模板），可作为其他 skill 修订 SKILL.md 的参考模板。
2. **monitor ↔ inspection 的"实时/离线"分工段写得清晰且对偶**：line 135-137 "monitor = 实时（当前/在线、REST、看盘、预警触发）；inspection = 离线回顾（昨日窗口批处理、DB 直连、日报 + 复合工况 + 巡检质量考核）"，是 5 skill 跨 skill 关系描述中**最干净的一段**。两个 skill 都引用相同的 `st_*` 表，但"时间模式/触发/产出/消费者"四维度清晰区分。
3. **5 规则 + 3 算法目录结构与声明完全对齐**：README、SKILL.md "12大监测类型"段、实际 `rules/` 5 文件 + `algorithms/` 3 文件三处一致（数量层面）。命名清晰（reservoir / rainfall / gate-pump / gnss / trend 五种分析名见各 rules/*.md 顶部"→ _shared"指针）。
4. **5 个 rules 指针 + 3 个 algorithms 指针 全部指向有实质内容的 _shared 文件**：`_shared/rules/` 总 1048 行，`_shared/algorithms/` 总 552 行（mad.md / outlier-methods.md 额外 + SKILL.md 未引用，但 governance/inspection 引用了）；`commit 9821868` (gate-pump/gnss) + `fd43767` (time-series-forecast/trend-detection) 重构无"断链"——本 skill 的"去重 → 共享层"重构质量高。
5. **schema 字段标注准确**：`dsm_dfr_srvrds_srhrds` 在 schema.md 中明确标 ⚠️ "无 stcd 列，eq_id 是 int 非 bigint"，SKILL.md:62 表格中**正确列 `point_id(测点ID)` 而非 `stcd(站码)`**，**doc ↔ schema 一致**——是 governance/chatbi 应当学习的范例（governance 报告 L 系列多处发现"schema 实际是 X 但 doc 写 Y"）。
6. **frontmatter 格式严格一致**：与 early-warning / governance / inspection / chatbi 4 个 skill 的 frontmatter 字段顺序与命名一致（`name / description / version / author / license / platforms / metadata.hermes.{tags, related_skills} / prerequisites.env_vars`），无字段缺失或拼写漂移。
7. **API 附录 13 个端点列举完整**：line 106-120 表覆盖 11 类监测类型 + 2 个特殊端点（`/monitor/overview/get` 总览 + `POST /att/dot-user/concern` 关注），与 SKILL.md "12大监测类型"段呼应，Agent 可直接据此调用 REST API。
8. **"按需加载指令"段（line 80-95）给出 14 个关键词路由表**：是 5 skill 中路由粒度最细的（early-warning 是 8 个，inspection 是 12 个，monitor 是 14 个），与"12 类"声明的 14 行实质内容（虽然 M1 标 12 vs 14 不一致）形成实际可达的 keyword → rule 映射。
9. **evolution/parameters.md 参数注册表结构整齐**：4 个分组（水库/雨情/GNSS/闸门泵站）覆盖 16 个数据参数，"合理范围"列便于后续调参时知道安全边界，与 early-warning parameters.md 同源设计。
10. **description 字段长度合理（52 字符 ≤ 57 字符窗口）**：全主类（实时监控/监测数据/趋势异常/水位变化率/位移速率）在窗口内可见——除 M4 提到的 rainfall/gate/pump 缺位外，路由入口本身是好的。

---

> **评审计数**：1 High + 4 Medium + 5 Low = **10 findings**（符合 brief 预期 "0 Blocker / 0-1 High / 0-3 Medium / 0-8 Low"——略超 Medium 上限 1 条，源于 M1/M2/M3/M4 都是"轻量但跨 skill 共性"问题；Low 略超 1 条源于 L2/L3 派生于 M1/M2/M3）。**核心修复优先级**：H1（frontmatter `related_skills` 补 chatbi）→ M1（12 → 14）→ M2（共享引用段补 reservoir）→ M3（feedback-log 加占位）→ M4（tags 补 4 个）。其余 Low 可与 governance/early-warning/chatbi 评审的同类问题一起在总报告 `REVIEW.md` §5 横向章节合并修复。
