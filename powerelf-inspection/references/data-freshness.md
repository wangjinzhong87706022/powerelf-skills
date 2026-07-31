# 数据新鲜度与"无数据"四分法

> 消费方：`impl/inspection_analyzer.py`（`no_data_result` / `probe_table_latest` / `QUERY_ERRORS`）。
> 原则：**查询失败 ≠ 无数据 ≠ 不适用**，严禁以 0 或空值充数（0 是有效读数）。

## 四分法（互斥）

| status_code | 含义 | 判定方法 | 下游动作 |
|---|---|---|---|
| `NOT_APPLICABLE` | 本工程无此类监测（表历史即空） | `MAX(tm)` 探针返回 NULL | 报告标注"不适用"，不算异常，**勿重试** |
| `NO_DATA` | 表有历史数据但分析窗口内为空 | 探针有历史 `MAX(tm)` 但窗口无行 | 子类型"采集中断"：`MAX(tm)` 距今 > 离线阈值 → 转 powerelf-data-governance 排查采集链路 |
| `QUERY_FAILED` | 查询本身失败（表缺失/超时/权限） | `QUERY_ERRORS[table]` 有登记 | 按 code 分支修复（TABLE_MISSING 勿重试；QUERY_TIMEOUT 缩窗口）；**严禁写 0/空充数** |
| `DATA_LOSS_GUARD` | DB 有值但报告拿不到 = 本 skill 自身 bug | 评测脚本比对 DB 实值 vs 报告 | 提 bug，不得当"无数据"糊弄过去 |

## 新鲜度探针

`probe_table_latest(engine, table, time_field="tm")` → 全表 `MAX(tm)`（不带窗口）：

- `NULL` → NOT_APPLICABLE；
- 有值且落后当前时间超过 `dg_equip_offline`/`eq_business_equip_relation.offline_threshold` → NO_DATA(采集中断)；
- 有值且新鲜 → 窗口选择问题（提示调大 `--days`）。

## 生命周期

- `QUERY_ERRORS` 在每次 `generate_report()` 开头 `clear()`，避免上轮失败污染本轮归因；
- `read_sensor_data` 成功时 `pop(table)`，失败时登记 `_classify_query_error(e)` 结果；
- 所有 no_data 维度进入报告 **Data Notes 表** 与 envelope `next_steps`（含 status_code + status_note）。

## 与数据质量闸的边界

- 四分法处理"**有没有**数据"；
- 质量闸（`check_data_quality`，色阶 >99 绿 / 95-99 黄 / 80-95 橙 / <80 红）处理"数据**够不够好**"；
- 红档 → 维度 `status: inconclusive` → envelope status `inconclusive` → 退出码 4。
