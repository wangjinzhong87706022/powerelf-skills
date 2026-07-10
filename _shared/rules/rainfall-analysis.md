# 雨情分析规则

> 测站雨量表：`st_pptn_r`（测站雨情）
> 分区雨量表：`st_pptn_region_r`（分区雨情）
> 日雨量表：`st_pptn_dp_s`（测站日雨情表）
> 月雨量表：`st_pptn_mtp_s`（测站月雨情表）
> 年雨量表：`st_pptn_yrp_s`（测站年雨情表）
> 旬雨量表：`st_pptn_dcp_s`（测站旬雨情表）

## 核心字段（st_pptn_r）

| DB字段 | Java字段 | 含义 | 类型 | 单位 |
|--------|----------|------|------|------|
| p | p | 时段雨量 | decimal(5,1) | mm |
| dr | dr | 时段长 | decimal(6,1) | **分钟(min)** |
| dyp | dyp | 日雨量 | decimal(5,1) | mm |
| cump | cump | 累计雨量 | decimal(5,1) | mm |
| pdr | pdr | 降水历时 | decimal(5,5) | — |
| stcd | stCode | 站码 | varchar(20) | — |
| eq_code | eqCode | 设备编码 | varchar(20) | — |
| st_id | stId | 测站ID | bigint | — |
| eq_id | eqId | 设备ID | bigint | — |
| tm | tm | 采集时间 | datetime | — |

> ⚠️ dr 字段单位是**分钟**，不是小时。计算降雨强度时需要转换：`强度 = p / (dr/60)` mm/h

## 分区雨量字段（st_pptn_region_r）

| DB字段 | Java字段 | 含义 | 类型 | 单位 |
|--------|----------|------|------|------|
| drp | drp | 时段雨量 | decimal(6,1) NOT NULL | mm |
| intv | intv | 时段长 | decimal(6,2) NOT NULL | **小时(h)** |
| pdr | pdr | 降水历时 | decimal(6,5) NOT NULL | h |
| dyp | dyp | 日累计雨量 | decimal(6,1) NOT NULL | mm |
| wth | wth | 天气 | char | — |
| re_id | reId | 区域编码 | bigint | — |
| tm | tm | 采集时间 | datetime | — |

> 注意：分区雨量表的 intv 单位是**小时**，与测站雨量表的 dr（分钟）不同。

## 降雨等级划分

| 等级 | 24小时雨量 | 颜色 |
|------|-----------|------|
| 小雨 | 0.1-9.9mm | 绿色 |
| 中雨 | 10.0-24.9mm | 蓝色 |
| 大雨 | 25.0-49.9mm | 黄色 |
| 暴雨 | 50.0-99.9mm | 橙色 |
| 大暴雨 | 100.0-249.9mm | 红色 |
| 特大暴雨 | ≥250mm | 紫色 |

## 分析规则

### 1. 降雨强度

```
# st_pptn_r 表: dr 单位是分钟，需转换为小时
强度 = p / (dr / 60) (mm/h)

# st_pptn_region_r 表: intv 单位已经是小时
强度 = drp / intv (mm/h)

if 强度 > 16:
  → 暴雨级别降雨强度
if 强度 > 30:
  → 极端降雨
```

### 2. 累计降雨趋势

```
查询最近N天的 dyp(日雨量)
累计 = sum(dyp)

if 累计 > 100mm (3天):
  → 持续降雨预警
if 累计 > 200mm (7天):
  → 严重持续降雨
```

### 3. 雨量数据校验

```
if p < 0:
  → 数据异常（雨量不能为负）
if p > 200 (单小时，即 dr≈60min):
  → 数据异常或极端天气，需确认
if dr == 0 and p > 0:
  → 时段为0但有雨量，数据异常
if dyp < 0:
  → 日雨量为负，数据异常
```

### 4. 分区雨情分析

```
查询 st_pptn_region_r 表
按 re_id(区域) 分组

if drp > 50 and intv <= 24:
  → 该区域暴雨预警
if dyp > 100:
  → 该区域大暴雨预警

天气字段(wth)辅助判断:
  wth = '雨'/'雪'/'雷阵雨' 等
```
