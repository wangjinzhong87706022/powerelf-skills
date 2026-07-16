# 参数优化

## 优化维度

### 1. 阈值优化

**分析方法：**
```sql
-- 查询历史水位统计
SELECT
  MIN(rz) as min_level,
  MAX(rz) as max_level,
  AVG(rz) as avg_level
FROM st_rsvr_r
WHERE eq_code = '606K215502'
  AND tm >= DATE_SUB(NOW(), INTERVAL 30 DAY);
```

**优化建议：**
- 阈值应基于历史数据设置
- 考虑季节性变化
- 预留安全余量

### 2. 规则优化

**分析方法：**
```sql
-- 查询规则触发频率
SELECT
  b.name as rule_name,
  COUNT(*) as trigger_count
FROM ew_info_message a
JOIN ew_info_rules b ON a.ew_rules_id = b.id
WHERE a.deleted = 0
  AND a.create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY b.name
ORDER BY trigger_count DESC;
```

**优化建议：**
- 高频触发规则：检查阈值是否合理
- 低频触发规则：检查是否需要保留
- 冲突规则：合并或删除

### 3. 通知策略优化

**分析方法：**
```sql
-- 查询通知策略
SELECT id, name, ew_level, ew_rules_type, notice_manner
FROM ew_notice_tactics
WHERE deleted = 0;
```

**优化建议：**
- 覆盖所有告警类型
- 通知对象合理
- 通知方式适当

### 4. 确认率优化

**分析方法：**
```bash
python3 scripts/query_early_warning.py --type confirmation_rate --days 30
```

**优化建议：**
- 优化通知方式
- 设置自动确认规则
- 加强值班培训

## 优化报告模板

```
参数优化报告

1. 阈值分析
   - 当前阈值: XXX
   - 历史数据: 最小XXX, 最大XXX, 平均XXX
   - 优化建议: XXX

2. 规则分析
   - 规则总数: X条
   - 高频规则: XXX (X次)
   - 低频规则: XXX (X次)
   - 优化建议: XXX

3. 通知策略
   - 策略数量: X条
   - 覆盖率: XX%
   - 优化建议: XXX

4. 确认率
   - 当前确认率: XX%
   - 目标确认率: XX%
   - 优化建议: XXX
```
