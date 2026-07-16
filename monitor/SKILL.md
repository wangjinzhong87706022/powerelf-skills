---
name: powerelf-monitor
description: "实时监控分析 — 水位变化率/库容平衡/GNSS位移速率/闸泵电气校验/雨情强度/Mann-Kendall趋势检测。分析水位变化趋势，不是查水位也不是查异常。核心表: powerelf_data.st_rsvr_r, powerelf_data.dsm_dfr_srvrds_srhrds"
version: 2.0.0
author: dataagent-powerelf
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [monitoring, analysis, reservoir, gnss, gate, pump, rainfall, trend, anomaly, water-conservancy]
    category: powerelf
---

# 实时监控分析引擎 (Monitor Analysis Engine)

水利工程实时监控分析引擎。不只查询数据，而是内嵌完整分析逻辑——公式、阈值、判定规则全部就绪，Agent 可独立完成从原始数据到分析结论的全流程。

## When to Use

| Scenario | Use This Skill |
|----------|---------------|
| 分析水库水位变化趋势（变化率、库容平衡） | Yes |
| 判断 GNSS 位移是否异常（速率分级、方向判断） | Yes |
| 检查闸门/泵站运行是否正常（流量合理性、电气参数） | Yes |
| 分析降雨强度和累计趋势 | Yes |
| 检测数据趋势异常（Mann-Kendall、变化点、周期性） | Yes |
| 预测未来水位/流量/位移（指数平滑/ARIMA/LSTM） | Yes |
| 判断变形方向（上游/下游/下沉/上升） | Yes |
| 校验泵站电气参数（电压/频率/三相不平衡） | Yes |
| 纯数据查询（"查XX的水位"） | **No，用 powerelf-chatbi** |
| 预警通知触发（发送短信/推送） | **No，用 powerelf-early-warning** |

## Prerequisites

- **数据库:** **本地 MySQL** `127.0.0.1:3306/powerelf_data`（环境变量 POWERELF_DB_* / SRM_DB_*）
- **DB 助手:** **必须用** `skills/powerelf/lib/db.py`（不要用 water-resources 的）

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from db import query
```
- **SQL 安全:** 参考 `shared/sql_safety_rules.md`
- **Schema 参考:** `references/schema.md` — 监测数据表结构
- **算法参考:** `references/algorithm.md` — 完整算法公式与伪代码
- **业务规则:** `references/business_rules.md` — 阈值、等级、参数范围

## 核心分析能力

### 1. 水库水情分析

数据源: `st_rsvr_r`

| 分析项 | 方法 | 判定规则 |
|--------|------|----------|
| 水位变化率 | `\|z1-z2\|/z2*100%` | >1% 关注, >3% 预警, >5% 紧急 |
| 库容平衡 | inq vs otq vs rz 方向一致性 | 入库>出库但水位下降→异常(渗漏) |
| 10分钟流量汇总 | 按设备分组取最新, SUM(inq)/SUM(otq) | — |
| 异常值识别 | null/-1/超极值 | 数据缺失或异常标记 |

### 2. GNSS 变形分析

数据源: `dsm_dfr_srvrds_srhrds`, `srm_gnss_stat_day`

| 分析项 | 方法 | 判定规则 |
|--------|------|----------|
| 位移速率 | `(max-min)/月份数*100` cm/月 | <0.5稳定, 0.5-2缓慢, 2-5中速, >5快速 |
| 方向判断 | total_x>0=下游, total_h>0=下沉 | 反之为上游/上升 |
| 一致性检查 | 同断面多测点方向对比 | 一致→整体滑动, 相反→局部变形 |
| 年度统计 | maxh-minh 年变幅 | 超阈值预警 |
| 水位关联 | 水位+位移双曲线对比 | 水位升+位移加速→坝体稳定性 |

### 3. 闸泵工况分析

数据源: `rei_gate_r`, `rei_pump_r`

| 分析项 | 方法 | 判定规则 |
|--------|------|----------|
| 流量合理性 | 开启高度 vs 流量 | 关闭有流量=漏水, 开启无流量=堵塞 |
| 开关一致性 | status vs gtophgt | 状态关但有开度→异常 |
| 电气参数校验 | parseFloat后比较 | 电压340-420V, 频率48-52Hz |
| 三相不平衡 | `max\|差值\|/均值` | >10% 预警 |
| 负载率 | 实际功率/额定功率 | >95%过载, <10%空载 |
| 冷却系统 | 温升=出水-进水 | >10度冷却不足 |
| 励磁检查 | 电压=0且运行→异常 | — |

### 4. 雨情分析

数据源: `st_pptn_r`, `st_pptn_region_r`

| 分析项 | 方法 | 判定规则 |
|--------|------|----------|
| 降雨强度 | `p/(dr/60)` mm/h (dr单位为分钟) | >16暴雨, >30极端 |
| 降雨等级 | 24h累计雨量6级划分 | 小雨~特大暴雨 |
| 累计趋势 | N天dyp求和 | 3天>100mm/7天>200mm预警 |
| 数据校验 | 负值/零时段有雨量/超极值 | 标记异常 |

### 5. 趋势异常检测

对任意监测数据序列执行统计检验。

| 方法 | 用途 | 核心逻辑 |
|------|------|----------|
| Mann-Kendall | 线性趋势 | S统计量: 逐对比较计数, S>0上升, S<0下降 |
| 变化点检测 | 突变识别 | 左右均值差>阈值→变化点 |
| 周期性检测 | 周期识别 | 自相关函数ACF峰值→周期长度 |

### 6. 时序预测

| 算法 | 适用场景 | 水利参数建议 |
|------|----------|-------------|
| 指数平滑(Holt-Winters) | 实时/短期预测 | alpha=0.2, beta=0.05, gamma=0.2, m=24 |
| ARIMA | 中短期, 需置信区间 | p=2-4, d=1, q=1-2 |
| LSTM | 长期依赖, 多变量 | hidden=64, layers=2, seq=96, pred=24 |

## Workflow

```
用户需求
  │
  ▼
0. 确定时间窗口 🔴 CHECKPOINT
  │               用户指定 → 使用用户给定的起止时间
  │               用户未指定 → 按分析类型选择默认窗口（与源码一致）:
  │                 实时概览 → 不限时间，取各设备最新一条（MAX(tm)）
  │                 GNSS 趋势 → 默认 1 年：START = DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
  │                 GNSS 月度 → 默认当年：YEAR(tm) = YEAR(CURDATE())
  │                 日统计 → 默认前一天：START = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
  │                 水位/雨量/闸泵趋势 → 用户必须指定时间范围，否则提示
  │               参数化: START='YYYY-MM-DD HH:MM:SS', END='YYYY-MM-DD HH:MM:SS'
  │               有时间条件的 SQL 带 WHERE tm BETWEEN '{START}' AND '{END}'
  │
  ▼
1. 获取数据 ──→ 用 execute_code 从 powerelf_data 查询原始监测数据（限定时间窗口）
  │               (参考下方"数据输入"确定查哪张表)
  │
  ▼
2. 选择分析方法 ──→ 根据分析目标匹配核心分析能力
  │                  水位变化→能力1, 位移→能力2, 闸泵→能力3, 雨量→能力4
  │                  趋势→能力5, 预测→能力6
  │
  ▼
3. 执行分析 ──→ 调用 lib/ 下的 Python 模块执行计算
  │              reservoir.py / gnss.py / gate_pump.py / rainfall.py / trend.py
  │              阈值参数来自 references/business_rules.md
  │
  ▼
4. 生成结论 ──→ 输出分析结果 + 判定等级 + 建议措施
  │              保留计算过程（变化率数值、速率等级等）
  │
  ▼
5. 关联预警 ──→ 若分析结果触发预警条件
                 → 关联 powerelf-early-warning 发出预警通知
```

## 数据输入

所有数据通过 `execute_code` 从 `powerelf_data` 查询。关键表和字段:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from db import query

# 水库水情
rows = query("SELECT stcd, tm, rz, inq, otq, w, blrz FROM st_rsvr_r WHERE stcd=%s AND tm >= %s ORDER BY tm DESC LIMIT 100", params=('ST001', '2026-05-01'), db='powerelf_data')

# GNSS变形
rows = query("SELECT point_id, tm, wgs84_delta_h, wgs84_delta_x, wgs84_delta_y, wgs84_total_h, wgs84_total_x, wgs84_total_y, speed_gh, speed_gx, speed_gy FROM dsm_dfr_srvrds_srhrds WHERE point_id=%s AND tm >= %s ORDER BY tm", params=('P001', '2026-01-01'), db='powerelf_data')

# 闸门工情
rows = query("SELECT stcd, slcd, tm, gtq, gtophgt, gtopnum, status FROM rei_gate_r WHERE stcd=%s AND tm >= %s ORDER BY tm DESC", params=('ST001', '2026-05-31'), db='powerelf_data')

# 泵站工情 (电气参数为varchar, 需parseFloat)
rows = query("SELECT stcd, tm, uab, ubc, uca, ia, ib, ic, p, freq, speed, status, fan_run, fan_fault, ot, it, ul, al FROM rei_pump_r WHERE stcd=%s AND tm >= %s ORDER BY tm DESC", params=('ST001', '2026-05-31'), db='powerelf_data')

# 测站雨量 (dr单位为分钟!)
rows = query("SELECT stcd, tm, p, dr, dyp, cump FROM st_pptn_r WHERE stcd=%s AND tm >= %s ORDER BY tm", params=('ST001', '2026-05-01'), db='powerelf_data')

# GNSS日统计
rows = query("SELECT st_id, eq_id, tm, maxh, minh, avgh, maxx, minx, avgx, maxy, miny, avgy FROM srm_gnss_stat_day WHERE st_id=%s AND tm >= %s ORDER BY tm", params=(1, '2026-01-01'), db='powerelf_data')

# 渗流量 / 渗压 / 墒情
rows = query("SELECT stcd, tm, percolation FROM st_percolation_r WHERE stcd=%s AND tm >= %s ORDER BY tm DESC", ...)
rows = query("SELECT section_id, point_id, tm, ext_pressure, water_pressure, ext_temperature FROM st_pressure_r WHERE section_id=%s AND tm >= %s ORDER BY tm", ...)
rows = query("SELECT stcd, tm, soil_water10cm, soil_water20cm, soil_water30cm, ec, ph, groundwater_depth FROM st_soil_moisture_r WHERE stcd=%s AND tm >= %s ORDER BY tm DESC", ...)
```

## Related Skills

| Skill | 说明 |
|-------|------|
| powerelf-data-governance | 数据治理 — 缺失检测、异常检测、质量评分（本skill产出的异常标记可流入治理流程） |
| powerelf-early-warning | 预警系统 — 阈值预警、通知发送（本skill分析结论可触发预警） |
| powerelf-chatbi | NL2SQL查询 — 纯数据查询场景（不涉及分析逻辑时使用） |
