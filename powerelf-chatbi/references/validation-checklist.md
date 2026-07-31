# ChatBI 验证清单（SQL/结果级）

> **本文件职责**：查"SQL 对不对、结果站不站得住"——**执行前语义 lint + 执行后结果健全**。
>
> **不在本文件**：报告措辞与统计结论的护栏。那些走 `_shared/references/analysis-qa-checklist.md`（18 项四类清单 + 8 类陷阱 + 红旗阈值）与 `_shared/references/statistical-caution.md`（7 条统计措辞护栏）。两份 `_shared` 文件已做水利映射，**勿在此重复**。
>
> **最终产出**：通过下面两段校验后，填 `confidence_tier`（三标签见文末，复用 `_shared` canonical 标签）。

---

## 一、Pre-exec 语义 lint（生成 SQL 后、执行前）

> 目的：**避免一次无谓的 DB 往返**。这里查的是"DB **不会**报错、但会返回**成功却错误**的数据"的语义问题。列存在性/语法错误由 `query_exec.py` 透传 MySQL 错误（exit 2 + stderr）让 agent 自修正——**不在本表重复**。

逐条对照生成的 SQL：

- [ ] **软删除**：涉及业务表（`st_*` / `eq_*` / `ew_*` / `business_check_*`）的 WHERE 含 `deleted = 0`。漏写→捞出已删行（最常见静默错误）。
- [ ] **多租户**：多租户表带 `tenant_id = 1`（除非用户显式跨租户）。
- [ ] **关联键类型**（铁律，见 `rules/sql-generation.md`）：
  - `st_rsvr_r` / `st_pptn_r` / `st_percolation_r` 用 `stcd`（varchar）↔ `eq_equip_base.code`
  - `st_pressure_r` 用 `eq_id`（bigint）↔ `eq_equip_base.id`
  - GNSS `dsm_dfr_srvrds_srhrds` 用 `eq_id`（int）↔ `eq_equip_base.id`
  - **红旗**：`eq_id = '606K...'`（把字符串赋给 bigint）、`stcd = eq_equip_base.id`（varchar=int 跨类型）。
- [ ] **单位陷阱**：`st_pptn_r.dr` 是**分钟**，`st_pptn_region_r.intv` 是**小时**——小时/分钟换算勿混。
- [ ] **类型陷阱**：泵站 `rei_pump_r` 的 `uab/ubc/uca/ia/ib/ic/p/freq` 均为 **varchar**，数值比较/聚合前 `CAST(... AS DECIMAL)`。
- [ ] **JOIN 爆炸**：多表 JOIN 后用 `COUNT(DISTINCT id)` 而非 `COUNT(*)` 核数；行数异常爆增→检查是否many-to-many。
- [ ] **实体消歧**：用户说的"水位"映射对了表/列吗？水库=`st_rsvr_r.rz`、河道=`st_river_r.z`、闸站上游=`st_was_r.upz`——选错表是根本性错误。（**消歧权威出处**：`references/domain-knowledge.md` §一，含水位/流量/雨量/压力/电气全候选表 + 消歧线索；另见 §二"本项目无特征水位列"——勿写 `WHERE rz > 汛限水位`。）
- [ ] **聚合粒度**：`GROUP BY` 含所有非聚合列；`AVG(SUM(...))` 这类"平均的平均"是经典错（见 `_shared` 陷阱目录）。

**任一红旗命中**：回到"生成SQL"修正后重试，**不要带着已知错执行**。

---

## 二、Post-exec 结果健全（`query_exec.py` 返回后）

> 读 `query_exec.py` 的 JSON 输出字段：`columns` / `rows` / `row_count` / `truncated`。**无需改其代码**。

- [ ] **`truncated=true`**：结果被截断到 `--display`（默认 20）或 `--limit`（默认 2000）。若结论依赖聚合/全量统计→**必须**在回复标注"仅前 N 行"，且聚合结论降级。
- [ ] **`row_count=0`**：区分三种——① 真无数据（时间窗/站码条件合理却空）→ 标注"暂无数据"（呼应 `_shared` load-bearing 表处理）；② 条件过严（站名 LIKE 不匹配、时间窗太窄）→ 放宽重试；③ 表本身暂无数据（见 `schema.md`）。**不要**对空结果下强结论。
- [ ] **量级红旗**：均值/求和出现负数（水位/雨量/流量不应负）、百分比越 0–100、水位超物理范围、`NULL` 占比 >30%。
- [ ] **时间窗完整性**：周/月对比时两端是否完整周期？"本周 vs 上周"在周三比→不完整周期对比陷阱（见 `_shared`）。
- [ ] **列对齐**：返回 `columns` 与 SQL SELECT 一致；别名中文是否到位（如 `rz AS 水位_m`）。

---

## 三、置信度评级（填 `confidence_tier`）

> 三标签为项目 canonical（`_shared/references/analysis-qa-checklist.md` §一），**勿自创**（不用 governance 的"高/中/低"变体）。由 agent 自判填，**不自动打分**。注意：这不是 inspection 的 `0.3×阈值+...` per-anomaly 置信度——那是异常检测概念，不混用。

| `confidence_tier` | chatbi 判据 | 交付动作 |
|---|---|---|
| **`Ready to share`** | pre-exec 全过 + 结果非空非截断 + 无量级红旗 + 实体消歧明确 | 直接交付 |
| **`Share with caveats`** | 有截断标注 / 部分假设（如"假设水位指水库 rz"）/ 数据暂无已标注，但结论主体成立 | 交付，**必附 caveat** |
| **`Needs revision`** | 漏 `deleted=0` / 关联键错 / 空结果未澄清 / 量级异常 / 实体歧义未解 | **不交付**，回"生成SQL"修正重试 |

### 流程位置

```
生成SQL（内含 pre-exec 自检）
  → query_exec 执行
  → 【VALIDATE】= 本文件 §一 已在生成步过 + §二 结果健全 + 过 _shared analysis-qa-checklist.md（报告级）+ statistical-caution.md（措辞）
  → 填 confidence_tier
  → Ready/caveats → 图表决策→生成→解读（交付）；Needs revision → 回生成SQL
```

`Needs revision` 复用现有 SQL 错误自修正通路（agent 读 `query_exec` 透传的 MySQL 错误自修正）；pre-exec 抓的是 DB 不报的语义错，post-exec 抓的是 DB 报不了的结果错。
