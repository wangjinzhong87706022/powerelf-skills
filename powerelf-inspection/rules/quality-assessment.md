# 巡检质量评估规则

> 数据源：`business_check_task` 表（CheckTask 模块）
> 评分算法实现：`impl/inspection_tool.py --mode quality`
> Java 端统计逻辑：`CheckTaskServiceImpl.endTask()`

## 评分模型（分段制，非线性）

```
巡检质量评分 = 完成率(30分) + 及时率(25分) + 缺陷发现率(25分) + 路线覆盖率(20分)
满分100分
注：每项按区间取固定分值，不是线性计算。Python工具 inspection_tool.py 已实现此模型。
```

## 指标定义

### 1. 完成率（30分）

```
数据来源: business_check_task.status
计算: 完成率 = COUNT(status='3') / COUNT(*) WHERE deleted=0

评分（分段制）：
  >= 95%  → 30分
  90-95%  → 25分
  80-90%  → 20分
  70-80%  → 15分
  < 70%   → 10分
```

### 2. 及时率（25分）

```
数据来源: business_check_task.exceed_time
计算: 及时率 = 1 - COUNT(exceed_time='1') / COUNT(*)
超时判定: Java端在 endTask() 中自动计算 → planTime < endTime 则 exceed_time="1"

评分（分段制）：
  >= 95%  → 25分
  90-95%  → 20分
  80-90%  → 15分
  < 80%   → 10分
```

### 3. 缺陷发现率（25分）

```
数据来源: business_check_task.bad_num, business_check_task.real_objitem
计算: 缺陷发现率 = SUM(bad_num) / SUM(real_objitem)
注意: 此指标需要平衡——太高说明设备问题多，太低可能是漏检

评分（分段制）：
  1-5%    → 25分（正常范围）
  5-10%   → 20分
  10-20%  → 15分
  > 20%   → 10分（可能设备老化）
  < 1%    → 15分（可能漏检）
```

### 4. 路线覆盖率（20分）

```
数据来源: business_check_task.check_percent
计算: 覆盖率 = 1 - AVG(check_percent解析为小数)
check_percent 由 Java 端 endTask() 自动计算: (1 - realObjitem/planObjitem) * 100%

评分（分段制）：
  >= 95%  → 20分
  90-95%  → 15分
  80-90%  → 10分
  < 80%   → 5分
```

## SQL 查询示例

```sql
-- 查询指定时间段的任务统计
SELECT
  COUNT(*) AS total_tasks,
  SUM(CASE WHEN status = '3' THEN 1 ELSE 0 END) AS completed_tasks,
  SUM(CASE WHEN exceed_time = '1' THEN 1 ELSE 0 END) AS overtime_tasks,
  SUM(bad_num) AS total_defects,
  SUM(real_objitem) AS total_real_items,
  AVG(CAST(REPLACE(check_percent, '%', '') AS DECIMAL(5,2))) AS avg_omission_pct
FROM business_check_task
WHERE create_time BETWEEN :start_date AND :end_date
  AND deleted = 0;
```

## 等级划分

| 等级 | 分数范围 | 含义 |
|------|----------|------|
| A | 90-100 | 优秀 |
| B | 80-89 | 良好 |
| C | 70-79 | 一般 |
| D | 60-69 | 较差 |
| E | < 60 | 严重不足 |

## 异常检测规则

### 超时预警
```
数据: business_check_task.plan_time, business_check_task.status
条件: status != '3' AND plan_time < NOW()
级别: WARNING
动作: 通知执行人(executor)和监督人(supervisor)
```

### 漏检预警
```
数据: business_check_task.check_percent
条件: check_percent 遗漏率 > 20%（即解析后 > 0.20）
级别: WARNING
动作: 标记为"需补检"
```

### 缺陷积压预警
```
数据: business_check_error.status, business_check_error.create_time
条件: status = '0' AND create_time < NOW() - INTERVAL 7 DAY
级别: CRITICAL
动作: 升级通知负责人
Java 端: CheckTaskServiceImpl.createCheckErrorDOBatch() 创建缺陷时 status 默认为 "0"
```

### 连续缺陷预警
```
数据: business_check_error.obj_id, business_check_error.create_time
条件: 同一 obj_id 连续3次巡检均出现在 business_check_error 中
级别: WARNING
动作: 建议专项检查
```
