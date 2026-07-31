# 水利领域知识库（实体消歧 + 术语 + 阈值语义 + 派生指标）

> **本文件职责**：管"**词义**"——用户说的"水位/流量/雨量/警戒水位"到底指哪张表哪个列、水利术语什么意思、阈值在本项目里怎么存。
>
> **不在本文件（分工，勿重复）**：
> | 要查 | 去哪 |
> |---|---|
> | SQL 写作 gotchas（`deleted=0` / 关联键类型 / varchar CAST / JOIN 爆炸） | `references/validation-checklist.md` §一 |
> | 表 DDL / 字段类型 / 列注释（COLUMN_MEANINGS） | `_shared/references/schema.md` |
> | 表→字段速查映射、典型 SQL 模式 | `rules/sql-generation.md` |
> | 报告措辞 / 统计陷阱（平均之平均、不完整周期） | `_shared/references/analysis-qa-checklist.md` + `statistical-caution.md` |
>
> **何时查本文件**：① 生成 SQL **选表/选列前**（消歧）② 填 envelope 的 `assumptions` 时（把"我假设水位= rz"变成**有据**的声明）③ VALIDATE 的"实体消歧"检查项。运行时拿不准列还存在性 → 先 `columns(table)`（见 governance `lib/db.py`），本文件给语义层。

---

## 一、实体消歧表（核心）

> 水利数据的根本性错误不是语法错，是**选错表/选错列**——"水位"在 6 张表里都有列。下表给**自然语言词 → 候选 `表.列` → 消歧线索**。

### 1.1 水位类

| 用户说的 | 候选（表.列） | 消歧线索 |
|---|---|---|
| **水位**（无上下文） | 水库 `st_rsvr_r.rz`（库上水位）/ 河道 `st_river_r.z` / 闸站 `st_was_r.upz`(上游)、`dwz`(下游) / 潮汐 `st_tide_r.tdz` / 防洪区 `st_flood_r.z` / 水库下游 `st_rsvr_r.blrz` | "水库/库"→`rz`；"河道/河"→`z`；"闸/上游/下游"→`upz`/`dwz`；含"潮"→`tdz`。**默认按水库 `rz`**（本项目主力表，194k 行；见 `schema.md` load-bearing 标注）。歧义未解→`Share with caveats` 并列候选，**勿猜**。 |
| 库水位 / 坝上水位 | `st_rsvr_r.rz` | "水库/坝上"明确 → `rz`。 |
| 下游水位 | 水库 `st_rsvr_r.blrz` / 闸站 `st_was_r.dwz` | "水库下游"→`blrz`；"闸下游"→`dwz`。 |

### 1.2 流量类

| 用户说的 | 候选（表.列） | 消歧线索 |
|---|---|---|
| **流量**（无上下文） | 水库入库 `st_rsvr_r.inq` / 出库 `st_rsvr_r.otq` / 河道 `st_river_r.q` / 闸站总过闸 `st_was_r.tgtq` / 闸门 `rei_gate_r.gtq` / 防洪区 `st_flood_r.q` | "入库/出库"→`inq`/`otq`；"河道"→`q`；"闸"→`tgtq`/`gtq`。**入库 vs 出库是最常见歧义**——未指定默认**两者都给**（`inq, otq` 同列），勿只取一个。 |
| 过闸流量 | 闸站总 `st_was_r.tgtq` / 单闸门 `rei_gate_r.gtq` | "总过闸/整站"→`tgtq`；"某闸门"→`rei_gate_r.gtq`（按 `eq_id` 定位单门）。 |

### 1.3 雨量类（⚠️ 单位陷阱高发）

| 用户说的 | 候选（表.列） | 消歧线索 |
|---|---|---|
| **雨量** | 时段 `st_pptn_r.p`（`dr`=**分钟**）/ 日 `st_pptn_r.dyp` / 累计 `st_pptn_r.cump` / 分区时段 `st_pptn_region_r.drp`（`intv`=**小时**）/ 日累计 `st_pptn_dp_s.dp` | 单站→`st_pptn_r`；区域/面雨量→`st_pptn_region_r`；"今天/日"→`dyp`/`dp`；"累计"→`cump`。**`dr` 是分钟、`intv` 是小时**——算雨强换算别混（见 §四）。 |
| 时段雨量 | `st_pptn_r.p` | `p` 是一个 `dr` 分钟时段内的雨量；要得"每小时"需 `p / dr * 60`。 |

### 1.4 大坝安全 / 渗流渗压

| 用户说的 | 候选（表.列） | 消歧线索 |
|---|---|---|
| **压力** | 渗压 `st_pressure_r.ext_pressure` / 水位压力 `st_pressure_r.water_pressure` | "渗压/孔隙水压"→`ext_pressure`；均 kPa，应与库水位正相关（合理性校验用）。 |
| 渗流量 | `st_percolation_r.percolation`（L/s） | 注意单位是 **L/s** 不是 m³/s。 |
| 变形 / 位移 | 本次变化 `dsm_dfr_srvrds_srhrds.wgs84_delta_h/x/y` / 累计 `wgs84_total_h/x/y` / 速率 `speed_gh/gx/gy` | "本次/单次"→`delta_*`；"累计"→`total_*`；"速率"→`speed_g*`。单位 mm。 |

### 1.5 设备工情 / 墒情

| 用户说的 | 候选（表.列） | 消歧线索 |
|---|---|---|
| 电压 / 电流 / 功率 / 频率 | `rei_pump_r.uab/ubc/uca`（电压）/ `ia/ib/ic`（电流）/ `p`（功率）/ `freq`（频率） | ⚠️ **全是 varchar**，数值比较/聚合前 `CAST(... AS DECIMAL)`（见 `validation-checklist.md` §一）。 |
| 闸门开度 | `rei_gate_r.gtophgt`（开启高度 m）/ `gtopnum`（开启孔数）/ `status`（开关 bit） | "开度/开启高度"→`gtophgt`；"开了几孔"→`gtopnum`。 |
| 土壤含水量 / 墒情 | `st_soil_moisture_r.soil_water10cm~100cm`（各深度 %） | 注意是**多深度分层**（10/20/.../100cm），未指定深度→默认给 10cm 或全列。 |
| 土温 | `st_pressure_r.ext_temperature`（渗压表附带）/ `st_soil_moisture_r.soil_temp10cm~100cm` | 设备附带温度→`ext_temperature`；土壤分层温度→`soil_temp*`。 |

---

## 二、特征水位与告警术语

### 2.1 水库/河道特征水位（从高到低）

| 术语 | 定义 | 适用 |
|---|---|---|
| **校核洪水位** | 遇**校核标准**洪水时水库/河道达到的最高水位（最高设防） | 水库 |
| **设计洪水位** | 遇**设计标准**洪水时达到的最高水位 | 水库 |
| **正常蓄水位** | 水库正常情况下允许维持的最高水位（兴利上限） | 水库 |
| **汛限水位** | 汛期允许兴利蓄水的**上限**（防汛硬约束，预留防洪库容）；汛期 ≤ 正常蓄水位 | 水库 |
| **保证水位** | 防洪工程能**安全抗御**的最高水位（堤防设计依据） | 河道/堤防 |
| **警戒水位** | 达到此水位**可能出险**，需警戒防守（低于保证水位） | 河道为主，水库也用 |
| **死水位** | 允许水库降到的**最低**水位，低于此不再兴利 | 水库 |

> 量级关系（水库，从高到低）：校核洪水位 ≥ 设计洪水位 ≥ 正常蓄水位 ≥ 汛限水位 ≥ ... ≥ 死水位。
> 合理性校验（`analysis-qa-checklist.md` §二）：实测 `rz` 应落在 **死水位 ~ 校核洪水位** 之间；越汛限/越警戒即触发预警。

### 2.2 ⚠️ 关键：本项目**没有**"特征水位列"

> **最高频的领域性翻车**：用户问"查超过汛限水位的水库"或"水位有没有超警戒"，agent 容易写成
> ```sql
> -- ❌ 错：项目里没有 汛限水位 / 警戒水位 这种列
> SELECT * FROM st_rsvr_r WHERE rz > 汛限水位
> ```
> **真相**：`st_rsvr_r` 只有实时 `rz` / `blrz`（已核 `schema.md`，无任何特征水位列）。特征水位是 **per-station 配置的阈值**，三种正确来源：
> 1. **预警规则表** `ew_info_rules.extend`（JSON `{content:[min,max], condition}`，按 `st_id`/`eq_id`/`dot_id` 定位单站，见 §三）——"超警戒"的阈值就配在这里。
> 2. **已触发的预警消息** `ew_info_message`（`value` = 触发值，`level_r` = 等级）——"哪些站已超警"直接查这里。
> 3. **问用户**要具体数值（如"该站汛限水位是 150m"），**绝不凭空给数**。
>
> 因此"超警戒水位查询"的正确写法通常是 **JOIN `ew_info_rules` 取阈值** 或 **查 `ew_info_message` 看是否已触发**，而不是对 `rz` 比一个不存在的列。few_shots 里出现硬编码 `AND r.z > 3.5 -- 警戒水位` 仅为示意，**实际数值 per-station，必须从规则表取或问用户**。

---

## 三、预警等级与阈值语义（`ew_info_rules`）

> 详细规则见 `powerelf-early-warning/rules/threshold-rules.md`；本节只给 chatbi 写 SQL 时**必须知道**的语义。

### 3.1 阈值存在 `extend` JSON 里（不在普通列）

```json
// ew_info_rules.extend 示例
{ "content": [min, max], "condition": "FOUR" }
```
- `condition` 是 10 种枚举之一：`ZERO(=)` `ONE(!=)` `TOW(>=)` `THREE(<=)` `FOUR([min,max])` `FIVE(>)` `SIX(<)` `SEVEN((min,max))` `EIGHT([min,max))` `NINE((min,max])`。
- 单边（`TOW`/`FIVE`）只用 `min`；单边（`THREE`/`SIX`）只用 `max`。
- **查阈值要 `JSON_EXTRACT`**：`JSON_EXTRACT(extend, '$.content[0]')` 取 min、`'$.content[1]'` 取 max（MySQL 模式，见 treasure-map Tier 2.6）。

### 3.2 `ew_type` 预警类型（决定查哪类规则）

| 值 | 含义 | 规则文件 |
|----|------|----------|
| 0 | 水位预警 | threshold-rules |
| 1 | 水质预警 | threshold-rules |
| 2 | 雨量预警 | threshold-rules |
| 3 | 开关变化预警 | state-change-rules |
| 4 | 开关量预警 | switch-rules |
| 5 | 大坝安全预警 | dam-rules |
| 6 | 洪水预警 | threshold-rules |
| 7 | 趋势预警 | trend-rules |

### 3.3 等级 `level_r`（I~IV，1 最严重）

| level_r | 名称 | 语义 |
|---|---|---|
| 1 | I 级（特别严重） | 需立即响应 |
| 2 | II 级（严重） | 需尽快处理 |
| 3 | III 级（较重） | 需关注 |
| 4 | IV 级（一般） | 提示性 |

> 动态等级按**超标比例** `|value - threshold|/|threshold|` 自动调（≤10%→IV、≤30%→III、≤60%→II、else→I），最终取 `max(配置等级, 动态等级)`。chatbi 查"X 级以上预警"时，`level_r` 越小越严重（`level_r IN ('1','2')` = II 级以上）——**别按数字升序当"严重度升序"**。

---

## 四、派生指标定义（source / formula / caveat）

| 指标 | 公式 | 来源列 | caveat |
|---|---|---|---|
| **净流量（蓄/泄判据）** | `inq - otq` | `st_rsvr_r.inq, otq` | >0 入库>出库（蓄水）；<0 泄水。两者单位均 m³/s。 |
| **水位变率** | `Δrz / Δt` | `st_rsvr_r.rz, tm` | 趋势/陡涨陡落预警用；注意采样间隔（`tm`）。 |
| **雨强（mm/h）** | `p / dr * 60` | `st_pptn_r.p, dr` | **`dr` 是分钟**，换算到每小时 ×60；`st_pptn_region_r.intv` 已是小时，别再 ×60。 |
| **超标比例** | `abs(value - threshold) / abs(threshold)` | 触发值 vs `ew_info_rules.extend` 阈值 | 即动态等级公式；threshold=0 时除零需 `NULLIF`。 |
| **蓄水量** | 直读 `w` | `st_rsvr_r.w` | 单位以 `schema.md` 标注为准（通常 万m³）；勿与"库容"混——库容是水位→库容曲线查得，非实时列。 |
| **平均流速** | 直读 `xsavv` | `st_river_r.xsavv` | m/s；断面平均，非垂线平均。 |

> 派生指标的统计措辞（"净流量持续为负"≠"必然泄洪决策"——相关≠因果）走 `_shared/references/statistical-caution.md`。

---

## 五、标准过滤（每条业务表 SQL 必带）

> 详见 `validation-checklist.md` §一 与 `sql-generation.md` 注意事项；此处仅列清单，**不展开**。

- `AND deleted = 0`（软删除；漏写→捞出已删行，最常见静默错误）
- `AND tenant_id = 1`（多租户表；除非用户显式跨租户）
- 关联键类型：`st_*` 多用 `stcd`(varchar)↔`eq_equip_base.code`；`st_pressure_r`/GNSS 用 `eq_id`(bigint/int)↔`eq_equip_base.id`。红旗：`eq_id = '606K...'`
- 时间字段统一 `tm`(datetime)；默认窗口见 `sql-generation.md`（周/月对比注意完整周期）
