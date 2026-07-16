-- ============================================================
-- 完整测试数据集 - 覆盖所有场景
-- 版本: v1.0
-- 日期: 2026-06-09
-- 说明: 覆盖103个测试问题的所有场景
-- ============================================================

-- 清理旧测试数据
DELETE FROM ew_info_message WHERE ew_name LIKE 'TEST_%';
DELETE FROM st_rsvr_r WHERE eq_code LIKE 'TEST_%';
DELETE FROM st_pptn_r WHERE eq_code LIKE 'TEST_%';
DELETE FROM st_pressure_r WHERE eq_code LIKE 'TEST_%';
DELETE FROM st_percolation_r WHERE eq_code LIKE 'TEST_%';
DELETE FROM weather_warn WHERE docid LIKE 'TEST_%';

-- ============================================================
-- 场景1: 正常告警（基础知识问答 Q1-Q12）
-- ============================================================

-- 最近7天未确认告警（Q1）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES
('TEST_水位预警_未确认1', 'TEST_ST001', 'TEST_EQ001', '0', '1', '462.5', DATE_SUB(NOW(), INTERVAL 3 DAY), 0, '1', '水位超过警戒线', DATE_SUB(NOW(), INTERVAL 3 DAY), 0, 18),
('TEST_水位预警_未确认2', 'TEST_ST001', 'TEST_EQ001', '0', '2', '459.0', DATE_SUB(NOW(), INTERVAL 5 DAY), 0, '1', '水位接近警戒线', DATE_SUB(NOW(), INTERVAL 5 DAY), 0, 18),
('TEST_雨量预警_未确认', 'TEST_ST002', 'TEST_EQ002', '2', '1', '105.0', DATE_SUB(NOW(), INTERVAL 2 DAY), 0, '1', '1小时降雨量超过100mm', DATE_SUB(NOW(), INTERVAL 2 DAY), 0, 18),
('TEST_渗流预警_未确认', 'TEST_ST003', 'TEST_EQ003', '20', '2', '28.5', DATE_SUB(NOW(), INTERVAL 4 DAY), 0, '1', '渗流量超过二级阈值', DATE_SUB(NOW(), INTERVAL 4 DAY), 0, 18);

-- 最近30天各级别告警（Q2）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES
('TEST_红色告警_L1', 'TEST_ST004', 'TEST_EQ004', '0', '1', '465.0', DATE_SUB(NOW(), INTERVAL 15 DAY), 1, '1', '水位红色预警', DATE_SUB(NOW(), INTERVAL 15 DAY), 0, 18),
('TEST_橙色告警_L2', 'TEST_ST005', 'TEST_EQ005', '2', '2', '80.0', DATE_SUB(NOW(), INTERVAL 20 DAY), 1, '1', '雨量橙色预警', DATE_SUB(NOW(), INTERVAL 20 DAY), 0, 18),
('TEST_黄色告警_L3', 'TEST_ST006', 'TEST_EQ006', '20', '3', '20.0', DATE_SUB(NOW(), INTERVAL 10 DAY), 1, '1', '渗流三级预警', DATE_SUB(NOW(), INTERVAL 10 DAY), 0, 18),
('TEST_蓝色告警_L4', 'TEST_ST007', 'TEST_EQ007', '12', '4', NULL, DATE_SUB(NOW(), INTERVAL 8 DAY), 0, '1', '设备离线', DATE_SUB(NOW(), INTERVAL 8 DAY), 0, 18);

-- 最近3天告警列表（Q3）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES
('TEST_最近告警_1', 'TEST_ST008', 'TEST_EQ008', '0', '1', '461.0', DATE_SUB(NOW(), INTERVAL 1 DAY), 0, '1', '水位预警', DATE_SUB(NOW(), INTERVAL 1 DAY), 0, 18),
('TEST_最近告警_2', 'TEST_ST009', 'TEST_EQ009', '2', '2', '55.0', DATE_SUB(NOW(), INTERVAL 2 DAY), 0, '1', '雨量预警', DATE_SUB(NOW(), INTERVAL 2 DAY), 0, 18),
('TEST_最近告警_3', 'TEST_ST010', 'TEST_EQ010', '20', '3', '22.0', DATE_SUB(NOW(), INTERVAL 3 DAY), 0, '1', '渗流预警', DATE_SUB(NOW(), INTERVAL 3 DAY), 0, 18);

-- ============================================================
-- 场景2: 三域关联高风险（Q64, Q75）
-- ============================================================

-- 水位告警（红色）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_三域_水位红色', 'TEST_DAM001', 'TEST_DAM_EQ001', '0', '1', '465.5', NOW(), 0, '1', '水位超过警戒线', NOW(), 0, 18);

-- 降雨告警（橙色）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_三域_降雨橙色', 'TEST_DAM002', 'TEST_DAM_EQ002', '2', '2', '75.0', NOW(), 0, '1', '1小时降雨量超过70mm', NOW(), 0, 18);

-- 渗流告警（黄色）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_三域_渗流黄色', 'TEST_DAM003', 'TEST_DAM_EQ003', '20', '3', '32.0', NOW(), 0, '1', '渗流量超过三级阈值', NOW(), 0, 18);

-- ============================================================
-- 场景3: 告警风暴（Q73, Q92）
-- ============================================================

-- 生成50+条告警模拟告警风暴
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
SELECT
  CONCAT('TEST_风暴_', seq) as ew_name,
  CONCAT('TEST_STORM_', FLOOR(seq/10)) as st_code,
  CONCAT('TEST_STORM_EQ_', seq) as eq_code,
  CASE WHEN seq % 3 = 0 THEN '0' WHEN seq % 3 = 1 THEN '2' ELSE '20' END as ew_type,
  CASE WHEN seq % 4 = 0 THEN '1' WHEN seq % 4 = 1 THEN '2' WHEN seq % 4 = 2 THEN '3' ELSE '4' END as level_r,
  CAST(450 + seq AS CHAR) as value,
  DATE_SUB(NOW(), INTERVAL seq MINUTE) as gather_time,
  0 as message_confirm,
  '1' as ew_rules_type,
  CONCAT('告警风暴测试 #', seq) as content,
  DATE_SUB(NOW(), INTERVAL seq MINUTE) as create_time,
  0 as deleted,
  18 as tenant_id
FROM (
  SELECT a.N + b.N * 10 + 1 as seq
  FROM (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
       (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5) b
) numbers
WHERE seq <= 60;

-- ============================================================
-- 场景4: 持续告警（Q65, Q98）
-- ============================================================

-- 24小时持续告警
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES
('TEST_持续_水位1', 'TEST_PERSIST001', 'TEST_PERSIST_EQ001', '0', '1', '463.0', DATE_SUB(NOW(), INTERVAL 24 HOUR), 0, '1', '水位持续高位', DATE_SUB(NOW(), INTERVAL 24 HOUR), 0, 18),
('TEST_持续_水位2', 'TEST_PERSIST001', 'TEST_PERSIST_EQ001', '0', '1', '463.5', DATE_SUB(NOW(), INTERVAL 20 HOUR), 0, '1', '水位持续高位', DATE_SUB(NOW(), INTERVAL 20 HOUR), 0, 18),
('TEST_持续_水位3', 'TEST_PERSIST001', 'TEST_PERSIST_EQ001', '0', '1', '464.0', DATE_SUB(NOW(), INTERVAL 16 HOUR), 0, '1', '水位持续高位', DATE_SUB(NOW(), INTERVAL 16 HOUR), 0, 18),
('TEST_持续_水位4', 'TEST_PERSIST001', 'TEST_PERSIST_EQ001', '0', '2', '462.0', DATE_SUB(NOW(), INTERVAL 12 HOUR), 0, '1', '水位开始下降', DATE_SUB(NOW(), INTERVAL 12 HOUR), 0, 18),
('TEST_持续_水位5', 'TEST_PERSIST001', 'TEST_PERSIST_EQ001', '0', '2', '461.0', DATE_SUB(NOW(), INTERVAL 8 HOUR), 0, '1', '水位继续下降', DATE_SUB(NOW(), INTERVAL 8 HOUR), 0, 18),
('TEST_持续_水位6', 'TEST_PERSIST001', 'TEST_PERSIST_EQ001', '0', '3', '460.0', DATE_SUB(NOW(), INTERVAL 4 HOUR), 0, '1', '水位恢复正常', DATE_SUB(NOW(), INTERVAL 4 HOUR), 0, 18);

-- ============================================================
-- 场景5: 告警升级（Q33, Q80）
-- ============================================================

INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES
('TEST_升级_L4', 'TEST_ESC001', 'TEST_ESC_EQ001', '0', '4', '458.0', DATE_SUB(NOW(), INTERVAL 12 HOUR), 1, '1', '水位四级预警', DATE_SUB(NOW(), INTERVAL 12 HOUR), 0, 18),
('TEST_升级_L3', 'TEST_ESC001', 'TEST_ESC_EQ001', '0', '3', '459.0', DATE_SUB(NOW(), INTERVAL 10 HOUR), 1, '1', '水位三级预警', DATE_SUB(NOW(), INTERVAL 10 HOUR), 0, 18),
('TEST_升级_L2', 'TEST_ESC001', 'TEST_ESC_EQ001', '0', '2', '460.0', DATE_SUB(NOW(), INTERVAL 8 HOUR), 0, '1', '水位二级预警', DATE_SUB(NOW(), INTERVAL 8 HOUR), 0, 18),
('TEST_升级_L1', 'TEST_ESC001', 'TEST_ESC_EQ001', '0', '1', '461.0', DATE_SUB(NOW(), INTERVAL 6 HOUR), 0, '1', '水位一级预警', DATE_SUB(NOW(), INTERVAL 6 HOUR), 0, 18);

-- ============================================================
-- 场景6: 设备离线（Q11, Q74, Q89）
-- ============================================================

INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES
('TEST_设备离线_1', 'TEST_OFF001', 'TEST_OFF_EQ001', '12', '3', NULL, DATE_SUB(NOW(), INTERVAL 2 HOUR), 0, '1', '设备离线', DATE_SUB(NOW(), INTERVAL 2 HOUR), 0, 18),
('TEST_设备离线_2', 'TEST_OFF002', 'TEST_OFF_EQ002', '12', '3', NULL, DATE_SUB(NOW(), INTERVAL 3 HOUR), 0, '1', '设备离线', DATE_SUB(NOW(), INTERVAL 3 HOUR), 0, 18),
('TEST_设备离线_3', 'TEST_OFF003', 'TEST_OFF_EQ003', '12', '4', NULL, DATE_SUB(NOW(), INTERVAL 1 HOUR), 0, '1', '设备离线', DATE_SUB(NOW(), INTERVAL 1 HOUR), 0, 18);

-- ============================================================
-- 场景7: 边界场景（Q94-Q98）
-- ============================================================

-- 仅有蓝色告警（Q94）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES
('TEST_边界_蓝色1', 'TEST_BOUND001', 'TEST_BOUND_EQ001', '0', '4', '458.0', NOW(), 0, '1', '低水位预警', NOW(), 0, 18),
('TEST_边界_蓝色2', 'TEST_BOUND002', 'TEST_BOUND_EQ002', '2', '4', '15.0', NOW(), 0, '1', '小雨', NOW(), 0, 18),
('TEST_边界_蓝色3', 'TEST_BOUND003', 'TEST_BOUND_EQ003', '20', '4', '12.0', NOW(), 0, '1', '渗流四级', NOW(), 0, 18);

-- 单条红色告警无关联（Q95）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_边界_单红', 'TEST_BOUND004', 'TEST_BOUND_EQ004', '0', '1', '466.0', NOW(), 0, '1', '水位红色预警', NOW(), 0, 18);

-- 所有告警已确认（Q97）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES
('TEST_已确认_1', 'TEST_CONF001', 'TEST_CONF_EQ001', '0', '1', '463.0', NOW(), 1, '1', '已确认水位预警', NOW(), 0, 18),
('TEST_已确认_2', 'TEST_CONF002', 'TEST_CONF_EQ002', '2', '2', '60.0', NOW(), 1, '1', '已确认雨量预警', NOW(), 0, 18),
('TEST_已确认_3', 'TEST_CONF003', 'TEST_CONF_EQ003', '20', '3', '25.0', NOW(), 1, '1', '已确认渗流预警', NOW(), 0, 18);

-- ============================================================
-- 场景8: 水位数据（Q66, Q79, Q82）
-- ============================================================

-- 生成24小时水位数据（上升趋势）
INSERT INTO st_rsvr_r (eq_code, rz, tm, deleted, tenant_id)
SELECT
  'TEST_WL001' as eq_code,
  450.0 + (seq * 0.1) as rz,
  DATE_SUB(NOW(), INTERVAL (24 - seq) HOUR) as tm,
  0 as deleted,
  18 as tenant_id
FROM (
  SELECT a.N + b.N * 10 as seq
  FROM (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
       (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2) b
) numbers
WHERE seq <= 24;

-- 生成24小时水位数据（下降趋势）
INSERT INTO st_rsvr_r (eq_code, rz, tm, deleted, tenant_id)
SELECT
  'TEST_WL002' as eq_code,
  465.0 - (seq * 0.15) as rz,
  DATE_SUB(NOW(), INTERVAL (24 - seq) HOUR) as tm,
  0 as deleted,
  18 as tenant_id
FROM (
  SELECT a.N + b.N * 10 as seq
  FROM (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
       (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2) b
) numbers
WHERE seq <= 24;

-- ============================================================
-- 场景9: 降雨数据（Q22, Q74）
-- ============================================================

-- 生成24小时降雨数据
INSERT INTO st_pptn_r (eq_code, p, tm, deleted, tenant_id)
SELECT
  'TEST_RAIN001' as eq_code,
  CASE WHEN seq % 6 = 0 THEN 10.0 ELSE 0.0 END as p,
  DATE_SUB(NOW(), INTERVAL (24 - seq) HOUR) as tm,
  0 as deleted,
  18 as tenant_id
FROM (
  SELECT a.N + b.N * 10 as seq
  FROM (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
       (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2) b
) numbers
WHERE seq <= 24;

-- ============================================================
-- 场景10: 渗压数据（Q16, Q75）
-- ============================================================

-- 生成渗压数据
INSERT INTO st_pressure_r (eq_code, water_pressure, tm, deleted, tenant_id)
VALUES
('TEST_PRES001', 35.0, DATE_SUB(NOW(), INTERVAL 24 HOUR), 0, 18),
('TEST_PRES001', 36.5, DATE_SUB(NOW(), INTERVAL 18 HOUR), 0, 18),
('TEST_PRES001', 38.0, DATE_SUB(NOW(), INTERVAL 12 HOUR), 0, 18),
('TEST_PRES001', 37.5, DATE_SUB(NOW(), INTERVAL 6 HOUR), 0, 18),
('TEST_PRES001', 37.0, NOW(), 0, 18);

-- ============================================================
-- 场景11: 渗流数据（Q16, Q75）
-- ============================================================

-- 生成渗流数据
INSERT INTO st_percolation_r (eq_code, percolation, tm, deleted, tenant_id)
VALUES
('TEST_PERC001', 0.25, DATE_SUB(NOW(), INTERVAL 24 HOUR), 0, 18),
('TEST_PERC001', 0.28, DATE_SUB(NOW(), INTERVAL 18 HOUR), 0, 18),
('TEST_PERC001', 0.32, DATE_SUB(NOW(), INTERVAL 12 HOUR), 0, 18),
('TEST_PERC001', 0.30, DATE_SUB(NOW(), INTERVAL 6 HOUR), 0, 18),
('TEST_PERC001', 0.29, NOW(), 0, 18);

-- ============================================================
-- 场景12: 气象预警（Q77, Q102, Q103）
-- ============================================================

INSERT INTO weather_warn (docid, docabstract, chnlname, model_type, docpubtime, docpuburl, warn_status, update_time)
VALUES
('TEST_WARN001', 'TEST_暴雨黄色预警：预计未来24小时内将出现50-80mm降雨', '气象预警', '暴雨', DATE_SUB(NOW(), INTERVAL 6 HOUR), 'http://test.url', '1', NOW()),
('TEST_WARN002', 'TEST_大风蓝色预警：预计未来24小时将出现6级以上大风', '气象预警', '大风', DATE_SUB(NOW(), INTERVAL 12 HOUR), 'http://test.url', '1', NOW());

-- ============================================================
-- 场景13: 不存在的测站（Q89）
-- ============================================================

-- 不插入数据，测试查询不存在测站时的行为

-- ============================================================
-- 场景14: 数据缺失（Q90）
-- ============================================================

-- 插入告警但不插入对应的水位数据
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_数据缺失_水位', 'TEST_MISSING001', 'TEST_MISSING_EQ001', '0', '2', '456.0', NOW(), 0, '1', '水位预警（无对应水位数据）', NOW(), 0, 18);

-- ============================================================
-- 场景15: 跨日告警（Q98）
-- ============================================================

INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_跨日_告警', 'TEST_CROSS001', 'TEST_CROSS_EQ001', '0', '2', '460.0', DATE_SUB(NOW(), INTERVAL 14 HOUR), 0, '1', '跨日持续告警', DATE_SUB(NOW(), INTERVAL 14 HOUR), 0, 18);

-- ============================================================
-- 验证数据
-- ============================================================

SELECT '告警数据' as category, COUNT(*) as count FROM ew_info_message WHERE ew_name LIKE 'TEST_%'
UNION ALL
SELECT '水位数据', COUNT(*) FROM st_rsvr_r WHERE eq_code LIKE 'TEST_%'
UNION ALL
SELECT '降雨数据', COUNT(*) FROM st_pptn_r WHERE eq_code LIKE 'TEST_%'
UNION ALL
SELECT '渗压数据', COUNT(*) FROM st_pressure_r WHERE eq_code LIKE 'TEST_%'
UNION ALL
SELECT '渗流数据', COUNT(*) FROM st_percolation_r WHERE eq_code LIKE 'TEST_%'
UNION ALL
SELECT '气象预警', COUNT(*) FROM weather_warn WHERE docid LIKE 'TEST_%';
