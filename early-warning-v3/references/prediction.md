# 预测预警

## 预测方法

### 1. 趋势预测

基于历史数据预测未来趋势：

```sql
-- 查询最近24小时水位趋势
SELECT rz, tm
FROM st_rsvr_r
WHERE eq_code = '606K215502'
ORDER BY tm DESC
LIMIT 24;
```

### 2. 阈值预测

判断是否会超限：

```sql
-- 查询当前水位和阈值
SELECT
  (SELECT rz FROM st_rsvr_r WHERE eq_code = '606K215502' ORDER BY tm DESC LIMIT 1) as current_level,
  (SELECT JSON_EXTRACT(extend, '$.content[0]') FROM ew_info_rules WHERE name = '水位红色预警' AND deleted = 0 LIMIT 1) as threshold;
```

### 3. 恢复预测

预测告警何时恢复：

```sql
-- 查询告警持续时间
SELECT
  id, ew_name, st_code, gather_time,
  TIMESTAMPDIFF(HOUR, gather_time, NOW()) as hours_pending
FROM ew_info_message
WHERE status = 'TRIGGERED' AND deleted = 0
  AND st_code = '606K2155'
ORDER BY gather_time DESC
LIMIT 1;
```

## 预测场景

### 水位预测

```bash
# 查询当前水位
python3 scripts/query_early_warning.py --type water_level --station 606K215502

# 查询水位趋势
mysql -u root -p123456aA. -e "USE powerelf_srm_yml; SELECT rz, tm FROM st_rsvr_r WHERE eq_code = '606K215502' ORDER BY tm DESC LIMIT 24;"
```

### 降雨预测

```bash
# 查询当前降雨
python3 scripts/query_early_warning.py --type rainfall --station 606K215501
```

### 告警风暴预测

```bash
# 查询告警风暴状态
python3 scripts/query_early_warning.py --type alarm_storm
```

## 预测报告模板

```
预测预警报告

1. 当前状态
   - 测站: XXX
   - 当前值: XXX
   - 阈值: XXX
   - 安全余量: XXX

2. 趋势分析
   - 最近24小时变化: 上升/下降/稳定
   - 变化速率: XXX/小时
   - 预计达到阈值时间: XXX

3. 预测结论
   - 是否会超限: 是/否
   - 预计超限时间: XXX
   - 置信度: XX%

4. 建议措施
   - 预防措施: XXX
   - 应急准备: XXX
```
