# GNSS 变形分析规则

> 数据表：`dsm_dfr_srvrds_srhrds`（GNSS变形趋势图）
> 统计日报表：`srm_gnss_stat_day`（位移统计日报表）

## 核心字段

### 本次变化量（增量）

| DB字段 | Java字段 | 含义 | 单位 |
|--------|----------|------|------|
| wgs84_delta_h | wgs84DeltaH | 垂直位移变化量 | mm |
| wgs84_delta_x | wgs84DeltaX | 水平X位移变化量 | mm |
| wgs84_delta_y | wgs84DeltaY | 水平Y位移变化量 | mm |

### 累计变化量

| DB字段 | Java字段 | 含义 | 单位 |
|--------|----------|------|------|
| wgs84_total_h | wgs84TotalH | H方向累计位移 | mm |
| wgs84_total_x | wgs84TotalX | X方向累计位移 | mm |
| wgs84_total_y | wgs84TotalY | Y方向累计位移 | mm |

### 速率字段

| DB字段 | Java字段 | 含义 | 单位 |
|--------|----------|------|------|
| speed_gh | speedGh | 高程方向速率 | mm/月 |
| speed_gx | speedGx | X方向速率 | mm/月 |
| speed_gy | speedGy | Y方向速率 | mm/月 |
| speed_rx | speedRx | X方向速率(varchar) | — |
| speed_ry | speedRy | Y方向速率(varchar) | — |

### 坐标与观测字段

| DB字段 | Java字段 | 含义 | 单位 |
|--------|----------|------|------|
| data_b | dataB | 纬度 | ° |
| data_l | dataL | 经度 | ° |
| data_h | dataH | 大地高 | m |
| data_x/y/z | dataX/Y/Z | 空间直角坐标 | m |
| data_p | dataP | 平面偏移量 | mm |
| gx_data/gy_data | gxData/gyData | 高斯平面坐标 | m |
| distance | distance | 斜距 | m |
| hangle | hangle | 水平角 | ° |
| vangle | vangle | 垂直角 | ° |
| data_count | dataCount | 观测次数 | 次 |
| point_id | pointId | 测点ID | — |
| point_address | pointAddress | 测点地址 | — |
| st_id | stId | 测站ID | — |
| eq_id | eqId | 设备ID | — |
| tm | tm | 观测时间 | datetime |

## 分析规则

### 1. 位移速率分析

```
速率 = (最大值 - 最小值) / 月份数 * 100 (cm/月)

if 速率 > 5 cm/月:
  → 快速变形，高风险
if 速率 > 2 cm/月:
  → 中速变形，需关注
if 速率 > 0.5 cm/月:
  → 缓慢变形，持续监测
```

详见 `algorithms/displacement-rate.md`

### 2. 累计位移分析

```
累计位移 = |wgs84_total_x/y/h|

if 累计位移 > 预设阈值:
  → 超限预警

方向判断:
  wgs84_total_x > 0 → 向下游偏移
  wgs84_total_x < 0 → 上游偏移
  wgs84_total_h > 0 → 下沉
  wgs84_total_h < 0 → 上升
```

### 3. 一致性检查（同一断面多测点）

```
查询同一 point_id 的历史数据序列
对 wgs84_delta_x/y/h 进行趋势分析

if 同一断面多个测点偏移方向一致:
  → 可能是整体滑动，升级告警
if 相邻测点偏移方向相反:
  → 可能是局部变形，关注
```

### 4. 年度位移统计

```
查询 srm_gnss_stat_day 表（GNSS日统计表）
字段: maxh/minh/avgh, maxx/minx/avgx, maxy/miny/avgy

按测站分组:
  年变幅 = maxh - minh (垂直方向)
  年变幅 = maxx - minx (X方向)
  年变幅 = maxy - miny (Y方向)
```

### 5. 位移与水位关联分析

```
同时查询水位数据和GNSS数据
构建4条曲线: 水位、水平位移Y、水平位移X、垂直沉降H

if 水位上升 and 位移加速:
  → 水位变化可能影响坝体稳定性
if 水位稳定 and 位移持续:
  → 非水位因素导致的变形
```
