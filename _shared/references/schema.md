# powerelf 数据库表结构（唯一事实源）

> **单一事实源**：本文件合并自原 `data-governance/references/{schema,actual_schema}.md` 与
> `inspection/references/{database-schema,data-model}.md` 四份文档，消除跨 skill 的表结构
> 描述分歧。各 skill 的本地 schema 文档现为指向本文件的薄指针。
>
> **冲突仲裁规则**：当列名/关联键/类型出现分歧时，以实测记录（2026-07-08）为准；
> DDL 精度（如 `DECIMAL(8,3)` vs `(10,2)`）可能随库演化，以线上实际为准，字段语义与
> 关键字段名为本文件关注的重点。
>
> **巡检业务实体**（`business_check_*` 11 张表）属 inspection 专有领域，仍在
> `inspection/references/data-model.md` 维护，不在本文件范围。

---

## ⚠️ 关键修正：设备关联键（必须先读）

历史文档对监测表与设备表的关联键说法不一，**实测（2026-07-08）**结论如下：

| 业务表 | 关联键 | 关联方式 | 检测字段 |
|--------|--------|----------|----------|
| st_rsvr_r | **stcd** (varchar) | `WHERE stcd = eq_equip_base.code` | rz, inq, otq |
| st_pptn_r | **stcd** (varchar) | `WHERE stcd = eq_equip_base.code` | p |
| st_percolation_r | **stcd** (varchar) | `WHERE stcd = eq_equip_base.code` | percolation |
| st_pressure_r | **eq_id** (bigint) | `WHERE eq_id = eq_equip_base.id` | ext_pressure, water_pressure, ext_temperature |
| st_pressure_r | stcd (varchar) | 备选 | 同上 |
| dsm_dfr_srvrds_srhrds (GNSS) | **eq_id** (int) | `WHERE eq_id = eq_equip_base.id` | wgs84_total_h/x/y, wgs84_delta_h/x/y |
| dsm_dfr_srvrds_srhrds (GNSS) | st_id (bigint) | 备选 | 同上 |

**铁律**：`eq_equip_base.code` 是字符串（如 `"606K215001"`），**不能**直接放进 `eq_id = '606K215001'`
——MySQL 会把它当列名报 `Unknown column`。要用 `eq_equip_base.id`（bigint）做 `eq_id` 查询，
或用 `code` 匹配 `stcd`。

常见错误假设纠正：

| 常见错误假设 | 实际正确值 |
|------------|----------|
| 时间列是 `data_time` / `tm`（治理记录表） | 监测表是 `tm`；治理记录表是 **`create_time`** |
| 设备关联列是 `station_id` | 实际是 **`eq_id`**(bigint) 或 **`stcd`**(varchar)（见上表） |
| 表名 `sl_rsvr_rt_r` | 实际是 **`st_rsvr_r`** |
| 设备类型列是 `type` | 实际是 **`type_flag`** |
| 设备表有 `freq` 采集频率列 | 无；采集频率默认 **10 分钟** |
| pymysql 用 `conn.execute(sql)` | 正确: **`conn.cursor().execute(sql)`** |

---

## 一、监测表（原始数据，12 类）

### 1.1 水文气象

#### st_rsvr_r — 水库水情
```sql
CREATE TABLE st_rsvr_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    rz   DECIMAL(10,2) COMMENT '库水位(m)',
    inq  DECIMAL(10,2) COMMENT '入库流量(m³/s)',
    otq  DECIMAL(10,2) COMMENT '出库流量(m³/s)',
    w    DECIMAL(10,2) COMMENT '蓄水量(万m³)',
    blrz DECIMAL(10,2) COMMENT '下游水位(m)',
    stcd VARCHAR(20) COMMENT '站码',
    PRIMARY KEY (st_id, tm)
);
```

#### st_river_r — 河道水情
```sql
CREATE TABLE st_river_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    z      DECIMAL(10,2) COMMENT '水位(m)',
    q      DECIMAL(10,2) COMMENT '流量(m³/s)',
    xsa    DECIMAL(10,2) COMMENT '断面面积(m²)',
    xsavv  DECIMAL(5,2)  COMMENT '平均流速(m/s)',
    xsmxv  DECIMAL(5,2)  COMMENT '最大流速(m/s)',
    stcd   VARCHAR(20) COMMENT '站码',
    PRIMARY KEY (st_id, tm)
);
```

#### st_was_r — 闸站水情
```sql
CREATE TABLE st_was_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    upz  DECIMAL(10,2) COMMENT '上游水位(m)',
    dwz  DECIMAL(10,2) COMMENT '下游水位(m)',
    tgtq DECIMAL(10,2) COMMENT '总过闸流量(m³/s)',
    stcd VARCHAR(20) COMMENT '站码',
    PRIMARY KEY (st_id, tm)
);
```

#### st_tide_r — 潮汐水情
```sql
CREATE TABLE st_tide_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    tdz   DECIMAL(10,2) COMMENT '潮位(m)',
    airp  DECIMAL(10,2) COMMENT '气压(hPa)',
    tdptn VARCHAR(10) COMMENT '潮位状态',
    hltdmk VARCHAR(4)  COMMENT '高低潮标记',
    stcd  VARCHAR(20) COMMENT '站码',
    PRIMARY KEY (st_id, tm)
);
```

#### st_pptn_r — 测站雨量
```sql
CREATE TABLE st_pptn_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    p    DECIMAL(5,1) COMMENT '时段雨量(mm)',
    dr   DECIMAL(6,1) COMMENT '时段长(分钟)',
    dyp  DECIMAL(5,1) COMMENT '日雨量(mm)',
    cump DECIMAL(5,1) COMMENT '累计雨量(mm)',
    pdr  DECIMAL(5,5) COMMENT '降水历时',
    stcd VARCHAR(20) COMMENT '站码',
    PRIMARY KEY (st_id, tm)
);
```
> ⚠️ `dr` 单位是**分钟**，计算降雨强度需转换：`强度 = p / (dr/60)` mm/h

#### st_pptn_region_r — 分区雨情
```sql
CREATE TABLE st_pptn_region_r (
    re_id INT NOT NULL, tm DATETIME NOT NULL,
    drp DECIMAL(6,1) NOT NULL COMMENT '时段雨量(mm)',
    intv DECIMAL(6,2) NOT NULL COMMENT '时段长(小时)',
    pdr  DECIMAL(6,5) NOT NULL COMMENT '降水历时(h)',
    dyp  DECIMAL(6,1) NOT NULL COMMENT '日累计雨量(mm)',
    wth  CHAR COMMENT '天气',
    PRIMARY KEY (re_id, tm)
);
```
> ⚠️ `intv` 单位是**小时**，与 `st_pptn_r.dr`（分钟）不同

#### 雨量汇总表
- `st_pptn_dp_s`：日雨量，键 `(st_id, dt)`，字段 `dp`
- `st_pptn_mtp_s`：月雨量，键 `(st_id, mt)`，字段 `mp`
- `st_pptn_yrp_s`：年雨量，键 `(st_id, yr)`，字段 `yp`
- `st_pptn_dcp_s`：旬雨量，键 `(st_id, tm)`，字段 `dp`

#### st_flood_r — 防洪区水情
```sql
CREATE TABLE st_flood_r (
    fca_id INT NOT NULL, tm DATETIME NOT NULL,
    z DECIMAL(10,2) COMMENT '水位(m)',
    q DECIMAL(10,2) COMMENT '流量(m³/s)',
    PRIMARY KEY (fca_id, tm)
);
```

### 1.2 设备工情

#### rei_gate_r — 闸门工情
```sql
CREATE TABLE rei_gate_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    gtq     DECIMAL(10,2) COMMENT '流量(m³/s)',
    gtophgt DECIMAL(5,2)  COMMENT '开启高度(m)',
    gtopnum TINYINT       COMMENT '开启孔数',
    status  TINYINT       COMMENT '闸门状态(1=开启/2=关闭/3=异常)',
    stcd    VARCHAR(20)   COMMENT '站码',
    slcd    VARCHAR(20)   COMMENT '闸码',
    PRIMARY KEY (st_id, tm)
);
```

#### rei_pump_r — 泵站工情
```sql
CREATE TABLE rei_pump_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    uab VARCHAR(10) COMMENT 'AB相电压', ubc VARCHAR(10) COMMENT 'BC相电压', uca VARCHAR(10) COMMENT 'CA相电压',
    ia  VARCHAR(10) COMMENT 'A相电流', ib VARCHAR(10) COMMENT 'B相电流', ic VARCHAR(10) COMMENT 'C相电流',
    p   VARCHAR(10) COMMENT '有功功率', freq VARCHAR(10) COMMENT '频率', speed VARCHAR(10) COMMENT '转速',
    status TINYINT     COMMENT '运行状态(0=停止/1=运行/2=故障)',
    angle  DECIMAL(5,1) COMMENT '叶片角度(°)',
    PRIMARY KEY (st_id, tm)
);
```
> ⚠️ 电气参数（uab/ubc/uca/ia/ib/ic/p/freq/speed）为 **varchar**，数值比较前需 CAST 或应用层转换

### 1.3 大坝安全

#### dsm_dfr_srvrds_srhrds — GNSS 位移
```sql
CREATE TABLE dsm_dfr_srvrds_srhrds (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    wgs84_delta_h DECIMAL(6,3) COMMENT '高程变化量(mm)',
    wgs84_delta_x DECIMAL(6,3) COMMENT 'X方向变化量(mm)',
    wgs84_delta_y DECIMAL(6,3) COMMENT 'Y方向变化量(mm)',
    wgs84_total_h DECIMAL(8,3) COMMENT '累计高程变化(mm)',
    wgs84_total_x DECIMAL(8,3) COMMENT '累计X方向变化(mm)',
    wgs84_total_y DECIMAL(8,3) COMMENT '累计Y方向变化(mm)',
    speed_gh DECIMAL(5,2) COMMENT 'H方向速率(mm/d)',
    speed_gx DECIMAL(5,2) COMMENT 'X方向速率(mm/d)',
    speed_gy DECIMAL(5,2) COMMENT 'Y方向速率(mm/d)',
    point_id VARCHAR(50) COMMENT '测点ID',
    PRIMARY KEY (st_id, tm)
);
```

#### st_percolation_r — 渗流
```sql
CREATE TABLE st_percolation_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    percolation DECIMAL(10,2) COMMENT '渗流量(L/s)',
    stcd    VARCHAR(20) COMMENT '站码',
    eq_code VARCHAR(50) COMMENT '设备编码',
    PRIMARY KEY (st_id, tm)
);
```

#### st_pressure_r — 渗压
```sql
CREATE TABLE st_pressure_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    ext_pressure    DECIMAL(10,2) COMMENT '渗压(kPa)',
    water_pressure  DECIMAL(10,2) COMMENT '水位压力(kPa)',
    ext_temperature DECIMAL(5,1)  COMMENT '温度(℃)',
    section_id INT         COMMENT '断面ID',
    point_id   VARCHAR(50) COMMENT '测点ID',
    PRIMARY KEY (st_id, tm)
);
```

### 1.4 其他

#### wq_pcp_d — 水质
```sql
CREATE TABLE wq_pcp_d (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    ph   DECIMAL(3,1) COMMENT 'pH值',
    do   DECIMAL(5,1) COMMENT '溶解氧(mg/L)',
    nh3n DECIMAL(6,3) COMMENT '氨氮(mg/L)',
    tn   DECIMAL(6,3) COMMENT '总氮(mg/L)',
    tp   DECIMAL(6,3) COMMENT '总磷(mg/L)',
    PRIMARY KEY (st_id, tm)
);
```

#### st_soil_moisture_r — 墒情
```sql
CREATE TABLE st_soil_moisture_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    soil_water10cm .. soil_water100cm DECIMAL(5,1) COMMENT '各深度含水量(%)',
    soil_temp10cm  .. soil_temp100cm  DECIMAL(4,1) COMMENT '各深度温度(℃)',
    ec                DECIMAL(8,2) COMMENT '电导率(uS/cm)',
    ph                DECIMAL(3,1) COMMENT 'pH值',
    tension           DECIMAL(6,2) COMMENT '张力(kPa)',
    groundwater_depth DECIMAL(6,2) COMMENT '地下水位(m)',
    soil_moist_evaluation VARCHAR(10) COMMENT '评价(正常/轻度/中度/严重干旱)',
    PRIMARY KEY (st_id, tm)
);
```

#### st_termite_monitor_r — 白蚁
```sql
CREATE TABLE st_termite_monitor_r (
    st_id INT NOT NULL, tm DATETIME NOT NULL,
    termite_species VARCHAR(50) COMMENT '蚁种',
    pest_density    TINYINT     COMMENT '密度等级(0-4)',
    damage_level    TINYINT     COMMENT '危害等级',
    check_result    VARCHAR(20) COMMENT '检查结果(无白蚁/发现/疑似痕迹)',
    PRIMARY KEY (st_id, tm)
);
```

---

## 二、设备 / 关联 / 基础信息表

### eq_equip_base — 设备台账
```sql
CREATE TABLE eq_equip_base (
    id          BIGINT PRIMARY KEY,          -- 关联业务表的 eq_id
    code        VARCHAR(20) COMMENT '设备编码(如 606K215001)',
    name        VARCHAR(100) COMMENT '设备名称',
    type_flag   INT COMMENT '设备类型(1=水尺,2=雨量,3=渗压,5=渗流,7=GNSS,8=摄像机,9/11/13/14/20=其他)',
    category    VARCHAR(255) COMMENT '分类',
    status      INT COMMENT '状态(0=离线/1=在线/2=异常)',
    st_base_id  BIGINT COMMENT '所属测站ID',
    manufacturer VARCHAR(255) COMMENT '厂商',
    deleted     BIT(1) COMMENT '逻辑删除'
);
```
**⚠️ 没有 `type` 列（用 `type_flag`），没有 `freq` 列（采集频率默认 10 分钟）。**

### eq_business_equip_relation — 设备-业务映射
```sql
CREATE TABLE eq_business_equip_relation (
    id BIGINT PRIMARY KEY,
    business_table VARCHAR(255) COMMENT '业务表名',
    eq_id BIGINT COMMENT '设备ID',
    st_id BIGINT COMMENT '测站ID',
    st_type VARCHAR(20) COMMENT '站类型',
    frequency INT COMMENT '采集频率(分钟)',
    offline_threshold INT COMMENT '离线阈值(分钟)'
);
```

### att_st_base — 测站基本表
```sql
CREATE TABLE att_st_base (
    st_id INT PRIMARY KEY,
    st_name VARCHAR(100), st_code VARCHAR(20),
    st_type VARCHAR(20) COMMENT 'RSVR/RIVER/PPTN/PRESSURE/...',
    lgtd DECIMAL(10,6), lttd DECIMAL(10,6), stlc VARCHAR(200),
    status TINYINT COMMENT '0=离线/1=在线/2=异常',
    dam_id INT COMMENT '关联大坝ID'
);
```

---

## 三、治理输出表（data-governance 写入）

> 以下记录表均**无 `deleted` 字段**，不做逻辑删除。时间列是 `create_time`（非 `tm`）。

### eq_data_anomaly_record / eq_data_missing_record — 数据异常/缺失记录
| 字段 | 说明 |
|------|------|
| id (bigint, PK) | 主键 |
| equipment_code (varchar) | 设备编码 |
| data_{anomaly\|missing}_datetime (datetime) | 异常/缺失数据时间 |
| whether_{fix\|add} (tinyint) | 是否已修复/增补 |
| {fix\|filled}_data_content (json) | 修复/填充数据内容 |
| table_name (varchar) | 来源业务表名 |
| data_missing_count (int) | 缺失条数（仅 missing 表） |
| time_period_id (tinyint) | 时间段ID（仅 missing 表） |
| create_time / update_time / creator / updater | 审计字段 |

### eq_equip_offline_record / eq_equip_anomaly_record — 设备离线/异常记录
| 字段 | 说明 |
|------|------|
| id (bigint, PK) | 主键 |
| equipment_code (varchar) | 设备编码 |
| {offline\|anomaly}_start_date (date) + _start_time (time) | 开始日期/时间 |
| {offline\|anomaly}_end_time (time) | 结束时间 |
| total_{offline\|anomaly}_duration (int) | 累计时长(秒) |
| create_time / update_time / creator / updater | 审计字段 |

---

## 四、统计表

| 表 | 键 | 关键字段 |
|----|----|----------|
| stats_data_collection_daily | (tm date, table_name) | collection_data_number（时间槽覆盖数，**非总行数**） |
| stats_data_missing_daily | (tm date, table_name) | missing_data_number |
| stats_data_anomaly_daily | (tm date, table_name) | anomaly_data_number |

> ⚠️ `collection_data_number` 是**时间槽覆盖数**，不是总行数。

---

## 五、配置表

### dg_equip_offline — 离线阈值配置
| 字段 | 说明 |
|------|------|
| id (bigint, PK) | 主键 |
| st_type (varchar) | 站类型编码 |
| tm (int) | 离线阈值(分钟) |
| frequency (int) | 采集频率(分钟) |

站类型与阈值对照：

| st_type | 站类型 | tm(阈值min) | frequency(采集频率min) |
|---------|--------|------------|----------------------|
| SP | 水位站 | 360 | -- |
| GN | GNSS站 | 60 | 60 |
| EL | 闸门站 | 60 | 60 |
| ZS | 雨量站 | 60 | 60 |
| WQ | 水质站 | 60 | 60 |
| PP | 渗压站 | 60 | 60 |
| DP | 渗流站 | 60 | 60 |
| DD | 位移站 | 60 | 60 |
| YZ | 墒情站 | 60 | 60 |
| ZG/RR/ZQ/TT/BB/MM/SS/DC | 其他 | 0(不检测) | -- |

---

## 六、预警 / 数据源注册表

### ew_info_rules — 预警规则/阈值
```sql
CREATE TABLE ew_info_rules (
    id INT PRIMARY KEY,
    name VARCHAR(100), ew_type CHAR(2) COMMENT '0=水位/1=水质/2=雨量/3=开关变化/4=开关',
    level_r VARCHAR(10) COMMENT '预警级别(I/II/III/IV)',
    st_id INT COMMENT '测站ID(空=全局)',
    extend JSON COMMENT '扩展配置(阈值JSON)',
    status TINYINT, rule_content TEXT
);
```
`extend` JSON 示例：`{"threshold":248.0, "rate":{"max_change":0.5,"window":1}, "trend":{"consecutive":6,"window_hours":6}}`

### ew_info_message — 预警消息
```sql
CREATE TABLE ew_info_message (
    id INT PRIMARY KEY,
    ew_name VARCHAR(100), ew_type VARCHAR(50), level_r VARCHAR(10) COMMENT 'I/II/III',
    value DECIMAL(10,2) COMMENT '触发值', content TEXT COMMENT '告警内容',
    st_id INT, st_name VARCHAR(100), gather_time DATETIME,
    status TINYINT COMMENT '0=未确认/1=已确认',
    create_time DATETIME, confirm_time DATETIME, deleted TINYINT DEFAULT 0
);
```

### sys_data_source_registry — 数据源注册表
```sql
CREATE TABLE sys_data_source_registry (
    id INT PRIMARY KEY,
    name VARCHAR(100), source_table VARCHAR(100),
    keywords VARCHAR(500) COMMENT '匹配关键词(逗号分隔)',
    station_type VARCHAR(20), max_distance INT,
    query_fields VARCHAR(500), time_field VARCHAR(50),
    default_hours INT, judge_rules JSON,
    sort_order INT, status TINYINT, deleted TINYINT DEFAULT 0
);
```

---

## 七、常见 SQL 查询模式

```sql
-- 水库：最近一周水位变化
SELECT tm, rz, inq, otq FROM st_rsvr_r WHERE st_id = ? AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY) ORDER BY tm;
-- 水库：最新一条
SELECT * FROM st_rsvr_r WHERE st_id = ? ORDER BY tm DESC LIMIT 1;
-- 河道
SELECT tm, z, q FROM st_river_r WHERE st_id = ? AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY);
-- 今日降雨量（按站汇总）
SELECT st_id, SUM(p) AS total FROM st_pptn_r WHERE DATE(tm) = CURDATE() GROUP BY st_id;
-- 离线设备
SELECT name, code FROM eq_equip_base WHERE status = 0 AND deleted = 0;
-- 最近预警
SELECT ew_name, level_r, value, gather_time FROM ew_info_message WHERE deleted = 0 ORDER BY gather_time DESC LIMIT 20;
-- 按月平均水位
SELECT DATE_FORMAT(tm, '%Y-%m') AS month, AVG(rz) FROM st_rsvr_r WHERE deleted = 0 GROUP BY month;
```

---

## 八、注意事项

- 业务表查询需带 `AND deleted = 0` 软删除过滤（治理记录表无 deleted，见第三节）
- 多租户环境需带 `AND tenant_id = ?` 过滤
- 时间字段：监测表统一为 `tm`(datetime)；治理记录表为 `create_time`
- 大数据量查询限制 `max-num = 2000`；默认显示 `display-num = 20`
- 泵站电气参数为 varchar，数值比较前需 CAST
- 雨量时段长：`st_pptn_r.dr`(分钟) ≠ `st_pptn_region_r.intv`(小时)
- **卡滞检测特殊规则**：雨量传感器是步进式读数（0.5mm 步进），连续相同值属**正常**——
  雨量站建议 `tolerance=0.5` 或 `min_consecutive=24`；其他类型保持 `tolerance=0.001, min_consecutive=5`

---

## 九、数据量参考（2026-07-08 实测，单日）

| 表 | 记录数 | 测点数 | 备注 |
|----|--------|--------|------|
| st_rsvr_r | ~1700 | 2 | 高频采集 |
| st_pptn_r | ~2000 | 7 | 小时级 |
| st_pressure_r | ~100 | 63 | 低频 |
| st_percolation_r | ~30 | 2 | 低频 |
| dsm_dfr_srvrds_srhrds | ~100 | 3 | 低频 |

设备类型分布合计 **128** 台（type_flag 1/3/7/8/9/11/13/14/20）。
