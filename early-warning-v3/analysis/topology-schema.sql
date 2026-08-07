-- ============================================================
-- topology-schema.sql — 水利对象知识图谱存储表
-- ============================================================
-- 用途: 把散落在 att_st_base / eq_equip_base / att_dam_base /
--       att_dam_section / st_pressure_r / dsm_dfr_srvrds_srhrds 等
--       十余张表里的隐式拓扑关系, 抽取为统一的"节点表 + 边表",
--       供 compute_blast_radius / find_fault_cluster 做 BFS 查询,
--       供 rank_root_causes 做根因排序.
--
-- 设计原则:
--   1. 轻量 MySQL 边表方案, 不引入 Neo4j (告警侧 BFS 1-2 跳够用)
--   2. node_id 统一格式 {type}:{ref_id}, 一张表存所有节点类型
--   3. edge_type 限定 4 种: belongs_to / upstream_of / causes / near
--   4. 所有表带 deleted 软删 + tenant_id 多租户, 与业务表一致
--
-- 数据来源对照 (建图脚本 build_topology.py 使用):
--   station 节点  ← att_st_base (id, code, name, longitude, latitude, project_id)
--   device 节点   ← eq_equip_base (id, code, name, type_flag, status, st_base_id)
--   project 节点  ← att_st_base.project_id 聚合 / att_res_base
--   dam 节点      ← att_dam_base (id, dam_code, dam_name, start_long, start_lat, ...)
--   section 节点  ← att_dam_section (id, dam_code, code, name, point_ids JSON)
--   point 节点    ← att_st_point (id, name, code, st_id, eq_id, lgtd, lttd, stel)
--                  + att_st_dot (id, st_id, eq_id, point_id, name, indicator_type)
--
-- 边来源对照:
--   belongs_to device→station  ← eq_equip_base.st_base_id
--   belongs_to station→project ← att_st_base.project_id
--   belongs_to section→dam     ← att_dam_section.dam_code ↔ att_dam_base.dam_code
--   belongs_to point→section   ← att_dam_section.point_ids JSON 数组包含 point_id
--   belongs_to dam→project     ← att_dam_base.dam_code 关联 (需通过 att_st_base 同水库)
--   upstream_of station→station← att_st_base 经纬度空间推断 (haversine < 10km, 雨量→水库)
--   causes     *→*             ← causal-rules.json 规则匹配
--   near       point↔point     ← 同 section_id 的 point 两两组合
--   near       station↔station ← 经纬度 haversine < 1km
-- ============================================================


-- ============================================================
-- 表 1: topo_node — 拓扑节点表 (统一存所有水利对象)
-- ============================================================
DROP TABLE IF EXISTS topo_node;
CREATE TABLE topo_node (
  node_id     VARCHAR(64)  NOT NULL                COMMENT '节点唯一ID, 格式 {type}:{ref_id}, 如 station:123',
  node_type   VARCHAR(20)  NOT NULL                COMMENT '节点类型: project/station/device/dam/section/point/inspection_obj',
  ref_id      BIGINT       NOT NULL                COMMENT '原表主键 (att_st_base.id / eq_equip_base.id / att_dam_base.id 等)',
  name        VARCHAR(255)          DEFAULT NULL   COMMENT '节点显示名 (测站名/设备名/大坝名等)',
  project_id  BIGINT                DEFAULT NULL   COMMENT '所属工程ID, 冗余字段加速按工程过滤',
  properties  JSON                  DEFAULT NULL   COMMENT '灵活属性: 经纬度/status/type_flag/subtype 等',
  tenant_id   BIGINT       NOT NULL DEFAULT 1      COMMENT '租户编号',
  deleted     BIT(1)       NOT NULL DEFAULT b'0'   COMMENT '是否删除',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (node_id),
  UNIQUE KEY uk_type_ref (node_type, ref_id),
  KEY idx_project (project_id),
  KEY idx_type (node_type),
  KEY idx_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='水利对象拓扑节点表 — 知识图谱节点存储';


-- ============================================================
-- 表 2: topo_edge — 拓扑边表 (统一存 4 种关系)
-- ============================================================
DROP TABLE IF EXISTS topo_edge;
CREATE TABLE topo_edge (
  id          BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键',
  from_node   VARCHAR(64)  NOT NULL                 COMMENT '起始节点 node_id',
  to_node     VARCHAR(64)  NOT NULL                 COMMENT '目标节点 node_id',
  edge_type   VARCHAR(20)  NOT NULL                 COMMENT '边类型: belongs_to/upstream_of/causes/near',
  weight      DECIMAL(5,2) NOT NULL DEFAULT 1.00    COMMENT '边权重 [0.00, 1.00], 用于根因打分',
  lag_min     INT                   DEFAULT NULL    COMMENT 'causes 边的典型因果延迟(分钟), 其他类型为 NULL',
  evidence    VARCHAR(500)          DEFAULT NULL    COMMENT '边依据, 如 "att_st_base.project_id" 或 "空间推断:haversine 3.2km"',
  rule_id     VARCHAR(30)           DEFAULT NULL    COMMENT 'causes 边的规则ID, 指向 causal-rules.json 的 rule_id',
  tenant_id   BIGINT       NOT NULL DEFAULT 1       COMMENT '租户编号',
  deleted     BIT(1)       NOT NULL DEFAULT b'0'    COMMENT '是否删除',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_edge (from_node, to_node, edge_type),
  KEY idx_from_type (from_node, edge_type),
  KEY idx_to_type (to_node, edge_type),
  KEY idx_edge_type (edge_type),
  KEY idx_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='水利对象拓扑边表 — 知识图谱关系存储';


-- ============================================================
-- 表 3: topo_alarm_event — 告警聚合后的故障事件表
-- ============================================================
-- 用途: 告警收敛算法 aggregate_alarms_to_events 的输出落盘,
--       供根因排序 rank_root_causes 读取, 供历史复发率统计查询.
-- ============================================================
DROP TABLE IF EXISTS topo_alarm_event;
CREATE TABLE topo_alarm_event (
  event_id        VARCHAR(40)  NOT NULL             COMMENT '事件ID, 格式 EVT-{yyyyMMdd}-{seq3}, 如 EVT-20260805-001',
  tenant_id       BIGINT       NOT NULL DEFAULT 1   COMMENT '租户编号',
  start_time      DATETIME     NOT NULL             COMMENT '事件首条告警时间',
  end_time        DATETIME     NOT NULL             COMMENT '事件末条告警时间',
  max_level       CHAR(2)      NOT NULL             COMMENT '事件内最高告警级别 1=红色/2=橙色/3=黄色/4=蓝色',
  alarm_count     INT          NOT NULL DEFAULT 0   COMMENT '事件内告警总数',
  affected_nodes  JSON                  DEFAULT NULL COMMENT '事件涉及的节点 node_id 列表',
  cluster_id      INT                   DEFAULT NULL COMMENT '故障团ID (union-find 连通分量编号)',
  centroid_node   VARCHAR(64)           DEFAULT NULL COMMENT '团内度数最高的节点 (近似根因)',
  severity_score  DECIMAL(5,2)          DEFAULT NULL COMMENT '团的严重程度评分 [0.00, 1.00]',
  root_cause_node VARCHAR(64)           DEFAULT NULL COMMENT '根因排序后的 TOP1 节点 node_id',
  root_cause_conf DECIMAL(5,2)          DEFAULT NULL COMMENT 'TOP1 根因的置信度 [0.00, 1.00]',
  root_cause_rank JSON                  DEFAULT NULL COMMENT '完整 TOPN 根因排序结果 (含五维分数)',
  status          VARCHAR(20)  NOT NULL DEFAULT 'open' COMMENT '事件状态: open/confirmed/resolved/escalated',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (event_id),
  KEY idx_start (start_time),
  KEY idx_level (max_level),
  KEY idx_status (status),
  KEY idx_tenant (tenant_id),
  KEY idx_root_cause (root_cause_node)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警聚合故障事件表 — 告警收敛 + 根因排序落盘';


-- ============================================================
-- 索引补充 (在 ew_info_message 上加索引, 加速告警→节点映射)
-- ============================================================
-- 注: ew_info_message 已有 st_code / level_r 等字段, 这里只补
--     告警聚合查询最常用的联合索引, 避免全表扫描.

-- 告警聚合常用: WHERE deleted=0 AND tenant_id=? AND create_time >= ?
ALTER TABLE ew_info_message
  ADD INDEX idx_agg_tenant_time (tenant_id, deleted, create_time) COMMENT '告警聚合加速索引';

-- 告警→节点映射常用: WHERE st_code=? AND deleted=0
-- (st_code 已有单独索引的话可省略, 这里保守加一条)
ALTER TABLE ew_info_message
  ADD INDEX idx_st_code_deleted (st_code, deleted) COMMENT '按测站查告警加速索引';


-- ============================================================
-- 验证查询 (建表后执行, 确认表结构正确)
-- ============================================================
-- SHOW CREATE TABLE topo_node\G
-- SHOW CREATE TABLE topo_edge\G
-- SHOW CREATE TABLE topo_alarm_event\G
--
-- -- 确认节点表为空 (建图脚本运行前)
-- SELECT COUNT(*) AS node_count FROM topo_node;
-- SELECT COUNT(*) AS edge_count FROM topo_edge;
-- SELECT COUNT(*) AS event_count FROM topo_alarm_event;


-- ============================================================
-- 完毕
-- ============================================================
