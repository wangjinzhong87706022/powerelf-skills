-- 高风险测试数据：模拟三域关联场景
-- 水位告警 + 降雨告警 + 渗流告警

-- 清理旧测试数据
DELETE FROM ew_info_message WHERE ew_name LIKE 'TEST_%';

-- 插入水位告警（红色）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_高水位预警', '606K2155', '606K215502', '0', '1', '459.2', NOW(), 0, '1', '水位超过警戒线', NOW(), 0, 18);

-- 插入降雨告警（橙色）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_强降雨预警', '606K2156', '606K215601', '2', '2', '52.5', NOW(), 0, '1', '1小时降雨量超过50mm', NOW(), 0, 18);

-- 插入渗流告警（黄色）
INSERT INTO ew_info_message (ew_name, st_code, eq_code, ew_type, level_r, value, gather_time, message_confirm, ew_rules_type, content, create_time, deleted, tenant_id)
VALUES ('TEST_渗流量增大', '606K2157', '606K215701', '20', '3', '35.8', NOW(), 0, '1', '渗流量超过正常范围', NOW(), 0, 18);

-- 预期结果：
-- alert_summary.total = 3
-- alert_summary.by_level = {"red": 1, "orange": 1, "yellow": 1}
-- alert_summary.by_type = {"water_level": 1, "rainfall": 1, "seepage": 1}
-- correlation_analysis.compound_risks 包含 dam_risk (三域关联)
-- risk_assessment.risk_level = "high" (红色告警+三域关联直接判定)
-- plan_trigger.recommended = true
