# 预测性预警

## 概念

基于历史数据趋势，在实际超限前提前预警，给运维人员预留处理时间。

## 预测方法

### 方法 1: 线性外推

基于最近 N 小时的变化速率，预测未来值。

```sql
-- 获取最近 6 小时的水位数据
SELECT rz as value, tm as time
FROM st_rsvr_r 
WHERE st_id = #{stId} 
  AND tm >= DATE_SUB(NOW(), INTERVAL 6 HOUR)
ORDER BY tm ASC
```

计算：
```
rate = (latest_value - first_value) / hours
predicted_value = latest_value + rate * forecast_hours
```

### 方法 2: 移动平均

基于最近 N 个数据点的移动平均值预测。

```sql
-- 获取最近 24 小时的水位数据，按小时聚合
SELECT 
  DATE_FORMAT(tm, '%Y-%m-%d %H:00:00') as hour,
  AVG(rz) as avg_value
FROM st_rsvr_r 
WHERE st_id = #{stId} 
  AND tm >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY DATE_FORMAT(tm, '%Y-%m-%d %H:00:00')
ORDER BY hour ASC
```

### 方法 3: 指数平滑

```javascript
// 简单指数平滑
function exponentialSmoothing(data, alpha = 0.3) {
  let result = [data[0]];
  for (let i = 1; i < data.length; i++) {
    result.push(alpha * data[i] + (1 - alpha) * result[i-1]);
  }
  return result;
}
```

## 查询阈值配置（读 — 直连数据库）

```sql
-- 查询预警规则中的阈值
SELECT er.id, er.name, er.type, er.ew_type, er.level_r, er.extend
FROM ew_info_rules er
WHERE er.st_code = #{stCode} AND er.status = '1' AND er.deleted = 0
```

## 预测分析报告

```
📊 预测性预警分析

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 设备：{stName} ({stCode})
📏 当前值：{currentValue} {unit}
⚠️ 阈值：{threshold} {unit}
📈 距阈值：{distance} {unit}

🔮 预测结果

方法 1 - 线性外推：
- 最近 6 小时变化速率：{rate1} {unit}/小时
- 预计 {hours1} 小时后达到阈值
- 预计超限时间：{predictedTime1}

方法 2 - 移动平均：
- 最近 24 小时平均变化：{rate2} {unit}/小时
- 预计 {hours2} 小时后达到阈值
- 预计超限时间：{predictedTime2}

方法 3 - 指数平滑：
- 平滑变化率：{rate3} {unit}/小时
- 预计 {hours3} 小时后达到阈值
- 预计超限时间：{predictedTime3}

📊 综合预测
- 置信度：{confidence}%
- 建议预警等级：{suggestedLevel}
- 建议处理时间：{suggestedActionTime}

💡 建议
{suggestion}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Agent 行为指引

当用户问"这个设备会不会超限？"时：
1. 查询设备当前值和历史数据
2. 查询预警规则中的阈值
3. 使用多种方法预测
4. 综合判断并给出置信度

当用户问"预计什么时候会超限？"时：
1. 计算当前变化速率
2. 预测达到阈值的时间
3. 给出不同预测方法的结果
4. 建议处理时间窗口

当用户说"提前预警"时：
1. 对所有活跃设备执行预测分析
2. 筛选预计在 24 小时内超限的设备
3. 生成预测性预警列表
4. 按紧急程度排序
