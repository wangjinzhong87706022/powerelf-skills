---
name: powerelf-data-governance
description: "监测数据（水库水位/雨量/渗压/渗流/GNSS）有没有异常值、缺失、离线、卡滞？→数据质量治理：MAD/缺失/离线检测、评分、插值、报告。"
version: 2.0.0
author: Powerelf Team
license: MIT
platforms: [linux, windows, macos]
prerequisites:
  env_vars: [POWERELF_DB_HOST, POWERELF_DB_PORT, POWERELF_DB_NAME, POWERELF_DB_USER, POWERELF_DB_PASSWORD]
metadata:
  hermes:
    tags: [water-conservancy, data-governance, quality, anomaly, interpolation, scoring, offline, stagnation, correlation, writeback]
    related_skills: [powerelf-early-warning, powerelf-monitor, powerelf-chatbi, powerelf-inspection]
---

# 数据治理 Skill

水利工程数据质量治理引擎。

**区分**：本 skill 分析"数据本身有没有异常/缺失/质量问题"，不是查询"数据内容是什么"。

---

## ⚠️ 强制指令（每次对话必须遵守）

> **优先级高于所有其他内容**，违反 = 错误响应。

### 核心原则：优先用内置脚本，禁止自己写代码（最高优先级）

**所有任务必须优先调用 skill 内置的 impl/ 或 scripts/ 脚本**，禁止自己写 Python/SQL 到 `/tmp/` 再用 terminal 跑。

内置脚本已经处理好 `eq_id`/`stcd` 关联、`deleted=0` 过滤、Decimal 格式化、阈值边界等高频翻车点。直接调用可省 10+ 次工具调用和 200+ 秒反复 patch。

**结论必须自述所用方法名**：检测/分析类回答要写明用了什么方法（MAD/中位数绝对偏差、IQR、变化率、插值、环比、周期等，中英任一）——这是判定可追溯、可人工复核的最低要求，只给结论不述方法 = 不合格回答。

| 任务类型 | 必用内置脚本 | ❌ 禁止行为 |
|---|---|---|
| 异常检测（MAD/IQR） | `python3 impl/anomaly_detector.py --db "$DB_URL" --table <T> --field <F> [--method mad|iqr]` | ❌ 自己写 `/tmp/check_xxx.py` |
| 异常明细拆分/CSV 导出 | `python3 impl/anomaly_detector.py --db "$DB_URL" --table <T> --field <F> --detail full --format csv --output /tmp/xxx.csv`（含按天聚合 daily_summary） | ❌ 自己写 `/tmp/pptn_anomaly_detail.py` 拼 CSV |
| 缺失检测 | `python3 impl/missing_detector.py --db "$DB_URL" --table <T> --st-id <ID> --freq <F> --days <D>` | ❌ 自己写 `/tmp/missing_xxx.py` |
| 离线分级 | `python3 scripts/classify_offline_by_duration.py --db "$DB_URL"` | ❌ 逐站循环检测、手写 SQL |
| 日报/异常报告生成 | **日**: `python3 impl/generate_report.py --type anomaly --date YYYY-MM-DD`　**月度汇总**: `--date YYYY-MM`（如 `2026-05`，跨整月汇总全部表异常，秒级出报告；月度/区间报告一律用此参数，勿自拼 SQL） | ❌ 自己拼 Markdown、循环单日查询 |
| 质量评分（单设备算分） | `python3 impl/quality_scorer.py --missing-ratio <0-1> --anomaly-ratio <0-1> --offline-date-ratio <0-1> --anomaly-date-ratio <0-1> --offline-count <N> --anomaly-count <N> --actual-records <N> --expected-records <N> [--previous-total <分>]`（四维加权：完整性35%+准确性10%+及时性40%+一致性15%，输出总分+等级+趋势；各比值从 `missing_detector`/`offline_detector`/`profiler` 输出取。注意：本脚本算**单个设备**，不吃 `--db`，详见 `rules/quality-scoring.md`） | ❌ 自己实现评分公式 |
| 指定表和测站检测 | `python3 impl/offline_detector.py --db "$DB_URL" --table <T> --st-id <ID> --threshold <秒>`（单站离线检测） | ❌ 自己写 `/tmp/check_st_xxx.py` |
| 概览/总览分析 | `python3 impl/profiler.py --db "$DB_URL" --table <T>`（含概览/概览明细） | ❌ 自己写 `/tmp/overview_xxx.py` |
| 环比/趋势分析 | ⚠️ profiler.py **没有** `--compare-days` / `--trend` 参数（实测报 unrecognized arguments）；实际参数仅 `--db --table [--field] [--sample] [--format {json,text}]`。趋势对比改用 `generate_report.py --type anomaly --date <日期>` 跑本周/上周各一天再对比，或按 references/analysis-guide.md 自写（一次写对） | ❌ 调用不存在的 `--compare-days`/`--trend` 参数；❌ 自己拼环比 SQL |
| 设备筛选/较差等级（"低于60分"类） | **评分分级口径：≥90 A优秀 / ≥80 B良好 / ≥60 C一般 / <60 D较差（需维护、重点关注）**。全库一键扫描**没有现成命令**（不存在 `--filter-grade`/`--top` 参数）：先对目标表用 `missing_detector`/`offline_detector` 按站聚合指标，再按上表分级筛出 <60 的站；少量重点站可逐站用 `quality_scorer.py` 算精确总分。回答时先给分级口径、再列设备清单 | ❌ 自己写全库扫描大脚本反复 patch（10 次收敛纪律适用）；❌ 调用不存在的 `--db --filter-grade --top` 参数 |
| MTTR/时长计算 | `python3 impl/offline_detector.py --db "$DB_URL" --table <T> --st-id <ID> --mttr`（含 MTTR 输出） | ❌ 自己写时长 SQL |
| 插值/缺失补全 | `python3 impl/interpolate.py --db "$DB_URL" --table <T> --field <F> [--st-id <ID>] [--days 7]`（四策略自适应：线性/二次/样条/滑动平均，输出所选策略+逐点填补值+缺失率；只报告不写回库）。**用户未指明测站/字段/窗口时禁止先 clarify**——直接跑缺省（如 `--table st_rsvr_r --field rz --days 7`），先报告"哪个站缺失最多+缺失率 TOP"，末尾再问要不要深挖某站；要快速定位缺哪站可先跑 `impl/missing_detector.py` | ❌ 自己写 `/tmp/interpolate_xxx.py` 反复 patch；❌ 开工前先问"缺失的具体情况"（先跑缺省再问，不空转） |
| 连续相同值检测 | ⚠️ 暂无内置脚本，允许参考 `references/analysis-guide.md` 自写，但**必须一次写对** | ❌ 反复 patch 重跑 |
| 趋势分析（改善/恶化） | ⚠️ 同上：profiler.py 无 `--trend` 参数；用 generate_report.py 跑两周同日期对比，或自写趋势 SQL（一次写对） | ❌ 调用不存在的 `--trend 30d` 参数；❌ 自己写趋势 SQL 反复 patch |
| 异常明细 + 设备关联 | `python3 impl/anomaly_detector.py --db "$DB_URL" --table <T> --field <F> --detail full --format csv --output /tmp/xxx.csv`（**CSV 已含 st_id 设备列**，一次拿全异常+设备维度，无需再查关联表） | ❌ 用 `execute_code` 自己写代码串联（沙箱会 scrub `.env` 的 `DB_URL` 导致脚本报错，且会触发 `code_retry_guard` 插件 bug 杀进程） |

**自写豁免的收敛纪律**：表中仍标 ⚠️"暂无内置脚本"的任务（如连续相同值检测）确需自写时，先读 schema.md 确认字段、**一次写对**；若 10 次工具调用内仍未跑通，**必须停下，先输出已得到的中间结论**（已发现什么、卡在哪、建议下一步）再决定是否继续——禁止让最终回答停在"让我检查一下…"式的半成品中间态。

**判定流程**（每次对话第一步必须执行）：

0. **先判归属（最高优先级，先于识别任务类型）**：若查询是要"查某个具体值 / 实时状态 / 趋势可视化 / 预警判断 / 纯取数"——这**不是数据治理任务**（本 skill 只管"数据本身有没有质量问题"，不管"数据内容是什么"）。**只回一行路由建议并立即结束**：
   - 当前水位 / 雨量值（实时取数）→ `powerelf-chatbi`
   - 水位变化曲线 / 趋势可视化 → `water-situation`
   - 是否超警戒水位、发预警通知 → `powerelf-early-warning`
   - 闸门开度 / 泵站运行状态 → `powerelf-monitor` / `gate-pump-operation`
   - 纯查某张表的数据 → `powerelf-chatbi`

   回复模板：`这是<复述用户任务关键词>（<实时值/运维状态/预警/纯取数/维保周期等>）查询，不属于数据治理（数据质量分析）。请改用 \`<目标skill>\`。`——**必须复述用户原话里的任务关键词**（如问"是不是该保养了"→答"维保周期检查"），确认理解无误再转出。
   ⛔ 命中此步后**必须停止**：禁止 `skill_view` 加载目标 skill、禁止 `terminal` / `execute_code` 代为查询、禁止自己拼 SQL 取数。路由建议给出即结束，代劳会造成 10+ 次无谓工具调用。

1. **识别任务类型**：异常检测 / 缺失检测 / 离线分级 / 日报 / 评分 / 概览
2. **查上表**：命中 → 直接调内置脚本（跳到"工具命令"段复制命令行参数）
3. **未命中**：才允许参考 `references/` 自己写代码，但必须遵守下方"写代码前必读"

**自检闸**（交付前必问自己）：
- ❓ 我是不是又自己在 `/tmp/` 写脚本了？→ 删掉，改调内置脚本
- ❓ 内置脚本参数够不够？→ 不够先看 `--help`，再看 `references/analysis-guide.md`，最后才考虑 wrap
- ❓ 用户问"严重吗/什么级别/严重性/分级"？→ 必须用 INFO/WARNING/ERROR/CRITICAL 文本分级（见下），禁止 emoji

### 严重性分级输出规范（问"严重吗/级别/分级"时强制）

当用户询问任何与**严重性 / 级别 / 严重程度 / 分级**相关的问题时（关键词：严重吗、什么级别、严重性、分级、等级、卡滞严重吗、异常严重吗），**必须用运维日志标准四级文本分级**输出，**禁止 emoji（🔴🟡🟢）/自创分级（"中等关注"/"非紧急"等）**：

| 级别 | 含义 | 典型场景 |
|---|---|---|
| **CRITICAL** | 紧急，立即处置 | 大面积断档(>72h)、整表数据异常、安全相关测站离线 |
| **ERROR** | 严重，当日处置 | 单站连续卡滞/漂移、关键设备长时间离线 |
| **WARNING** | 警告，关注趋势 | 短时离线、低频采集、单点突变 |
| **INFO** | 提示，记录备查 | 已自恢复、边界值、偶发零值 |

**输出必须包含**：①总体级别判定（如"总体：**WARNING**"）；②每类问题/设备的级别标注（用上表文本，非 emoji）；③对应处置建议。复用 `generate_anomaly_report` 已有的分级口径，不要自创体系。

### 离线分级任务（最高优先级）

当用户询问任何与**离线设备分级**相关的问题时（关键词：离线/offline/批量分级/所有离线设备），**必须**：

1. **使用批量脚本**（禁止逐站循环）：
   ```bash
   python3 scripts/classify_offline_by_duration.py --db "$DB_URL"
   ```

2. **输出限制**：
   - 默认：`--limit 20`（前 20 台）
   - 用户要求"全部"/"完整"时：`--full`

3. **禁止行为**：
   - ❌ 不要调用 `impl/offline_detector.py`（单站检测）
   - ❌ 不要手写 SQL 逐台检测
   - ❌ 不要重新实现分级逻辑

### 其他任务

参考下方"使用指南"和 `references/`。

---

## 使用指南

### 快速查找

- **数据库连接 / 表结构 / 常用 SQL**: `references/quick-reference.md`
- **分析方法 API**: `references/analysis-guide.md`
- **最佳实践 / Pitfalls**: `references/best-practices.md`

### 规则文件（离线检测 / 异常检测 / 缺失检测）

| 任务 | 规则文件 |
|------|---------|
| 离线检测 | `rules/offline-detection.md` |
| 异常检测（MAD） | `rules/anomaly-detection.md` |
| 缺失检测 | `rules/missing-detection.md` |
| 智能插值 | `rules/interpolation.md` |
| 质量评分 | `rules/quality-scoring.md` |

---

## 写代码前必读（高频翻车点）

> 单条错 ≈ 2 轮 LLM 调用 ≈ 24 秒，照做可省大量重试。

### 0. 连哪个库

- 本 skill 连**本地 `powerelf_srm_yml`**（环境变量 `POWERELF_DB_*`）。
- ❌ 不是远程 `192.168.100.103` 的 SL323 库。**河道水位 `st_river_r` 已于 2026-08-19 从 SL323 迁入本地（54 站 / 42.4 万行），本地库已可直接查，禁止再连 SL323。**
- ✅ 凭证由 `query()` 自动读取，**永远不需要、也不应该**看到密码。
- 🚫 **禁止 grep 代码找密码**，**禁止把密码打印到输出**。

### 1. 查库只用 `query()`，禁止手写 pymysql

```python
import sys, os
sys.path.insert(0, os.path.join(
    os.environ.get("POWERELF_SKILLS_ROOT", "/home/scada/powerelf-skills"), "_shared", "lib"))
from db import query

rows = query("SELECT * FROM st_rsvr_r WHERE deleted=0 LIMIT 5")  # → list[dict]
```

- 🚫 禁止：`conn.execute(`、`cursor().execute(...).fetchall()`、`pymysql.connect(`
- ✅ 只用：`query(sql)` / `query_multi([sql1, sql2])`
- 📌 上述禁令针对 **agent 手写脚本**；`lib/writeback.py`（回写）/`lib/overview.py` 等库内模块为受信基础设施，可用 raw connection 完成写操作与复杂查询——agent 应调用其函数，而非自行重写连接

### 2. 脚本用 terminal 跑，不要用 execute_code

- ✅ 数据库脚本写文件后用 terminal 跑：`python3 /tmp/xxx.py`

### 3. 列名调 `columns(table)`，禁止猜

```python
from db import columns
for c in columns("st_rsvr_r"): print(c["column"], c["type"], c["meaning"])
```

### 4. 关联键用 `eq_id`，不用 `stcd`

- `stcd` 99.8% 为 NULL → 用它 JOIN 会得全 None 设备名
- 统一 `JOIN eq_equip_base e ON r.eq_id = e.id`
- ⚠️ `eq_id` 是 bigint、`code` 是字符串，不能 `eq_id='606K...'`

### 5. 每条 SQL 必须带 `deleted = 0`

漏写会捞出已删行。

---

## When to Use

| 场景 | 说明 |
|------|------|
| 检测监测数据是否有异常值（MAD） | 自适应窗口 MAD |
| 水库水位/雨量/渗压数据异常检测 | 分指标阈值 |
| 数据有没有问题/数据质量怎么样 | 概览型分析 |
| 判断设备是否离线及离线时长分级 | 三态+分级（优先批量脚本） |
| 评估设备数据质量评分 | 四维度评分 |
| 生成 YYYY-MM-DD 数据质量日报 | `impl/generate_report.py --date YYYY-MM-DD` |

## When NOT to Use

| 场景 | 应使用 |
|------|--------|
| 查询水库当前水位是多少 | `powerelf-chatbi` / `water-situation` |
| 查询河道水位趋势曲线 | `water-situation` |
| 查询是否超过警戒水位 | `powerelf-early-warning` |
| 闸门/泵站运行状态查询 | `powerelf-monitor` / `gate-pump-operation` |
| 纯数据查询不涉及分析 | `powerelf-chatbi` |

---

## 工具命令

**前置**：执行任何脚本前，先设置 DB_URL：

```bash
source ../_shared/bootstrap.sh  # 导出 DB_URL
```

### 批量离线分级（推荐）

```bash
# 基础用法（分级汇总 + 前 20 台）
python3 scripts/classify_offline_by_duration.py --db "$DB_URL"

# 完整列表
python3 scripts/classify_offline_by_duration.py --db "$DB_URL" --full

# 导出 CSV
python3 scripts/classify_offline_by_duration.py --db "$DB_URL" --format csv --output /tmp/offline.csv
```

### 单站离线检测

```bash
python3 impl/offline_detector.py --db "$DB_URL" --table st_pressure_r --st-id 201 --threshold 60
```

### 异常检测

```bash
# MAD（默认）
python3 impl/anomaly_detector.py --db "$DB_URL" --table st_pressure_r --field water_pressure --threshold 4.0

# IQR（雨量/流量）
python3 impl/anomaly_detector.py --db "$DB_URL" --table st_pptn_r --field p --method iqr
```

### 缺失检测

```bash
python3 impl/missing_detector.py --db "$DB_URL" --table st_rsvr_r --st-id 128 --freq 60 --days 1
```

### 日报生成

```bash
python3 impl/generate_report.py --date 2026-07-28
python3 impl/generate_report.py --date 2026-07 --type anomaly
```

---

## 工作流

```
确定时间窗口 → 获取原始数据 → 选择分析方法 → 执行算法 → 生成判定结果 → 记录到治理表
```

**第一步必须确定分析时间窗口**：

- 用户指定 → 使用用户给定的起止时间
- 用户未指定 → 按分析类型选择默认窗口：
  - 缺失/异常/数据统计 → 前一天
  - 离线检测 → 滚动检测，无固定窗口
  - 质量评分 → 当前月

**后续步骤**：

1. 从原始监测表获取数据（限定在时间窗口内）
2. 根据任务类型选择对应分析方法
3. 执行内嵌算法
4. 生成结构化判定结果
5. **数据回写** — 调用 `lib/writeback.py`
6. **生成报告** — 调用 `lib/report.py`

---

## 核心数据表（简版）

**完整表结构**: `_shared/references/schema.md`

### 设备表

| 表名 | 关键字段 |
|------|---------|
| eq_equip_base | id, name, code, type_flag, status(0=离线/1=在线/2=异常) |
| eq_business_equip_relation | business_table, eq_id, offline_threshold |
| eq_equip_offline_record | equipment_code, total_offline_duration(秒) |

### 监测表

| 表名 | 时间列 | 关联键 |
|------|--------|--------|
| st_rsvr_r | tm | eq_id |
| st_river_r | tm | eq_id |  <!-- 2026-08-19 从 SL323 迁入，54站/42.4万行，水位 z/流量 q -->
| st_pptn_r | tm | eq_id |
| st_pressure_r | tm | eq_id |
| st_percolation_r | tm | eq_id |
| dsm_dfr_srvrds_srhrds | tm | eq_id (int) |

---

## Pitfalls（高频错误）

1. **MAD 窗口参数误设** — 窗口过小漏检，过大约束无意义
2. **插值长度误用** — 连续缺失超过 3 天不应插值
3. **评分分母选错** — 应在线设备数 ≠ 有数据设备数
4. **离线阈值错配** — 不同站型离线阈值不同
5. **回写权限失控** — 只读账号不应执行 writeback

**完整列表**: `references/best-practices.md`

---

## Validation Gate（交付前 QA 闸）

报告交付前必须检查：

1. **数据完整性** — 时间窗口内的数据是否完整？
2. **异常判定合理性** — 异常值是否经过 MAD/IQR 验证？
3. **设备状态一致性** — 离线设备是否与 eq_equip_base.status 一致？
4. **置信度评级** — `Ready to share` / `Share with caveats` / `Needs revision`（项目 canonical，与 `_shared/references/analysis-qa-checklist.md` 及 `lib/report.py` 实际输出一致；Agent 自填，不自动打分）

**详细清单**: `references/best-practices.md`

---

## Related Skills

- `powerelf-early-warning` — 预警规则引擎
- `powerelf-monitor` — 实时监控分析
- `powerelf-chatbi` — NL2SQL 智能查询
- `powerelf-inspection` — 智能巡检

---

**详细文档**: 见 `references/` 目录
