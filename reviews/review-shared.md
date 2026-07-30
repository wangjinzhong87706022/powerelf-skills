# _shared/ 共享层评审 — 2026-07-30

## 0. 概览

| 项 | 值 |
|---|---|
| 模块 | `_shared/`（5 主 skill 的"单一事实源"共享层） |
| 评审版本 | HEAD `dc312ac`（branch `review/2026-07-29-skills-deep`）；工作树 `_shared/lib/db.py` 和 `_shared/references/schema.md` 有未提交改动 |
| 跟踪文件 | **24 文件**：`references/` 5 md + `algorithms/` 5 md + `rules/` 5 md + `evolution/` 3 md + `lib/` 3 py + `api-auth.md` 1 md + `bootstrap.sh` 1 sh + `hooks/block_raw_pymysql.py` 1 py |
| 跟踪 LOC | **约 3,100 行**（references 1,503 + rules 497 + algorithms 430 + lib 421 + evolution 68 + hooks 87 + api-auth 40 + bootstrap 31） |
| 未跟踪文件 | **15 文件 + 1 目录**：`check_st128*.py` ×5 + `report_*.py` ×2 + md 报告 ×8 + `hooks/__pycache__/` |
| Python 编译 | ✅ 全部通过（`py_compile` 对 `lib/*.py` + `hooks/*.py` 无错误） |
| 评审日期 | 2026-07-30 |
| 评审人 | Claude (sub-agent, Task 6/6) |

**摘要**：`_shared/` 作为 5 主 skill 的共享基础层，整体架构设计良好——`lib/db.py` 提供了完善的数据库连接抽象（.env 自加载、端口防呆、只读护栏、表名注入防护、列名查询），`references/schema.md` 是迄今最全面的表结构文档（735 行覆盖 27+ 张表），`algorithms/` 和 `rules/` 成功实现了跨 skill 单一事实源（monitor 和 inspection 的文件已转为薄指针）。**主要问题是 schema.md 的"铁律"声明与 4 张监测表 DDL 自相矛盾**（`rei_gate_r` / `rei_pump_r` / `st_soil_moisture_r` / `st_termite_monitor_r` 的 DDL 段缺少框架列 `eq_id` / `eq_code` / `deleted` / `tenant_id`，但文件开头的铁律声称所有监测表都具备这些列），以及 **`hooks/block_raw_pymysql.py` 虽代码完善但未在任何 `.claude/settings.json` 中配置**（事实上是死代码）。14 个未跟踪文件中，1 个应入 git（hook），7 个一次性调试脚本应删除，7 个报告应归档。

---

## 1. Blockers

| # | 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|---|--------|------|---------|------|------|
| B1 | **Blocker** | SQL/Schema + 文档一致性 | `references/schema.md:17-36`（铁律声明）vs `:335-345`（rei_gate_r DDL）/ `:349-358`（rei_pump_r DDL）/ `:454-465`（st_soil_moisture_r DDL）/ `:469-477`（st_termite_monitor_r DDL） | **schema.md "铁律"与自身 4 张表 DDL 自相矛盾，"唯一事实源"地位受损**。文件 §🧱（lines 17-36）声明"所有监测表/设备表/基础表都遵循同一套列模式"，铁律第 3 条明确写"**所有监测表都有** `eq_id`(BIGINT)"；§⚠️（line 47）进一步强调"所有监测表都同时具备 `eq_id` 与 `eq_code` 两列"。但同文件 4 张表 DDL 段完全缺少这些框架列：(1) `rei_gate_r`（line 335）仅有 `st_id/tm/gtq/gtophgt/gtopnum/status/stcd/slcd`，无 `eq_id`/`eq_code`/`deleted`/`tenant_id`；(2) `rei_pump_r`（line 349）同理缺失；(3) `st_soil_moisture_r`（line 454）同理缺失；(4) `st_termite_monitor_r`（line 469）同理缺失。**交叉验证**：`_shared/rules/gate-pump-status.md`（line 16-18）列出 `rei_gate_r` 有 `eq_code`(varchar) 和 `eq_id`(bigint)；`eq_business_equip_relation` 映射表（schema.md line 527）也记录了 `rei_gate_r: DD×7` / `rei_pump_r: DP×4`（这些映射以 `eq_id` 为键），证明**实际数据库很可能有这些列**，只是 schema.md 的 DDL 段仍停留在"SL323 简版"未更新。**影响**：所有下游 skill（governance/chatbi/early-warning 均引用 schema.md）在查这 4 张表时会按铁律假设 `eq_id` 存在，但 DDL 示例却不含该列，造成 agent SQL 生成的混乱。chatbi `few_shots.md` #13/#14 的 JOIN 键错误（chatbi M8 finding）根源在此。 | 用 `SHOW CREATE TABLE` 重新校准这 4 张表的 DDL 段（与 st_rsvr_r/st_pptn_r 等已校准表保持一致），补全 `eq_id`/`eq_code`/`deleted`/`tenant_id` 等框架列。若线上确实有这些列，更新 DDL；若没有，则铁律声明需加注例外（"除以下 4 张表外"）。同步修正 chatbi few_shots #13/#14/#15。 |

---

## 2. High

| # | 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|---|--------|------|---------|------|------|
| H1 | **High** | 代码安全 + 架构 | `hooks/block_raw_pymysql.py:1-87` | **hook 代码完善但未在任何 settings.json 中配置——事实上是死代码**。`block_raw_pymysql.py` 实现了 `pre_tool_call` hook 接口（从 stdin 读 JSON → 扫描 command/code 中的 `pymysql.connect` 模式 → 输出 block/allow），代码质量高（87 行，`py_compile` 通过，覆盖了 terminal 和 execute_code 两种 tool_input 类型，还处理了 `cd` + 相对路径的文件读取）。但 `grep -r "block_raw_pymysql\|hooks/" .claude/` 返回空——**没有任何 `.claude/settings.json` 或 `settings.local.json` 配置 `pre_tool_call` hook 指向该文件**。`ls .claude/*.json` 仅有 `settings.local.json`，其中无 `hooks` 键。该 hook 的文档声称"2026-07-17 agent.log 实证：本地 27B 模型手写 pymysql.connect → 空密码/猎密码/连错库连环翻车"，说明它解决了一个真实痛点，但目前完全不生效。 | (a) 在 `.claude/settings.json` 中配置 `pre_tool_call` hook：`{"hooks": {"pre_tool_call": [{"matcher": "terminal|execute_code", "command": "python3 _shared/hooks/block_raw_pymysql.py"}]}}`；(b) 将 `hooks/` 目录纳入 git 跟踪（目前是 untracked）；(c) 补一个 README.md 说明 hook 的安装方式。 |
| H2 | **High** | 文档一致性 | `_shared/rules/gate-pump-status.md:16-18` vs `_shared/references/schema.md:335-345` | **rules 与 schema.md 列定义冲突**。`_shared/rules/gate-pump-status.md` 的"闸门工情字段"表列出 `eq_id`(bigint, line 18) / `eq_code`(varchar, line 16) / `st_id`(bigint, line 17) 等列，且 `rei_pump_r` 字段表列出 20+ 列（含 `lx`/`lu`/`fan_run`/`fan_fault`/`ot`/`it`/`ul`/`al`/`extend`/`idstcd` 等）。但 schema.md 的 `rei_gate_r` DDL 仅 8 列（无 eq_id/eq_code），`rei_pump_r` DDL 仅 13 列（无 eq_id/eq_code/lx/lu/fan_run 等）。两个 _shared 文件对同一张表的列定义相差 2-3 倍。**影响**：monitor skill 同时引用这两个文件（rules 指针指向 _shared/rules，SKILL.md 引用 schema.md），agent 不知道该信谁。 | 与 B1 合并修复——用 `SHOW CREATE TABLE` 取真实 DDL，统一 schema.md 和 rules/ 的列定义。 |

---

## 3. Medium

| # | 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|---|--------|------|---------|------|------|
| M1 | Medium | 代码安全 | `lib/db.py:332-335` get_sqlalchemy_url | **密码明文嵌入连接 URL 字符串**。`get_sqlalchemy_url()` 返回 `f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"`，密码出现在 URL 中。虽然这是 SQLAlchemy 的标准连接格式，但该 URL 可能被：(a) `bootstrap.sh` 导出到 `DB_URL` 环境变量（line 16 `export DB_URL=...`），在 `ps aux` 或 `/proc/*/environ` 中可见；(b) 出现在 Python traceback 或日志中。`get_readonly_sqlalchemy_url()`（line 370）同理。 | 考虑在 URL 中对密码做 `urllib.parse.quote()` 编码（防特殊字符），并在 bootstrap.sh 中加 `readonly DB_URL` 防止子进程意外修改。长期可考虑 SQLAlchemy 的 `URL.create()` 方法（参数式构建，不拼接字符串）。 |
| M2 | Medium | 文档一致性 | `references/data-profiling.md:398-400` 白名单表名 | **profiler 白名单含 11 张 schema.md 未记录的表名**。`data-profiling.md` §6.7 列出的允许表白名单包含 `st_deformation_r` / `st_gnss_r` / `st_seepage_r` / `st_rain_r` / `st_wind_r` / `st_temp_r` / `st_strlevel_r` / `st_strain_r` / `st_tilt_r` / `st_environment_r` 等名称，这些表名在 schema.md 中**完全不存在**（实际对应表为 `dsm_dfr_srvrds_srhrds` / `st_pressure_r` / `st_percolation_r` / `st_pptn_r` 等）。白名单若被 `impl/profiler.py` 代码实际使用，这些幽灵表名永远不会匹配到真实表。 | 更新白名单为 schema.md 中的实际表名，或删除白名单段（标注"随 impl/profiler.py 代码演进"即可，文档不必镜像）。 |
| M3 | Medium | 架构 | `_shared/` 整体 | **缺少版本追踪机制**。`_shared/` 是 5 个 skill 的共享依赖层，但没有任何版本管理机制：无 `VERSION` 文件、无 `CHANGELOG.md`、无 frontmatter 中的 version 字段。当 `_shared/lib/db.py` 或 `references/schema.md` 发生变更时，5 个下游 skill 无法感知自己依赖的版本是否兼容。本次评审就遇到 `lib/db.py` 和 `schema.md` 有未提交改动的情况。 | 在 `_shared/` 根添加 `CHANGELOG.md`（记录每次变更及影响的 skill），或在每个被引用的关键文件头部加版本号注释。git log 已提供版本历史，但显式 CHANGELOG 对不读 git 的 agent 更友好。 |
| M4 | Medium | 代码正确性 | `lib/bootstrap.py:27` | **`_root()` 返回类型注解使用 Python 3.10+ 语法**。`def _root() -> Path | None:` 使用 `|` 联合类型语法，Python 3.9 及以下版本会在 import 时报 `TypeError`。当前部署环境有 cpython-311 和 cpython-312 的 `.pyc` 缓存文件，说明实际运行的是 3.11+，暂无问题。但若在其他环境（如 CI 容器使用 3.9）运行会崩溃。 | 改为 `def _root() -> Optional[Path]:` 并 `from typing import Optional`，兼容 Python 3.8+。或在文件头部加 `from __future__ import annotations`。 |
| M5 | Medium | 文档一致性 | `api-auth.md:20` | **`tenant-id` 硬编码为 `1`**。文档的"通用请求头"段写 `tenant-id: 1`（line 20），curl 示例也用 `-H "tenant-id: 1"`（line 31）。schema.md 的框架列定义 `tenant_id BIGINT NOT NULL DEFAULT 1` 也默认 1。在多租户部署（`talent.tenant.enable: true`）下，不同租户应使用不同的 tenant-id，但文档只给了硬编码值，未说明如何获取当前租户 ID 或如何切换。 | 在 api-auth.md 补充 `tenant-id` 的来源说明（如从 `POWERELF_TENANT_ID` 环境变量获取，默认 1），并在 curl 示例中使用 `${POWERELF_TENANT_ID:-1}` 变量替代硬编码。 |

---

## 4. Low

| # | 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|---|--------|------|---------|------|------|
| L1 | Low | 工程卫生 | `hooks/__pycache__/block_raw_pymysql.cpython-311.pyc` | **`__pycache__/` 在 untracked 的 hooks/ 目录中**。若 hooks/ 目录后续纳入 git，`__pycache__/` 也会被意外提交。`lib/__pycache__/` 也存在类似问题（`bootstrap.cpython-311.pyc` / `db.cpython-311.pyc` / `db.cpython-312.pyc` / `__init__.cpython-311.pyc`），但 lib/ 已 tracked 且 __pycache__ 可能被 .gitignore 覆盖。 | 确认 `.gitignore` 包含 `__pycache__/`；若 hooks/ 入 git 前先清理 pyc 缓存。 |
| L2 | Low | 工程卫生 | `bootstrap.sh:16` | **未检查 `python3` 是否可用**。`export DB_URL="$(python3 -c "..." 2>/dev/null)"` 将 python3 的 stderr 重定向到 /dev/null，若 python3 不存在或 pymysql 未安装，`DB_URL` 会静默为空。line 18-22 的空值检查能兜底，但错误原因被吞掉了（用户只看到"DB_URL 为空"，不知道为什么）。 | 在 python3 调用前加 `command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; return 1; }`。 |
| L3 | Low | 文档一致性 | `evolution/parameters.template.md` + `feedback-log.template.md` | **模板占位符 `{{placeholder}}` 无处理机制**。两个模板文件使用 `{{param}}` / `{{value}}` / `{{range}}` 等占位符，但没有模板引擎处理它们——全靠人工替换。这与 Jinja2/Mustache 语法相似但无关联，可能造成混淆。 | 在模板头部注明"占位符为人工替换用，非模板引擎语法"，或改用更明显的占位符格式如 `<PARAM_NAME>` / `[当前值]`。 |

---

## 5. 文档-代码一致性矩阵

### 5.1 algorithms/ 引用矩阵

| _shared/algorithms/ | powerelf-data-governance | powerelf-inspection | powerelf-monitor | powerelf-early-warning | powerelf-chatbi |
|---------------------|-------------------------|--------------------|-----------------|----------------------|----------------|
| `displacement-rate.md` (38L) | — | ✓ 指针(7L) | ✓ 指针(7L) | — (无 algorithms/) | — (无 algorithms/) |
| `time-series-forecast.md` (249L) | — | ✓ 指针(9L) | ✓ 指针(7L) | — | — |
| `water-level-change.md` (43L) | — | ✓ 指针(7L) | ✓ 指针(7L) | — | — |
| `mad.md` (124L) | ✓ 指针(mad-algorithm.md) | ✓ 指针(mad-statistical-method.md) | — | — | — |
| `outlier-methods.md` (102L) | ✓ (mad.md 引用) | — | — | — | — |

**结论**：单一事实源模式运行良好。monitor 和 inspection 的本地文件都是薄指针（7-9 行），无内容重复。governance 的 `mad-algorithm.md` 也是指针。early-warning 和 chatbi 无 algorithms/ 目录（设计如此——early-warning 走 REST API 不做本地计算，chatbi 专注 SQL 生成）。

### 5.2 rules/ 引用矩阵

| _shared/rules/ | governance | inspection | monitor | early-warning | chatbi |
|----------------|-----------|-----------|---------|--------------|--------|
| `gate-pump-status.md` (138L) | — | — | ✓ 指针(3L) | — | — |
| `gnss-deformation.md` (120L) | — | — | ✓ 指针 | — | — |
| `rainfall-analysis.md` (108L) | — | — | ✓ 指针 | — | — |
| `reservoir-analysis.md` (63L) | — | — | ✓ 指针 | — | — |
| `trend-detection.md` (68L) | — | ✓ 引用 | ✓ 指针 | — | — |

**结论**：rules/ 的单一事实源覆盖率低于 algorithms/——只有 monitor 一个消费者。governance / inspection / early-warning / chatbi 各有自己的 rules 体系，未引用 _shared/rules/。这不是问题（各 skill 的领域规则本就不同），但说明 `_shared/rules/` 的定位更偏向"monitor 的远程规则库"而非真正的跨 skill 共享层。

### 5.3 references/ 引用矩阵

| _shared/references/ | governance | inspection | monitor | early-warning | chatbi |
|---------------------|-----------|-----------|---------|--------------|--------|
| `schema.md` (734L) | ✓ 核心引用 | ✓ 核心引用 | ✓ 引用 | ✓ 引用 | ✓ 核心引用 |
| `data-profiling.md` (514L) | ✓ (profiling.py) | — | — | — | — |
| `sql-discipline.md` (62L) | ✓ | ✓ | — | — | ✓ |
| `statistical-caution.md` (69L) | ✓ | — | — | ✓ | — |
| `analysis-qa-checklist.md` (123L) | ✓ | — | — | — | — |

**结论**：`schema.md` 是唯一真正被全部 5 个 skill 引用的文件（名副其实的"唯一事实源"），其内部矛盾（B1）的影响因此特别大。其余 references 主要被 governance 引用。

### 5.4 lib/ 引用矩阵

| _shared/lib/ | governance | inspection | monitor | early-warning | chatbi |
|-------------|-----------|-----------|---------|--------------|--------|
| `db.py` (370L) | ✓ (`lib/db.py` shim) | ✓ (`lib/db.py` shim) | — (REST API) | — (REST API) | ✓ (query_exec.py 依赖) |
| `bootstrap.py` (47L) | ✓ (path resolver) | ✓ | — | — | — |
| `__init__.py` (2L) | — | — | — | — | — |

**结论**：`db.py` 是 3 个有代码的 skill（governance / inspection / chatbi）的共同基础。monitor 和 early-warning 是纯文档 skill（无 Python），通过 REST API 获取数据，不直接依赖 db.py。

---

## 6. SQL/Schema 用表

### 6.1 schema.md 覆盖的表（27+ 张）

| 类别 | 表名 | DDL 完整性 | 框架列(eq_id/eq_code/deleted/tenant_id) |
|------|------|-----------|--------------------------------------|
| 水文气象 | st_rsvr_r | ✅ 完整(SHOW CREATE TABLE 校准) | ✅ 全部 |
| 水文气象 | st_river_r | ✅ 完整 | ✅ 全部 |
| 水文气象 | st_pptn_r | ✅ 完整 | ✅ 全部 |
| 水文气象 | st_pptn_region_r | ⚠️ 简化 | ❌ 无(re_id 主键) |
| 水文气象 | st_flood_r | ⚠️ 简化 | ❌ 无(fca_id 主键) |
| 水文气象 | st_was_r | ⚠️ 简化 | ❌ 无 |
| 水文气象 | st_tide_r | ⚠️ 简化 | ❌ 无 |
| 设备工情 | **rei_gate_r** | ⚠️ **简化(仅 8 列)** | ❌ **缺 eq_id/eq_code/deleted/tenant_id** |
| 设备工情 | **rei_pump_r** | ⚠️ **简化(仅 11 列)** | ❌ **缺 eq_id/eq_code/deleted/tenant_id** |
| 大坝安全 | dsm_dfr_srvrds_srhrds | ✅ 完整 | ✅ 全部(eq_id=int) |
| 大坝安全 | st_percolation_r | ✅ 完整 | ✅ 全部 |
| 大坝安全 | st_pressure_r | ✅ 完整 | ✅ 全部 |
| 其他 | wq_pcp_d | ⚠️ 简化 | ❌ 无 |
| 其他 | **st_soil_moisture_r** | ⚠️ **简化** | ❌ **缺 eq_id/eq_code/deleted/tenant_id** |
| 其他 | **st_termite_monitor_r** | ⚠️ **简化** | ❌ **缺 eq_id/eq_code/deleted/tenant_id** |
| 设备 | eq_equip_base | ✅ 完整 | ✅ (自身是被引用表) |
| 映射 | eq_business_equip_relation | ✅ 完整 | 部分(无 deleted) |
| 基础 | att_st_base | ✅ 完整 | ✅ 全部 |
| 治理 | eq_data_anomaly_record | 描述(无 DDL) | 注明"无 deleted" |
| 治理 | eq_data_missing_record | 描述(无 DDL) | 注明"无 deleted" |
| 治理 | eq_equip_offline_record | 描述(无 DDL) | — |
| 治理 | eq_equip_anomaly_record | 描述(无 DDL) | — |
| 统计 | stats_*_daily (3 张) | 描述(无 DDL) | — |
| 配置 | dg_equip_offline | 描述(无 DDL) | — |
| 预警 | ew_info_rules | ⚠️ DDL | 部分 |
| 预警 | ew_info_message | ⚠️ DDL | 部分(有 deleted) |
| 注册 | sys_data_source_registry | ⚠️ DDL | 部分(有 deleted) |

### 6.2 铁律覆盖缺口

schema.md 铁律声称"所有监测表"具备框架列，但实际只有 6 张主力表（st_rsvr_r / st_river_r / st_pptn_r / st_pressure_r / st_percolation_r / dsm_dfr_srvrds_srhrds）经过了 `SHOW CREATE TABLE` 校准且 DDL 完整。另有 **4 张被 chatbi/inspection 引用的表**（rei_gate_r / rei_pump_r / st_soil_moisture_r / st_termite_monitor_r）DDL 仍为 SL323 简版，与铁律矛盾。其余简化/描述式 DDL 的表（st_was_r / st_tide_r / wq_pcp_d 等）因未被 5 主 skill 高频引用，影响较小。

### 6.3 COLUMN_MEANINGS 与 schema.md 的同步

`lib/db.py` 的 `COLUMN_MEANINGS` 字典（lines 196-277）定义了 9 张表的列含义。schema.md 的"列名速查字典"（lines 78-150）覆盖了相同的 9 张表加上 GNSS。两者内容基本一致（db.py 注释 line 193 声明"COLUMN_MEANINGS 是 meanings 的唯一事实源，schema.md 镜像它"）。**未发现数值冲突**。

---

## 7. untracked 处置建议

### 7.1 A 类：应入 git（1 文件）

| 文件 | 大小 | 用途 | 建议 |
|------|------|------|------|
| `hooks/block_raw_pymysql.py` | 87 行 | `pre_tool_call` hook，拦截 agent 手写 `pymysql.connect` | **入 git + 配置 settings.json hook**。代码质量好，解决了真实问题（27B 模型反复手写直连翻车）。需配合 H1 修复（配置 settings.json）。 |

注：`hooks/__pycache__/` 不应入 git，应加入 `.gitignore`。

### 7.2 B 类：应删除（7 文件）

| 文件 | 大小 | 用途 | 处置理由 |
|------|------|------|----------|
| `check_st128.py` | 3,165B | st_id=128 设备排查脚本 | 一次性调试，硬编码 `/home/scada/powerelf-skills/_shared/lib` 路径，使用 `get_connection()` 而非 `query()`（违反 hook 精神），无通用价值 |
| `check_st128b.py` | 3,415B | 同上，第二版 | 同上 |
| `check_st128c.py` | 3,643B | 同上，第三版 | 同上 |
| `check_st128_final.py` | 3,875B | 同上，"最终版" | 同上 |
| `check_st128_final2.py` | 3,406B | 同上，"最终版2" | 同上。5 个迭代版本说明是一次性探索，非持续维护的脚本 |
| `report_128.py` | 11,377B | st_id=128 五月数据报告生成器 | 一次性报告生成，硬编码路径和 st_id=128，使用裸 cursor（非 query()），输出 CSV/JSON 到本地文件 |
| `report_anomalies.py` | 11,361B | st_id=128 异常数据报告 | 与 report_128.py 几乎同功能（diff 极小），一次性调试产物 |

**共同特征**：
- 权限 `rw-------`（600），仅所有者可读写
- 硬编码 `sys.path.insert(0, '/home/scada/powerelf-skills/_shared/lib')`
- 针对 st_id=128 单点排查，无参数化
- 使用 `get_connection()` + 裸 cursor 而非封装的 `query()`
- 生成于 2026-07-17 同一天（4 小时内 5 个 check 迭代），明显是一次性探索

### 7.3 C 类：应归档到 `docs/` 或 `.superpowers/`（7 文件）

| 文件 | 大小 | 生成日期 | 内容 | 建议 |
|------|------|----------|------|------|
| `hermes_test_final_report.md` | 7,108B | 2026-07-28 | Hermes Agent 性能测试（tool 调用次数/token/耗时对比） | 归档到 `.superpowers/reports/` 或删除（一次性性能基准，已被后续测试超越） |
| `hermes_verification_summary.md` | 7,856B | 2026-07-28 | 批量离线分级脚本的 Hermes 测试验证 | 归档到 `.superpowers/reports/` |
| `optimization_analysis_20260728.md` | 18,118B | 2026-07-28 | SKILL.md 优化技术分析报告（token 优化前后对比） | 归档到 `.superpowers/reports/`（有参考价值：优化方法论） |
| `real_world_test_report.md` | 7,215B | 2026-07-28 | 真实场景测试（"有多少设备离线？"等 5 个 query） | 归档到 `.superpowers/reports/` |
| `routing_verification_report.md` | 5,944B | 2026-07-28 | 路由规则验证（system prompt 分析） | 归档到 `.superpowers/reports/` |
| `skill_optimization_final_report.md` | 5,719B | 2026-07-28 | SKILL.md 优化成果报告（731 行→272 行） | 归档到 `.superpowers/reports/` |
| `test_verification_summary.md` | 6,414B | 2026-07-28 | 批量离线分级脚本的单元验证总结 | 归档到 `.superpowers/reports/` |
| `verification_report_20260728.md` | 7,066B | 2026-07-28 | `classify_offline_by_duration.py` 验证报告 | 归档到 `.superpowers/reports/` |

**共同特征**：
- 全部生成于 2026-07-28 同一天
- 全部是 Hermes Agent 的测试/验证/优化产物
- 内容是运行结果快照（非模板或工具脚本）
- 放在 `_shared/` 根目录不合理（污染了共享层的文件列表）
- 归档后可作为"skill 优化历程"的参考资料

### 7.4 额外：`hooks/__pycache__/` 和 `lib/__pycache__/`

两个 `__pycache__/` 目录应确保被 `.gitignore` 覆盖。`lib/__pycache__/` 包含 4 个 `.pyc` 文件（cpython-311 和 cpython-312 混合），暗示曾在两个 Python 版本下运行。

---

## 8. 正面发现

| # | 发现 | 详情 |
|---|------|------|
| P1 | **db.py 工程质量高** | 370 行覆盖了：(a) .env 自加载（不依赖进程 env，gateway/CLI/execute_code 任意启动方式都能拿到凭证）；(b) 端口字段防呆（非数字回退 3306 并告警，防止历史上"把密码粘进端口字段"的崩溃）；(c) `_assert_readonly()` 只读护栏（注释剥离 + 首关键字检查）；(d) `_sanitize_table_name()` 表名注入防护（正则白名单）；(e) `query()` 自动开关连接 + DictCursor + 超时 + 空结果返回 []；(f) `columns()` 列名查询 + 中文含义叠加（COLUMN_MEANINGS 唯一事实源）。整体设计思路清晰，是"防 agent 犯错"的典范。 |
| P2 | **单一事实源模式在 algorithms/ 成功落地** | 5 个算法文件中，被 monitor 和 inspection 引用的 3 个（displacement-rate / time-series-forecast / water-level-change）已成功从各 skill 提取到 `_shared/algorithms/`，skill 本地仅保留 7-9 行指针文件。governance 和 inspection 的 MAD 算法也统一到了 `_shared/algorithms/mad.md`。消除了跨 skill 内容重复，确保算法描述修改一处生效全局。 |
| P3 | **schema.md 全面且实用** | 735 行覆盖了 27+ 张表的列定义，附带中文含义、数据量参考（实测行数 + tm 范围）、常见 SQL 查询模式（含"一次性概览"查询）、常见错误假设纠正表。对于 agent 生成 SQL 来说，是目前最全面的参考源。6 张主力监测表的 DDL 经过 `SHOW CREATE TABLE` 校准，精度可信。 |
| P4 | **bootstrap 双入口设计** | `bootstrap.sh`（shell 导出 DB_URL）和 `bootstrap.py`（Python 路径解析）提供两种入口，覆盖了 shell 脚本和 Python import 两种消费方式。两者的 DB 配置解析逻辑一致（POWERELF_DB_* → SRM_DB_* → 默认值），保持了单一来源。 |
| P5 | **references/ 文档网络互联** | 5 个 reference 文件之间有完整的相对路径交叉引用（`data-profiling.md` → `outlier-methods.md` → `mad.md` → `statistical-caution.md` → `analysis-qa-checklist.md`），形成了闭环的方法论体系。每个文件开头都标注了"跨 skill 单一事实源"定位和姊妹文档链接。 |
| P6 | **evolution/ 模板设计合理** | `parameters.template.md` 和 `feedback-log.template.md` 提供了清晰的参数追踪和反馈记录格式。README.md 描述了完整的进化流程（执行 → 反馈 → 归因 → 调参），且明确"本目录提供格式模板，各 skill 的实际参数值仍各自维护"。5 个主 skill 都已具备 evolution/ 目录。 |
| P7 | **block_raw_pymysql.py 设计巧妙** | 虽然未配置生效（H1），但 hook 代码本身设计周到：(a) 覆盖了 terminal 和 execute_code 两种 tool_input；(b) 解析命令中的 `cd` 指令以正确解析相对路径引用的 .py 文件；(c) 扫描多个候选根目录（CWD、/、/root、/tmp、/home/scada）；(d) 正则匹配 3 种 pymysql 直连模式；(e) block 消息包含完整的使用示例代码，指导 agent 改用 query()。 |
