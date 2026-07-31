# 诊断路由表（巡检→诊断自动衔接）

> 消费方：`impl/inspection_analyzer.py` 的 `run_auto_diagnosis()`（`DIAG_ROUTES`）。
> 模式：CRITICAL/WARNING finding → 路由匹配 → 分层时间窗查询（先验概率序）→ 命中即停 → 结果回填 finding。
> 触发语义：CRITICAL 恒候选；WARNING 需命中路由（路由命中即高风险信号——渗压/水位/闸门维度只发 WARNING，若仅收 CRITICAL 则路由不可达）。CRITICAL 优先占配额。
> 扩展指引：**新增巡检维度的专项诊断复用本路由表模式**——加一行路由 + 一个 `_diagnose_*` 函数即可。

## 执行纪律

- **只读**：诊断链只发 SELECT，不写任何表；
- **限流**：每轮巡检最多 3 条诊断链（`MAX_DIAG_CHAINS`），防爆炸；
- **证据充分即停**：任一层产出 root_cause 级证据即终止后续 fallback；
- **尝试轨迹入报告**：finding.detail 记录"已查窗口与结果"（区分"已检为空"与"忘了检"）；
- **瞬时错误重试至多一次**：再失败标准化为 `DIAG_QUERY_FAILED(code)` 并入结果，不中断报告；
- **禁止内联可执行处置 SQL/命令**：结论用"建议在维护窗口内核查 X"式措辞；
- 时间窗三级纵向扩展 `[-2h] → [-12h] → [-3d]`，之后一层横向 fallback（切关联维度再试一次）。
- opt-out：CLI `--no-auto-diagnosis`。

## 首批 3 条路由

### R1 · 渗压 MAD 离群（CRITICAL/WARNING）→ `_diagnose_pressure_outlier`

根因先验概率序（首版拍经验值，按 `evolution/feedback-log.md` 实测修正）：

| 序 | 候选根因 | 先验 | 查询（数据源锚点） | 命中判据 | 结论模板 |
|---|---|---|---|---|---|
| ① | 上游水位抬升 | ~50% | `st_rsvr_r.rz` 窗口 MAX-MIN | Δ ≥ 0.2m | 上游水位抬升→渗压响应（因果链）|
| ② | 降雨入渗 | ~25% | `st_pptn_r.p` 窗口 SUM | ≥ 10mm | 同期降雨入渗→渗压抬升 |
| ③ | 闸门调度 | ~15% | `rei_gate_r.gtophgt` DISTINCT 数 | > 1 档 | 同期闸门调度→渗流场扰动 |
| ④ | 传感器漂移/真实渗漏 | ~10% | （兜底）横向查同期其他渗压计 | — | 外因均排除，需人工现场确认 |

### R2 · 水位变化率超限（CRITICAL/WARNING）→ `_diagnose_water_level_rate`

产出：区分"调度行为"与"异常水情"。

| 序 | 候选根因 | 查询 | 命中判据 |
|---|---|---|---|
| ① | 闸门调度 | `rei_gate_r.gtophgt` DISTINCT 数 | > 1 档 |
| ② | 泵站启停 | `rei_pump_r` 窗口记录数 | > 0 |
| ③ | 上游降雨 | `st_pptn_r.p` 窗口 SUM | ≥ 10mm |
| 兜底 | 异常水情不能排除 | — | 需人工核查 |

### R3 · 闸门关闭但有流量（CRITICAL/WARNING）→ `_diagnose_gate_closed_flow`

产出：区分"传感器故障"与"真实漏水"。

| 序 | 检查 | 查询 | 命中判据 | 结论 |
|---|---|---|---|---|
| ① | 状态时序跳变 | `rei_gate_r.gtophgt` 12h DISTINCT 数 | > 3 档 | 疑似开度传感器故障 |
| ② | 断面流量交叉验证 | `st_river_r.q` 12h 过流记录数 | > 0 | 疑似闸门真实漏水 |
| 兜底 | 未获交叉证实 | — | — | 疑似流量传感器故障，现场核查 |

## 结果回填契约

- 命中：finding 加 `diagnosis_root_cause`；envelope 中该 finding `category` 升级为 `root_cause`（stop-ready，不再追加分析轮次）；`detail` 追加 `｜诊断: <根因>（证据链: …）`；
- 未命中：`detail` 追加 `｜诊断: <排除结论>（已查: …）`；
- 昂贵诊断准入：跨表大窗口查询（如近 3 年同期分布）只在前置轻量检查已命中且实体缺口明确时执行，不作为例行动作。
