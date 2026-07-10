# 巡检业务数据模型

源自 Java Spring 后端（powerelf-wplms）的 11 个巡检业务实体。

## 核心实体关系

```
business_check_route (路线)
    │
    ├── selectId (逗号分隔点ID) ──→ business_check_point (巡检点)
    │                                      │
    │                                      └── has ──→ business_check_obj (对象)
    │                                                       │
    │                                                       ├── typeId ──→ business_check_obj_type (类型)
    │                                                       │                  │
    │                                                       │                  └── has ──→ business_check_obj_type_item (检查项)
    │                                                       │
    │                                                       └── pointId ──→ business_check_point
    │
    └── (1) ──→ business_check_task (任务)  [routeId FK]
                     │
                     ├── serial ──→ business_check_result (结果)
                     │                  │
                     │                  └── 异常时创建 ──→ business_check_error (缺陷)
                     │
                     └── endTask 时创建 ──→ business_check_regular (定期记录)
                                             └── 可关联 ──→ business_check_report (报告)

business_check_standard (检查标准文档，独立)
business_check_viewing (观测记录，独立)
```

## 实体字段明细

### 1. business_check_route（巡检路线）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| dept_id | bigint | 部门ID |
| project_id | bigint | 项目ID |
| serial | varchar | 编号 |
| name | varchar | 路线名称 |
| type | tinyint | 类型 |
| status | tinyint | 状态 |
| max_time | int | 最大耗时(分钟) |
| standard | varchar | 检查标准 |
| select_id | text | 逗号分隔的巡检点ID列表 |
| in_order | tinyint | 是否按序执行 |
| remark | varchar | 备注 |
| dispatch | varchar | 调度配置 |

### 2. business_check_point（巡检点）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| point_serial | varchar | 点编号 |
| point_name | varchar | 点名称 |
| location_way | tinyint | 定位方式(1=GPS/2=RFID/3=QR) |
| lon_lat | varchar | GPS坐标 |
| rfid_id | varchar | RFID编号 |
| qr_code | varchar | 二维码 |
| remark | varchar | 备注 |

### 3. business_check_obj（巡检对象）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| obj_leibie | tinyint | 类别(1=设备/2=建筑/3=自定义) |
| obj_name | varchar | 对象名称 |
| obj_id | varchar | 对象ID |
| type_id | bigint | 类型ID(business_check_obj_type) |
| point_id | bigint | 所属巡检点 |
| order_key | int | 排序 |

### 4. business_check_obj_type（对象类型）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| type_name | varchar | 类型名称 |
| remark | varchar | 备注 |

### 5. business_check_obj_type_item（检查项）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| check_obj_type_id | bigint | 所属类型 |
| required | text | 检查要求描述 |
| application | varchar | 适用范围 |
| enable | tinyint | 是否启用 |
| remark | varchar | 备注 |

### 6. business_check_task（巡检任务） — 核心

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| dept_id | bigint | 部门ID |
| project_id | bigint | 项目ID |
| project_name | varchar | 项目名称 |
| serial | varchar | 任务编号 |
| name | varchar | 任务名称 |
| route_id | bigint | 关联路线(business_check_route) |
| task_type | tinyint | 类型(10=日常/20=经常/30=专项) |
| plan_time | datetime | 计划开始时间 |
| begin_time | datetime | 实际开始时间 |
| end_time | datetime | 实际结束时间 |
| executor | bigint | 执行人(admin_user_id) |
| supervisor | bigint | 监督人(admin_user_id) |
| principal | bigint | 负责人(admin_user_id) |
| status | tinyint | 状态(1=待巡检/2=巡检中/3=已完成) |
| plan_checknum | int | 计划检查点数 |
| plan_checkobj | int | 计划检查对象数 |
| plan_objitem | int | 计划检查项数 |
| real_checknum | int | 实际检查点数 |
| real_objitem | int | 实际检查项数 |
| check_percent | decimal | 检查完成率(% ) |
| bad_num | int | 异常/缺陷数 |
| weather | varchar | 天气 |
| remark | text | 备注 |
| exceed_time | tinyint | 是否超时 |
| lon_lat | varchar | 坐标 |
| pdf_file | varchar | PDF报告文件路径 |

### 7. business_check_result（巡检结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| serial | varchar | 编号 |
| task_serial | varchar | 关联任务编号 |
| obj_id | varchar | 被检对象 |
| result | tinyint | 结果(0=正常/1=异常) |
| remark | varchar | 备注 |
| opinion | varchar | 处理意见 |
| project_id | bigint | 项目ID |
| check_obj_type_item_id | bigint | 检查项ID |
| problem | varchar | 问题描述 |
| file | varchar | 附件 |
| url | varchar | 图片URL |
| lon_lat | varchar | 坐标 |

### 8. business_check_error（缺陷/问题库）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| dept_id | bigint | 部门ID |
| task_id | bigint | 关联任务 |
| task_name | varchar | 任务名称 |
| project_id | bigint | 项目ID |
| obj_id | varchar | 设备对象ID |
| result_id | bigint | 关联结果 |
| problem | varchar | 问题描述 |
| problem_file | varchar | 问题附件 |
| check_user_id | bigint | 发现人 |
| check_time | datetime | 发现时间 |
| opinion | varchar | 处理意见 |
| deal_type | tinyint | 处理方式 |
| deal_advice | varchar | 处理建议 |
| deal_time | datetime | 处理时间 |
| deal_user | bigint | 处理人 |
| deal_file | varchar | 处理附件 |
| status | tinyint | 状态(0=未处理/1=处理中/2=已完成) |

### 9. business_check_report（巡检报告）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| task_id | bigint | 关联任务 |
| name | varchar | 报告名称 |
| type | varchar | 类型 |
| url | varchar | 报告文件URL |
| unit | varchar | 编制单位 |
| check_time | datetime | 检查时间 |
| duty_person | varchar | 责任人 |
| report_describe | text | 报告描述 |
| report_dept | varchar | 编制部门 |
| report_person | varchar | 编制人 |

### 10. business_check_regular（定期检查记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| task_name | varchar | 任务名称 |
| task_type | tinyint | 任务类型 |
| check_dept | varchar | 检查部门 |
| dept_id | bigint | 部门ID |
| responsible_person | varchar | 负责人 |
| executors | varchar | 执行人 |
| description | text | 说明 |
| check_report | text | JSON 格式报告内容 |
| plan_start_time | datetime | 计划开始 |
| plan_end_time | datetime | 计划结束 |
| task_status | tinyint | 状态 |
| type | tinyint | 标记 |

### 11. business_check_standard（检查标准）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| name | varchar | 标准名称 |
| type | varchar | 类型 |
| release_date | date | 发布日期 |
| dept_id | bigint | 部门 |
| project_id | bigint | 项目 |
| file_attch | varchar | 附件 |
| remark | text | 备注 |

## 枚举

| 枚举 | 值 | 说明 |
|------|-----|------|
| 任务状态 | 1/2/3 | 待巡检/巡检中/已完成 |
| 任务类型 | 10/20/30 | 日常/经常/专项 |
| 检查结果 | 0/1 | 正常/异常 |
| 定位方式 | 1/2/3 | GPS/RFID/二维码 |
| 对象类别 | 1/2/3 | 设备设施/建筑物/自定义 |
| 缺陷状态 | 0/1/2 | 未处理/处理中/已完成 |
| 缺陷险情 | 1/2/3/4 | 轻微/一般/严重/特别紧急 |

## 任务生命周期（状态机）

```
待巡检 (1) ──startTask()──→ 巡检中 (2) ──endTask()──→ 已完成 (3)
   │                              │
   │                              ├── 设置执行人、开始时间
   │                              ├── 批量查询巡检结果
   │                              ├── 统计遗漏率/超时率/缺陷数
   │                              ├── 异常项 → 创建缺陷记录
   │                              └── 异步: PDF生成 + 定期记录写入
   │
   └── Quartz 定时创建新任务
       (解析 semicolon 分隔参数: routeId;supervisor;principal;executor1;...;taskName)
```

## 路线树（内存组装 5 层嵌套）

```
CheckRouteDO
  └── List<CheckPointDO>
        └── List<CheckObjDO>
              └── List<CheckObjTypeDO>
                    └── List<CheckObjTypeItemDO>
                          └── CheckResultDO (运行期填充，可空)
```

## 传感器表一览（Python 技能分析范围）

> 12 类监测表（`st_*` / `rei_*` / `dsm_*` / `wq_*`）的完整 DDL、字段语义、关联键映射已统一至
> 跨 skill 单一事实源：**[`../../_shared/references/schema.md`](../../_shared/references/schema.md)**。
> 本文件仅维护上方的巡检业务实体（`business_check_*`）。
>
> 常用监测表速查：水库 `st_rsvr_r`(rz)、河道 `st_river_r`(z,q)、雨量 `st_pptn_r`(p)、
> 渗压 `st_pressure_r`(water_pressure,ext_pressure)、渗流 `st_percolation_r`(percolation)、
> GNSS `dsm_dfr_srvrds_srhrds`(wgs84_delta_h)、闸门 `rei_gate_r`、泵站 `rei_pump_r`、
> 水质 `wq_pcp_d`、墒情 `st_soil_moisture_r`、白蚁 `st_termite_monitor_r`。
