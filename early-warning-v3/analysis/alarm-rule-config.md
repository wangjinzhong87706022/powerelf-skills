# 告警规则配置

## 功能

用户用自然语言描述规则，Agent 解析意图并生成 JSON 规则写入数据库。

## 用户指令 → 规则映射

### 示例 1: 阈值预警

用户说：
> "当主坝渗压计 P-001 水位超过 12 米时触发红色预警"

Agent 解析：
- 设备：主坝渗压计 P-001
- 条件：> 12.0
- 等级：红色 (L1)
- 类型：水位预警 (ew_type=0, type=YZ)

生成的规则 JSON：
```json
{
  "name": "主坝渗压计 P-001 水位超限预警",
  "status": "1",
  "type": "YZ",
  "ewType": "0",
  "level": "1",
  "stCode": "ST_P001",
  "eqCode": "EQ_P001",
  "dotAddress": "P001-WL",
  "extend": "{\"condition\":\">=\",\"content\":[12.0,null]}"
}
```

### 示例 2: 区间预警

用户说：
> "当雨量站在 1 小时内降雨量在 50 到 100 毫米之间时触发橙色预警"

Agent 解析：
- 条件：50 <= value <= 100
- 等级：橙色 (L2)
- 类型：雨量预警 (ew_type=2, type=YZ)

生成的规则 JSON：
```json
{
  "name": "雨量站小时降雨量区间预警",
  "status": "1",
  "type": "YZ",
  "ewType": "2",
  "level": "2",
  "extend": "{\"condition\":\"{}\",\"content\":[50.0,100.0]}"
}
```

### 示例 3: 大坝安全预警

用户说：
> "当主坝断面 S-001 的 H 方向位移超过 5 毫米时触发红色预警，需要至少 2 个测点触发"

Agent 解析：
- 断面：S-001
- 字段：wgs84DeltaH
- 条件：> 5.0
- 等级：红色 (L1)
- 触发测点数：2

生成的规则 JSON：
```json
{
  "name": "主坝断面 S-001 H方向位移预警",
  "status": "1",
  "type": "DAM-YZ",
  "ewType": "5",
  "level": "1",
  "damId": 1,
  "sectionId": 100,
  "triggerNumber": 2,
  "extend": "[{\"field\":\"wgs84DeltaH\",\"condition\":\">\",\"content\":[5.0,null]}]"
}
```

## 10 种条件运算符

| 用户表述 | 运算符 | JSON condition | JSON content |
|----------|--------|----------------|--------------|
| "超过 X" / "大于 X" | > | `>` | `[X, null]` |
| "低于 X" / "小于 X" | < | `<` | `[null, X]` |
| "大于等于 X" | >= | `>=` | `[X, null]` |
| "小于等于 X" | <= | `<=` | `[null, X]` |
| "等于 X" | = | `=` | `[X, X]` |
| "不等于 X" | != | `!=` | `[X, X]` |
| "在 X 到 Y 之间"（含端点） | 闭区间 | `{}` | `[X, Y]` |
| "在 X 到 Y 之间"（不含端点） | 开区间 | `()` | `[X, Y]` |
| "大于等于 X 小于 Y" | 左闭右开 | `{)` | `[X, Y]` |
| "大于 X 小于等于 Y" | 左开右闭 | `(}` | `[X, Y]` |

## 等级映射

| 用户表述 | 等级值 |
|----------|--------|
| "红色预警" / "一级" / "特别严重" | 1 |
| "橙色预警" / "二级" / "严重" | 2 |
| "黄色预警" / "三级" / "较重" | 3 |
| "蓝色预警" / "四级" / "一般" | 4 |

## 预警类型映射

| 用户表述 | ew_type | type |
|----------|---------|------|
| "水位" / "水位预警" | 0 | YZ |
| "水质" / "水质预警" | 1 | YZ |
| "雨量" / "降雨" / "雨量预警" | 2 | YZ |
| "开关变化" / "状态变化" | 3 | ZGB |
| "开关量" / "闸门" | 4 | KG |
| "大坝" / "位移" / "大坝安全" | 5 | DAM-YZ |
| "洪水" / "洪水预警" | 6 | YZ |

## 创建规则（写 — 走后端 API）

```
POST {API_BASE}/earlywaring/info-rules/create
Headers: Authorization: Bearer {TOKEN}, tenant-id: {tenantId}
Body: {规则 JSON}
```

## 查询现有规则（读 — 直连数据库）

```sql
SELECT er.id, er.name, er.type, er.ew_type, er.level_r, 
       er.status, er.extend, er.st_code, er.eq_code,
       er.create_time
FROM ew_info_rules er
WHERE er.deleted = 0
  AND er.tenant_id = #{tenantId}
ORDER BY er.create_time DESC
```

### 查询指定设备的规则

```sql
SELECT er.id, er.name, er.type, er.ew_type, er.level_r, 
       er.status, er.extend
FROM ew_info_rules er
WHERE er.eq_code = #{eqCode} AND er.deleted = 0
  AND er.status = '1'
```

## Agent 行为指引

当用户说"创建一个告警规则"时：
1. 询问：设备名称/编号、监测指标、条件、阈值、等级
2. 解析用户意图，映射到标准字段
3. 生成规则 JSON
4. 展示给用户确认
5. 调用 API 创建规则
6. 确认创建成功

当用户说"当水位超过 12 米时触发红色预警"时：
1. 解析：条件 >=, 阈值 12.0, 等级 1 (红色), 类型 YZ
2. 询问用户确认设备信息
3. 生成规则 JSON
4. 调用 API 创建
5. 确认创建成功

当用户说"查看当前的告警规则"时：
1. 查询所有启用的规则
2. 按类型分组展示
3. 展示每条规则的条件和等级
