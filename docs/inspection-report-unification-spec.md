# 智能巡检报告统一化 · 设计与实施方案（Agent 实施版）

> 版本：1.0 · 2026-08-13
> 读者：**实施 agent**（可能非评审者本人）
> 前置阅读：**必读** [`inspection-architecture-review.md`](./inspection-architecture-review.md)（讲清"为什么"）与 [`inspection-run-analysis-and-optimization.md`](./inspection-run-analysis-and-optimization.md)（既有根因）
> 本文档只讲"做什么 / 怎么做 / 怎么验收"。所有 `file:line` 引用以 2026-08-13 代码为准，实施前请用 `Read` 复核（行号可能已漂移）。

---

## 0. 阅读契约

- **红线（不可违反）**：任何改动后，`simulate_7d_data.py` + `inspection_analyzer.py --days 7` 必须仍 **5/5 命中问题设备、正常设备零误报**。这是引擎红线，每改一处都须回归。
- **每个 Task 自包含**：目标 / 涉及文件 / 当前代码 / 改动骨架 / 验收 / 测试 / 风险。可独立领取、独立提交。
- **代码骨架是参考实现**，不是 copy-paste 圣旨；须适配上下文、补类型与异常处理、对齐既有注释风格（`# Why:` 来源注释）。
- **SQL 纪律**：参数化查询、标识符走 `_ALLOWED_TABLES` 白名单、禁字符串拼接表名（见 `_shared/references/sql-discipline.md`）。

---

## 1. 背景与目标（精简）

实测（两次真实 hermes 会话 `20260813_140543_8f197a` / `20260813_185807_f55ddb`）证实：近 7 天巡检报告存在 5 类一致性问题，根因是 **Agent 按 inspection `SKILL.md` 边界指引跨 skill 调用 data-governance 工具**，把不同窗口/分组/计数口径的输出拼进同一份报告；且**置信度闸为硬编码**，矛盾报告仍被判可分享。详见评审文档 §3-5。

**目标**（按优先级）：
1. 报告数字全部由代码计算（消除 Agent 自由叙述带来的矛盾）；
2. 切断报告路径对 data-governance MAD/离线 的依赖（inspection 已有等价能力）；
3. 修复离线阈值真实 bug；
4. 清掉测试库 MOCK 污染；
5.（后续）DRY 下沉、图表增强。

**非目标**：不改 5 层判定逻辑、不改阈值字典 `THRESHOLDS`、不改自动诊断路由、不动业务内核。

---

## 2. 设计原则

| 原则 | 含义 |
|---|---|
| 引擎不动 | `lib/anomaly.py` / 15 个 `analyze_*` 的检测算法零改动 |
| 程序化优先 | 进报告的每个数字必须可由代码复现；Agent 只负责呈现，不发明数字 |
| 最小侵入 | 先用小改动消问题（T1–T3），大重构（DRY/图表）放后面且可跳过 |
| 可对账 | 汇总计数 ≡ 明细之和；不一致即降级置信度 |

---

## 3. 目标架构

### 3.1 AS-IS（当前）

```
用户提示词("...MAD统计/设备状态...")
   └─ Agent 按 SKILL.md "When NOT to Use" 边界
       ├─ inspection_analyzer  (15维, 窗口=7天, 按st_id分组)  ← 正确
       └─ data-governance:
            ├─ anomaly_detector×4   (MAD, 窗口=30天, 全表混排)  ← 误报源
            ├─ classify_offline     (离线, 全历史, 记录口径)    ← 524 源
            └─ profiler×4           (行数)
   → Agent 自由叙述合成报告（含"Ready to share"断言）
```

### 3.2 TO-BE（目标）

```
用户提示词
   └─ inspection_analyzer = 唯一报告生产者
        ├─ 15 维 analyze_*（含自带 analyze_mad_anomaly / analyze_equipment）
        ├─ validate_report_consistency() 一致性闸   ← 新增 T1
        └─ 渲染报告 + envelope（置信度由闸驱动）    ← 改 T1
   data-governance 工具：降级为"诊断原语"，仅供独立深度排查，禁止被 inspection 报告路径调用 ← T2 在 SKILL.md 立规
```

### 3.3 契约（进报告的数字须遵守）

1. **观测窗口**：`--days` 是唯一驱动计数的窗口。
2. **计数单位**：每个数字标注设备数 / 记录数；汇总用 `DISTINCT eq_id`。
3. **分组**：传感器统计按 `st_id`（禁全表混排）。
4. **一致性**：汇总 ≡ 明细；矛盾即 `confidence_tier = "Needs revision"`。

---

## 4. 任务分解

> 推荐顺序：**T1 → T5 → T3 → T2 → T6 → T8 → T7**（见 §5 依赖图）。T1/T2/T3 是"只做 3 件事"消除可见问题的最小集。

---

### T1 · 报告一致性断言闸（最高 ROI）

- **优先级**：P0 · **依赖**：无 · **工作量**：~1h · **针对**：N1 + 全部 5 问题

**目标**：在 `generate_report` 渲染前插入程序化校验；任一失败 → 置信度强制 `Needs revision`，违规清单写入 `data_notes`。替代当前硬编码的 `confidence_tier`。

**涉及文件**：`powerelf-inspection/impl/inspection_analyzer.py`

**当前代码**（行号近似）：
- `:1709-1712` 统计 `total_findings / critical / warnings / ok_count`
- `:1772` `qa_checklist = _QA_CHECKLIST.format(confidence_tier="With caveats")` ← 硬编码，无校验
- `:1753-1764` `data_notes` 构造

**改动骨架**：

```python
import re as _re  # 顶部已有 import re（按实际调整）

def validate_report_consistency(analyses, critical, warnings):
    """报告一致性断言闸（T1）。
    返回 (passed: bool, violations: list[str])。
    设计：汇总计数必须 ≡ 明细；不得"全成功"与"无数据"同现；不得"变化率N次"与"正常"同现。
    Why: 实测一份带 5 处矛盾的报告被评为 Ready to share（评审 N1）。
    """
    violations = []

    # 1. severity 汇总 ≡ findings 明细（口径漂移检测）
    exp_critical = sum(1 for a in analyses for f in (a.get('findings') or [])
                       if f.get('level') == 'CRITICAL')
    exp_warning  = sum(1 for a in analyses for f in (a.get('findings') or [])
                       if f.get('level') == 'WARNING')
    if exp_critical != critical or exp_warning != warnings:
        violations.append(
            f"severity 汇总与明细不符：报告 critical={critical}/warnings={warnings}，"
            f"明细 critical={exp_critical}/warnings={exp_warning}")

    # 2. "N 维全部成功" 与 "无数据维度" 不得同现
    dim_total = len(analyses)
    no_data_dims = [a.get('category') for a in analyses
                    if a.get('status') in ('无数据', '数据不足', 'inconclusive')]
    if no_data_dims and len(no_data_dims) < dim_total:
        # 即模板会渲染"dim_count 项"却同时有 data_notes 列无数据 → 误导
        violations.append(
            f"声明覆盖 {dim_total} 维，但 {len(no_data_dims)} 维无数据/不足：{no_data_dims}；"
            f"应将 dim_count 改为 {dim_total - len(no_data_dims)} 或显式标注未覆盖")

    # 3. "变化率 N 次" 与 "正常" 自相矛盾检测（问题③）
    for a in analyses:
        for f in (a.get('findings') or []):
            text = f"{f.get('message','')} {f.get('detail','')}"
            has_rate = bool(_re.search(r'变化率|change_rate', text)) and bool(_re.search(r'(\d+)\s*次', text))
            has_normal = ('正常' in text) or ('分布正常' in text)
            if has_rate and has_normal:
                violations.append(
                    f"{a.get('category')} 自相矛盾：既报变化率超限又标正常 —— {f.get('message','')[:50]}")

    # 4. MAD 维度数一致性：由 T2 保证报告路径不混入 governance MAD；此处仅兜底告警
    mad_sections = [a for a in analyses if a.get('category') == 'MAD统计异常']
    if len(mad_sections) > 1:
        violations.append(f"MAD 统计出现 {len(mad_sections)} 个来源，疑似跨工具混装")

    passed = len(violations) == 0
    return passed, violations
```

**接线**（`generate_report` 内，统计计算之后、渲染之前）：

```python
# 现有：critical / warnings / ok_count 已算（~:1710）
passed, violations = validate_report_consistency(analyses, critical, warnings)
confidence_tier = "Ready to share" if passed else "Needs revision"

# data_notes 追加违规（~:1753 data_notes 构造处）
if not passed:
    violation_block = "## ⚠ 一致性闸未通过（置信度降为 Needs revision）\n\n" \
        + "\n".join(f"- {v}" for v in violations)
    data_notes = (data_notes + "\n\n" + violation_block) if data_notes else violation_block

# 替换 :1772 硬编码
qa_checklist = _QA_CHECKLIST.format(confidence_tier=confidence_tier)
```

**验收标准**：
- 对当前污染数据重跑 `inspection_analyzer --days 7`，若报告仍混入 governance 数字（注：T2 前可能仍混入），闸应触发 ≥1 条 violation 且 `confidence_tier` 不再是默认值。
- 构造单元测试：喂入 `critical=1` 但 findings 实际 2 条 CRITICAL → 闸报 violation。
- 喂入 findings 含"变化率 5 次…正常" → 闸报 violation。

**测试步骤**：
```
source _shared/bootstrap.sh
python3 powerelf-inspection/impl/inspection_analyzer.py --db "$DB_URL" --days 7 --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('agent',{}).get('summary'))"
# 另：powerelf-inspection/lib/ 下补 test_consistency.py（参照 test_anomaly.py 风格），至少 3 个用例（sev 漂移/无数据同现/矛盾措辞）
```

**风险**：`status` 字段的取值集合（'无数据'/'数据不足'/'inconclusive'）须与 `no_data_result` 实际返回对齐——实施前 `grep -n "status" powerelf-inspection/impl/inspection_analyzer.py | head` 确认枚举，勿硬编码猜。

---

### T2 · 切断报告路径对 data-governance 的依赖（含离线分母实时化）

- **优先级**：P0 · **依赖**：建议 T1 之后（T1 兜底验证 T2 效果）· **工作量**：~1.5h · **针对**：N2 + N5 + 问题①②③⑤

**目标**：从源头阻止 Agent 把 data-governance 的 MAD/离线 输出混进 inspection 报告；同时确保离线数字用 inspection 的实时分母（`analyze_equipment` 已 `total=len(equip)`，即 149，非过期 128）。

**涉及文件**：
- `powerelf-inspection/SKILL.md`（"When NOT to Use" 表 ~`:128-131`，及目录结构/工具命令段）
- `powerelf-inspection/references/pitfalls.md`（新增一条"禁止跨 skill 混装报告"）

**当前代码**（`SKILL.md:126-131`）：
```
| 你想要的 | 应使用 |
| 数据质量（异常/缺失/离线/卡滞/插值） | `powerelf-data-governance` |
```
→ 这条边界**误导 Agent 在做巡检报告时也去调 governance**。

**改动**：
1. 将该行改为**限定语义**——governance 仅用于"独立的数据质量深度排查"，**明确声明巡检报告必须且只能由 `inspection_analyzer` 单一产出**：

```markdown
| 你想要的 | 应使用 |
| **作为巡检报告一部分的** MAD/离线/设备状态 | **本 skill（inspection_analyzer 自带维度 12 设备状态 / 维度 14 MAD）——禁止再调 data-governance 拼装** |
| 独立的数据质量深度排查（缺失/插值/卡滞专题） | `powerelf-data-governance`（独立产出，不进巡检报告） |
```

2. 在 SKILL.md "工具命令"段顶部加一条**报告纪律**：
```markdown
> **报告单源纪律**：巡检报告（Markdown / envelope）必须且只能由 `inspection_analyzer.py` 一次产出。
> 禁止在生成报告后再去调用 `powerelf-data-governance` 的 `anomaly_detector` / `classify_offline_by_duration` / `profiler`
> 并把其输出拼进报告——那会引入不同时间窗口（30天/全历史）、不同分组（全表混排）、不同计数单位（记录数），
> 历史上导致"524记录 vs 54/128""渗压507次却正常"等矛盾（见 docs/inspection-architecture-review.md）。
> inspection 已内置等价且按 st_id 分组的 MAD（维度14）与设备快照（维度12）。
```

3. `pitfalls.md` 新增第 8 条（同义摘要 + ❌/✅ 示例）。

**验收标准**：
- 重跑 hermes 同提示词，会话轨迹中 **inspection 报告生成后不再出现 `anomaly_detector` / `classify_offline` / `profiler` 调用**（用 `hermes sessions export` 核查 tool profile）。
- 报告"设备离线"数字 = `analyze_equipment` 的 `offline/total`（实时 149 分母），不再出现 `54/128`。
- 报告"MAD 统计"若出现，维度数 = `analyze_mad_anomaly` 的 `sensor_configs`（4），且按 st_id；不再出现全表"507 次变化率"。

**测试步骤**：
```
hermes -z "<同提示词>" --cli   # 观察是否还调 governance
hermes sessions export --format jsonl --session-id <新会话> -   # grep anomaly_detector/classify_offline 应为 0
```
> ⚠ 若 Agent 仍调 governance：说明 SKILL.md 措辞不够强或 Agent 读到的描述截断（见 memory `hermes-skill-description-truncation`：description 仅前 57 字符影响路由）。需同步检查 skill `description` 字段是否声明"报告自包含"。

**风险**：纯文档约束对 LLM 不是 100% 可靠——故 **T1 的一致性闸是程序化兜底**：即便 Agent 仍混装，矛盾数字也会被闸捕获并降级置信度。T1+T2 是"防御纵深"。

---

### T3 · 修复 offline_detector 阈值键不匹配（真实 bug）

- **优先级**：P0 · **依赖**：无 · **工作量**：~1.5h · **针对**：离线误判（渗压计批量判离线 76 天）

**目标**：让 `dg_equip_offline` 按站类型配置的阈值（SP=360/PP=120/YZ=0…）真正生效，替代当前"键不匹配→全量 60 分钟兜底"。

**涉及文件**：
- `powerelf-data-governance/impl/offline_detector.py`（`:43-53` `DEFAULT_THRESHOLDS`、`:90-91` 取阈值、`:75` `run_detection` 签名）
- `powerelf-data-governance/lib/offline.py`（`determine_status`）

**当前代码**（`offline_detector.py:90-91`）：
```python
if threshold is None:
    threshold = DEFAULT_THRESHOLDS.get(table, 60)   # 键=站类型码(SP/GN..)，table=表名 → 永不命中
```

**改动骨架**：

```python
# offline_detector.py 新增：按 st_id 解析站类型，读 dg_equip_offline
def resolve_threshold(engine, table, st_id, default=60):
    """按站类型从 dg_equip_offline 读阈值。
    解析链：st_id → eq_business_equip_relation.st_type → dg_equip_offline.<阈值列>
    任一环缺失 → 回退 DEFAULT_THRESHOLDS[st_type] → 再回退 default。
    Why: 旧代码 .get(table,60) 键是站类型却查表名，配置从未生效（评审 §6.1）。
    """
    # 1. 实施前必查真实列名（勿猜）：
    #    python3 -c "import sys;sys.path.insert(0,'_shared/lib');from db import columns;print(columns('eq_business_equip_relation'));print(columns('dg_equip_offline'))"
    st_type = _lookup_st_type(engine, st_id)          # SELECT st_type FROM eq_business_equip_relation WHERE <st_id列>=:st_id
    if st_type is None:
        return DEFAULT_THRESHOLDS.get(_table_to_stype(table), default)  # 表名→主站类型兜底映射
    configured = _lookup_dg_offline(engine, st_type)  # SELECT <阈值列> FROM dg_equip_offline WHERE st_type=:st_type
    if configured is not None and configured >= 0:
        return int(configured)
    return DEFAULT_THRESHOLDS.get(st_type, default)

# run_detection 内（:90-91）替换为：
if threshold is None:
    threshold = resolve_threshold(engine, table, st_id)
```

**注意**：
- `YZ` 类（渗压相关）在 `dg_equip_offline` 阈值为 **0**，语义是"不检测"。`resolve_threshold` 返回 0 时，`run_detection` 须短路返回 `{"status":"NOT_MONITORED", ...}` 而非按 0 分钟判离线。**实施时务必处理 0 值**。
- `st_id` 在不同表的主键列名可能不同（`eq_id`/`stcd`/`st_id`，见 pitfalls #2）——`_lookup_st_type` 的关联键须按表核实。

**验收标准**：
- 对已知渗压测站调用，返回阈值 = `dg_equip_offline` 配置值（非 60）。
- YZ 类返回 `NOT_MONITORED`，不再判离线。
- 单测：mock engine 返回 `st_type='SP'` + `dg_equip_offline` 值 360 → `resolve_threshold` 返回 360。

**测试步骤**：
```
source _shared/bootstrap.sh
python3 powerelf-data-governance/impl/offline_detector.py --db "$DB_URL" --table st_rsvr_r --st-id <SP站>
# 预期 threshold_minutes = 360（而非 60）
```

**风险**：`eq_business_equip_relation` / `dg_equip_offline` 的列名、`st_type` 取值集合须以 `columns()` 实查为准；若表为空或关联缺失，须优雅回退并日志告警（勿静默 fallback 到 60）。

---

### T4 · ~~离线分母实时化~~（已并入 T2）

`analyze_equipment`（`:889`）已 `total = len(equip)`（实时 149）。报告里的 `54/128` 来自 governance/Agent 叙述，**不是 inspection 代码 bug**。T2 切断 governance 后，报告自然用 inspection 的实时分母。无需独立改动，仅需在 T2 验收中确认。

---

### T5 · 模拟数据 MOCK 清理扩窗

- **优先级**：P0 · **依赖**：无 · **工作量**：~0.5h · **针对**：问题④（MAD 率虚高）

**目标**：`simulate_7d_data.py` 的清理范围从"近 `days` 天"扩到"覆盖 `anomaly_detector` 默认 30 天窗"，或提供全清 `eq_code='MOCK'` 模式，消除上一代 MOCK（rz≈786m / p=60mm）对 30 天 MAD 的污染。

**涉及文件**：`powerelf-inspection/scripts/simulate_7d_data.py`（`:97 _delete_window`、CLI 参数）

**当前代码**（`:97-115` 近似）：
```python
def _delete_window(conn, table, days):
    # 先按 eq_code='MOCK' 精删窗口内，兜底删整窗
    n = _exec(conn, f"DELETE FROM {table} WHERE deleted=0 AND tm >= NOW()-INTERVAL {days} DAY")
    ...
```

**改动骨架**：
```python
def _delete_mock(conn, table, window_days=None):
    """清 eq_code='MOCK' 数据。window_days=None 表示全清（推荐，防跨代残留）。
    Why: anomaly_detector 默认 30 天窗，旧清理只清 7 天 → 7–30 天带残留 MOCK 污染 MAD（评审 §6.2）。
    """
    if window_days is None:
        sql = f"DELETE FROM {table} WHERE deleted=0 AND eq_code='MOCK'"
    else:
        sql = (f"DELETE FROM {table} WHERE deleted=0 AND eq_code='MOCK' "
               f"AND tm >= NOW()-INTERVAL {window_days} DAY")
    return _exec(conn, sql)

# main() 新增 --clean-mode {window,all-mock}，默认 all-mock（或 --clean-days 30）
```

**验收标准**：
- 运行 `simulate_7d_data.py --days 7` 后，`SELECT COUNT(*) FROM st_rsvr_r WHERE rz>700 AND tm>=NOW()-INTERVAL 30 DAY` = 0（清干净）。
- 重跑 `anomaly_detector`，水位 MAD 异常率从 21.6% 回落到合理区间（接近 0）。

**测试步骤**：
```
python3 powerelf-inspection/scripts/simulate_7d_data.py --days 7
python3 -c "<上面的 COUNT 校验>"
```

**风险**：`all-mock` 模式会删除所有 `eq_code='MOCK'` 历史；若库内有非本次模拟的、需保留的 MOCK 数据，改用 `--clean-days 30`。实施前 `SELECT DISTINCT eq_code FROM <表>` 确认 MOCK 标记一致性。

---

### T6 · 清理 powerelf-monitor 版本目录重复（side-fix）

- **优先级**：P1 · **依赖**：无 · **工作量**：~0.5h · **针对**：N4（monitor 路由歧义）

**目标**：消除"2 个 skill 同名 `powerelf-monitor`"导致的 `skill_view` 拒载。

**涉及文件**：`~/.hermes/skills/` 下重复的 monitor 目录（及可能的 `external_dirs`）。

**排查**：
```
grep -rl "name: powerelf-monitor" ~/.hermes/skills/ ~/.hermes/external_dirs 2>/dev/null
# 预期命中 ≥2 个 SKILL.md
```

**改动**：保留现行版本目录，将旧版目录改名（如 `powerelf-monitor.old/`）或删除其 `SKILL.md` 的 `name:` 行使其不再被索引。参照 memory `powerelf-module-version-duplication`（chatbi/monitor/early-warning 各有新旧版目录）。

**验收标准**：`skill_view powerelf-monitor` 返回单个 skill，不再 `Ambiguous`。

**风险**：勿误删现行版本——改前 `ls -la` 确认哪个是 symlink/现行、哪个是旧版。

---

### T7 · MAD / 离线 DRY 下沉 `_shared/lib`（后续，可跳过）

- **优先级**：P2 · **依赖**：T2（报告路径稳定后再合并）· **工作量**：~1d · **针对**：三套重复实现

**目标**：MAD 与离线算法各留**唯一实现**于 `_shared/lib/`（outliers.py / offline.py），inspection 与 governance 同源调用，消除分叉。

**步骤**：
1. 以 inspection `analyze_mad_anomaly`（按 st_id + 季节护栏）为基准，提取检测核心到 `_shared/lib/outliers.py`。
2. governance `anomaly_detector.py` 改为调用该核心（保留其 CLI / 30 天窗能力，但分组逻辑统一为按 st_id）。
3. 离线同理：三路径（snapshot / classify_by_duration / freshness）统一到 `_shared/lib/offline.py`，`resolve_threshold`（T3）归入。

**验收**：`grep -rn "def mad_anomaly\|def determine_status" powerelf-*/ _shared/` 命中点收敛到 `_shared/lib`。

**风险**：跨两个 skill 的接口变更面大，须全量回归两 skill 的 eval（inspection 47 用例 + governance evaluate_v2）。**T1–T6 已消除可见问题，T7 非必须，建议单独立项。**

---

### T8 · 报告增强（后续）

- **优先级**：P2 · **依赖**：T1 + T3 · **工作量**：~2-3d · **针对**：体验

按评审 §7 + 既有文档 §6.4 / §7：
1. **离线三口径**（快照 A / 窗口新增 B / 窗口活跃度 C）落进 `analyze_equipment` 与模板。
2. **三层窗口声明**：报告头部统一声明 + 每章节标题注窗口 + 计数口径统一（既有文档 §5.2）。
3. **图表**：matplotlib 趋势图 / 异常分布 / 离线双口径 / 水位-渗压关联（环境已有 matplotlib 3.11.1）。
4. **附录数据覆盖清单**：各表窗口内行数，防"无数据"误判。

---

## 5. 实施顺序与依赖图

```
T1(一致性闸) ──┐
T5(MOCK清理) ──┼──→ 可重跑出"干净基线报告"
T3(阈值修复) ──┘
        │
        T2(切断governance) ──→ T6(monitor去重, 独立可并行)
                │
                T8(三口径/图表/窗口声明)
                │
                T7(DRY下沉, 可选)
```

- **最小可见修复集**：T1 + T2 + T3（评审"只做 3 件事"）。
- **可并行**：T5 / T6 与任何任务并行。
- **必须串行**：T3 在 T8 的"活跃度 C 口径"之前（否则 C 建立在错误阈值上）；T7 在 T2 之后。

---

## 6. 端到端验收

实施完 T1+T2+T3+T5 后，执行以下验收（全绿才算完成）：

```
# 0. 环境与数据
source _shared/bootstrap.sh
python3 powerelf-inspection/scripts/simulate_7d_data.py --days 7

# 1. 引擎红线（不可退化）
python3 powerelf-inspection/impl/inspection_analyzer.py --db "$DB_URL" --days 7 --json > /tmp/env.json; echo $?
#   期望 exit=2（CRITICAL）；envelope agent.findings 命中 5 台问题设备（渗压93/位移97/泵89/闸90/雨85）

# 2. 一致性闸
python3 -c "import json;d=json.load(open('/tmp/env.json'));print('status',d['agent']['status'])"
grep -c "一致性闸未通过\|Needs revision" <(python3 powerelf-inspection/impl/inspection_analyzer.py --db "$DB_URL" --days 7 --output /dev/stdout > /tmp/r.md; cat /tmp/r.md)
#   干净数据下应为 0（Ready to share）；故意构造矛盾时应 ≥1

# 3. 离线阈值生效
python3 powerelf-data-governance/impl/offline_detector.py --db "$DB_URL" --table st_rsvr_r --st-id <SP站>
#   threshold_minutes=360（非 60）

# 4. hermes 端到端不再跨 skill
hermes -z "<同提示词>" --cli   # 观察输出
hermes sessions export --format jsonl --session-id <新会话> - | grep -c "anomaly_detector\|classify_offline"
#   期望 0
```

**完成判据**：
- 引擎 5/5 命中零误报不退化；
- 报告不再出现 `524` / `54/128` / `507次却正常` / `21.6%(MOCK)` / "15维全成功 vs 4维无数据"；
- 一致性闸对污染数据触发降级、对干净数据放行；
- 离线阈值按 `dg_equip_offline` 生效。

---

## 7. 回归保护

- 每个 Task 提交前跑该 skill 的 eval：
  - inspection：`python3 powerelf-inspection/impl/eval_runner.py`（Layer A 47 用例须仍 100%）+ `impl/test_inspection.py`。
  - governance（T3/T7 触及时）：`powerelf-data-governance/autoresearch-data-governance/evaluate_v2.py`。
- 引擎红线（§6 步骤 1）是 hard gate，任何 PR 触红即 block。

---

## 8. 范围边界（不做什么）

- ❌ 不改 `lib/anomaly.py` 5 层判定算法、不改 `THRESHOLDS` 兜底字典、不改自动诊断路由表 `DIAG_ROUTES`。
- ❌ 不改业务内核（`quality.py` / `defect_predict.py` / `route_opt.py`）。
- ❌ 不把 inspection 改成依赖 governance import（违反"无代码 import"边界，见 `SKILL.md:300`）。
- ❌ 不在本批做 T7（DRY）/ T8（图表）——它们独立立项，不阻塞可见问题修复。

---

## 9. 实施清单（checklist）

- [ ] T1 一致性闸：`validate_report_consistency` + 接线 + 3 个单测
- [ ] T2 SKILL.md 边界 + 报告单源纪律 + pitfalls #8
- [ ] T3 `resolve_threshold` + 0 值短路 + 单测
- [ ] T5 `_delete_mock` + `--clean-mode`
- [ ] T6 monitor 去重
- [ ] §6 端到端验收全绿
- [ ] 引擎红线回归通过
- [ ] 更新 `docs/inspection-run-analysis-and-optimization.md` 状态（标注已修复项）
