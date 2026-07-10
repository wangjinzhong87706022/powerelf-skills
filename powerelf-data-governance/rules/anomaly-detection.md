# 异常检测规则

> 异常记录表：`eq_data_anomaly_record`
> 异常统计表：`stats_data_anomaly_daily`

## 指标-表-字段映射

| 指标 | 数据表 | 检测字段 | 设备关联 |
|------|--------|----------|----------|
| 水位 | st_rsvr_r | rz(decimal 8,3) | eq_id → eq_equip_base |
| 河道水位 | st_river_r | z(decimal 8,3) | eq_id → eq_equip_base |
| 雨量 | st_pptn_r | p(decimal 5,1) | eq_id → eq_equip_base |
| 渗压 | st_pressure_r | ext_pressure(decimal 11,5), water_pressure(decimal 11,5) | eq_id → eq_equip_base |
| 渗流 | st_percolation_r | percolation(decimal 11,5) | eq_id → eq_equip_base |
| GNSS位移 | dsm_dfr_srvrds_srhrds | wgs84_delta_h/x/y(double) | eq_id → eq_equip_base |
| 流量(入库) | st_rsvr_r | inq(decimal 10,3) | eq_id → eq_equip_base |
| 流量(出库) | st_rsvr_r | otq(decimal 10,3) | eq_id → eq_equip_base |

## 核心算法

自适应窗口 MAD（Median Absolute Deviation）法。详见 `algorithms/mad-algorithm.md`。

### 快速参考

```
对每个数据点:
  1. 取窗口内所有值
  2. median = 中位数
  3. MAD = median(|xi - median|)
  4. modified_z_score = 0.6745 * |value - median| / MAD
  5. if modified_z_score > threshold → 异常
```

### 自适应窗口

```
windowSize = min(max(数据量 * 0.15, 10), 50)
```
- 数据量 < 10: 窗口 = 数据量（退化为全局）
- 数据量 10~333: 窗口 = 10~50（线性增长）
- 数据量 > 333: 窗口 = 50（固定上限）

摒弃原始实现中 `windowSize = 数据量`（退化为全局MAD，无法捕捉局部异常）。

### 分指标阈值

| 指标 | 阈值 | 理由 |
|------|------|------|
| 水位(rz) | 3.0 | 日变化平缓，异常容易识别 |
| 雨量(p) | 5.0 | 波动大，需要更高容忍度 |
| 渗压 | 4.0 | 中等波动 |
| GNSS位移 | 3.5 | 缓慢变化，突变即异常 |
| 流量(inq/otq) | 4.0 | 中等波动 |
| 通用默认 | 4.0 | 兜底值 |

摒弃原始实现中所有指标统一 `threshold=5`。

### 变化率检测（新增）

MAD 只检测绝对偏差，遗漏了"缓慢但持续偏移"的情况。增加变化率检测：

```
changeRate = |currentValue - previousValue| / |previousValue|

if previousValue != 0 and changeRate > 变化率阈值:
  → 标记为"可疑"（不直接判定异常，结合MAD结果）

变化率阈值:
  水位: 5%（日变化通常 < 1%）
  雨量: 不适用（可突变）
  渗压: 3%
  GNSS: 2%
  流量: 10%
```

### 综合判定

```
if MAD检测为异常 and 变化率超标:
  → 确认异常（高置信度）
if MAD检测为异常 and 变化率正常:
  → 可能异常（中置信度），检查是否为正常波动峰值
if MAD正常 and 变化率超标:
  → 可疑（低置信度），标记待人工确认
```

## 异常值处理

检测出异常值后的标准流程：

```
1. 将异常值设为 null
2. 调用智能插值(rules/interpolation.md)填补
3. 合并修复数据，记录到 fixDataContent
4. 生成异常记录: {equipmentCode, datetime, tableName, fixDataContent}
```

## 参数来源

所有阈值和窗口参数可在 `evolution/parameters.md` 中调整。
