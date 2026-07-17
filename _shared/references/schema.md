# powerelf 数据库表结构（唯一事实源）

> **单一事实源**：本文件合并自原 `data-governance/references/{schema,actual_schema}.md` 与
> `inspection/references/{database-schema,data-model}.md` 四份文档，消除跨 skill 的表结构
> 描述分歧。各 skill 的本地 schema 文档现为指向本文件的薄指针。
>
> **冲突仲裁规则**：当列名/关联键/类型出现分歧时，以**最新实测**为准；
> DDL 精度（如 `DECIMAL(8,3)` vs `(10,2)`）可能随库演化，以线上实际为准，字段语义与
> 关键字段名为本文件关注的重点。
>
> **⚠️ 2026-07-16 全表复核**：下列监测/设备/基础表的 DDL 已用 `SHOW CREATE TABLE`
> 逐表校准为线上真实结构（此前版本是"理想化 SL323 简版"，缺大量实际列，曾导致
> 7/16 河道查询的"写脚本→报错→改写"4 轮死循环）。历史 2026-07-08 记录保留于 git 历史。

---

## 🧱 关键结构性事实：多租户框架列模式（2026-07-16 实测，写 SQL 前必读）

线上库是**多租户业务框架**（类若依/RuoYi），**所有**监测表 / 设备表 / 基础表都遵循同一套列模式，
与"纯 SL323 简版"差异巨大。任一业务表都至少包含以下**框架列**（与业务检测字段并存）：

| 框架列 | 类型 | 说明 |
|--------|------|------|
| `id` | `BIGINT AUTO_INCREMENT` | **真正的物理主键**（`PRIMARY KEY (id)`）—— **不是 `(st_id, tm)`** |
| `deleted` | `BIT(1) DEFAULT b'0'` | 逻辑删除标志，查询**必须**带 `deleted = 0` |
| `tenant_id` | `BIGINT DEFAULT 1` | 租户编号，多租户环境带 `tenant_id = ?` |
| `eq_id` | `BIGINT` | **设备 id**（→ `eq_equip_base.id`）；**所有监测表都有**，不止渗压/GNSS |
| `eq_code` | `VARCHAR(20) NOT NULL` | 设备编码（→ `eq_equip_base.code`）；NOT NULL |
| `creator` / `create_time` / `updater` / `update_time` | 审计四件套 | 创建/更新人与时间 |
| `project_id` | `BIGINT` | 工程 id（部分表） |

**铁律（踩坑总结）**：
1. **主键是 `id`**，不是 `(st_id, tm)`。`GROUP BY`/`ORDER BY` 别依赖复合主键；按 `tm` 排序需显式写。
2. **必须 `WHERE deleted = 0`**，否则会捞出已删除行（`deleted` 是 `BIT`，写 `deleted = 0` 而非 `= '0'`）。
3. **设备关联首选 `eq_id` 直连** `eq_equip_base.id`（所有监测表都可用），其次 `eq_code`↔`code`、`stcd`↔`code`。
4. **精度以线上为准**：水位/流量多为 `DECIMAL(8,3)`/`(10,3)`，渗压渗流为 `DECIMAL(11,5)`，GNSS 为 `double(20,4)`。
>
> **巡检业务实体**（`business_check_*` 11 张表）属 inspection 专有领域，仍在
> `inspection/references/data-model.md` 维护，不在本文件范围。

---

## ⚠️ 关键修正：设备关联键（必须先读）

历史文档对监测表与设备表的关联键说法不一，**实测（2026-07-16 全表复核）**结论如下：

**所有监测表都同时具备 `eq_id`(BIGINT) 与 `eq_code`(varchar) 两列**，因此设备关联统一走 `eq_id`：

| 业务表 | 首选关联键 | 关联方式 | 检测字段 |
|--------|-----------|----------|----------|
| st_rsvr_r | **eq_id** (bigint) | `WHERE t.eq_id = eq_equip_base.id` | rz, inq, otq, w |
| st_river_r | **eq_id** (bigint) | `WHERE t.eq_id = eq_equip_base.id` | z, q |
| st_pptn_r | **eq_id** (bigint) | `WHERE t.eq_id = eq_equip_base.id` | p, dyp, cump |
| st_pressure_r | **eq_id** (bigint) | `WHERE t.eq_id = eq_equip_base.id` | ext_pressure, water_pressure, ext_temperature |
| st_percolation_r | **eq_id** (bigint) | `WHERE t.eq_id = eq_equip_base.id` | percolation |
| dsm_dfr_srvrds_srhrds (GNSS) | **eq_id** (int) | `WHERE t.eq_id = eq_equip_base.id` | wgs84_delta_h/x/y, wgs84_total_h/x/y, speed_gh/gx/gy |
| （任意表）备选 | eq_code / stcd (varchar) | `WHERE t.eq_code = eq_equip_base.code` 或 `t.stcd = eq_equip_base.code` | 同上 |

业务映射表 `eq_business_equip_relation`（70 条）给出 `business_table ↔ eq_id ↔ st_id ↔ st_type` 的完整对应，是"一张业务表有哪些设备/测站"的权威来源。

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

#### st_rsvr_r — 水库水情（实测 2026-07-16，194,111 行）
```sql
CREATE TABLE st_rsvr_r (
  id        BIGINT PRIMARY KEY AUTO_INCREMENT,
  st_id     BIGINT,                  -- 测站id
  project_id BIGINT,                 -- 工程id
  tm        DATETIME,                -- 采集时间
  rz        DECIMAL(8,3),            -- 水库上水位(m)        ★MAD检测字段
  blrz      DECIMAL(7,3),            -- 水库下水位(m)
  inq       DECIMAL(10,3),           -- 入库流量(m³/s)       ★检测字段
  otq       DECIMAL(10,3),           -- 出库流量(m³/s)       ★检测字段
  w         DECIMAL(10,3),           -- 蓄水量(m³)
  rwchrcd   CHAR(1),                 -- 河水特征码
  rwptn     CHAR(2),                 -- 水势状态码
  msqmt     CHAR(2),  msvmt CHAR(2), -- 测流/测速方法
  inqdr     DECIMAL(5,2),            -- 入流时段长
  eq_id     BIGINT,                  -- 设备id → eq_equip_base.id
  eq_code   VARCHAR(20) NOT NULL,    -- 设备编码
  stcd      VARCHAR(20),             -- 测站编码
  creator VARCHAR(64), create_time DATETIME,
  updater VARCHAR(64), update_time DATETIME,
  deleted    BIT(1) NOT NULL DEFAULT b'0',
  tenant_id  BIGINT NOT NULL DEFAULT 1,
  KEY (tenant_id, tm)
);
```
> tm 范围实测：2026-01-11 17:05 ~ 2026-07-01 08:00。

#### st_river_r — 河道水情（实测 2026-07-16，**0 行 — 本部署未启用**）
```sql
CREATE TABLE st_river_r (
  id        BIGINT PRIMARY KEY AUTO_INCREMENT,
  st_id     BIGINT,                  -- 测站id
  project_id BIGINT,                 -- 工程id
  tm        DATETIME,                -- 采集时间
  z         DECIMAL(8,3),            -- 水位(m)              ★MAD检测字段
  q         DECIMAL(10,3),           -- 流量(m³/s)           ★检测字段
  xsa       DECIMAL(10,3),           -- 过水面积(㎡)
  xsavv     DECIMAL(6,3),            -- 平均流速(m/s)
  xsmxv     DECIMAL(6,3),            -- 最大流速(m/s)
  flwchrcd  CHAR(1),                 -- 水流特征码
  wptn      CHAR(2),                 -- 水势状态码
  msqmt/msamt/msvmt CHAR(2),         -- 流量/面积/测速方法
  eq_id     BIGINT,                  -- 设备id
  eq_code   VARCHAR(20) NOT NULL,    -- 设备编码
  stcd      VARCHAR(20),             -- 测站编码
  creator VARCHAR(64), create_time DATETIME,
  updater VARCHAR(64), update_time DATETIME,
  deleted    BIT(1) NOT NULL DEFAULT b'0',
  tenant_id  BIGINT NOT NULL DEFAULT 1
);
```
> ⚠️ **本部署该表为空**（4 个站映射里 3 个设备已删、1 个错配渗压计 type_flag=20）。
> 水库系统查询"水位异常"应走 `st_rsvr_r`，不要因问"河道"就空转此表。

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
> ⚠️ **本部署不适用**：潮汐表针对河口/感潮河段，内陆水库无潮汐；线上 0 行，查询"水位"类问题应走 `st_rsvr_r`，不要落到此表。

#### st_pptn_r — 测站雨量（实测 2026-07-16，261,398 行）
```sql
CREATE TABLE st_pptn_r (
  id      BIGINT PRIMARY KEY AUTO_INCREMENT,
  st_id   BIGINT,
  tm      DATETIME,
  p       DECIMAL(5,1),    -- 时段降水量(mm)   ★检测字段
  dr      DECIMAL(6,1),    -- 时段长(分钟)
  dyp     DECIMAL(5,1),    -- 日降水量
  cump    DECIMAL(5,1),    -- 累计降水量
  pdr     DECIMAL(5,5),    -- 降水历时
  eq_id   BIGINT,
  eq_code VARCHAR(20) NOT NULL,
  stcd    VARCHAR(20),
  creator VARCHAR(64), create_time DATETIME,
  updater VARCHAR(64), update_time DATETIME,
  deleted   BIT(1) NOT NULL DEFAULT b'0',
  tenant_id BIGINT NOT NULL DEFAULT 1
);
```
> ⚠️ `dr` 单位是**分钟**，计算降雨强度需转换：`强度 = p / (dr/60)` mm/h
> tm 范围实测：2025-12-03 ~ 2026-06-30。

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

#### dsm_dfr_srvrds_srhrds — GNSS 位移（实测 2026-07-16，19,223 行）
```sql
CREATE TABLE dsm_dfr_srvrds_srhrds (
  id    BIGINT PRIMARY KEY AUTO_INCREMENT,
  tm    DATETIME,                      -- 统计时间
  st_id BIGINT,
  eq_id INT,                           -- 设备（int，注意与其他表 bigint 不同）
  point_id INT,                        -- 测点id（int，非 varchar）
  point_address VARCHAR(255),
  -- 原始观测
  data_b DOUBLE(9,6),   data_l DOUBLE(9,6),    -- 纬度/经度
  data_h DOUBLE(20,4),  data_x/y/z DOUBLE(20,4), -- 大地高/直角坐标XYZ
  data_p DOUBLE(20,4),                          -- 平面偏移
  gx_data DOUBLE(20,4), gy_data DOUBLE(20,4),    -- 高斯平面xy
  distance DOUBLE(20,4), hangle DOUBLE(20,4), vangle DOUBLE(20,4),
  data_count INT,
  -- ★检测字段（均为 double(20,4)，非 decimal）
  wgs84_delta_h DOUBLE(20,4),  wgs84_delta_x DOUBLE(20,4),  wgs84_delta_y DOUBLE(20,4),
  wgs84_total_h DOUBLE(20,4),  wgs84_total_x DOUBLE(20,4),  wgs84_total_y DOUBLE(20,4),
  speed_gh DOUBLE(20,4), speed_gx DOUBLE(20,4), speed_gy DOUBLE(20,4),
  test_delta_a DOUBLE(20,4), test_delta_b DOUBLE(20,4),
  speed_rx VARCHAR(32), speed_ry VARCHAR(32),
  creator BIGINT, create_time DATETIME,
  updater BIGINT, update_time DATETIME,
  deleted   BIT(1) NOT NULL DEFAULT b'0',
  tenant_id BIGINT NOT NULL DEFAULT 1
);
```
> ⚠️ 类型是 `double(20,4)`（不是 decimal），`point_id` 是 `INT`（不是 varchar）。
> tm 范围实测：2025-12-03 ~ 2026-06-02。

#### st_percolation_r — 渗流（实测 2026-07-16，766 行）
```sql
CREATE TABLE st_percolation_r (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  percolation DECIMAL(11,5) NOT NULL,  -- 渗流量(L/s)  ★检测字段
  tm          DATETIME,
  st_id       BIGINT,
  eq_id       BIGINT,
  eq_code     VARCHAR(20) NOT NULL,
  stcd        VARCHAR(20),
  creator BIGINT, create_time DATETIME,
  updater BIGINT, update_time DATETIME,
  deleted   BIT(1) NOT NULL DEFAULT b'0',
  tenant_id BIGINT NOT NULL DEFAULT 1
);
```
> tm 范围实测：2026-05-01 ~ 2026-05-29。

#### st_pressure_r — 渗压（实测 2026-07-16，1,835 行）
```sql
CREATE TABLE st_pressure_r (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  st_id           BIGINT,
  eq_id           BIGINT,
  tm              DATETIME,
  ext_pressure    DECIMAL(11,5),   -- 渗压值(kPa)        ★检测字段
  water_pressure  DECIMAL(11,5),   -- 水位对应压力(kPa)   ★检测字段
  ext_temperature DECIMAL(11,5),   -- 温度(℃)            ★检测字段
  ext_status      VARCHAR(255),    -- 设备状态
  section_id      BIGINT NOT NULL, -- 断面id
  point_id        BIGINT,          -- 测点id（bigint，非 varchar）
  address         VARCHAR(255),    -- 位置
  sort            INT NOT NULL DEFAULT 0,
  eq_code         VARCHAR(20) NOT NULL,
  stcd            VARCHAR(20),
  creator BIGINT, create_time DATETIME,
  updater BIGINT, update_time DATETIME,
  deleted   BIT(1) NOT NULL DEFAULT b'0',
  tenant_id BIGINT NOT NULL DEFAULT 1
);
```
> tm 范围实测：2026-05-01 ~ 2026-05-29。

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

### eq_equip_base — 设备台账（实测 2026-07-16，149 台）
```sql
CREATE TABLE eq_equip_base (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,  -- 业务表 eq_id 关联此列
  name          VARCHAR(128) NOT NULL,
  code          VARCHAR(64)  NOT NULL,   -- 设备编码（varchar(64)，非 20）
  type_flag     TINYINT NOT NULL,        -- 设备类型（tinyint，非 int）
  model         VARCHAR(32),
  category      CHAR(2) NOT NULL DEFAULT '0',
  status        TINYINT NOT NULL DEFAULT 1,  -- 0离线/1在线/2异常
  status_flag   TINYINT DEFAULT 1,
  st_base_id    BIGINT,                  -- 所属测站id → att_st_base.id
  project_id    BIGINT,
  dept_id       BIGINT,
  manufacturer  VARCHAR(128),
  position      VARCHAR(255),
  manage_unit   VARCHAR(128), manage_person_id BIGINT,
  start_use_date DATE, maintenance_cycle INT, service_life INT,
  src_type_flag VARCHAR(32), src_id BIGINT,
  remark VARCHAR(500),
  creator BIGINT, create_time DATETIME,
  updater BIGINT, update_time DATETIME,
  deleted   BIT(1) NOT NULL DEFAULT b'0',
  tenant_id BIGINT NOT NULL DEFAULT 1
);
```
**⚠️ 没有 `type` 列（用 `type_flag`），没有 `freq` 列（采集频率默认 10 分钟）。**
实测 type_flag 分布：1=2, 3=4, 7=2, 8=7, 9=44, 11=2, 13=3, 14=2, 20=62 台。

### eq_business_equip_relation — 设备-业务映射（实测 2026-07-16，70 条）
```sql
CREATE TABLE eq_business_equip_relation (
  id             INT PRIMARY KEY AUTO_INCREMENT,
  business_table VARCHAR(255),   -- 业务表名（如 st_rsvr_r）
  eq_id          BIGINT,         -- 设备id → eq_equip_base.id
  st_id          BIGINT,         -- 测站id
  st_type        VARCHAR(4),     -- 测站类型（ZZ/RR/PP/YZ/GN/DD/DP...）
  tenant_id      BIGINT
  -- ⚠️ 实测无 frequency / offline_threshold 列（旧文档误记）；频率/阈值见 dg_equip_offline 配置表
);
```
实测映射分布（business_table / st_type / 条数）：
`st_rsvr_r`: RR×8, ZZ×2 ｜ `st_river_r`: RR×1, ZZ×3 ｜ `st_pptn_r`: PP×8, RR×1 ｜
`st_pressure_r`: YZ×25 ｜ `st_percolation_r`: YZ×3 ｜ `dsm_dfr_srvrds_srhrds`: GN×8 ｜
`rei_gate_r`: DD×7 ｜ `rei_pump_r`: DP×4。

### att_st_base — 测站基础信息表（实测 2026-07-16，⚠️ 列名与旧文档完全不同）
```sql
CREATE TABLE att_st_base (
  id         BIGINT PRIMARY KEY AUTO_INCREMENT,  -- 测站id（业务表 st_id 关联此列）
  code       CHAR(18) NOT NULL,    -- 测站编码（旧文档误记为 st_code）
  name       VARCHAR(100) NOT NULL,-- 测站名称（旧文档误记为 st_name）
  type       CHAR(2) NOT NULL,     -- 测站类型[字典]（旧文档误记为 st_type）
  longitude  DECIMAL(9,6) NOT NULL,-- 经度（旧文档误记为 lgtd）
  latitude   DECIMAL(8,6) NOT NULL,-- 纬度（旧文档误记为 lttd）
  location   VARCHAR(255),         -- 地理位置（旧文档误记为 stlc）
  status     TINYINT NOT NULL DEFAULT 1,  -- 0离线/1在线/2异常
  project_id BIGINT NOT NULL,
  cat_area   DECIMAL(10,2),        -- 集水面积(km²)
  year_mon DATETIME, beg_repo_year_mon DATETIME,
  dtm_name VARCHAR(64), dtm_elev DECIMAL(7,3),
  site_orientation VARCHAR(255), bnsd VARCHAR(255),
  related_program BIGINT,
  manage_person_id BIGINT, dept_id BIGINT, note VARCHAR(255),
  creator BIGINT, create_time DATETIME,
  updater BIGINT, update_time DATETIME,
  deleted   BIT(1) NOT NULL DEFAULT b'0',
  tenant_id BIGINT NOT NULL DEFAULT 1
);
```
**⚠️ 旧文档的 `st_id/st_name/st_code/st_type/lgtd/lttd/stlc/dam_id` 列名全部不存在；
正确列名为 `id/name/code/type/longitude/latitude/location`，且无 `dam_id`。**

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
-- 水库：最近一周水位变化（记得 deleted = 0）
SELECT tm, rz, inq, otq FROM st_rsvr_r
WHERE st_id = ? AND deleted = 0 AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY) ORDER BY tm;
-- 水库：最新一条
SELECT * FROM st_rsvr_r WHERE st_id = ? AND deleted = 0 ORDER BY tm DESC LIMIT 1;
-- 河道（注意：本部署 st_river_r 为空）
SELECT tm, z, q FROM st_river_r WHERE eq_id = ? AND deleted = 0 AND tm > DATE_SUB(NOW(), INTERVAL 7 DAY);
-- 今日降雨量（按站汇总）
SELECT st_id, SUM(p) AS total FROM st_pptn_r WHERE deleted = 0 AND DATE(tm) = CURDATE() GROUP BY st_id;
-- 离线设备
SELECT name, code FROM eq_equip_base WHERE status = 0 AND deleted = 0;
-- 最近预警
SELECT ew_name, level_r, value, gather_time FROM ew_info_message WHERE deleted = 0 ORDER BY gather_time DESC LIMIT 20;
-- 按月平均水位
SELECT DATE_FORMAT(tm, '%Y-%m') AS month, AVG(rz) FROM st_rsvr_r WHERE deleted = 0 GROUP BY month;
```

### 数据治理"一次性概览"查询（取代逐表 N 步试探）

排查"某类数据有没有异常"时，**先用下面这条**把所有监测表的全貌一次取完，避免反复写脚本：

```sql
-- 各监测表：行数 + 时间范围（一条搞定，governance 入口首选）
SELECT 'st_rsvr_r'      AS t, COUNT(*) c, MIN(tm) mn, MAX(tm) mx FROM st_rsvr_r      WHERE deleted=0
UNION ALL SELECT 'st_river_r',     COUNT(*), MIN(tm), MAX(tm) FROM st_river_r     WHERE deleted=0
UNION ALL SELECT 'st_pptn_r',      COUNT(*), MIN(tm), MAX(tm) FROM st_pptn_r      WHERE deleted=0
UNION ALL SELECT 'st_pressure_r',  COUNT(*), MIN(tm), MAX(tm) FROM st_pressure_r  WHERE deleted=0
UNION ALL SELECT 'st_percolation_r',COUNT(*),MIN(tm), MAX(tm) FROM st_percolation_r WHERE deleted=0
UNION ALL SELECT 'dsm_gnss',       COUNT(*), MIN(tm), MAX(tm) FROM dsm_dfr_srvrds_srhrds WHERE deleted=0;
```
配合 `eq_business_equip_relation`（业务表↔设备↔测站↔st_type）+ `eq_equip_base`（status 在线状态）
即可一次判断"哪些表有数据 / 哪些设备离线 / 站点映射是否错配"。详见 governance skill 的
`lib/` 一次性脚本 `overview.py`。

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

## 九、数据量参考（2026-07-16 全表实测）

| 表 | 总记录数 | tm 范围 | 备注 |
|----|---------|---------|------|
| st_rsvr_r | 194,111 | 2026-01-11 ~ 2026-07-01 | 水库主力表，高频 |
| st_pptn_r | 261,398 | 2025-12-03 ~ 2026-06-30 | 雨量主力表 |
| st_pressure_r | 1,835 | 2026-05-01 ~ 2026-05-29 | 渗压 |
| st_percolation_r | 766 | 2026-05-01 ~ 2026-05-29 | 渗流 |
| dsm_dfr_srvrds_srhrds | 19,223 | 2025-12-03 ~ 2026-06-02 | GNSS |
| st_river_r | **0** | — | 河道表，本部署未启用（设备已删/错配） |

设备台账 `eq_equip_base` 共 **149** 台（type_flag 1/3/7/8/9/11/13/14/20，其中 type_flag=20 占 62 台）。
业务映射 `eq_business_equip_relation` 共 **70** 条。

> 注：旧版（2026-07-08）记的是"单日"量（st_rsvr_r ~1700/日等），此处改为全表累计，更接近治理实际口径。
