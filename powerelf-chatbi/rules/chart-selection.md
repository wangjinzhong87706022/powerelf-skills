# 图表选择规则

## 图表类型

| chartType | 适用场景 |
|-----------|----------|
| line + 多组 | 多系列时间序列对比 |
| line + 多Y字段 | 同一时间轴多个Y指标 |
| line + 单Y字段 | 单指标时间序列 |
| bar + 分组 | 分类对比（多系列） |
| bar + 单系列 | 分类对比（单系列） |
| pie | 占比分析 |
| none | 数据不适合图表 |

> 图表类型扩充（热力/散点/地图/双轴/堆叠等）见 B' 簇后续。agent 生成 ECharts option 时按本表语义选择。

## 选择逻辑

```
输入: 数据结构（字段数、行数、数据类型）

1. 数据行数 <= 1:
   → none（数据太少）

2. 有时间字段 + 数值字段:
   if 数值字段 >= 3:
     → line + 多Y字段
   elif 有分组字段:
     → line + 多组
   else:
     → line + 单Y字段

3. 有分类字段 + 数值字段:
   if 有分组字段:
     → bar + 分组
   else:
     → bar + 单系列

4. 有分类字段 + 占比数据:
   → pie

5. 其他:
   → none
```

## ECharts 输出格式

```json
{
  "option": {
    "xAxis": {"type": "category", "data": [...]},
    "yAxis": {"type": "value"},
    "series": [{"name": "...", "type": "line/bar/pie", "data": [...]}]
  }
}
```

SSE输出格式:
```
## **图表**
::: echarts {"option": {...}} :::
```
