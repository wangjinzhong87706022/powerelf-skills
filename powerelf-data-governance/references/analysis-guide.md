# 核心分析能力指南

> 本文件包含所有分析方法的详细说明。
> **按需加载**：仅在需要深度分析时读取本文件。

---

## 1. MAD 异常检测

自适应窗口 MAD + 变化率检测 + 综合判定。

| 指标 | 阈值 | 理由 |
|------|------|------|
| 水位(rz/z) | 3.0 | 日变化平缓，异常容易识别 |
| 雨量(p) | 5.0 | 波动大，需要更高容忍度 |
| 渗压(water_pressure/ext_pressure) | 4.0 | 中等波动 |
| 渗流(percolation)/流量(inq/otq) | 4.0 | 中等波动 |
| GNSS位移(wgs84_delta_h) | 3.5 | 缓慢变化，突变即异常 |
| 通用默认 | 4.0 | 兜底值 |

**详见**：`rules/anomaly-detection.md`

---

## 2. 智能插值

四策略自适应选择 + 置信度评估。

| 策略 | 适用场景 |
|------|---------|
| 线性插值 | 趋势平稳 |
| 二次插值 | 有趋势变化 |
| 样条插值 | 曲线平滑 |
| 滑动平均 | 高频噪声 |

**详见**：`rules/interpolation.md`

---

## 3. 质量评分

四维度加权评分（35%+10%+40%+15%）。

| 维度 | 权重 | 说明 |
|------|------|------|
| 完整性 | 35% | 缺失率 |
| 准确性 | 10% | 异常率 |
| 及时性 | 40% | 离线时长 |
| 一致性 | 15% | 采集频率 |

**详见**：`rules/quality-scoring.md`

---

## 4. 缺失检测

期望周期数比较 + 连续缺失递增告警 + 模式识别。

**详见**：`rules/missing-detection.md`

---

## 5. 离线检测

三态判定 + 渐进式告警 + 离线时长分级 + MTTR。

**详见**：`rules/offline-detection.md`

---

## 6. 卡滞检测

传感器连续输出相同值检测。

**API**: `stagnation.detect_stagnation(data, threshold=0.001, window=10)`

---

## 7. 极端事件区分

区分汛期高水位等合法极端事件与数据异常。

**API**: `extreme_event.classify_extreme_event(value, context)`

---

## 8. 相关性异常

跨指标物理矛盾检测（渗压-渗流/水位-渗流等 5 规则）。

**API**: `correlation.detect_correlation_anomaly(data)`

---

## 9. 设备上下文关联

异常 + 知识库 + 运维建议。

**API**: `device_context.analyze_with_context(device_id)`

---

## 10. 知识检索

多后端统一检索（MySQL/RAGFlow/ES/Chroma/HTTP）。

**API**: `knowledge.search_knowledge(query, backend='mysql')`

---

## 11. 数据回写

异常修复 / 缺失填补 / 设备状态 / 离线记录 CRUD。

| 操作 | 函数 |
|------|------|
| 修复异常 | `writeback.fix_anomaly(conn, id, fix_data)` |
| 填补缺失 | `writeback.fill_missing(conn, id, filled_data)` |
| 更新设备状态 | `writeback.update_device_status(conn, device_id, status)` |

---

## 12. 报告生成

| 报告类型 | 调用方式 |
|---------|---------|
| 数据质量日报 | `report.generate_daily_report_from_db(date)` |
| 异常分析报告 | `report.generate_anomaly_report()` |
| 评分报告 | `report.generate_score_report()` |

**输出格式**: Markdown / JSON / HTML / PDF

---

**模块架构**: 见 `lib/` 目录
**算法详情**: 见 `algorithms/` 目录
