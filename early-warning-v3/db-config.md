# 数据库连接配置

## 连接信息

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **主机** | 127.0.0.1 | 本地数据库 |
| **端口** | 3306 | MySQL 默认端口 |
| **数据库** | powerelf_srm_yml | 告警业务数据库 |
| **用户** | root | 只读用户 |
| **密码** | 123456aA. | 数据库密码 |

## 连接命令

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p123456aA. powerelf_srm_yml
```

## 环境变量设置

```bash
export POWERELF_DB_HOST=127.0.0.1
export POWERELF_DB_PORT=3306
export POWERELF_DB_NAME=powerelf_srm_yml
export POWERELF_DB_USER=root
export POWERELF_DB_PASSWORD=123456aA.
```

## 数据库表结构

### 告警消息表 (ew_info_message)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| ew_name | varchar(255) | 告警名称 |
| st_code | varchar(255) | 测站编码 |
| eq_code | varchar(255) | 设备编码 |
| ew_type | varchar(255) | 告警类型 |
| level_r | char(2) | 告警级别 |
| value | varchar(255) | 告警值 |
| gather_time | datetime | 采集时间 |
| message_confirm | bit(1) | 是否确认 |
| ew_rules_id | bigint | 规则ID |
| create_time | datetime | 创建时间 |
| deleted | bit(1) | 是否删除 |
| tenant_id | bigint | 租户ID |

### 告警规则表 (ew_info_rules)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| name | varchar(255) | 规则名称 |
| type | char(5) | 规则类型 |
| ew_type | char(2) | 告警类型 |
| level_r | char(2) | 告警级别 |
| st_code | varchar(255) | 测站编码 |
| extend | json | 规则扩展 |
| status | char(2) | 状态 |
| deleted | bit(1) | 是否删除 |
| tenant_id | bigint | 租户ID |

### 水库水情表 (st_rsvr_r)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| st_id | bigint | 测站ID |
| eq_code | varchar(20) | 设备编码 |
| rz | decimal(8,3) | 水位 |
| inq | decimal(10,3) | 入库流量 |
| otq | decimal(10,3) | 出库流量 |
| tm | datetime | 时间 |
| deleted | bit(1) | 是否删除 |
| tenant_id | bigint | 租户ID |

### 降雨数据表 (st_pptn_r)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| st_id | bigint | 测站ID |
| eq_code | varchar(20) | 设备编码 |
| p | decimal(7,1) | 降雨量 |
| dr | decimal(5,1) | 时段 |
| tm | datetime | 时间 |
| deleted | bit(1) | 是否删除 |
| tenant_id | bigint | 租户ID |

## 默认查询参数

### 查询范围限制

| 参数 | 默认值 | 说明 |
|------|--------|------|
| **时间范围** | 最近 7 天 | 避免全表扫描 |
| **分页大小** | 50 条 | 平衡性能和数据量 |
| **最大分页** | 200 条 | 防止内存溢出 |
| **排序方式** | 时间倒序 | 最新的在前面 |

### 查询模板（带默认参数）

```sql
-- 查询活跃告警（默认最近7天，最多50条）
SELECT id, ew_name, st_code, eq_code, ew_type, level_r, content, 
       value, gather_time, message_confirm, create_time
FROM ew_info_message 
WHERE deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
ORDER BY 
  CASE level_r WHEN '1' THEN 1 WHEN '2' THEN 2 WHEN '3' THEN 3 WHEN '4' THEN 4 END,
  create_time DESC
LIMIT 50;

-- 查询高级别告警（默认最近30天）
SELECT id, ew_name, st_code, eq_code, ew_type, level_r, content, 
       value, gather_time, message_confirm, create_time
FROM ew_info_message 
WHERE deleted = 0
  AND level_r IN ('1', '2')
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY create_time DESC
LIMIT 50;

-- 查询告警统计（默认最近30天）
SELECT level_r, COUNT(*) as count
FROM ew_info_message 
WHERE deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY level_r
ORDER BY level_r;

-- 查询特定测站告警（默认最近30天）
SELECT id, ew_name, level_r, value, gather_time, message_confirm
FROM ew_info_message 
WHERE st_code = '606K2155' AND deleted = 0
  AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY gather_time DESC
LIMIT 50;
```

## 索引建议

```sql
-- 添加联合索引
CREATE INDEX idx_deleted_create_time ON ew_info_message(deleted, create_time);
CREATE INDEX idx_level_deleted ON ew_info_message(level_r, deleted);
CREATE INDEX idx_st_code_deleted ON ew_info_message(st_code, deleted);
CREATE INDEX ew_rules_id ON ew_info_message(ew_rules_id);
```

## 性能基准

| 查询类型 | 预期时间 | 数据量 |
|----------|----------|--------|
| 查询活跃告警 | < 0.1s | 50条 |
| 查询高级别告警 | < 0.1s | 50条 |
| 查询告警统计 | < 0.05s | 4条 |
| 查询告警趋势 | < 0.1s | 30天 |
| 查询设备当前值 | < 0.05s | 1条 |
