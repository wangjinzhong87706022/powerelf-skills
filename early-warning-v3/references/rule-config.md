# 告警规则配置

## 规则表结构

```sql
CREATE TABLE ew_info_rules (
  id bigint PRIMARY KEY AUTO_INCREMENT,
  name varchar(255) COMMENT '规则名称',
  ew_type char(2) COMMENT '告警类型(0=水位,1=水质,2=雨量,20=渗压/流量,40=渗流/位移)',
  level_r char(2) COMMENT '告警级别(1=红,2=橙,3=黄,4=蓝)',
  st_code varchar(255) COMMENT '测站编码',
  extend json COMMENT '规则扩展(JSON格式)',
  status char(2) DEFAULT '1' COMMENT '状态',
  deleted bit(1) DEFAULT b'0',
  tenant_id bigint DEFAULT 1
);
```

## extend字段格式

```json
{
  "content": ["阈值1", "阈值2"],
  "condition": "运算符"
}
```

### 运算符说明

| 运算符 | 含义 | 示例 |
|--------|------|------|
| `>` | 大于 | `{"content": ["100", null], "condition": ">"}` |
| `>=` | 大于等于 | `{"content": ["100", null], "condition": ">="}` |
| `<` | 小于 | `{"content": ["100", null], "condition": "<"}` |
| `<=` | 小于等于 | `{"content": [null, "100"], "condition": "<="}` |
| `{)` | 左闭右开 | `{"content": ["50", "100"], "condition": "{)"}`  (50<=x<100) |
| `{}` | 闭区间 | `{"content": ["50", "100"], "condition": "{}"}`  (50<=x<=100) |

## 查询规则

```bash
# 查询所有规则
python3 scripts/query_early_warning.py --type rules

# 查询特定规则
python3 scripts/query_early_warning.py --type rule_detail --rule "水位"
```

## 规则清单

| 名称 | 类型 | 级别 | 测站 | 阈值 |
|------|------|------|------|------|
| 低水位预警 | 0 | 4 | 606K2155 | <=459 |
| 低水位预警 | 0 | 4 | 606K2158 | <=445 |
| 水位红色预警 | 0 | 1 | 606K2155 | >=480 |
| 红色雨量预警 | 2 | 1 | 606K2152 | >=100 |
| 橙色雨量预警 | 2 | 2 | 606K2152 | 80-100 |
| 黄色雨量预警 | 2 | 3 | 606K2152 | 50-80 |
| 蓝色雨量预警 | 2 | 4 | 606K2152 | 30-50 |
| 渗流一级预警 | 40 | 1 | 2023510006-SL | >=30 |
| 渗流二级预警 | 40 | 2 | 2023510006-SL | 15-30 |
| 溢洪道流量黄色预警 | 20 | 3 | 606K2153 | >=80 |
| 溢洪道出库流量蓝色预警 | 20 | 4 | 606K2153 | 50-80 |
