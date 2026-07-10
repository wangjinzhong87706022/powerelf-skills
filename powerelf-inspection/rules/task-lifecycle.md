# 巡检任务生命周期规则

> 数据源：`business_check_task` 表
> Java 实现：`CheckTaskServiceImpl` → `startTask()`, `endTask()`
> 状态枚举：`CheckTaskStatusEnum`（PENDING="1", IN_PROGRESS="2", COMPLETED="3"）

## 任务状态流转

```
status="1"(待开始/PENDING) → status="2"(进行中/IN_PROGRESS) → status="3"(已完成/COMPLETED)
       │                           │                              │
  Quartz定时创建              startTask()                    endTask()
  设置planTime               获取当前登录用户                 统计遗漏率/缺陷数
  初始status="1"             status→"2"                      创建CheckErrorDO
                             executor→当前用户ID              异步生成PDF
                             beginTime→当前时间               插入CheckRegularDO
                                                             exceedTime自动判定
```

## 开始任务（CheckTaskServiceImpl.startTask）

```java
// 实际Java逻辑
1. 获取当前登录用户: SecurityFrameworkUtils.getLoginUser()
2. 设置 status = CheckTaskStatusEnum.IN_PROGRESS ("2")
3. 设置 executor = 当前用户ID.toString()
4. 设置 beginTime = LocalDateTime.now()
5. checkTaskMapper.updateById(updateObj)
```

## 结束任务（CheckTaskServiceImpl.endTask）— 核心逻辑

```
1. 批量查询该任务的所有检查结果（一次查询，替代原来的N+1）:
   SELECT * FROM business_check_result WHERE task_serial = {task.serial}
   按巡检点分组: resultsByPoint = groupBy(result.serial)

2. 获取路线信息: checkRouteService.getCheckList(task.routeId)
   遍历路线树: 路线→巡检点→巡检对象→检查类型→检查项

3. 统计（逐巡检点）:
   planObj += 该巡检点的巡检对象数
   planObjitem += SELECT COUNT(*) FROM business_check_obj_type_item
                  WHERE check_obj_type_id = obj.typeId AND deleted = 0
   realObjitem += 该巡检点的 result="0"数 + result="1"数
   realChecknum += 1（如果该巡检点有检查结果）
   badNum += result="1"的数量

4. 遗漏率:
   if realObjitem > 0 AND planObjitem > 0:
     checkPercent = (1 - realObjitem/planObjitem) * 100%  // 格式: "12.34%"
   else:
     checkPercent = "100%"

5. 超时判定:
   exceedTime = planTime.isAfter(currentTime) ? "0" : "1"

6. 状态更新:
   status = CheckTaskStatusEnum.COMPLETED ("3")
   endTime = LocalDateTime.now()

7. 批量创建缺陷记录（createCheckErrorDOBatch）:
   筛选 result="1" 的检查结果
   批量查询涉及的巡检对象名称（一次查询）
   批量插入 business_check_error（insertBatchSomeColumn）
   缺陷记录默认: status="0"(未处理), checkUserId=executor

8. 异步执行（ewExecutor线程池）:
   - pdfTask(): 生成PDF报告，保存到文件系统，更新task.pdfFile
   - 插入 business_check_regular 记录（type="2"表示日常）
```

## 定时任务创建（CheckTaskServiceImpl.createCheckObjTask）

```
参数格式: routeId;supervisor;principal;executor1;executor2;...;taskName

解析流程:
  1. 按分号拆分参数
  2. 查询路线信息: business_check_route
  3. 解析巡检点列表: route.selectId.split(",") → pointIds
  4. 统计计划数量:
     - planChecknum = 巡检点数
     - planCheckobj = 巡检对象总数
     - planObjitem = 检查项总数
  5. 生成任务编号(serial)
  6. planTime = 当前时间 + route.maxTime 小时
  7. 初始 status = "1" (PENDING)
  8. checkTaskMapper.insert(task)
```

## 巡检点验证方式（business_check_point.location_way）

| 方式 | location_way | 说明 | 数据来源 |
|------|-------------|------|----------|
| GPS | "1" | 经纬度验证 | lon_lat 字段，格式: "纬度,经度" |
| RFID | "2" | RFID卡扫描 | rfid_id 字段 |
| 二维码 | "3" | QR码扫描 | qr_code 字段 |

## 端点

| 操作 | 方法 | 端点 |
|------|------|------|
| 创建任务 | POST | `/business/check-task/create` |
| 开始任务 | GET | `/business/check-task/startTask?id=` |
| 结束任务 | POST | `/business/check-task/endTask` |
| 生成PDF | GET | `/business/check-task/PDF?id=` |
