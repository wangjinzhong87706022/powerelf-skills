-- 数据缺失测试数据：模拟水位数据缺失场景

-- 清理旧测试数据
DELETE FROM ew_info_message WHERE ew_name LIKE 'TEST_%';

-- 插入告警（但对应设备无水位数据）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_水位预警_无数据', '999K9999', '999K999901', '0', '2', '456.0', NOW(), 0, '1', '水位接近警戒线', NOW(), 0, 18);

-- 注意：st_rsvr_r 表中没有 eq_code='999K999901' 的数据
-- 预期结果：
-- alert_summary.total = 1
-- risk_assessment 包含 "数据不完整" 标记
-- trend_prediction.water_level.confidence = "low"
-- trend_prediction.water_level.trend = "unknown"
