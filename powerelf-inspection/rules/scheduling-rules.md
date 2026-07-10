# 排班规则

> 数据源：`business_work_force` 表（排班）、`business_duty_group` 表（班组）、`business_duty_record` 表（值班记录）

## 排班模型

```
班组(DutyGroup) → 排班(WorkForce) → 值班记录(DutyRecord)
```

## 排班创建

```
参数:
  groupId — 班组ID
  projectId — 工程ID
  startTime — 开始时间
  endTime — 结束时间
  dutyUser — 值班人员

规则:
  1. 排班时间段不能与同一班组的已有排班重叠
  2. 同一人员不能在同一时间段被排到多个班组
  3. 排班时间必须大于当前时间
```

## 班组状态

| 状态 | 说明 |
|------|------|
| 1 | 值班中 |
| 2 | 交接中 |

## 值班记录

```
创建:
  1. 检查当前用户是否在值班班组中 (loginGroups)
  2. 检查是否已有未完成的值班记录 (notCreate)
  3. 创建值班记录 (type=1: 值班, type=2: 交接)

交接:
  1. 当前值班人确认交班
  2. 下一班值班人确认接班 (catchGroup)
  3. 更新值班记录状态
```

## 排班与巡检任务联动

```
巡检任务创建时:
  1. 查询当前排班: business_work_force WHERE projectId=? AND startTime<=NOW() AND endTime>=NOW()
  2. 获取值班班组: business_duty_group WHERE id=workForce.groupId
  3. 设置任务执行人: checkTask.executor = dutyGroup.members (逗号分隔)

排班日历查询:
  GET /business/work-force/groupCalendar?projectId=&startTime=&endTime=
  返回: 按日期分组的排班信息，用于前端日历展示
```
