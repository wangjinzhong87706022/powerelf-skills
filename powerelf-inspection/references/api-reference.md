# API 参考手册

> 详细的 REST API 端点文档。入口文件 `SKILL.md` 中的速查表只列出关键端点。

## 通用请求头

> 鉴权约定统一至 [`../../_shared/api-auth.md`](../../_shared/api-auth.md)。摘要：

```
Authorization: Bearer ${POWERELF_API_TOKEN}
tenant-id: 1
```

## 任务状态流转

```
status="1"(待开始) → startTask() → status="2"(进行中) → endTask() → status="3"(已完成)
                                                    ↓
                                        自动统计: realChecknum, realObjitem, badNum, checkPercent
                                        自动判定: exceedTime ("0"=未超时/"1"=超时)
                                        自动创建: business_check_error (result="1"的异常项)
                                        异步生成: PDF报告 + business_check_regular 记录
```

---

## 巡检任务（CheckTaskController，路径前缀 /admin-api）

| 方法 | 端点 | 说明 | 请求体/参数 |
|------|------|------|------------|
| POST | `/business/check-task/create` | 创建巡检任务 | CheckTaskCreateReqVO |
| PUT | `/business/check-task/update` | 更新巡检任务 | CheckTaskUpdateReqVO |
| POST | `/business/check-task/delete` | 删除巡检任务(逻辑删除) | `{"ids": [1,2,3]}` |
| GET | `/business/check-task/get?id=` | 任务详情(含路线树+检查结果) | id |
| GET | `/business/check-task/page` | 任务分页列表 | CheckTaskPageReqVO |
| GET | `/business/check-task/startTask?id=` | 开始任务(设置执行人+开始时间) | id |
| POST | `/business/check-task/endTask` | 结束任务(统计+创建缺陷+异步生成PDF) | CheckTaskUpdateReqVO |
| GET | `/business/check-task/PDF?id=` | 生成巡检PDF报告 | id |
| GET | `/business/check-task/export-excel` | 导出Excel | CheckTaskExportReqVO |

## 巡检路线（CheckRouteController）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/business/check-route/page` | 路线分页列表 |
| GET | `/business/check-route/getCheckList?id=` | 路线详情(含巡检点→巡检对象→检查项完整树) |

## 巡检缺陷（CheckErrorController）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/business/check-error/page` | 缺陷分页列表 |
| PUT | `/business/check-error/update` | 更新缺陷(处理方案/状态) |

## 巡检统计（CheckSummaryInfoController）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/business/check-summary/cartogram?date=` | 统计看板(年度/月度任务数) |
| POST | `/business/check-summary/calendar` | 日历视图(按月展示任务分布) |

## 排班（WorkForceController）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/business/work-force/groupCalendar` | 排班日历 |

## 智慧巡查大屏（InspectController，路径前缀 /powerstation）

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/powerstation/inspect/getTjData` | 缺陷统计（按 handle_status 分组） |
| POST | `/powerstation/inspect/getDataByPage` | 缺陷数据挖掘（分页） |
| POST | `/powerstation/inspect/getDataList` | 巡检任务列表 |
| POST | `/powerstation/inspect/getSheBeiList` | 巡查监测设备展示 |
| POST | `/powerstation/inspect/getSheBeiInById?id=` | 单设备填录信息展示 |

## 水库巡检集成（CheckSRMController，路径前缀 /srm）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/srm/check/element/all` | 智能巡检（风险分组+违规统计） |
| GET | `/srm/check/curve?projectId=` | 巡查曲线图（月度巡检次数+缺陷数） |
| GET | `/srm/check/element/supervision?projectId=&startTime=&endTime=` | 智慧监管（按时间范围统计+违规数） |
| GET | `/srm/check/screen/fourReaction?startTime=&endTime=` | 四管工作（巡检次数+除险时间+无人机+机器人） |

## Agent API 分析流程

### 质量评估

```
1. GET /business/check-task/page?pageSize=100&pageNo=1 → 获取任务列表
2. 遍历每个任务，提取 status, exceedTime, badNum, realObjitem, checkPercent
3. 按 quality-assessment.md 的分段公式计算评分
4. 输出：各维度得分 + 综合评分 + 等级
```

### 异常检测规则

| 检测项 | 条件 | 级别 | 动作 |
|--------|------|------|------|
| 超时任务 | status != '3' AND planTime < now() | WARNING | 通知执行人和监督人 |
| 漏检率异常 | checkPercent 遗漏率 > 20% | WARNING | 标记为"需补检" |
| 缺陷积压 | status='0' AND create_time > 7天前 | CRITICAL | 升级通知负责人 |
| 连续缺陷 | 同一 obj_id 连续3次出现在 error 表 | WARNING | 建议专项检查 |

### 缺陷热点分析

```
1. GET /business/check-error/page?pageSize=200 → 获取缺陷列表
2. 按 objId 聚合 → 找出高频缺陷对象 TOP10
3. 按时间趋势 → 缺陷是增加还是减少
4. 输出：TOP10缺陷对象 + 趋势方向
```

### Agent 输出格式示例

```markdown
## 巡检质量月报 (2026年5月)

### 总体指标
- 总任务数: 45
- 完成率: 88.9% (得分: 20/30)
- 超时率: 6.7% (得分: 25/25)
- 缺陷发现率: 3.2% (得分: 25/25)
- 平均遗漏率: 12.3% (得分: 10/20)
- 综合评分: 80/100 (B级)

### 缺陷热点 TOP5
| 排名 | 巡检对象 | 缺陷次数 | 趋势 |
|------|----------|----------|------|
| 1 | 2#闸门 | 5 | ↑ |
| 2 | 启闭机A | 3 | → |

### 建议
1. 2#闸门连续3次巡检发现缺陷，建议专项检查
2. 巡检路线"大坝巡查"遗漏率最高(25%)，建议优化路线
```
