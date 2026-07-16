# Inspection 业务规则溯源字典

> 本文件收录巡检业务各状态码/枚举值的语义与来源，供 Agent / 开发者查表使用。每项标注**来源**（表名 + 字段）。

---

## 1. 任务状态（business_check_task.status）

| 值 | 语义 | 说明 |
|----|------|------|
| **1** | 待巡检 | 任务已创建，未开始执行 |
| **2** | 巡检中 | 执行人已开始巡检，仍在进行 |
| **3** | 已完成 | 巡检结束，结果已归档 |

**来源:** `business_check_task.status`
**代码引用:** `references/data-model.md` §6、"状态流转：1 → 2 → 3"
**测试:** `impl/test_inspection.py` 各 `_check_*` 均按 1/2/3 过滤

---

## 2. 预警类型（ew_info_rules.ew_type / ew_info_message.ew_type）

| 值 | 语义 | 说明 |
|----|------|------|
| **0** | 水位 | 水库/河道水位越限 |
| **1** | 水质 | pH/DO/NH3N/TN/TP 越限 |
| **2** | 雨量 | 小时/日累计雨量越限 |
| **3** | 开关变化 | 闸门/泵站开关状态变化 |
| **4** | 开关 | 通用开关量告警 |

**来源:** `ew_info_rules.ew_type`（`_shared/references/schema.md` §六）
**代码引用:** `impl/inspection_analyzer.py` `load_thresholds()`、`get_threshold()` / `ew_type, level_r` 复合键

---

## 3. 设备状态（eq_equip_base.status）

| 值 | 语义 | 说明 |
|----|------|------|
| **0** | 离线 | 设备无心跳或通信中断 |
| **1** | 在线 | 设备正常运行 |
| **2** | 异常 | 设备存在故障告警 |

**来源:** `eq_equip_base.status`（`_shared/references/schema.md` §二）

---

## 4. 设备类型（eq_equip_base.type_flag）

**注意：字段名为 `type_flag`，非 `type`。**（常见混淆点，参见 `pitfalls.md` §2 关联键混淆）

| 值 | 语义 | 来源表 |
|----|------|--------|
| **1** | 水尺（水位） | `st_rsvr_r`, `st_river_r` |
| **2** | 雨量 | `st_pptn_r` |
| **3** | 渗压 | `st_pressure_r` |
| **5** | 渗流 | `st_percolation_r` |
| **7** | GNSS 位移 | `dsm_dfr_srvrds_srhrds` |
| **8** | 摄像机 | `ew_camera_info` |
| **9, 11, 13, 14, 20** | 其他 | 各类监测 |

**来源:** `eq_equip_base.type_flag`（`_shared/references/schema.md` §二）

---

## 5. 巡检路线类型（business_check_route.type）

| 值 | 语义 | 说明 |
|----|------|------|
| **10** | 日常巡检 | 每日例行路线 |
| **20** | 经常检查 | 定期（周/旬）检查路线 |
| **30** | 专项检查 | 特定项目/工况路线 |
| **40** | 应急检查 | 汛期/事故后紧急检查 |

**来源:** `business_check_route.type`（`references/data-model.md` §1，与 `business_check_task.task_type` 对应）
**代码引用:** `impl/inspection_tool.py:analyze_route_efficiency()` 按 route 分组统计

---

## 6. 巡检任务类型（business_check_task.task_type）

| 值 | 语义 | 说明 |
|----|------|------|
| **10** | 日常巡检 | 对应 route.type=10 |
| **20** | 经常检查 | 对应 route.type=20 |
| **30** | 专项检查 | 对应 route.type=30 |

**来源:** `business_check_task.task_type`（`references/data-model.md` §6）

---

## 7. 巡检点定位方式（business_check_point.location_way）

| 值 | 语义 | 说明 |
|----|------|------|
| **1** | GPS | GPS 坐标定位 |
| **2** | RFID | RFID 标签感应 |
| **3** | QR | 二维码扫码 |

**来源:** `business_check_point.location_way`（`references/data-model.md` §2）

---

## 8. 检查结果（business_check_result.result）

| 值 | 语义 | 说明 |
|----|------|------|
| **0** | 正常 | 检查项通过 |
| **1** | 异常 | 检查项存在缺陷 |

**来源:** `business_check_result.result`（`references/data-model.md` §7）

---

## 9. 缺陷状态（business_check_error.status）

| 值 | 语义 | 说明 |
|----|------|------|
| **0** | 未处理 | 缺陷已登记，待处置 |
| **1** | 处理中 | 已安排维修/处置 |
| **2** | 已完成 | 缺陷已修复/闭环 |

**来源:** `business_check_error.status`（`references/data-model.md` §8）

---

## 10. 告警确认状态（ew_info_message.status）

| 值 | 语义 | 说明 |
|----|------|------|
| **0** | 未确认 | 告警未处理 |
| **1** | 已确认 | 告警已被确认/处置 |

**来源:** `ew_info_message.status`（`_shared/references/schema.md` §六）

---

## 11. 检查完成率语义（check_percent）

```python
# H1 默认处置：check_percent = 完成率（completed / total），非"遗漏率"
CHECK_PERCENT_SEMANTICS = "completion"  # 详见 lib/quality.py
```

| 字段 | 语义 | 计算方式 |
|------|------|----------|
| `check_percent` | 检查完成率 | `real_checknum / plan_checknum`（已完成点数 / 计划点数） |
| `omission_rate` | 遗漏率 | `1 - check_percent` |

**来源:** `business_check_task.check_percent`（`references/data-model.md` §6）
**代码引用:** `lib/quality.py:CHECK_PERCENT_SEMANTICS`

---

## 12. 缺陷发现率分母

| 分母字段 | 语义 | 优先顺序 |
|----------|------|----------|
| `real_objitem` | 实际检查项数 | 优先（C2 修后） |
| `real_checkobj` | 实际检查对象数 | 备选 |
| `plan_checkobj` | 计划检查对象数 | 降级（含未执行项） |
| `real_checknum` | 实际检查点数 | 最后降级 |

**公式:** `defect_discovery_rate = bad_num / real_objitem`
**来源:** `business_check_task.bad_num` + `real_objitem`（`references/data-model.md` §6）
**代码引用:** `lib/quality.py:compute_defect_discovery_rate(defects_found, real_checkitems)`

---

## 参考

- `_shared/references/schema.md` — DDL / 关联键 / 类型定义
- `_shared/references/sql-discipline.md` — SQL 写作纪律
- `_shared/references/analysis-qa-checklist.md` — 交付前 QA 闸
- `_shared/references/statistical-caution.md` — 统计措辞护栏
- `_shared/references/data-profiling.md` — 数据画像方法论
- `references/pitfalls.md` — 7 类高频错误
- `references/few_shots.md` — SQL 最佳实践示例
- `references/data-model.md` — 巡检业务 ER 模型