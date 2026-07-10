# 数据治理 Skill — 基于真实数据的测试问题集

> 本文档基于 `powerelf_srm_yml` 数据库中的**实际数据**构造测试问题，用于验证
> `powerelf-data-governance` skill 各模块功能的正确性。
>
> 数据库状态基准日: **2026-07-08**

---

## 测试前提

```bash
# 环境变量（~/.hermes/.env 已配置；切勿在此写入真实密码）
export SRM_DB_HOST=127.0.0.1
export SRM_DB_PORT=3306
export SRM_DB_NAME=powerelf_srm_yml
export SRM_DB_USER=root
export SRM_DB_PASSWORD="${SRM_DB_PASSWORD}"   # 从 ~/.hermes/.env 读取，文档中不落盘明文
```

> ⚠️ **安全提示**：本文件历史版本曾包含明文密码 `123456aA.`，该凭证已随仓库历史泄露，
> **请立即在数据库侧轮换该密码**。后续所有密码一律通过环境变量注入，禁止写进文档。

---

## 1. MAD 异常检测

### T1.1 128号测站水位异常检测

```
请检测128号测站(st_rsvr_r)最近1周的水位(rz)数据是否有异常。
```

**预期**: 2026-05-14 ~ 2026-05-20 期间检测。

| tm | rz | inq | otq | 说明 |
|----|-----|-----|-----|------|
| 2026-05-20 12:00 | 440.000 | 10.000 | 200.000 | 数据截止点 |
| 2026-05-15 08:00 | 500.000 | 200.000 | 50.000 | 前一记录点 |

5月15日到20日水位从 500 → 440（↓60），变化率 = |440-500|/500 = **12%**，
远超水位变化率阈值 5%，应标记为**确认异常（高置信度）**。

**验证命令**:
```bash
python3 impl/anomaly_detector.py \
  --db "$DB_URL" \
  --table st_rsvr_r --field rz --threshold 3.0 --st-id 128 --days 7
```

---

### T1.2 416号测站渗压异常检测

```
检测416号测站(st_pressure_r)渗压数据最近7天的异常值。
```

**预期**: 5/29 wp=450.0 相比前日 5/28 wp=430.5 变化率 = |450-430.5|/430.5 ≈ **4.5%**，
超过渗压变化率阈值 3%，应标记为**确认异常**。

| tm | water_pressure | ext_pressure |
|----|---------------|--------------|
| 2026-05-29 12:00 | 450.00000 | 60.00000 |
| 2026-05-29 08:00 | 431.20000 | 54.80000 |
| 2026-05-28 08:00 | 430.50000 | 54.50000 |
| 2026-05-27 19:00 | 430.57300 | NULL |

**验证命令**:
```bash
python3 impl/anomaly_detector.py \
  --db "$DB_URL" \
  --table st_pressure_r --field water_pressure --threshold 4.0 --st-id 416 --days 7
```

---

### T1.3 全量水位MAD检测

```
对st_rsvr_r表的rz字段做全量MAD异常检测（5月份）。
```

**预期**: 水位日变化平缓（阈值 3.0），极端跳跃应被检出。5月15日 500→440 至少在 TOP 异常中。

**验证命令**:
```bash
python3 impl/anomaly_detector.py \
  --db "$DB_URL" \
  --table st_rsvr_r --field rz --threshold 3.0 --days 30
```

---

### T1.4 雨量异常检测

```
检测雨量数据(st_pptn_r)最近7天是否有异常。
```

**预期**: 雨量阈值 5.0（最高容忍度），较小波动不报警，极端值才标记。

**验证命令**:
```bash
python3 impl/anomaly_detector.py \
  --db "$DB_URL" \
  --table st_pptn_r --field p --threshold 5.0 --days 7
```

---

## 2. 缺失检测

### T2.1 128号测站缺失检测

```
检查128号测站2026年5月的st_rsvr_r数据是否有缺失。
```

**预期**: 计算期望周期数（采集频率60min），与实际记录数比较。
5月应有 31天 × 24 = 744 条，实际可能不足，尤其5/15~5/20期间数据稀疏。

**验证命令**:
```bash
python3 impl/missing_detector.py \
  --db "$DB_URL" \
  --table st_rsvr_r --st-id 128 --freq 60 --days 31
```

---

### T2.2 渗压表缺失模式分析

```
分析st_pressure_r表416号测站2026年5月的缺失模式。
```

**预期**: 
- 5月共31天 × 24 = 744条（按小时），实际仅数百条
- 判断缺失是**周期性**（每天固定时段）还是**随机**（无规律）
- 如果是连续3天同时段缺失 → 周期性（定时维护/信号遮挡）

---

### T2.3 缺失率趋势

```
分析最近一周(stats_data_missing_daily)的缺失率趋势。
```

**预期**: 环比变化 > 50% 预警；连续3天缺失率 > 10% 预警。
查询 `stats_data_collection_daily` + `stats_data_missing_daily` 做趋势分析。

---

## 3. 离线检测

### T3.1 单设备离线判定

```
检查设备104(西坝咀雨量计)当前是否离线。
```

**预期**: 
- 设备104 type_flag=8(雨量计), 离线阈值 `dg_equip_offline` 中 SP 类型 = 360min
- eq_data_anomaly_record 中状态 status=2(异常)
- 最新数据时间可能已超过阈值，应判定 OFFLINE

**验证命令**:
```bash
python3 impl/offline_detector.py \
  --db "$DB_URL" \
  --table st_pptn_r --st-id 104 --threshold 360
```

---

### T3.2 批量离线检测

```
哪些设备离线超过24小时了？
```

**预期**: 从 `eq_equip_offline_record` 筛选 `total_offline_duration > 86400`。
585 条离线记录中应筛选出长时间离线的设备。

---

### T3.3 MTTR 计算

```
计算最近30天的平均修复时间(MTTR)。
```

**预期**: MTTR = mean(最近30天的 `eq_equip_offline_record.total_offline_duration`)。
> 4小时建议维护。

---

### T3.4 离线时长分级

```
对当前离线的设备按离线时长分级。
```

**预期**: 0-1h=INFO / 1-4h=WARNING / 4-24h=ERROR / >24h=CRITICAL

---

## 4. 质量评分

### T4.1 单设备评分

```
对设备139(振弦渗压计E01)做2026年5月的质量评分。
```

**预期**: 4维度加权评分，需要聚合查询：
- `stats_data_collection_daily` — 采集数
- `stats_data_missing_daily` — 缺失数
- `stats_data_anomaly_daily` — 异常数
- `eq_equip_offline_record` — 离线情况

**最终输出**: 总分 + 4项分维度得分 + 趋势(改善/恶化/稳定)

**验证命令**:
```bash
python3 impl/quality_scorer.py \
  --missing-ratio 0.XX --anomaly-ratio 0.XX \
  --offline-date-ratio 0.XX --anomaly-date-ratio 0.XX \
  --offline-count X --anomaly-count X \
  --actual-records XX --expected-records XX
```

*(参数需先查询实际数据计算)*

---

### T4.2 设备评分对比

```
对比设备140(振弦渗压计E02, status=2异常)和139(同批次, status=0正常)的评分。
```

**预期**: 
- 设备140 status=2，应有异常记录和离线记录
- 评分应显著低于设备139
- 故障频率维度(权重40%)应拉开差距

---

### T4.3 厂商质量排名

```
生成2026年5月的厂商质量排名。
```

**预期**: 按 `eq_equip_base.type_flag` 分组，聚合各维度指标，按总分排序。

---

## 5. 插值修复

### T5.1 自适应插值

```
2026年5月st_pressure_r表416号测站在water_pressure字段上有缺失值，
请用自适应策略填补。
```

**预期**: 
1. 识别缺失位置
2. 按决策树选择策略（线性/二次/样条/滑动平均）
3. 输出插值结果 + 置信度
4. 置信度 < 0.6 标记"需人工复核"

---

### T5.2 水位突变判定与修复建议

```
对128号测站5月15日水位突变点(500→440)，
判断是需要修复的异常还是真实事件。
```

**预期**: 
- 综合判定：MAD异常 + 变化率12% >> 5% → **确认异常（高置信度）**
- 需额外确认：是否有降雨支撑？5月是否为汛期？
- 极端事件判定：若5月非汛期(6-9月)，排除极端事件，更可能是传感器异常

---

## 6. 卡滞检测

### T6.1 传感器卡滞检测

```
检测5月下旬是否有传感器卡滞——多台渗压计连续输出相同值。
```

**预期**: 
- 查询 `st_pressure_r` 连续3次以上相同值的传感器
- 使用 `lib/stagnation.detect_stagnation()`
- 相同值连续 >6 次标记 ERROR，>24 次标记 CRITICAL

---

## 7. 相关性异常

### T7.1 渗压-渗流矛盾检测

```
检查416号测站5月29日渗压数据是否存在物理矛盾。
```

**预期**: 
- wp=450.0(↑), 同期 percolation 若下降则触发"渗压↑且渗流↓"的 HIGH 级别矛盾
- 使用 `lib/correlation.detect_correlation_anomaly()`

---

## 8. 极端事件区分

### T8.1 汛期 vs 异常区分

```
416号测站5/29渗压450 vs 5/28的430.5，区分是极端事件还是传感器异常。
```

**预期**:
- 5月为非汛期（6-9月是汛期）→ 排除汛期极端事件
- 无降雨数据支撑 → 置信度降低
- 最终判定更倾向**传感器异常**而非极端事件

---

## 9. 报告生成

### T9.1 数据质量日报

```
生成2026年5月15日的数据质量日报。
```

### T9.2 异常分析报告

```
生成5月份的异常分析报告。
```

### T9.3 设备评分报告（PDF）

```
输出所有设备的评分报告PDF版本。
```

```python
from lib.report import generate_daily_report, generate_anomaly_report, generate_score_report, to_pdf

# 日报
md = generate_daily_report('2026-05-15', overview, collection, anomalies, offline, score)

# 异常分析
md = generate_anomaly_report(start='2026-05-01', end='2026-05-31')

# 评分报告 PDF
md = generate_score_report(month='2026-05')
to_pdf(md, title='2026年5月设备评分报告', output_path='/tmp/score_report_202605.pdf')
```

---

## 10. 数据回写（谨慎测试）

> ⚠️ 以下测试涉及写操作，建议在**测试环境**或**事务回滚**下执行。

### T10.1 异常修复回写

```
对T1.1检出的水位异常，用插值修复后写回eq_data_anomaly_record。
```

### T10.2 缺失填补回写

```
对T2.1检出的缺失，用插值填补后写回eq_data_missing_record。
```

### T10.3 设备状态更新

```
将离线设备104(西坝咀雨量计)的状态标记为离线。
```

```python
from lib.writeback import fix_anomaly, fill_missing, update_device_status
from lib.db import get_connection

conn = get_connection()
# update_device_status(conn, device_id=104, status=0)
```

---

## 11. 设备上下文关联

### T11.1 智能运维建议

```
设备140(振弦渗压计E02, status=2)出现异常，查询设备上下文并给出运维建议。
```

**预期**: 
```python
from lib.device_context import analyze_with_context

conn = get_connection()
result = analyze_with_context(conn, equipment_code=140, anomaly_type="offline")
# → {device_context: {...}, knowledge: [...], suggestion: {priority, suggestion, actions}}
```

应输出：设备基本信息、历史缺陷、维保记录、优先级建议(P0-P3)、处理动作。

---

## 附录: 数据库关键数据摘要

| 表 | 关键字段 | 数据范围 |
|----|---------|---------|
| st_rsvr_r | st_id(测站), tm, rz(水位), inq(入库), otq(出库) | 2026-01 ~ 2026-07, 19万条 |
| st_pressure_r | st_id, tm, water_pressure, ext_pressure | 2026-05, 1835条 |
| st_pptn_r | st_id, tm, p(雨量) | 2025-12 ~ 2026-06, 26万条 |
| eq_equip_base | id, name, code, type_flag, status | 128台设备 |
| eq_data_missing_record | equipment_code, data_missing_datetime, count | 140条 |
| eq_data_anomaly_record | equipment_code, data_anomaly_datetime, whether_fix | 39条 |
| eq_equip_offline_record | equipment_code, offline_start/end, duration | 585条 |
| dg_equip_offline | st_type, tm(阈值min), frequency(采集频率) | SP=360, GN/EL/ZS/WQ=60 |

**测试设备列表**:

| id | name | type | status | 说明 |
|----|------|------|--------|------|
| 104 | 西坝咀雨量计 | 8(雨量计) | 2(异常) | 离线测试对象 |
| 125 | 1#水位计（模拟） | 7 | 1(在线) | 正常对照 |
| 128 | 1#闸门（模拟） | 1 | 2(异常) | 水位异常测试 |
| 139 | 振弦渗压计E01 | 20 | 0(正常) | 评分对照 |
| 140 | 振弦渗压计E02 | 20 | 2(异常) | 评分对比对象 |
