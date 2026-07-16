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
| map | 地理分布 — 含省份/城市/区域字段 + 数值 |
| heatmap | 矩阵/交叉分析 — 两个分类维度 + 数值（如站点×月份→雨量） |
| scatter | 分布/相关性 — 两个数值字段的关系 |
| dual-axis | 双轴对比 — 两数值量纲或尺度差异大（如水位+流量） |
| stacked | 堆叠构成 — 时间/分类 + 分组累计占比（如各类型设备离线数月变化） |
| none | 数据不适合图表 |

agent 生成 ECharts option 时按本表语义选择。

## 选择逻辑

```
输入: 数据结构（字段数、行数、数据类型）

1. 数据行数 <= 1:
   → none（数据太少）

   # B' 簇扩充：优先匹配特化图表类型
2. 有地理字段（省份/城市/区域/坐标）+ 数值字段:
   → map

3. 有 2 个分类/维度字段 + 1 个数值字段（矩阵/交叉数据）:
   → heatmap

4. 无时间字段，有 2+ 数值字段，数据行数适中（≤ 约 200）:
   → scatter

5. 有时间字段 + 2 个数值字段，且数值量纲不同或尺度差异大（如水位+流量、雨量+温度）:
   → dual-axis

6. 有时间/分类字段 + 分组字段 + 数值字段，且分组间呈累计/占比构成关系:
   → stacked

   # 原逻辑（线图/柱图/饼图）
7. 有时间字段 + 数值字段:
   if 数值字段 >= 3:
     → line + 多Y字段
   elif 有分组字段:
     → line + 多组
   else:
     → line + 单Y字段

8. 有分类字段 + 数值字段:
   if 有分组字段:
     → bar + 分组
   else:
     → bar + 单系列

9. 有分类字段 + 占比数据:
   → pie

10. 其他:
    → none
```

## ECharts 输出格式

### 通用格式

```json
{
  "option": {
    "xAxis": {"type": "category", "data": [...]},
    "yAxis": {"type": "value"},
    "series": [{"name": "...", "type": "line/bar/pie", "data": [...]}]
  }
}
```

### 扩充类型示例

**地图 (map)：**
```json
{
  "option": {
    "visualMap": {"min": 0, "max": 100, "calculable": true},
    "series": [{"type": "map", "map": "china", "data": [{"name": "广东省", "value": 95}, ...]}]
  }
}
```

**热力图 (heatmap)：**
```json
{
  "option": {
    "xAxis": {"type": "category", "data": ["站点A","站点B",...]},
    "yAxis": {"type": "category", "data": ["1月","2月",...]},
    "visualMap": {"min": 0, "max": 300, "calculable": true},
    "series": [{"type": "heatmap", "data": [[0,0,120], [0,1,85], ...]}]
  }
}
```

**散点图 (scatter)：**
```json
{
  "option": {
    "xAxis": {"type": "value", "name": "流量(m³/s)"},
    "yAxis": {"type": "value", "name": "水位(m)"},
    "series": [{"type": "scatter", "data": [[12.5, 98.3], [8.2, 95.1], ...]}]
  }
}
```

**双轴图 (dual-axis)：**
```json
{
  "option": {
    "xAxis": {"type": "category", "data": [...]},
    "yAxis": [
      {"type": "value", "name": "水位(m)"},
      {"type": "value", "name": "流量(m³/s)"}
    ],
    "series": [
      {"name": "水位", "type": "line", "data": [...]},
      {"name": "流量", "type": "bar", "yAxisIndex": 1, "data": [...]}
    ]
  }
}
```

**堆叠图 (stacked)：**
```json
{
  "option": {
    "xAxis": {"type": "category", "data": [...]},
    "yAxis": {"type": "value"},
    "series": [
      {"name": "闸门故障", "type": "bar", "stack": "total", "data": [...]},
      {"name": "通信异常", "type": "bar", "stack": "total", "data": [...]},
      {"name": "传感器失效", "type": "bar", "stack": "total", "data": [...]}
    ]
  }
}
```

SSE输出格式:
```
## **图表**
::: echarts {"option": {...}} :::
```
