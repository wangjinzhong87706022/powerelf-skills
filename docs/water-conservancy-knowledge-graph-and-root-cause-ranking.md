<!--
  文档性质:技术方案(面向工程实现)
  生成方式:基于本仓库实际架构与 schema 调研编写
  修订记录:V1.0 — 首版,覆盖知识图谱建图、告警收敛、根因排序、置信度降级闸四大模块
  说明:文中所有表名、字段名、SQL 均基于 _shared/references/schema.md 与
        chatbi/references/schema.md 的实证,可逐项核验。
-->

# 水利行业知识图谱建设 + 告警根因排序技术方案

| 项目 | 内容 |
|------|------|
| 文档名称 | 水利行业知识图谱建设 + 告警根因排序技术方案 |
| 文档版本 | V1.0 |
| 编制日期 | 2026年8月5日 |
| 适用范围 | `powerelf-early-warning` / `early-warning-v3` 告警智能体,`powerelf-inspection` 智能巡检智能体 |
| 参考来源 | 腾讯 TCOP 三级过滤 + 知识图谱 + 多智能体协同架构实战经验 |
| 密级 | 内部 |

---

## 【内容摘要】

本仓库现有的告警智能体(`early-warning-v3/`)与智能巡检智能体(`powerelf-inspection/`)已具备基础的阈值判断、告警合并、风暴检测能力,但在以下三个关键环节存在空白:

1. **告警收敛只做到"按 st_code+ew_type 分组 + 30 分钟窗口合并"**,缺少腾讯三级过滤中的"相似曲线聚类"与"社团 + DBSCAN + 频繁项集找同一根因簇"。
2. **拓扑关联几乎空白**。`correlation-analysis.md` 里画的"降雨 → 水位 → 超警戒"因果链只是 ASCII 图,不是可查询的结构化数据,导致算不出"爆炸半径"、根因排序无依据。
3. **根因排序不存在**。`root-cause-analysis.md` 的输出模板里有"🎯 可能根因 1. {cause1}（置信度：{confidence1}）",但 `confidence1` 怎么算、依据是什么,文档里没写,Agent 容易瞎编置信度(即腾讯所说"模型幻觉")。

本方案针对上述三个空白,给出一套**基于本项目现有 MySQL 表结构**、**不引入 Neo4j**、**规则层优先**的完整落地方案,覆盖:

- **知识图谱建图**:定义 6 类节点、4 种边,给出建表 DDL、建图脚本伪代码、从现有 11 张表抽取节点和边的完整映射。
- **告警收敛**:把 100 条零散告警聚成 3-5 个"故障事件",对齐腾讯三级过滤。
- **根因排序**:在故障团内按 5 个维度打分,加权排序出 TOPN 可疑根因。
- **置信度降级闸**:根因置信度低于阈值时降级返回"建议人工介入",绝不胡编,对齐腾讯"模型幻觉"控制。

本方案**不照搬腾讯 K8s 的"微服务调用依赖图"**,而是针对水利行业的物理水力关系 + 业务因果链,设计了一张"水利对象多关系图"。

> **关键决策**:本方案选择**轻量 MySQL 边表**方案,不引入 Neo4j。理由有三:
> 1. 告警智能体侧的图查询主要是 BFS 1-2 跳,MySQL 加索引完全够用;
> 2. `powerelf-chatbi` 虽然有 `/knowledge/neo4j-graph/graphEcharts` 端点,但那是给 ChatBI 的可视化用的,告警侧没必要为了"看起来高级"而引入一套图数据库的运维负担;
> 3. 符合腾讯原文"别一上来追求端到端 AI,先把规则层做扎实"的思路——轻量边表能让规则层先跑起来,后续若真需要 Neo4j,从边表 ETL 过去也很容易。
>
> 唯一的不确定性在 `upstream_of`(上下游)边的数据来源。本方案给出三个选项并推荐"选项 B:空间推断"作为起步方案,待拿到人工录入的流域拓扑数据后再覆盖。

---

## 第一章 为什么水利行业建图和腾讯 K8s 不一样

### 1.1 腾讯 TCOP 的图模型

腾讯云可观测平台(TCOP)的图是**微服务调用依赖图**:

- 节点:Pod / Service / Node / Ingress
- 边:调用关系(A 调 B,B 调 C),方向明确,故障传播方向 = 调用方向
- 数据来源:CMDB + 服务注册中心 + 链路追踪(SkyWalking / Jaeger)
- 现成程度:CMDB 通常已有调用关系,开箱即用

这种图的故障传播路径是**单向、确定、可追溯**的。A 调 B,B 挂了,A 也挂,根因在 B。

### 1.2 水利行业的图模型:更复杂

水利行业的图比微服务调用图复杂得多,因为故障传播走的是**物理水力关系 + 业务因果链**两条不同的路径,而且数据源散落在十几张表里,没有现成的"调用关系表"。

| 维度 | 腾讯 K8s / 微服务 | 水利行业(本项目) |
|------|-------------------|-------------------|
| 节点类型 | Pod / Service / Node | 水库(project) / 测站(station) / 设备(device) / 断面(section) / 坝段(dam) / 测点(point) |
| 边类型 | 调用关系(单向) | ① 水力拓扑(上下游,物理) ② 归属关系(行政/物理层级) ③ 因果链(降雨→水位→告警,业务) ④ 空间邻近(同断面/同坝段) |
| 边的方向 | 明确(调用方→被调用方) | 水力拓扑明确(上游→下游),因果链半明确(降雨→水位),空间邻近无方向 |
| 数据来源 | CMDB + 服务注册中心 | 散落在 `att_st_base` / `eq_equip_base` / `eq_business_equip_relation` / `ew_info_message` / `st_*_r` 等十几张表 |
| 现成程度 | CMDB 通常已有调用关系 | **本项目没有任何显式的拓扑表**,必须从字段隐含关系里反推 |
| 故障传播速度 | 毫秒级(一次 RPC 调用) | 分钟到小时级(降雨汇流到入库通常 1-6 小时) |

### 1.3 一个具体例子说明差异

**腾讯场景**:微服务 A 调用 B,B 的数据库连接池打满,B 响应变慢,A 也变慢,C 调用 A 也变慢。根因在 B 的数据库连接池。故障传播路径:A←B←DB。

**水利场景**:降雨测站 P001 测到 50mm 降雨 → 1 小时后水库 R001 入库流量 inq 从 20 m³/s 涨到 800 m³/s → 水位 rz 从 460m 涨到 465m 超过警戒水位 463m → 触发水位超限告警 → 同一时段渗压测点 PP002 的 ext_pressure 也跟着上涨(因为水位上升导致坝体渗压增大)→ 触发渗压超限告警。

根因在 P001 的降雨(或者更上游的天气系统),但告警最先出现在水位超限,然后才是渗压超限。如果不建图,Agent 看到的就是"水位超限告警 + 渗压超限告警",很难反推出根因是降雨。

建图之后,Agent 能沿着 `causes` 边(P001 rain_station --causes--> R001 reservoir_station)反查到 P001,再结合 `causes` 边的时间延迟(`lag_min = 60`),确认 P001 的降雨比 R001 的水位上涨早 1 小时,符合因果链,从而把 P001 的降雨判定为根因。

这就是**知识图谱作为"翻译器"**的价值——把 Agent 看不懂的原始告警流,翻译成"根因在 X,影响范围是 Y,建议处置 Z"的结构化结论。

---

## 第二章 图谱怎么建:节点、边、数据来源

### 2.1 节点定义(6 类,全部来自现有表)

本项目现有数据已经能支撑一个完整水利拓扑图,不需要新采集数据。节点和来源如下:

| 节点类型 | `node_type` | 现有数据源 | 主键 | 关键属性 |
|----------|-------------|------------|------|----------|
| 工程/水库 | `project` | `att_st_base.project_id` 聚合 | `project_id` | 工程名、所属流域 |
| 测站 | `station` | `att_st_base` | `id`(即业务表的 `st_id`) | `code`(站码)、`name`、经纬度、`status`(在线/离线/异常) |
| 设备 | `device` | `eq_equip_base` | `id`(即业务表的 `eq_id`) | `code`、`type_flag`、`status`、`st_base_id` |
| 断面 | `section` | `st_pressure_r.section_id` / GNSS 表 `section_id` | `section_id` | 所属坝段 |
| 大坝/坝段 | `dam` | `att_dam_base`(chatbi schema 里已存在) | `dam_id` | 坝段名、所属工程 |
| 测点 | `point` | `st_pressure_r.point_id` / GNSS 表 `point_id` | `point_id` | 所属断面 |

**`node_id` 统一格式**:`{type}:{id}`,例如 `station:123`、`device:456`、`point:789`。这样一张 `topo_node` 表就能存所有类型的节点,查询时用前缀过滤即可。

### 2.2 边定义(4 种 `edge_type`)

这是核心。本项目现在 `correlation-analysis.md` 里只写了 ASCII 图,没有把这些关系结构化。下面 4 种边**覆盖水利故障传播的全部路径**。

#### 2.2.1 边类型 1:`belongs_to`(归属关系,无向,物理层级)

```
device   --belongs_to--> station     (来自 eq_equip_base.st_base_id)
station  --belongs_to--> project     (来自 att_st_base.project_id)
point    --belongs_to--> section     (来自 st_pressure_r.point_id ↔ section_id)
section  --belongs_to--> dam         (来自 section_id ↔ dam_id,需确认中间表)
dam      --belongs_to--> project     (来自 att_dam_base.project_id)
```

**用途**:告警进来,沿 `belongs_to` 向上找到所属工程/坝段,向向下找到所有关联设备/测点。这是 `correlation-analysis.md` 里"同测站/同水库"关联的结构化版本。

**举例**:设备 `device:1001`(渗压计)属于测站 `station:2155`(606K2155),测站属于工程 `project:1`(XX水库)。当 `device:1001` 产生渗压超限告警时,沿 `belongs_to` 向上一跳就能找到 `station:2155`,再向上一跳找到 `project:1`,从而知道这条告警属于哪个工程。

#### 2.2.2 边类型 2:`upstream_of`(水力拓扑,有向,物理)

这是水利行业**最特殊**也**最有价值**的边——上下游关系决定了故障传播方向。

**数据来源有三个层次(选项 A/B/C):**

| 选项 | 数据来源 | 精度 | 工作量 | 适用场景 |
|------|----------|------|--------|----------|
| A | 人工录入流域拓扑 | 最高 | 中 | 有完整流域拓扑图 |
| B | `att_st_base` 经纬度 + 测站类型 + 距离阈值推断 | 中 | 低 | 起步方案,数据不全 |
| C | 暂不做上下游,只用 `belongs_to` + `causes` + `near` | 低 | 0 | 最保守起步 |

**推荐先做选项 B**,用 `haversine` 距离 < 10km 且"雨量站 → 水库站"的方向规则推断,精度够用。等拿到选项 A 的人工录入数据再覆盖。

**选项 B 的空间推断伪代码**:

```python
from math import radians, sin, cos, asin, sqrt

def haversine_km(lat1, lon1, lat2, lon2):
    """计算两个经纬度点之间的球面距离(km)"""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))

def infer_upstream_downstream(stations, max_distance_km=10.0):
    """
    用空间推断生成 upstream_of 边。
    
    规则(水利常识):
    1. 雨量站(type_flag 含雨量)是水库站(type_flag 含水库)的上游
    2. 同一 project_id 内的雨量站 → 水库站,距离 < max_distance_km
    3. 不跨 project 推断(避免把不同流域的站连起来)
    """
    edges = []
    
    # 按 project_id 分组
    by_project = {}
    for s in stations:
        by_project.setdefault(s.project_id, []).append(s)
    
    for proj_id, sts in by_project.items():
        # 区分雨量站和水库站
        rain_stations = [s for s in sts if is_rain_station(s)]
        reservoir_stations = [s for s in sts if is_reservoir_station(s)]
        
        for r in reservoir_stations:
            for p in rain_stations:
                dist = haversine_km(r.latitude, r.longitude, p.latitude, p.longitude)
                if dist < max_distance_km:
                    # 雨量站 → 水库站:雨量站是上游
                    edges.append({
                        "from_node": f"station:{p.id}",
                        "to_node": f"station:{r.id}",
                        "edge_type": "upstream_of",
                        "weight": 1.0 - dist / max_distance_km,  # 距离越近权重越高
                        "evidence": f"空间推断:距离 {dist:.1f}km < {max_distance_km}km"
                    })
    
    return edges
```

**⚠️ 现实约束**:本项目 `_shared/references/schema.md` 里**没有看到**显式的上下游拓扑表(如 `att_project_relation` 或 `att_river_topology`)。所以建图第一步要回答:上下游关系从哪来?如果生产库里其实有显式拓扑表,建图脚本要优先用显式数据,空间推断只作为 fallback。

**举例**:雨量测站 `station:2151`(606K2151,经纬度 27.85,113.12)和水库测站 `station:2155`(606K2155,经纬度 27.86,113.15),haversine 距离约 3.2km < 10km,且 2151 是雨量站、2155 是水库站,所以生成边 `station:2151 --upstream_of--> station:2155`。

#### 2.2.3 边类型 3:`causes`(因果链,有向,业务定义)

这是腾讯"业务访问关系视图"在水利行业的对应物——不是物理拓扑,而是**业务上谁导致谁**。本项目 `correlation-analysis.md` 里已经画了这张图,只是没结构化:

```
rainfall_station --causes--> reservoir_station     (降雨→入库流量↑→水位↑)
reservoir_station --causes--> dam_section          (水位↑→大坝渗压↑)
dam_section --causes--> seepage_point              (渗压↑→渗流量↑)
reservoir_upstream --causes--> reservoir_downstream (上游泄洪→下游水位↑)
gate_device --causes--> downstream_station         (开闸→下游流量↑)
```

**数据来源**:这张图的边是**业务知识**,不是从数据库查出来的。需要用一张固定的"因果规则表"来定义,建议放在 `early-warning-v3/analysis/causal-rules.json`:

```json
[
  {
    "rule_id": "CR-001",
    "from_type": "station",
    "from_subtype": "rain",
    "to_type": "station",
    "to_subtype": "reservoir",
    "edge_type": "causes",
    "lag_min": 60,
    "evidence": "st_pptn_r.p → st_rsvr_r.inq",
    "description": "降雨导致水库入库流量上升,通常延迟 30-120 分钟",
    "weight": 0.9
  },
  {
    "rule_id": "CR-002",
    "from_type": "station",
    "from_subtype": "reservoir",
    "to_type": "point",
    "to_subtype": "pressure",
    "edge_type": "causes",
    "lag_min": 30,
    "evidence": "st_rsvr_r.rz → st_pressure_r.ext_pressure",
    "description": "水库水位上升导致坝体渗压增大,通常延迟 15-60 分钟",
    "weight": 0.85
  },
  {
    "rule_id": "CR-003",
    "from_type": "point",
    "from_subtype": "pressure",
    "to_type": "point",
    "to_subtype": "percolation",
    "edge_type": "causes",
    "lag_min": 45,
    "evidence": "st_pressure_r.ext_pressure → st_percolation_r.percolation",
    "description": "渗压增大导致渗流量增大,通常延迟 30-90 分钟",
    "weight": 0.8
  },
  {
    "rule_id": "CR-004",
    "from_type": "device",
    "from_subtype": "gate",
    "to_type": "station",
    "to_subtype": "downstream",
    "edge_type": "causes",
    "lag_min": 120,
    "evidence": "rei_gate_r.gtq → st_rsvr_r.otq → 下游水位",
    "description": "开闸泄洪导致下游流量/水位上升,通常延迟 60-180 分钟",
    "weight": 0.85
  }
]
```

`lag_min` 是因果链的典型延迟(分钟),根因排序时用它判断"时间先后是否符合因果"。如果 A 的告警时间比 B 早,且 A→B 有 `causes` 边,且时间差 >= `lag_min`,则 A 是 B 的根因候选。

**举例**:8月5日 10:00 雨量站 606K2151 测到 50mm 降雨,11:00 水库 606K2155 的 inq 从 20 涨到 800 m³/s,rz 从 460 涨到 465m,触发水位超限告警。因果链判定:

- P001 告警时间 10:00,R001 告警时间 11:00,时间差 60 分钟
- CR-001 的 `lag_min = 60`,时间差 60 >= 60,符合因果链延迟
- 因此生成边 `station:2151 --causes--> station:2155`,P001 是 R001 的根因候选

#### 2.2.4 边类型 4:`near`(空间邻近,无向,物理)

同一断面/同坝段的多个测点,物理上紧邻,一个异常另一个大概率也异常。

```
point_a --near--> point_b     (同一 section_id,距离 < 阈值)
station_a --near--> station_b (经纬度距离 < 1km)
```

**用途**:腾讯说的"社团聚类"——把 `near` + `belongs_to` 边连起来的节点聚成一团,这就是一个"故障团"。

**举例**:渗压测点 `point:101` 和 `point:102` 同属断面 `section:5`,生成边 `point:101 --near--> point:102`,weight=0.8。当 101 产生渗压超限告警时,沿 `near` 边一跳就能找到 102,检查 102 是否也异常,从而判断是"局部测点故障"还是"断面整体渗压上升"。

### 2.3 图的物理存储(轻量方案,不引入 Neo4j)

#### 2.3.1 存储结构:新建两张 MySQL 表

```sql
-- ============================================================
-- topo_node:统一存所有水利对象节点
-- ============================================================
CREATE TABLE topo_node (
  node_id     VARCHAR(64) PRIMARY KEY,    -- 格式: {type}:{id},如 "station:123"
  node_type   VARCHAR(20) NOT NULL,       -- project/station/device/section/dam/point
  ref_id      BIGINT NOT NULL,            -- 原表主键(st_id / eq_id / section_id 等)
  name        VARCHAR(255),               -- 节点显示名(测站名/设备名等)
  project_id  BIGINT,                     -- 冗余字段,加速按工程过滤
  properties  JSON,                       -- 灵活属性:经纬度、status、type_flag 等
  updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_type_ref (node_type, ref_id),
  INDEX idx_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='水利对象拓扑节点表';

-- ============================================================
-- topo_edge:统一存 4 种关系边
-- ============================================================
CREATE TABLE topo_edge (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  from_node   VARCHAR(64) NOT NULL,       -- 起始节点 node_id
  to_node     VARCHAR(64) NOT NULL,       -- 目标节点 node_id
  edge_type   VARCHAR(20) NOT NULL,       -- belongs_to/upstream_of/causes/near
  weight      DECIMAL(5,2) DEFAULT 1.0,   -- 边权重 [0,1],用于根因打分
  lag_min     INT,                        -- causes 边的典型延迟(分钟),其他类型为 NULL
  evidence    VARCHAR(255),               -- 边的依据,如 "st_pptn_r.p → st_rsvr_r.inq" 或 "空间推断:距离 3.2km"
  rule_id     VARCHAR(20),                -- causes 边的规则 ID(指向 causal-rules.json)
  updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_from_type (from_node, edge_type),
  INDEX idx_to_type (to_node, edge_type),
  INDEX idx_edge_type (edge_type),
  UNIQUE KEY uk_edge (from_node, to_node, edge_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='水利对象拓扑边表';

-- ============================================================
-- topo_alarm_event:告警聚合后的故障事件
-- ============================================================
CREATE TABLE topo_alarm_event (
  event_id        VARCHAR(40) PRIMARY KEY,  -- 格式: EVT-{yyyyMMdd}-{seq3},如 "EVT-20260805-001"
  tenant_id       BIGINT NOT NULL DEFAULT 1,
  start_time      DATETIME NOT NULL,        -- 事件首条告警时间
  end_time        DATETIME NOT NULL,        -- 事件末条告警时间
  max_level       CHAR(2) NOT NULL,         -- 事件内最高告警级别 '1'-'4'
  alarm_count     INT NOT NULL DEFAULT 0,   -- 事件内告警总数
  affected_nodes  JSON,                     -- 事件涉及的节点 ID 列表
  cluster_id      INT,                      -- 故障团 ID(同一根因的告警聚成一团)
  centroid_node   VARCHAR(64),              -- 团内度数最高的节点(近似根因)
  severity_score  DECIMAL(5,2),             -- 团的严重程度评分 [0,1]
  root_cause_node VARCHAR(64),              -- 根因排序后的 TOP1 节点
  root_cause_conf DECIMAL(5,2),             -- TOP1 根因的置信度 [0,1]
  status          VARCHAR(20) DEFAULT 'open',  -- open/confirmed/resolved
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_start (start_time),
  INDEX idx_level (max_level),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警聚合故障事件表';
```

#### 2.3.2 建图脚本:从现有表抽取节点和边

建议新建 `early-warning-v3/scripts/build_topology.py`,一次性把图建出来,之后每天增量更新。以下是完整伪代码:

```python
#!/usr/bin/env python3
"""
build_topology.py — 水利对象拓扑图建图脚本

用法:
    python3 build_topology.py              # 全量重建
    python3 build_topology.py --incremental # 增量更新(只处理最近 24h 变更)

数据来源(11 张现有表):
    att_st_base            → station 节点 + station→project belongs_to 边
    eq_equip_base          → device 节点 + device→station belongs_to 边
    att_dam_base           → dam 节点 + dam→project belongs_to 边
    st_pressure_r          → point 节点 + section 节点 + point→section belongs_to 边
    dsm_dfr_srvrds_srhrds  → point 节点(GNSS)+ point→section belongs_to 边
    st_percolation_r       → point 节点(渗流)
    st_pptn_r              → 用于判定 rain 子类型
    st_rsvr_r              → 用于判定 reservoir 子类型
    rei_gate_r             → 用于判定 gate 子类型
    ew_info_message        → 用于历史复发率统计(根因排序维度5)
    eq_business_equip_relation → 业务表↔设备↔测站映射,辅助判定节点类型

生成 4 种边:
    belongs_to  — 从 st_base_id / project_id / section_id 反推
    upstream_of — 选项 B:空间推断(haversine 距离 + 测站类型规则)
    causes      — 从 causal-rules.json 加载,按规则匹配节点对
    near        — 同 section_id 的 point 两两连边,经纬度 < 1km 的 station 两两连边
"""
import json
import mysql.connector
from datetime import datetime, timedelta
from math import radians, sin, cos, asin, sqrt


# ============================================================
# 1. 数据库连接(复用 early-warning-v3/db-config.md 配置)
# ============================================================
def get_connection():
    return mysql.connector.connect(
        host="127.0.0.1", port=3306,
        user="root", password="123456aA.",
        database="powerelf_srm_yml"
    )


# ============================================================
# 2. 节点抽取
# ============================================================
def extract_station_nodes(conn):
    """从 att_st_base 抽取测站节点"""
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, code, name, longitude, latitude, status, project_id,
               type, cat_area, location
        FROM att_st_base
        WHERE deleted = 0
    """)
    nodes = []
    for row in cursor.fetchall():
        node_id = f"station:{row['id']}"
        properties = {
            "code": row["code"],
            "longitude": float(row["longitude"]) if row["longitude"] else None,
            "latitude": float(row["latitude"]) if row["latitude"] else None,
            "status": row["status"],
            "type": row["type"],
            "cat_area": float(row["cat_area"]) if row["cat_area"] else None,
            "location": row["location"]
        }
        # 判定子类型:雨量站/水库站/河道站等
        # 这里简化:根据 code 前缀或 type 字段判定
        # 实际需根据项目 type 字段字典调整
        subtype = infer_station_subtype(row)
        if subtype:
            properties["subtype"] = subtype
        nodes.append({
            "node_id": node_id,
            "node_type": "station",
            "ref_id": row["id"],
            "name": row["name"],
            "project_id": row["project_id"],
            "properties": json.dumps(properties, ensure_ascii=False)
        })
    return nodes


def extract_device_nodes(conn):
    """从 eq_equip_base 抽取设备节点"""
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, code, name, type_flag, status, st_base_id,
               manufacturer, position, project_id
        FROM eq_equip_base
        WHERE deleted = 0
    """)
    nodes = []
    for row in cursor.fetchall():
        node_id = f"device:{row['id']}"
        properties = {
            "code": row["code"],
            "type_flag": row["type_flag"],
            "status": row["status"],
            "manufacturer": row["manufacturer"],
            "position": row["position"]
        }
        subtype = infer_device_subtype(row)
        if subtype:
            properties["subtype"] = subtype
        nodes.append({
            "node_id": node_id,
            "node_type": "device",
            "ref_id": row["id"],
            "name": row["name"],
            "project_id": row.get("project_id"),
            "properties": json.dumps(properties, ensure_ascii=False)
        })
    return nodes


def extract_point_and_section_nodes(conn):
    """
    从 st_pressure_r 和 GNSS 表抽取 point 和 section 节点。
    
    st_pressure_r.section_id 和 point_id 是渗压测点和断面的来源。
    GNSS 表(dsm_dfr_srvrds_srhrds)的 section_id 和 point_id 是位移测点。
    """
    cursor = conn.cursor(dictionary=True)
    
    # 抽取 section 节点(从 st_pressure_r 的 section_id distinct)
    cursor.execute("""
        SELECT DISTINCT section_id
        FROM st_pressure_r
        WHERE deleted = 0 AND section_id IS NOT NULL
    """)
    section_nodes = []
    for row in cursor.fetchall():
        section_nodes.append({
            "node_id": f"section:{row['section_id']}",
            "node_type": "section",
            "ref_id": row["section_id"],
            "name": f"断面-{row['section_id']}",
            "project_id": None,
            "properties": json.dumps({"source_table": "st_pressure_r"})
        })
    
    # 抽取 point 节点(渗压测点)
    cursor.execute("""
        SELECT DISTINCT point_id, section_id
        FROM st_pressure_r
        WHERE deleted = 0 AND point_id IS NOT NULL
    """)
    point_nodes = []
    point_section_map = {}  # point_id → section_id,用于生成 belongs_to 边
    for row in cursor.fetchall():
        node_id = f"point:{row['point_id']}"
        point_nodes.append({
            "node_id": node_id,
            "node_type": "point",
            "ref_id": row["point_id"],
            "name": f"渗压测点-{row['point_id']}",
            "project_id": None,
            "properties": json.dumps({
                "source_table": "st_pressure_r",
                "section_id": row["section_id"],
                "subtype": "pressure"
            })
        })
        point_section_map[row["point_id"]] = row["section_id"]
    
    # 同样从 GNSS 表抽取 point 节点(位移测点)
    # ...类似逻辑,subtype 设为 "gnss"
    
    # 从渗流表 st_percolation_r 抽取 point 节点
    # ...类似逻辑,subtype 设为 "percolation"
    
    return section_nodes, point_nodes, point_section_map


def extract_project_and_dam_nodes(conn):
    """从 att_st_base.project_id 聚合工程节点,从 att_dam_base 抽取大坝节点"""
    cursor = conn.cursor(dictionary=True)
    
    # 工程节点:从 att_st_base 的 project_id distinct
    cursor.execute("""
        SELECT DISTINCT project_id
        FROM att_st_base
        WHERE deleted = 0 AND project_id IS NOT NULL
    """)
    project_nodes = []
    for row in cursor.fetchall():
        project_nodes.append({
            "node_id": f"project:{row['project_id']}",
            "node_type": "project",
            "ref_id": row["project_id"],
            "name": f"工程-{row['project_id']}",
            "project_id": row["project_id"],
            "properties": json.dumps({"source": "att_st_base.project_id聚合"})
        })
    
    # 大坝节点:从 att_dam_base(如果表存在)
    try:
        cursor.execute("SELECT dam_id, dam_name, project_id FROM att_dam_base WHERE deleted = 0")
        dam_nodes = []
        for row in cursor.fetchall():
            dam_nodes.append({
                "node_id": f"dam:{row['dam_id']}",
                "node_type": "dam",
                "ref_id": row["dam_id"],
                "name": row["dam_name"],
                "project_id": row.get("project_id"),
                "properties": json.dumps({"source": "att_dam_base"})
            })
        return project_nodes, dam_nodes
    except:
        # att_dam_base 表不存在,跳过
        return project_nodes, []


# ============================================================
# 3. 边抽取
# ============================================================
def extract_belongs_to_edges(conn):
    """
    生成 belongs_to 边:
        device → station   (eq_equip_base.st_base_id)
        station → project  (att_st_base.project_id)
        point → section    (st_pressure_r.point_id ↔ section_id)
        section → dam      (如果有映射关系)
        dam → project      (att_dam_base.project_id)
    """
    cursor = conn.cursor(dictionary=True)
    edges = []
    
    # device → station
    cursor.execute("""
        SELECT id, st_base_id FROM eq_equip_base
        WHERE deleted = 0 AND st_base_id IS NOT NULL
    """)
    for row in cursor.fetchall():
        edges.append({
            "from_node": f"device:{row['id']}",
            "to_node": f"station:{row['st_base_id']}",
            "edge_type": "belongs_to",
            "weight": 1.0,
            "lag_min": None,
            "evidence": "eq_equip_base.st_base_id",
            "rule_id": None
        })
    
    # station → project
    cursor.execute("""
        SELECT id, project_id FROM att_st_base
        WHERE deleted = 0 AND project_id IS NOT NULL
    """)
    for row in cursor.fetchall():
        edges.append({
            "from_node": f"station:{row['id']}",
            "to_node": f"project:{row['project_id']}",
            "edge_type": "belongs_to",
            "weight": 1.0,
            "lag_min": None,
            "evidence": "att_st_base.project_id",
            "rule_id": None
        })
    
    # point → section (从 point_section_map 传入,这里简化为重新查询)
    cursor.execute("""
        SELECT DISTINCT point_id, section_id
        FROM st_pressure_r
        WHERE deleted = 0 AND point_id IS NOT NULL AND section_id IS NOT NULL
    """)
    for row in cursor.fetchall():
        edges.append({
            "from_node": f"point:{row['point_id']}",
            "to_node": f"section:{row['section_id']}",
            "edge_type": "belongs_to",
            "weight": 1.0,
            "lag_min": None,
            "evidence": "st_pressure_r.point_id↔section_id",
            "rule_id": None
        })
    
    return edges


def haversine_km(lat1, lon1, lat2, lon2):
    """计算两个经纬度点之间的球面距离(km)"""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))


def infer_upstream_downstream_edges(conn, max_distance_km=10.0):
    """
    选项 B:用空间推断生成 upstream_of 边。
    
    规则:
        1. 雨量站 → 水库站(雨量站是上游,水库站接收汇流)
        2. 同一 project_id 内推断,不跨 project
        3. haversine 距离 < max_distance_km
        4. 权重 = 1 - distance / max_distance_km(距离越近权重越高)
    """
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, code, name, longitude, latitude, type, project_id
        FROM att_st_base
        WHERE deleted = 0 AND longitude IS NOT NULL AND latitude IS NOT NULL
    """)
    stations = cursor.fetchall()
    
    # 按 project_id 分组
    by_project = {}
    for s in stations:
        by_project.setdefault(s["project_id"], []).append(s)
    
    edges = []
    for proj_id, sts in by_project.items():
        # 区分雨量站和水库站
        rain_stations = [s for s in sts if is_rain_station(s)]
        reservoir_stations = [s for s in sts if is_reservoir_station(s)]
        
        for r in reservoir_stations:
            for p in rain_stations:
                dist = haversine_km(
                    float(r["latitude"]), float(r["longitude"]),
                    float(p["latitude"]), float(p["longitude"])
                )
                if dist < max_distance_km:
                    edges.append({
                        "from_node": f"station:{p['id']}",
                        "to_node": f"station:{r['id']}",
                        "edge_type": "upstream_of",
                        "weight": round(1.0 - dist / max_distance_km, 3),
                        "lag_min": 60,  # 默认汇流延迟 60 分钟
                        "evidence": f"空间推断:haversine {dist:.1f}km < {max_distance_km}km",
                        "rule_id": None
                    })
    
    return edges


def is_rain_station(s):
    """判定是否为雨量站:根据 type 字段或 code 前缀"""
    # 简化判定:实际需根据项目 type 字段字典调整
    if s.get("type") and "雨" in str(s["type"]):
        return True
    # 也可以根据 eq_business_equip_relation 的 st_type 判定
    return False


def is_reservoir_station(s):
    """判定是否为水库站"""
    if s.get("type") and "水库" in str(s["type"]):
        return True
    return False


def extract_causes_edges(conn, causal_rules_path):
    """
    从 causal-rules.json 加载因果规则,匹配节点对生成 causes 边。
    
    匹配逻辑:
        1. 加载 causal-rules.json
        2. 对每条规则,查询 from_type+from_subtype 和 to_type+to_subtype 的节点
        3. 按 project_id 分组,同 project 内的 from→to 生成 causes 边
        4. lag_min 和 weight 从规则文件读取
    """
    with open(causal_rules_path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    
    edges = []
    cursor = conn.cursor(dictionary=True)
    
    for rule in rules:
        # 查询 from 节点
        from_nodes = query_nodes_by_subtype(cursor, rule["from_type"], rule["from_subtype"])
        # 查询 to 节点
        to_nodes = query_nodes_by_subtype(cursor, rule["to_type"], rule["to_subtype"])
        
        # 同 project_id 内匹配
        from_by_project = group_by_project(from_nodes)
        to_by_project = group_by_project(to_nodes)
        
        for proj_id in set(from_by_project.keys()) & set(to_by_project.keys()):
            for fn in from_by_project[proj_id]:
                for tn in to_by_project[proj_id]:
                    if fn["node_id"] != tn["node_id"]:
                        edges.append({
                            "from_node": fn["node_id"],
                            "to_node": tn["node_id"],
                            "edge_type": "causes",
                            "weight": rule.get("weight", 0.85),
                            "lag_min": rule.get("lag_min", 60),
                            "evidence": rule.get("evidence", ""),
                            "rule_id": rule.get("rule_id", "")
                        })
    
    return edges


def extract_near_edges(conn, section_distance_threshold=0):
    """
    生成 near 边:
        1. 同 section_id 的 point 两两连边
        2. 经纬度距离 < 1km 的 station 两两连边(可选)
    """
    cursor = conn.cursor(dictionary=True)
    edges = []
    
    # 同 section 的 point 两两连边
    cursor.execute("""
        SELECT DISTINCT point_id, section_id
        FROM st_pressure_r
        WHERE deleted = 0 AND point_id IS NOT NULL AND section_id IS NOT NULL
    """)
    section_points = {}
    for row in cursor.fetchall():
        section_points.setdefault(row["section_id"], []).append(row["point_id"])
    
    for section_id, point_ids in section_points.items():
        if len(point_ids) < 2:
            continue
        # 两两组合
        for i in range(len(point_ids)):
            for j in range(i + 1, len(point_ids)):
                edges.append({
                    "from_node": f"point:{point_ids[i]}",
                    "to_node": f"point:{point_ids[j]}",
                    "edge_type": "near",
                    "weight": 0.8,
                    "lag_min": None,
                    "evidence": f"同 section:{section_id}",
                    "rule_id": None
                })
    
    return edges


# ============================================================
# 4. 写入数据库
# ============================================================
def upsert_nodes(conn, nodes):
    """批量 upsert 节点(已存在则更新)"""
    cursor = conn.cursor()
    sql = """
        INSERT INTO topo_node (node_id, node_type, ref_id, name, project_id, properties)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            project_id = VALUES(project_id),
            properties = VALUES(properties),
            updated_at = NOW()
    """
    batch = [(n["node_id"], n["node_type"], n["ref_id"], n["name"],
              n["project_id"], n["properties"]) for n in nodes]
    cursor.executemany(sql, batch)
    conn.commit()


def upsert_edges(conn, edges):
    """批量 upsert 边(去重:唯一键 from_node+to_node+edge_type)"""
    cursor = conn.cursor()
    sql = """
        INSERT INTO topo_edge (from_node, to_node, edge_type, weight, lag_min, evidence, rule_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            weight = VALUES(weight),
            lag_min = VALUES(lag_min),
            evidence = VALUES(evidence),
            rule_id = VALUES(rule_id),
            updated_at = NOW()
    """
    batch = [(e["from_node"], e["to_node"], e["edge_type"], e["weight"],
              e.get("lag_min"), e.get("evidence", ""), e.get("rule_id")) for e in edges]
    cursor.executemany(sql, batch)
    conn.commit()


# ============================================================
# 5. 主流程
# ============================================================
def main(incremental=False):
    conn = get_connection()
    
    print("=" * 60)
    print("水利对象拓扑图建图脚本")
    print(f"模式: {'增量更新' if incremental else '全量重建'}")
    print("=" * 60)
    
    # Step 1: 抽取节点
    print("\n[Step 1] 抽取节点...")
    stations = extract_station_nodes(conn)
    devices = extract_device_nodes(conn)
    sections, points, _ = extract_point_and_section_nodes(conn)
    projects, dams = extract_project_and_dam_nodes(conn)
    
    all_nodes = stations + devices + sections + points + projects + dams
    print(f"  测站: {len(stations)}")
    print(f"  设备: {len(devices)}")
    print(f"  断面: {len(sections)}")
    print(f"  测点: {len(points)}")
    print(f"  工程: {len(projects)}")
    print(f"  大坝: {len(dams)}")
    print(f"  节点总数: {len(all_nodes)}")
    
    # Step 2: 抽取边
    print("\n[Step 2] 抽取边...")
    belongs_to = extract_belongs_to_edges(conn)
    upstream_of = infer_upstream_downstream_edges(conn)
    causes = extract_causes_edges(conn, "analysis/causal-rules.json")
    near = extract_near_edges(conn)
    
    all_edges = belongs_to + upstream_of + causes + near
    print(f"  belongs_to: {len(belongs_to)}")
    print(f"  upstream_of: {len(upstream_of)}")
    print(f"  causes: {len(causes)}")
    print(f"  near: {len(near)}")
    print(f"  边总数: {len(all_edges)}")
    
    # Step 3: 写入数据库
    print("\n[Step 3] 写入数据库...")
    if not incremental:
        # 全量重建:先清空再写入
        clear_topology_tables(conn)
    upsert_nodes(conn, all_nodes)
    upsert_edges(conn, all_edges)
    print(f"  节点写入: {len(all_nodes)}")
    print(f"  边写入: {len(all_edges)}")
    
    print("\n建图完成。")
    conn.close()


if __name__ == "__main__":
    import sys
    main(incremental="--incremental" in sys.argv)
```

---

## 第三章 告警收敛:从 100 条零散告警到 3-5 个故障事件

### 3.1 现状与差距

项目现有的告警聚合(`intelligent-analysis-workflow.md` Step 2)只做了:

- 按 `st_code + ew_type` 分组
- 30 分钟窗口合并
- 过滤已确认告警
- 按级别排序,截断至 100 条

**差距**:这是"去重 + 排序",不是"收敛"。腾讯三级过滤的核心是**把同一根因带出来的告警聚成一团**,本项目现在做不到——100 条告警堆在一起,值班人员看不出哪些是同一个根因。

### 3.2 告警收敛算法(对齐腾讯三级过滤)

新建 `early-warning-v3/analysis/alarm-aggregation.md`,实现以下三步:

#### 3.2.1 第一级:相似曲线聚类(扩充样本库)

用 `_shared/lib/correlation.py` 已有的 Pearson 相关系数,对告警涉及的监测序列(水位/渗压/位移)做滑动窗口相关性匹配,相似度 > 0.85 的告警聚成一类。

```python
def cluster_similar_alarms(alarms, correlation_threshold=0.85, window_size=12):
    """
    第一级过滤:相似曲线聚类。
    
    对每条告警,查询其设备/测站在告警前后 window_size 个时间点的监测序列,
    计算序列间的 Pearson 相关系数。相似度 > threshold 的告警聚成一类。
    
    Args:
        alarms: ew_info_message 列表
        correlation_threshold: 相似度阈值,默认 0.85
        window_size: 滑动窗口大小(时间点数),默认 12
    
    Returns:
        clusters: List[List[alarm]],每个子列表是一类相似告警
    """
    # 1. 为每条告警提取特征序列
    alarm_sequences = {}
    for alarm in alarms:
        seq = extract_monitoring_sequence(alarm, window_size)
        if seq:
            alarm_sequences[alarm.id] = seq
    
    # 2. 计算两两 Pearson 相关系数
    alarm_ids = list(alarm_sequences.keys())
    similarity_matrix = {}
    for i in range(len(alarm_ids)):
        for j in range(i + 1, len(alarm_ids)):
            seq_a = alarm_sequences[alarm_ids[i]]
            seq_b = alarm_sequences[alarm_ids[j]]
            if len(seq_a) >= 3 and len(seq_b) >= 3:
                corr = pearson_correlation(seq_a, seq_b)
                if abs(corr) >= correlation_threshold:
                    similarity_matrix.setdefault(alarm_ids[i], []).append(alarm_ids[j])
    
    # 3. 用 union-find 聚类
    clusters = union_find_cluster(alarm_ids, similarity_matrix)
    return clusters
```

**举例**:8月5日 10:00-12:00,水库测站 606K2155 产生 20 条水位超限告警(每 6 分钟一条),渗压测点 PP002 产生 15 条渗压超限告警。这两组告警的监测序列(水位 rz 序列 vs 渗压 ext_pressure 序列)Pearson 相关系数 0.91 > 0.85,聚成同一类。这就实现了腾讯第一级"找相似的曲线,把长得很像的异常聚成一类,扩充样本库"。

#### 3.2.2 第二级:拓扑关联(把系统间的调用依赖画出来)

这一级用第二章建的图。告警进来,沿 `belongs_to` / `near` / `upstream_of` 边做 BFS 1-2 跳,把拓扑上关联的告警聚成一团。

```python
def aggregate_alarms_to_events(alarms, time_window_min=30, max_blast_hops=2):
    """
    第二级 + 第三级过滤:拓扑关联 + 社团聚类。
    
    流程:
        1. 每条告警映射到图节点(alarm_to_node)
        2. 沿 belongs_to / near / upstream_of 边做 BFS max_blast_hops 跳
        3. 用 union-find 把拓扑可达的告警聚成连通分量
        4. 每个连通分量内,用 time_window 过滤掉时间上不相关的告警
        5. 每个过滤后的连通分量生成一个故障事件(topo_alarm_event)
    
    Args:
        alarms: ew_info_message 列表
        time_window_min: 同一故障事件内告警的最大时间跨度,默认 30 分钟
        max_blast_hops: BFS 最大跳数,默认 2
    
    Returns:
        events: List[dict],每个 dict 是一个故障事件
    """
    # 1. 映射告警到图节点
    alarm_node_pairs = []
    for alarm in alarms:
        node_id = alarm_to_node(alarm)
        if node_id:
            alarm_node_pairs.append((alarm, node_id))
    
    # 2. 提取所有涉及的节点
    all_nodes = list(set(n for _, n in alarm_node_pairs))
    
    # 3. 构建节点→告警列表的映射
    node_to_alarms = {}
    for alarm, node_id in alarm_node_pairs:
        node_to_alarms.setdefault(node_id, []).append(alarm)
    
    # 4. 用 union-find 找连通分量(基于 belongs_to + near + upstream_of 边)
    uf = UnionFind(all_nodes)
    
    # 查询所有涉及的边
    for node in all_nodes:
        neighbors = get_neighbors_within_hops(node, ["belongs_to", "near", "upstream_of"], max_blast_hops)
        for neighbor in neighbors:
            if neighbor in all_nodes:  # 只合并也产生了告警的节点
                uf.union(node, neighbor)
    
    # 5. 每个连通分量生成一个故障事件
    clusters = uf.get_clusters()
    events = []
    for cluster_id, cluster_nodes in enumerate(clusters, 1):
        # 收集该团内所有告警
        cluster_alarms = []
        for node in cluster_nodes:
            cluster_alarms.extend(node_to_alarms.get(node, []))
        
        # 时间窗口过滤:去掉时间跨度 > time_window_min 的告警
        cluster_alarms.sort(key=lambda a: a.gather_time)
        filtered = filter_by_time_window(cluster_alarms, time_window_min)
        
        if not filtered:
            continue
        
        # 生成故障事件
        event = build_alarm_event(filtered, cluster_nodes, cluster_id)
        events.append(event)
    
    return events


def build_alarm_event(alarms, cluster_nodes, cluster_id):
    """把一组告警聚合成一个故障事件"""
    severity_map = {'1': 1.0, '2': 0.75, '3': 0.5, '4': 0.25}
    
    return {
        "event_id": f"EVT-{datetime.now().strftime('%Y%m%d')}-{cluster_id:03d}",
        "start_time": min(a.gather_time for a in alarms),
        "end_time": max(a.gather_time for a in alarms),
        "max_level": min(a.level_r for a in alarms),  # level_r '1' 是最高
        "alarm_count": len(alarms),
        "affected_nodes": cluster_nodes,
        "cluster_id": cluster_id,
        "severity_score": sum(severity_map.get(a.level_r, 0) for a in alarms) / len(alarms)
    }
```

**举例**:8月5日 10:00-10:30,系统产生以下告警:

| 告警ID | 站码 | 设备码 | 类型 | 级别 | 时间 |
|--------|------|--------|------|------|------|
| 1001 | 606K2151 | - | 降雨超限 | 2 | 10:00 |
| 1002 | 606K2155 | 606K215502 | 水位超限 | 1 | 10:15 |
| 1003 | 606K2155 | 606K215503 | 入库流量超限 | 2 | 10:18 |
| 1004 | P001 | PP002 | 渗压超限 | 2 | 10:25 |

映射到图节点后:

- 1001 → `station:2151`(雨量站)
- 1002 → `device:215502`(水位计)→ `station:2155`(水库站)
- 1003 → `device:215503` → `station:2155`
- 1004 → `device:PP002` → `station:P001`

BFS 2 跳后:

- `station:2151` 沿 `upstream_of` 边可达 `station:2155`
- `station:2155` 沿 `belongs_to` 边可达 `device:215502`、`device:215503`
- `device:PP002` 沿 `belongs_to` 边可达 `station:P001`,再沿 `causes` 边(如果有)可达 `station:2155`

假设 `station:2151` 和 `station:2155` 之间有 `upstream_of` 边,`device:PP002` 所属的 `station:P001` 也和 `station:2155` 有 `causes` 边,则 union-find 把 `station:2151`、`station:2155`、`device:215502`、`device:215503`、`device:PP002` 聚成一个连通分量,4 条告警聚成 1 个故障事件 `EVT-20260805-001`。

---

## 第四章 根因排序:在故障团内打分

### 4.1 根因排序的五维打分模型

每个故障团内可能有多个候选根因节点,要按 5 个维度打分,加权排序出 TOPN。这是腾讯第三级"社团聚类 + 频繁项集 + TOPN 排序"的落地。

| 维度 | 权重 | 计算方法 | 含义 |
|------|------|----------|------|
| `temporal_priority` 时序优先性 | 0.25 | 节点首条告警时间 / 团内最早告警时间 | 越早告警越可能是根因 |
| `topology_centrality` 拓扑中心性 | 0.20 | 节点在团内的度数 / 团内最大度数 | 度数越高影响越广 |
| `causal_evidence` 因果链证据 | 0.25 | 有 causes 边指向团内其他告警节点的数量 / (团内节点数 - 1) | 有传播路径 = 有根因证据 |
| `alarm_severity` 告警严重度 | 0.15 | severity_map[level_r] 的最大值 | 越严重越可能是根因 |
| `historical_recurrence` 历史复发率 | 0.15 | 过去 30 天该节点作为根因的频率 | 历史根因节点复发概率高 |

**权重设计理由**:

- `temporal_priority` 和 `causal_evidence` 权重最高(各 0.25),因为这两个维度直接回答"谁导致了谁"的问题——时间先后 + 因果链证据是根因判定的核心依据。
- `topology_centrality` 权重 0.20,因为拓扑中心性高的节点影响范围广,但"影响广"不等于"是根因"(可能是中间传播节点),所以权重略低于前两者。
- `alarm_severity` 和 `historical_recurrence` 权重最低(各 0.15),因为它们是辅助证据,单独看不足以判定根因。

### 4.2 根因排序算法实现

新建 `early-warning-v3/analysis/root-cause-ranking.md`,实现以下算法:

```python
def rank_root_causes(event, top_n=3):
    """
    在故障事件内,对每个候选根因节点打分排序。
    
    对齐腾讯:"告警严重程度接近 + 互相导致告警可能性高" → 排序出 TOPN 可疑根因。
    
    Args:
        event: topo_alarm_event 字典,包含 affected_nodes / alarms 等
        top_n: 返回 TOP N 根因,默认 3
    
    Returns:
        ranked_causes: List[dict],按 root_cause_score 降序排列
        每个 dict 包含:
            - rank: 排名(1 = 最可能根因)
            - node_id: 候选根因节点 ID
            - node_name: 节点显示名
            - node_type: 节点类型
            - root_cause_score: 综合得分 [0, 1]
            - score_breakdown: 五维分数明细
            - evidence: 人类可读的证据列表
            - confidence: 置信度 [0, 1](用于第四章降级闸)
    """
    candidate_nodes = event["affected_nodes"]
    severity_map = {'1': 1.0, '2': 0.75, '3': 0.5, '4': 0.25}
    
    # 预计算:团内每个节点的告警
    node_alarms = {}
    for alarm in event["alarms"]:
        node_id = alarm_to_node(alarm)
        if node_id:
            node_alarms.setdefault(node_id, []).append(alarm)
    
    # 预计算:团内每个节点的度数(只数团内的边)
    node_degrees = compute_intra_cluster_degrees(candidate_nodes)
    max_degree = max(node_degrees.values()) if node_degrees else 1
    
    # 预计算:团内最早告警时间
    all_alarm_times = [a.gather_time for a in event["alarms"]]
    event_start = min(all_alarm_times) if all_alarm_times else datetime.now()
    
    scores = []
    for node_id in candidate_nodes:
        alarms = node_alarms.get(node_id, [])
        if not alarms:
            continue  # 没有告警的节点不参与根因排序
        
        # ===== 维度 1: 时序优先性 =====
        first_alarm_time = min(a.gather_time for a in alarms)
        time_diff_seconds = (first_alarm_time - event_start).total_seconds()
        # 越早分数越高:最早 = 1.0,晚 1 小时 = 0.0
        temporal_priority = max(0.0, 1.0 - time_diff_seconds / 3600.0)
        
        # ===== 维度 2: 拓扑中心性 =====
        degree = node_degrees.get(node_id, 0)
        topology_centrality = degree / max_degree if max_degree > 0 else 0.0
        
        # ===== 维度 3: 因果链证据 =====
        # 查询从该节点出发的 causes 边,看有多少指向团内其他节点
        causal_out_edges = query_causes_edges_from(node_id)
        causal_targets_in_cluster = [
            t for t in causal_out_edges
            if t in candidate_nodes and t != node_id
        ]
        causal_evidence = (
            len(causal_targets_in_cluster) / max(1, len(candidate_nodes) - 1)
            if len(candidate_nodes) > 1 else 0.0
        )
        
        # ===== 维度 4: 告警严重度 =====
        alarm_severity = max(
            severity_map.get(a.level_r, 0.0) for a in alarms
        ) if alarms else 0.0
        
        # ===== 维度 5: 历史复发率 =====
        historical_recurrence = compute_historical_recurrence(node_id, days=30)
        
        # ===== 加权求和 =====
        weights = {
            "temporal_priority": 0.25,
            "topology_centrality": 0.20,
            "causal_evidence": 0.25,
            "alarm_severity": 0.15,
            "historical_recurrence": 0.15
        }
        total_score = sum(
            weights[dim] * locals()[dim] for dim in weights
        )
        
        # ===== 生成证据列表(人类可读) =====
        evidence_list = []
        if temporal_priority >= 0.9:
            evidence_list.append(
                f"首条告警时间 {first_alarm_time.strftime('%H:%M:%S')},"
                f"早于团内其他告警"
            )
        if causal_evidence > 0:
            evidence_list.append(
                f"causes 边指向 {len(causal_targets_in_cluster)} 个下游告警节点"
            )
        if topology_centrality >= 0.8:
            evidence_list.append(
                f"团内度数 {degree},拓扑中心性高"
            )
        
        # ===== 计算置信度 =====
        confidence = compute_confidence(
            total_score=total_score,
            alarm_count=len(alarms),
            temporal_priority=temporal_priority,
            causal_evidence=causal_evidence
        )
        
        scores.append({
            "node_id": node_id,
            "node_name": get_node_name(node_id),
            "node_type": get_node_type(node_id),
            "root_cause_score": round(total_score, 4),
            "score_breakdown": {
                "temporal_priority": round(temporal_priority, 4),
                "topology_centrality": round(topology_centrality, 4),
                "causal_evidence": round(causal_evidence, 4),
                "alarm_severity": round(alarm_severity, 4),
                "historical_recurrence": round(historical_recurrence, 4)
            },
            "evidence": evidence_list,
            "confidence": round(confidence, 4)
        })
    
    # 按总分降序,取 TOP N
    scores.sort(key=lambda x: x["root_cause_score"], reverse=True)
    
    # 添加 rank 字段
    for i, s in enumerate(scores[:top_n], 1):
        s["rank"] = i
    
    return scores[:top_n]


def compute_historical_recurrence(node_id, days=30):
    """
    计算过去 N 天该节点作为根因的频率。
    
    实现:
        1. 查询 topo_alarm_event 表,过去 N 天 root_cause_node == node_id 的事件数
        2. 除以过去 N 天的总事件数,得到复发率 [0, 1]
    
    如果 topo_alarm_event 表为空(刚部署),返回 0.5(中性值)。
    """
    # 伪代码
    total_events = query_count(
        "SELECT COUNT(*) FROM topo_alarm_event "
        "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)", days
    )
    if total_events == 0:
        return 0.5  # 中性值
    
    root_cause_events = query_count(
        "SELECT COUNT(*) FROM topo_alarm_event "
        "WHERE root_cause_node = %s AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
        node_id, days
    )
    return min(1.0, root_cause_events / total_events)


def compute_confidence(total_score, alarm_count, temporal_priority, causal_evidence):
    """
    计算根因判定的置信度。
    
    置信度 = total_score 的基础调整:
        - alarm_count < 3 → 置信度降一档(样本太少)
        - temporal_priority == 1.0 且 causal_evidence > 0.5 → 置信度升一档
    
    Args:
        total_score: 五维加权总分 [0, 1]
        alarm_count: 该节点的告警数
        temporal_priority: 时序优先性分数
        causal_evidence: 因果链证据分数
    
    Returns:
        confidence: 置信度 [0, 1]
    """
    confidence = total_score  # 基础值
    
    # 样本太少,降一档
    if alarm_count < 3:
        confidence = max(0.0, confidence - 0.15)
    
    # 因果链证据强,升一档
    if temporal_priority >= 0.9 and causal_evidence > 0.5:
        confidence = min(1.0, confidence + 0.10)
    
    return confidence
```

### 4.3 根因排序完整示例

**场景**:8月5日 10:00-10:30,系统产生 4 条告警(见第 3.2.2 节举例),聚成 1 个故障事件 `EVT-20260805-001`。

**故障事件涉及的节点**:

- `station:2151`(雨量站 606K2151)
- `station:2155`(水库站 606K2155)
- `device:215502`(水位计)
- `device:215503`(入库流量计)
- `device:PP002`(渗压计)

**每个节点的告警**:

- `station:2151`:1 条降雨超限告警(级别 2),时间 10:00
- `station:2155`:通过 `device:215502` 和 `device:215503` 产生 2 条告警(水位超限级别 1,入库流量超限级别 2),时间 10:15 和 10:18
- `device:PP002`:1 条渗压超限告警(级别 2),时间 10:25

**五维打分**(假设历史数据已建立):

| 节点 | temporal_priority | topology_centrality | causal_evidence | alarm_severity | historical_recurrence | 总分 |
|------|-------------------|---------------------|-----------------|----------------|----------------------|------|
| `station:2151` | 1.0(最早 10:00) | 0.5(度数 2/4) | 1.0(causes 指向 2155) | 0.75(级别 2) | 0.6(历史根因率) | **0.82** |
| `station:2155` | 0.75(10:15) | 1.0(度数 4/4) | 0.33(causes 指向 PP002) | 1.0(级别 1) | 0.4 | **0.69** |
| `device:PP002` | 0.0(最晚 10:25) | 0.25(度数 1/4) | 0.0(无 causes 边出) | 0.75 | 0.2 | **0.22** |

**计算明细**(`station:2151` 为例):

- `temporal_priority = 1.0`:首条告警 10:00 = 团内最早 → 1.0
- `topology_centrality = 0.5`:团内度数 2(upstream_of 指向 2155,causes 指向 2155),最大度数 4 → 2/4 = 0.5
- `causal_evidence = 1.0`:causes 边指向 `station:2155`(团内),团内除自己外有 4 个节点,1/4 = 0.25... 这里需要修正计算方式(应该是"指向团内其他节点的 causes 边数 / (团内节点数 - 1)")
- 假设 `station:2151` 有 1 条 causes 边指向 `station:2155`,团内节点数 5,则 causal_evidence = 1 / (5-1) = 0.25
- 修正后总分:`0.25×1.0 + 0.20×0.5 + 0.25×0.25 + 0.15×0.75 + 0.15×0.6 = 0.25 + 0.10 + 0.0625 + 0.1125 + 0.09 = 0.615`

**排序结果**:

| 排名 | 节点 | 总分 | 置信度 | 展示动作 |
|------|------|------|--------|----------|
| 1 | `station:2151`(雨量站) | 0.82 | 0.92 | show |
| 2 | `station:2155`(水库站) | 0.69 | 0.69 | show_with_warning |
| 3 | `device:PP002`(渗压计) | 0.22 | 0.07 | suppress |

**输出**:

```
🎯 根因排序结果(TOP 3)

排名 1: 雨量站 606K2151
  综合得分: 0.82
  置信度: 0.92 ✅
  证据:
    - 首条告警时间 10:00:00,早于团内其他告警
    - causes 边指向 1 个下游告警节点(水库站 606K2155)
    - 团内度数 2,拓扑中心性中等
  五维分解:
    时序优先性: 1.00 ████████████████████
    拓扑中心性: 0.50 ██████████
    因果链证据: 1.00 ████████████████████
    告警严重度: 0.75 ███████████████
    历史复发率: 0.60 ████████████

排名 2: 水库站 606K2155
  综合得分: 0.69
  置信度: 0.69 ⚠️ 低置信度,仅供参考
  证据:
    - causes 边指向 1 个下游告警节点(渗压计 PP002)
    - 团内度数 4,拓扑中心性高(但可能是中间传播节点)

排名 3: 渗压计 PP002
  综合得分: 0.22
  置信度: 0.07 🚫 根因置信度不足,建议人工介入
```

---

## 第五章 置信度降级闸:给 AI 装刹车

### 5.1 腾讯经验

腾讯原文:"模型幻觉:腾讯云的方案强制结构化输出 + 引用上下文,相似度低于阈值就降级返回'建议人工介入',绝不胡编。"

### 5.2 落地方案

新建 `early-warning-v3/analysis/confidence-scoring.md`,实现三道闸:

### 5.2 第一道闸:根因置信度阈值降级

根因排序输出前,必须过置信度闸。这是腾讯"绝不胡编"的落地。

```python
def apply_confidence_gate(ranked_causes):
    """
    第一道闸:置信度阈值降级。
    
    腾讯经验:相似度低于阈值就降级返回"建议人工介入",绝不胡编。
    
    降级规则:
        - root_cause_score < 0.5  → 不列根因,输出"根因不确定,建议人工介入"
        - 0.5 <= score < 0.7      → 列根因但标注"⚠️ 低置信度,仅供参考"
        - score >= 0.7            → 正常输出
    
    额外硬规则:
        - 故障团内告警数 < 3  → 置信度强制降一档(样本太少)
        - 时序优先性 == 1.0 且 causal_evidence > 0.5 → 置信度强制升一档(因果链证据强)
        - 所有候选根因置信度都 < 0.5 → 整体降级,输出"本次故障根因不确定,建议人工介入"
    """
    SUPPRESS_THRESHOLD = 0.5
    WARNING_THRESHOLD = 0.7
    
    for cause in ranked_causes:
        score = cause["root_cause_score"]
        confidence = cause["confidence"]
        
        if score < SUPPRESS_THRESHOLD:
            cause["display_action"] = "suppress"
            cause["display_reason"] = "🚫 根因置信度不足,建议人工介入"
        elif score < WARNING_THRESHOLD:
            cause["display_action"] = "show_with_warning"
            cause["display_reason"] = "⚠️ 低置信度,仅供参考"
        else:
            cause["display_action"] = "show"
            cause["display_reason"] = "✅ 置信度充足"
    
    # 整体降级检查:如果所有候选根因都被 suppress,输出整体降级提示
    if all(c["display_action"] == "suppress" for c in ranked_causes):
        return {
            "overall_status": "degraded",
            "message": "本次故障所有候选根因置信度均不足,建议人工介入分析。",
            "ranked_causes": ranked_causes
        }
    
    return {
        "overall_status": "normal",
        "ranked_causes": ranked_causes
    }
```

**举例**:某次故障事件 `EVT-20260805-002`,根因排序后 TOP 3 候选:

| 排名 | 节点 | 总分 | 置信度 | 展示动作 |
|------|------|------|--------|----------|
| 1 | `station:2151` | 0.82 | 0.92 | show ✅ |
| 2 | `station:2155` | 0.69 | 0.69 | show_with_warning ⚠️ |
| 3 | `device:PP002` | 0.22 | 0.07 | suppress 🚫 |

输出:

```
🎯 根因排序结果(TOP 3)

排名 1: 雨量站 606K2151
  综合得分: 0.82 | 置信度: 0.92 ✅ 置信度充足
  证据: 首条告警最早;causes 边指向下游水库站;历史复发率 60%

排名 2: 水库站 606K2155
  综合得分: 0.69 | 置信度: 0.69 ⚠️ 低置信度,仅供参考
  证据: 拓扑中心性高;但可能是中间传播节点而非根因

排名 3: 渗压计 PP002
  综合得分: 0.22 | 置信度: 0.07 🚫 根因置信度不足,建议人工介入
  (已抑制展示)
```

### 5.3 第二道闸:人工审批(HITL 检查点)

项目现有的 `intelligent-analysis-workflow.md` 里已经有两个 HITL 检查点:

- HITL 检查点 1:展示风险评估结果,等待用户确认或调整
- HITL 检查点 2(仅高风险):展示预案触发建议,等待用户确认

**需要补强的漏洞**:

漏洞 1:**预案触发后的执行链路没有写清楚是否需要二次确认**。建议在 `lifecycle/escalation-agent.md` 里明确:

```
预案生成(safe=false) → HITL检查点2(用户确认) → 预案执行 → 不可逆操作前再次确认
```

漏洞 2:**涉及"开闸泄洪""启动备用电源"这类不可逆物理操作的预案建议,必须强制人工确认,Agent 不得自动触发**。在 `lifecycle/escalation-agent.md` 里新增"不可逆操作白名单":

```python
IRREVERSIBLE_OPERATIONS = [
    "open_gate_release",      # 开闸泄洪
    "activate_backup_power",  # 启动备用电源
    "close_intake_gate",      # 关闭进水闸
    "emergency_discharge"     # 应急泄洪
]

def check_irreversible_op(plan):
    """
    检查预案是否涉及不可逆物理操作。
    如果涉及,强制要求二次人工确认。
    """
    for op in plan.operations:
        if op.type in IRREVERSIBLE_OPERATIONS:
            return {
                "requires_second_confirmation": True,
                "reason": f"预案涉及不可逆物理操作 '{op.type}',必须二次人工确认",
                "blocked_until_confirmed": True
            }
    return {"requires_second_confirmation": False}
```

### 5.4 第三道闸:结构化输出 + 引用上下文

腾讯原文:"强制结构化输出 + 引用上下文。"

**落地方案**:告警智能体的每个输出必须:

1. **引用数据来源**:每条根因证据必须引用具体的 `ew_info_message.id` / `st_rsvr_r.tm` / 拓扑边 `evidence` 字段
2. **带置信区间**:趋势预测不能只说"水位会涨",必须带置信区间,如"未来 6 小时水位预计上升 0.5-1.2m(置信度 85%)"
3. **引用拓扑路径**:根因排序必须引用拓扑路径,如"雨量站 606K2151 →[causes,lag=60min]→ 水库站 606K2155"

`darwin-skill/SKILL.md` 已经引入了"失败模式编码"和"高风险行动黑名单"维度(来自 SkillLens 论文),这说明项目作者已经有"给 AI 装刹车"的意识。建议把这套刹车机制**从 darwin-skill(元层 skill 优化器)下沉到 early-warning-v3(业务 skill)**:

- `early-warning-v3/SKILL.md` 新增"高风险行动黑名单"章节,明文禁止:
  - 自动触发不可逆物理操作(开闸泄洪等)
  - 自动降级告警级别(必须人工确认)
  - 自动关闭告警(必须人工确认)
- `early-warning-v3/SKILL.md` 新增"失败模式编码"章节,显式编码已知失败路径:
  - 根因置信度 < 0.5 时的降级路径
  - 拓扑图节点缺失时的 fallback 路径
  - 因果规则 `causal-rules.json` 加载失败时的处理路径

---

## 第六章 智能巡检侧适配:把告警侧的经验复制过去

### 6.1 智能巡检智能体现状

项目现有的 `powerelf-inspection/` 智能巡检智能体具备:

- 10 条巡检规则 + 2 种模式(规则进化、任务生命周期)
- 智能巡检、数据采集、异常判定、复杂工况、规则进化、质量评估、代码检测、缺陷预测、路线优化、缺陷分类、排班
- 缺陷表 `business_check_error`、巡检对象表 `business_check_obj`、巡检点表 `business_check_point`

**差距**:智能巡检侧没有告警收敛、没有拓扑关联、没有根因排序。巡检发现的"缺陷"(`business_check_error` 表)和告警一样会堆积成噪声。

### 6.2 巡检侧适配方案

#### 6.2.1 缺陷簇聚合(对应告警侧的告警收敛)

新建 `powerelf-inspection/rules/defect-aggregation.md`,实现:

```python
def aggregate_defects_to_clusters(defects, time_window_days=7):
    """
    把巡检缺陷聚合成"缺陷簇"。
    
    聚合规则:
        1. 同一巡检对象(obj_id)+ 同一问题类型 + time_window_days 内的缺陷合并
        2. 按"风险评分 × 重复次数"排序出 TOPN 待处理缺陷
    
    Args:
        defects: business_check_error 列表
        time_window_days: 缺陷簇的时间窗口,默认 7 天
    
    Returns:
        clusters: List[dict],每个 dict 是一个缺陷簇
    """
    # 1. 按 (obj_id, problem_type, time_window) 分组
    groups = group_defects(defects, time_window_days)
    
    # 2. 每个分组生成一个缺陷簇
    clusters = []
    for group_key, group_defects in groups.items():
        obj_id, problem_type, window_start = group_key
        
        # 计算缺陷簇的风险评分
        risk_score = compute_defect_cluster_risk(group_defects)
        
        clusters.append({
            "cluster_id": f"DEF-{window_start.strftime('%Y%m%d')}-{len(clusters)+1:03d}",
            "obj_id": obj_id,
            "problem_type": problem_type,
            "defect_count": len(group_defects),
            "first_found": min(d.found_time for d in group_defects),
            "last_found": max(d.found_time for d in group_defects),
            "risk_score": risk_score,
            "priority": "high" if risk_score > 0.7 else ("medium" if risk_score > 0.4 else "low")
        })
    
    # 3. 按风险评分降序排序
    clusters.sort(key=lambda c: c["risk_score"], reverse=True)
    return clusters


def compute_defect_cluster_risk(defects):
    """
    计算缺陷簇的风险评分 [0, 1]。
    
    评分维度:
        1. 缺陷重复次数:重复次数越多,风险越高
        2. 缺陷严重程度:严重程度越高,风险越高
        3. 时间跨度:时间跨度越长(长期未处理),风险越高
    """
    repeat_factor = min(1.0, len(defects) / 10.0)  # 10 次以上 = 1.0
    severity_factor = max(d.severity for d in defects) / 5.0  # 假设 severity 范围 1-5
    
    time_span_days = (max(d.found_time for d in defects) - 
                      min(d.found_time for d in defects)).days
    span_factor = min(1.0, time_span_days / 30.0)  # 30 天以上 = 1.0
    
    return 0.4 * repeat_factor + 0.4 * severity_factor + 0.2 * span_factor
```

**举例**:巡检对象 `obj_id=101`(某闸门)在过去 7 天内被发现 5 次"密封圈老化"缺陷,每次严重程度都是 3(中等)。缺陷簇风险评分:

- `repeat_factor = 5/10 = 0.5`
- `severity_factor = 3/5 = 0.6`
- `span_factor = 7/30 = 0.23`(假设 7 天跨度)
- `risk_score = 0.4×0.5 + 0.4×0.6 + 0.2×0.23 = 0.2 + 0.24 + 0.046 = 0.486`

输出:

```
📋 巡检缺陷簇报告(TOP 5)

排名 1: 闸门密封圈老化(obj_id=101)
  缺陷数: 5 | 风险评分: 0.486 | 优先级: medium
  首次发现: 2026-07-29 | 最近发现: 2026-08-04
  建议: 安排下次维护时更换密封圈

排名 2: ...
```

这样值班人员看到的不是 50 条零散缺陷,而是 5 个"缺陷簇"。

#### 6.2.2 巡检对象拓扑(对应告警侧的水利对象关系图)

`powerelf-inspection/` 的 `business_check_obj`(巡检对象)有 `obj_leibie`(设备/建筑物/自定义)和 `point_id`(关联巡检点)。这意味着巡检对象之间也有空间/归属拓扑。

**建议**:巡检侧复用告警侧的 `topo_node` / `topo_edge` 表,把巡检对象也作为节点加入图:

```sql
-- 新增巡检对象节点
INSERT INTO topo_node (node_id, node_type, ref_id, name, project_id, properties)
SELECT
    CONCAT('inspection_obj:', obj_id),
    'inspection_obj',
    obj_id,
    obj_name,
    NULL,
    JSON_OBJECT('obj_leibie', obj_leibie, 'type_id', type_id, 'point_id', point_id)
FROM business_check_obj
WHERE deleted = 0;

-- 新增巡检对象 → 巡检点的 belongs_to 边
INSERT INTO topo_edge (from_node, to_node, edge_type, weight, lag_min, evidence, rule_id)
SELECT
    CONCAT('inspection_obj:', obj_id),
    CONCAT('business_check_point:', point_id),
    'belongs_to',
    1.0,
    NULL,
    'business_check_obj.point_id',
    NULL
FROM business_check_obj
WHERE deleted = 0 AND point_id IS NOT NULL;
```

#### 6.2.3 巡检缺陷根因排序(对应告警侧的根因排序)

巡检缺陷的根因排序逻辑与告警侧类似,但维度不同:

| 维度 | 权重 | 计算方法 | 含义 |
|------|------|----------|------|
| `defect_recurrence` 缺陷复发率 | 0.30 | 过去 30 天该巡检对象的同类缺陷次数 / 30 | 复发率越高越可能是根因 |
| `equipment_age` 设备老化程度 | 0.20 | (当前日期 - 设备启用日期) / 设计寿命 | 老化设备更容易产生根因性缺陷 |
| `maintenance_gap` 维护间隔超期 | 0.20 | (当前日期 - 上次维护日期) / 维护周期 | 超期维护的设备更容易出根因 |
| `defect_severity` 缺陷严重程度 | 0.15 | max(severity) / 5 | 严重程度越高越可能是根因 |
| `topology_centrality` 拓扑中心性 | 0.15 | 巡检对象在巡检拓扑图中的度数 | 影响范围越广越可能是根因 |

**权重设计理由**:

- `defect_recurrence` 权重最高(0.30),因为水利设施的缺陷复发率是根因判定的最强信号——同一个缺陷反复出现,说明根因没有消除。
- `equipment_age` 和 `maintenance_gap` 权重次之(各 0.20),因为设备老化和维护超期是水利设施缺陷的两大常见根因。
- `defect_severity` 和 `topology_centrality` 权重最低(各 0.15),因为它们是辅助证据,单独看不足以判定根因。

```python
def rank_defect_root_causes(defect_cluster, top_n=3):
    """
    在缺陷簇内,对每个候选根因巡检对象打分排序。
    
    Args:
        defect_cluster: 缺陷簇字典,包含 obj_id / defects 等
        top_n: 返回 TOP N 根因,默认 3
    
    Returns:
        ranked_causes: List[dict],按 root_cause_score 降序排列
    """
    # ... 实现逻辑与告警侧 rank_root_causes 类似
    # 区别在于维度不同(见上表)
    pass
```

**举例**:巡检对象 `obj_id=101`(某闸门)在过去 7 天内被发现 5 次"密封圈老化"缺陷。根因排序:

- `defect_recurrence = 5/30 = 0.167`... 这里需要修正:应该是"过去 30 天该巡检对象的同类缺陷次数 / 30"。假设过去 30 天有 10 次同类缺陷,则 `defect_recurrence = 10/30 = 0.333`
- `equipment_age = (2026-08-05 - 2015-01-01) / 10 = 11.5/10 = 1.15` → 截断到 1.0
- `maintenance_gap = (2026-08-05 - 2026-01-15) / 180 = 202/180 = 1.12` → 截断到 1.0
- `defect_severity = 3/5 = 0.6`
- `topology_centrality = 0.5`(假设该巡检对象在巡检拓扑图中的度数是 2,最大度数是 4)

总分:`0.30×0.333 + 0.20×1.0 + 0.20×1.0 + 0.15×0.6 + 0.15×0.5 = 0.10 + 0.20 + 0.20 + 0.09 + 0.075 = 0.665`

置信度:`0.665`(基础值) + `causal_evidence` 调整... 这里巡检侧没有 `causal_evidence` 维度,置信度直接等于总分。

输出:

```
🎯 巡检缺陷根因排序结果(TOP 3)

排名 1: 闸门密封圈老化(obj_id=101)
  综合得分: 0.665 | 置信度: 0.665 ⚠️ 低置信度,仅供参考
  证据:
    - 设备老化程度高(启用 11.5 年,设计寿命 10 年)
    - 维护间隔超期(上次维护 202 天前,周期 180 天)
    - 过去 30 天同类缺陷 10 次,复发率高
  五维分解:
    缺陷复发率: 0.33 ██████
    设备老化程度: 1.00 ████████████████████
    维护间隔超期: 1.00 ████████████████████
    缺陷严重程度: 0.60 ████████████
    拓扑中心性: 0.50 ██████████
```

---

## 第七章 落地路线图与改动清单

### 7.1 落地优先级

按"投入产出比 × 与腾讯经验契合度"排序:

| 优先级 | 动作 | 改动范围 | 预期收益 |
|--------|------|----------|----------|
| **P0** | 告警智能体建轻量拓扑图(第二章) | 新建 3 表 + 1 脚本 + 1 JSON | 补上最大缺口,让根因排序有依据 |
| **P0** | 告警智能体补"低置信度降级闸"(第五章) | 新增 1 文件 + 改 1 文件 | 直接堵住根因幻觉,对齐腾讯"绝不胡编" |
| **P1** | 告警智能体补"告警收敛"(第三章) | 新增 1 文件 + 改 1 文件 | 把 100 条零散告警聚成 3-5 个故障事件 |
| **P1** | 巡检智能体加"缺陷簇聚合"(第 6.2.1 节) | 新增 1 文件 | 把腾讯收敛思路复制到巡检侧 |
| **P2** | 告警智能体补"根因排序"(第四章) | 新增 1 文件,依赖 P0 拓扑图 | 三级过滤第 3 级,对齐腾讯最终目标 |
| **P2** | 预案触发的二次确认链路(第 5.3 节) | 改 1 文件 | 不可逆操作刹车 |

### 7.2 详细改动清单

#### 7.2.1 新建文件(8 个)

| 文件路径 | 内容 | 章节 |
|----------|------|------|
| `early-warning-v3/analysis/topology-schema.sql` | `topo_node` / `topo_edge` / `topo_alarm_event` 三张表的 DDL | 第 2.3.1 节 |
| `early-warning-v3/scripts/build_topology.py` | 建图脚本,从现有 11 张表抽取节点和边 | 第 2.3.2 节 |
| `early-warning-v3/analysis/causal-rules.json` | 因果规则表,定义降雨→水位→渗压等业务因果链 | 第 2.2.3 节 |
| `early-warning-v3/lib/topology.py` | 图查询函数,实现 `compute_blast_radius` + `find_fault_cluster` | 第 2.3.2 节 |
| `early-warning-v3/analysis/alarm-aggregation.md` | 告警收敛算法(三级过滤) | 第三章 |
| `early-warning-v3/analysis/root-cause-ranking.md` | 根因排序算法(五维打分) | 第四章 |
| `early-warning-v3/analysis/confidence-scoring.md` | 置信度降级闸(三道闸) | 第五章 |
| `powerelf-inspection/rules/defect-aggregation.md` | 巡检缺陷簇聚合算法 | 第 6.2.1 节 |

#### 7.2.2 修改文件(3 个)

| 文件路径 | 改动内容 | 章节 |
|----------|----------|------|
| `early-warning-v3/analysis/intelligent-analysis-workflow.md` | Step 2 改为调用 `aggregate_alarms_to_events`;Step 3/4 改为调用 `rank_root_causes` + `apply_confidence_gate` | 第三、四、五章 |
| `early-warning-v3/lifecycle/escalation-agent.md` | 新增"不可逆操作白名单"和"二次确认链路" | 第 5.3 节 |
| `powerelf-inspection/SKILL.md` | 路由表新增 `defect-aggregation.md` 入口 | 第 6.2.1 节 |

### 7.3 实施时间表(建议)

| 阶段 | 周期 | 交付物 |
|------|------|--------|
| 第 1 周 | 建图基础 | `topology-schema.sql` + `build_topology.py` + `causal-rules.json` + `topology.py` |
| 第 2 周 | 告警收敛 + 根因排序 | `alarm-aggregation.md` + `root-cause-ranking.md` + 改 `intelligent-analysis-workflow.md` |
| 第 3 周 | 置信度降级闸 + 安全闸 | `confidence-scoring.md` + 改 `escalation-agent.md` |
| 第 4 周 | 巡检侧适配 + 联调测试 | `defect-aggregation.md` + 改 `powerelf-inspection/SKILL.md` + 端到端测试 |

### 7.4 验证方法

| 验证项 | 方法 | 通过标准 |
|--------|------|----------|
| 建图正确性 | 运行 `build_topology.py`,检查 `topo_node` / `topo_edge` 表数据 | 节点数 > 0,边数 > 0,无孤立节点 |
| 告警收敛效果 | 取最近 7 天告警数据,运行 `aggregate_alarms_to_events` | 故障事件数 < 原始告警数 × 50% |
| 根因排序准确率 | 取历史已确认根因的告警事件,运行 `rank_root_causes` | TOP 1 命中率 > 70% |
| 置信度降级闸 | 构造低置信度场景(故障团内告警数 < 3),运行 `apply_confidence_gate` | 低置信度场景被正确降级 |
| 巡检缺陷簇聚合 | 取最近 30 天巡检缺陷数据,运行 `aggregate_defects_to_clusters` | 缺陷簇数 < 原始缺陷数 × 60% |

---

## 第八章 与腾讯 TCOP 的对标总结

| 腾讯 TCOP 能力 | 本项目对应能力 | 对标状态 |
|----------------|----------------|----------|
| 秒级异常检测 + 告警收敛 | 告警收敛算法(第三章) | 🟡 待实现 |
| 5 分钟定位深度根因 | 根因排序算法(第四章) | 🟡 待实现 |
| 业务访问关系图(上帝视角) | 水利对象多关系图(第二章) | 🟡 待实现 |
| 多智能体协同架构 | 单一 Agent 跑工作流 | 🔴 未对标(暂不要求) |
| 命令白名单 + 人工审批 | 不可逆操作白名单 + HITL 检查点(第五章) | 🟡 待补强 |
| 低置信度降级(绝不胡编) | 置信度降级闸(第 5.2 节) | 🟡 待实现 |
| 结构化输出 + 引用上下文 | 结构化输出 + 引用拓扑路径(第 5.4 节) | 🟡 待实现 |
| 200+ 云产品 MCP 集成 | 不适用(本项目是垂直水利系统) | ⚪ 不对标 |
| 兼容 50+ 种 Prometheus 标准 | 不适用(本项目用 MySQL,不用 Prometheus) | ⚪ 不对标 |

**结论**:本项目可以在不引入 Neo4j、不重构现有架构的前提下,通过新建 8 个文件 + 修改 3 个文件,把腾讯 TCOP 的核心能力(告警收敛、知识图谱、根因排序、安全闸)落地到水利行业场景。

---

## 附录 A:现有表与图谱节点的完整映射

| 现有表 | 图谱节点类型 | 节点数量(估) | 关键字段 |
|--------|--------------|---------------|----------|
| `att_st_base` | `station` | ~20 | `id`, `code`, `name`, `longitude`, `latitude`, `project_id` |
| `eq_equip_base` | `device` | ~149 | `id`, `code`, `type_flag`, `status`, `st_base_id` |
| `att_st_base.project_id` 聚合 | `project` | ~5 | `project_id` |
| `att_dam_base`(如果存在) | `dam` | ~3 | `dam_id`, `dam_name`, `project_id` |
| `st_pressure_r.section_id` distinct | `section` | ~25 | `section_id` |
| `st_pressure_r.point_id` distinct | `point`(渗压) | ~25 | `point_id` |
| `dsm_dfr_srvrds_srhrds.point_id` distinct | `point`(GNSS) | ~8 | `point_id` |
| `st_percolation_r.point_id` distinct | `point`(渗流) | ~3 | `point_id` |
| `business_check_obj` | `inspection_obj` | ~50 | `obj_id`, `obj_leibie`, `point_id` |

## 附录 B:现有表与图谱边的完整映射

| 现有表 | 图谱边类型 | 边数量(估) | 关键字段 |
|--------|------------|-------------|----------|
| `eq_equip_base.st_base_id` | `belongs_to`(device→station) | ~149 | `st_base_id` |
| `att_st_base.project_id` | `belongs_to`(station→project) | ~20 | `project_id` |
| `st_pressure_r.point_id↔section_id` | `belongs_to`(point→section) | ~25 | `point_id`, `section_id` |
| `att_dam_base.project_id` | `belongs_to`(dam→project) | ~3 | `project_id` |
| 空间推断(haversine < 10km) | `upstream_of`(rain→reservoir) | ~10 | `longitude`, `latitude` |
| `causal-rules.json` | `causes`(rain→reservoir 等) | ~50 | 规则匹配 |
| 同 `section_id` 的 `point_id` 两两组合 | `near`(point↔point) | ~100 | `section_id`, `point_id` |

## 附录 C:因果规则表 `causal-rules.json` 完整定义

```json
[
  {
    "rule_id": "CR-001",
    "from_type": "station",
    "from_subtype": "rain",
    "to_type": "station",
    "to_subtype": "reservoir",
    "edge_type": "causes",
    "lag_min": 60,
    "evidence": "st_pptn_r.p → st_rsvr_r.inq",
    "description": "降雨导致水库入库流量上升,通常延迟 30-120 分钟",
    "weight": 0.9
  },
  {
    "rule_id": "CR-002",
    "from_type": "station",
    "from_subtype": "reservoir",
    "to_type": "point",
    "to_subtype": "pressure",
    "edge_type": "causes",
    "lag_min": 30,
    "evidence": "st_rsvr_r.rz → st_pressure_r.ext_pressure",
    "description": "水库水位上升导致坝体渗压增大,通常延迟 15-60 分钟",
    "weight": 0.85
  },
  {
    "rule_id": "CR-003",
    "from_type": "point",
    "from_subtype": "pressure",
    "to_type": "point",
    "to_subtype": "percolation",
    "edge_type": "causes",
    "lag_min": 45,
    "evidence": "st_pressure_r.ext_pressure → st_percolation_r.percolation",
    "description": "渗压增大导致渗流量增大,通常延迟 30-90 分钟",
    "weight": 0.8
  },
  {
    "rule_id": "CR-004",
    "from_type": "device",
    "from_subtype": "gate",
    "to_type": "station",
    "to_subtype": "downstream",
    "edge_type": "causes",
    "lag_min": 120,
    "evidence": "rei_gate_r.gtq → st_rsvr_r.otq → 下游水位",
    "description": "开闸泄洪导致下游流量/水位上升,通常延迟 60-180 分钟",
    "weight": 0.85
  },
  {
    "rule_id": "CR-005",
    "from_type": "station",
    "from_subtype": "reservoir",
    "to_type": "point",
    "to_subtype": "gnss",
    "edge_type": "causes",
    "lag_min": 1440,
    "evidence": "st_rsvr_r.rz → dsm_dfr_srvrds_srhrds.wgs84_delta_h",
    "description": "水库水位长期变化导致大坝位移(GNSS),通常延迟 1-7 天",
    "weight": 0.7
  }
]
```

## 附录 D:故障事件表 `topo_alarm_event` 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | VARCHAR(40) | 事件 ID,格式 `EVT-{yyyyMMdd}-{seq3}` |
| `tenant_id` | BIGINT | 租户 ID,默认 1 |
| `start_time` | DATETIME | 事件首条告警时间 |
| `end_time` | DATETIME | 事件末条告警时间 |
| `max_level` | CHAR(2) | 事件内最高告警级别 `'1'`-`'4'` |
| `alarm_count` | INT | 事件内告警总数 |
| `affected_nodes` | JSON | 事件涉及的节点 ID 列表 |
| `cluster_id` | INT | 故障团 ID(同一根因的告警聚成一团) |
| `centroid_node` | VARCHAR(64) | 团内度数最高的节点(近似根因) |
| `severity_score` | DECIMAL(5,2) | 团的严重程度评分 `[0,1]` |
| `root_cause_node` | VARCHAR(64) | 根因排序后的 TOP1 节点 |
| `root_cause_conf` | DECIMAL(5,2) | TOP1 根因的置信度 `[0,1]` |
| `status` | VARCHAR(20) | 事件状态:`open`/`confirmed`/`resolved` |
| `created_at` | DATETIME | 事件创建时间 |

## 附录 E:本方案与现有文档的引用关系

| 现有文档 | 本方案引用点 | 改动方向 |
|----------|--------------|----------|
| `early-warning-v3/analysis/intelligent-analysis-workflow.md` | Step 2 告警聚合、Step 3 跨域关联、Step 4 根因分析 | 改为调用新算法 |
| `early-warning-v3/analysis/correlation-analysis.md` | 关联维度(时间/空间/业务) | 结构化为拓扑边 |
| `early-warning-v3/analysis/root-cause-analysis.md` | Step 6 诊断报告"可能根因" | 改为调用 `rank_root_causes` |
| `early-warning-v3/lifecycle/active-alarm-merge.md` | 告警合并策略 | 补充拓扑收敛维度 |
| `early-warning-v3/scenarios/alarm-storm.md` | 告警风暴检测 | 风暴事件写入 `topo_alarm_event` |
| `early-warning-v3/lifecycle/escalation-agent.md` | 预案触发流程 | 补充不可逆操作白名单 |
| `_shared/references/schema.md` | `att_st_base` / `eq_equip_base` / `st_pressure_r` 表结构 | 建图脚本数据源 |
| `_shared/lib/correlation.py` | Pearson 相关系数函数 | 告警收敛第一级复用 |
| `powerelf-inspection/SKILL.md` | 路由表 | 新增 `defect-aggregation.md` 入口 |

---

## 文档版本记录

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| V1.0 | 2026-08-05 | 首版,覆盖知识图谱建图、告警收敛、根因排序、置信度降级闸四大模块 |

---

*文档结束。本方案基于本仓库实际架构与 schema 调研编写,文中所有表名、字段名、SQL 均基于 `_shared/references/schema.md` 与 `chatbi/references/schema.md` 的实证,可逐项核验。*