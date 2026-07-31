# 实体缺口 → 聚焦动作路由表（Focused Action Map）

> 消费入口有两个：Phase 2 的**自动**诊断路由（预置，`references/diagnosis-routing.md`）
> 与 agent 交互式追问时的**手动**路由（本表）。同一张实体表。
>
> 铁律：**只根据已点名的缺失实体选下一步，不凭症状措辞推断。**

## 五类实体缺口

| 缺失实体 | 完备信号 | 聚焦动作（只读查询） |
|---|---|---|
| 异常归属传感器 | eq_id + 测点编码 + 所属工程/坝段 | `eq_business_equip_relation`（eq_id/st_id/business_table）+ `att_st_base`（code/name）关联链 |
| 外因事件 | 同期降雨/闸门操作/泵启停记录（有，或明确排除） | `st_pptn_r.p` / `rei_gate_r.gtophgt` / `rei_pump_r` 时间窗查询（三级窗 -2h/-12h/-3d） |
| 量级基线 | 当前值 + 历史同期中位数/MAD + 偏离倍数 | 历史同期分布查询（近 3 年同月，`seasonal_check` 同源 SQL） |
| 阈值依据 | 命中的规则 ID + `ew_info_rules.extend` 中的阈值原文 | `ew_info_rules` + `JSON_EXTRACT(extend, '$.content')`（注意 extend JSON 健壮性，见 pitfalls #4） |
| 数据质量佐证 | 该测点近期缺失率/插值率（排除"坏数据当异常"） | 引 powerelf-data-governance 的质量评分 / `eq_data_missing_record` / `eq_data_anomaly_record` |

## 使用纪律

1. 仅当 envelope/finding **点名了具体缺失实体**时才执行对应聚焦动作，一次一条；
2. 已闭合的实体**不重复核查**（不给已闭合实体加裸命令验证）；
3. 5 类实体全齐 → finding 升格 `root_cause`，stop-ready，不再追加分析轮次；
4. **禁止实体替换**：聚焦动作查空时，禁止拿"相邻测点/相似时段/同类工程"的数据顶替缺失实体下结论——只能呈现候选选项让用户选择，或按固定终止模板收束：
   > 该实体经 X/Y/Z 三途径查询均无数据，无法闭合，本 finding 维持 [Unverified]。
5. **禁止跨字段拼凑**：不得把 A 测点的量级 + B 测点的时间窗拼成一条"完备"证据。
