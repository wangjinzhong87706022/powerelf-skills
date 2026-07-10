# 缺陷分类规则

## 一、巡检缺陷（business_check_error）

> 数据源：`business_check_error` 表
> 创建时机：`CheckTaskServiceImpl.endTask()` → `createCheckErrorDOBatch()` 自动创建
> Java 端逻辑：筛选 `business_check_result.result = "1"` 的异常结果，批量写入缺陷表

### 缺陷来源

缺陷记录在任务结束时由 `endTask()` 自动从异常结果创建：
1. `CheckTaskServiceImpl.endTask()` 查询 `business_check_result` 中 `result="1"` 的记录
2. 批量查询涉及的巡检对象名称
3. 批量插入 `business_check_error`（`insertBatchSomeColumn`）
4. 默认状态 `status = "0"`（未处理）

### 缺陷表字段映射（business_check_error）

| 字段 | 来源 | 说明 |
|------|------|------|
| task_id | task.id | 关联任务ID |
| task_name | task.name | 任务名称（冗余） |
| dept_id | task.deptId | 站点ID |
| project_id | result.projectId | 工程ID |
| obj_id | result.objId | 巡检对象ID |
| result_id | result.id | 关联检查结果ID |
| problem | result.problem | 问题描述 |
| obj_name | checkObj.objName | 巡查对象名称 |
| check_user_id | task.executor | 巡查人ID |
| check_time | task.endTime | 巡查时间 |
| problem_file | result.url | 问题附件URL |
| opinion | result.opinion | 处理意见（默认空格） |
| status | "0" | 未处理 |

### 巡检缺陷等级

| 等级 | 含义 | 处理时限 | 说明 |
|------|------|----------|------|
| 一般 | 轻微缺陷 | 7天 | 不影响安全运行 |
| 较重 | 中等缺陷 | 3天 | 可能影响运行 |
| 严重 | 重大缺陷 | 24小时 | 影响安全运行 |
| 紧急 | 危险缺陷 | 立即 | 危及安全，需立即处理 |

---

## 二、设备缺陷（eq_equip_defect）

> 数据源：`eq_equip_defect` 表（来自 SmartTwinRes）
> 来源：巡检中发现的设备缺陷，或设备运维中发现的问题
> 关联：`eq_equip_defect.equip_id` → `eq_equip_base.id`

### 设备缺陷分类

| 类型 | 含义 | 处理优先级 | 说明 |
|------|------|-----------|------|
| 事故性缺陷 | 设备发生事故 | 最高 | 需立即停机处理 |
| 重大缺陷 | 设备存在重大隐患 | 高 | 需尽快安排检修 |
| 一般性缺陷 | 设备轻微异常 | 中 | 纳入计划检修 |

### 设备缺陷处理状态机

```
发现缺陷 → status="0"(待处理)
  │
  ├── 开始处理 → status="1"(处理中)
  │     ├── 处理成功 → status="2"(处理成功)
  │     └── 处理失败 → status="3"(处理失败) → 重新处理 → status="1"
  │
  └── 暂不处理 → status="4"(暂不处理) → 后续重新评估
```

| 状态码 | 含义 | 说明 |
|--------|------|------|
| 0 | 待处理 | 新发现的缺陷，等待分配处理人 |
| 1 | 处理中 | 已分配处理人，正在检修 |
| 2 | 处理成功 | 缺陷已修复，可关闭 |
| 3 | 处理失败 | 处理未成功，需重新安排 |
| 4 | 暂不处理 | 评估后决定暂不处理（如计划停机时统一处理） |

### 设备缺陷统计SQL

```sql
-- 按设备统计缺陷数（TOP10高频缺陷设备）
SELECT e.equip_id, b.name AS equip_name, COUNT(*) AS defect_count,
       SUM(CASE WHEN e.handle_status = '0' THEN 1 ELSE 0 END) AS pending_count
FROM eq_equip_defect e
LEFT JOIN eq_equip_base b ON e.equip_id = b.id
WHERE e.deleted = 0
GROUP BY e.equip_id, b.name
ORDER BY defect_count DESC LIMIT 10;

-- 按处理状态统计
SELECT handle_status,
       CASE handle_status
         WHEN '0' THEN '待处理'
         WHEN '1' THEN '处理中'
         WHEN '2' THEN '处理成功'
         WHEN '3' THEN '处理失败'
         WHEN '4' THEN '暂不处理'
       END AS status_name,
       COUNT(*) AS count
FROM eq_equip_defect WHERE deleted = 0
GROUP BY handle_status;

-- 按缺陷类型统计
SELECT type, COUNT(*) AS count
FROM eq_equip_defect WHERE deleted = 0
GROUP BY type ORDER BY count DESC;
```

---

## 三、违法行为（srm_illegal_acts）

> 数据源：`srm_illegal_acts` 表（来自 SmartTwinRes）
> 来源：巡查中发现的违规/违法行为

### 违法行为状态

| 状态码 | 含义 | 说明 |
|--------|------|------|
| 0 | 未处理 | 新发现的违法行为，待处理 |
| 1 | 已处理 | 已劝阻/已上报/已处罚 |

### 统计SQL

```sql
-- 按状态统计
SELECT status, COUNT(*) AS count
FROM srm_illegal_acts WHERE deleted = 0
GROUP BY status;

-- 按月统计趋势
SELECT DATE_FORMAT(create_time, '%%Y-%%m') AS month, COUNT(*) AS count
FROM srm_illegal_acts WHERE deleted = 0
GROUP BY DATE_FORMAT(create_time, '%%Y-%%m')
ORDER BY month;
```

---

## 四、缺陷处理优先级（通用）

```
优先级 = 缺陷等级 × 设备重要性

设备重要性:
  大坝核心设备: 权重 3
  主要机电设备: 权重 2
  一般辅助设备: 权重 1

if 优先级 >= 9:
  → 紧急处理
if 优先级 >= 6:
  → 优先处理
if 优先级 >= 3:
  → 正常处理
else:
  → 计划处理
```

## 五、缺陷处理流程

```
巡检缺陷(business_check_error):
  1. endTask() 自动创建 → status="0"(未处理)
  2. 巡检负责人查看 → GET /business/check-error/page
  3. 填写处理方案 → PUT /business/check-error/update
  4. 处理完成 → status 变更为已处理

设备缺陷(eq_equip_defect):
  1. 巡检/运维中发现 → 创建缺陷记录 → handle_status="0"
  2. 分配处理人 → handle_status="1"(处理中)
  3. 处理完成 → handle_status="2"(成功) 或 "3"(失败)
  4. 失败则重新处理 → handle_status="1"
```
