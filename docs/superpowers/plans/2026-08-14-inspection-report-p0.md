# 智能巡检报告改造 P0 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 巡检产出八章节正式报告（聊天摘要 + .md 文件双交付），新增 4 张水利四色图表，修复 3 个数据口径缺陷，时间范围全链路 `--days N` 参数化。

**Architecture:** 方案 A'——所有 DB 查询留在 `inspection_analyzer.py` 主流程（单源纪律），新增 `render_report.py` 纯渲染层（无 DB）与 `charts.py` 扩展；envelope 契约（`--json`）与退出码语义冻结不动。

**Tech Stack:** Python 3 + pandas + sqlalchemy + matplotlib(Agg) + pytest；中文字体 AR PL UKai CN。

**Spec:** `docs/superpowers/specs/2026-08-14-inspection-report-redesign-design.md`（计划与 spec 同行，执行者两份都读）

## Global Constraints

- **单源纪律**：巡检报告只能由 `inspection_analyzer.py` 一次产出；渲染层不碰 DB。
- **契约冻结**：`--json` envelope 字段零删减；退出码 `0/2/3/4/5` 语义不变。
- **时间范围**：任何代码/文案不得硬编码 7；窗口一律取自 `--days N`（默认 30 保持现状，SKILL.md 指导 agent 传 N）。
- **图色**：水利四色 红I `#E53E3E` / 橙II `#ED8936` / 黄III `#ECC94B`（保留档）/ 蓝IV `#3182CE`，正常绿 `#38A169`；黑白打印可辨（色板+线型双编码）。
- **SQL 铁律**：一切查询 `deleted = 0`；标识符经 `_validate_identifiers`；参数化绑定。
- **0 是有效读数**不是缺失；推断性表述用区间不用点值。
- 测试基线：47 用例 + EVAL10 综合分 ≥ **0.755**（基线 20260813-202128 重判分）。
- 每个任务结束必须 commit；中文注释风格与现有代码一致。
- 工作目录：`/home/scada/powerelf-skills/powerelf-inspection/`；DB 环境：`source ../_shared/bootstrap.sh`（导出 `DB_URL`）。

---

### Task 1: 修复 1 —— 降雨诊断逐时去重口径

**Files:**
- Modify: `impl/inspection_analyzer.py:1456-1467`（`_diagnose_pressure_outlier` 降雨分支）
- Test: `impl/test_report_units.py`（新建，纯单测无 DB）

**Interfaces:**
- Consumes: `_diag_sql(engine, sql, params) -> (DataFrame|None, code|None)`；`_DIAG_WINDOWS`（既有）。
- Produces: `_diagnose_pressure_outlier` 返回的 `root_cause` 字符串含"逐时去重"口径标注；后续任务不变更此签名。

- [ ] **Step 1: 写失败测试**

新建 `impl/test_report_units.py`：

```python
#!/usr/bin/env python3
"""巡检报告改造 P0 纯单测（无 DB，monkeypatch 依赖）。"""
import sys, os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import pandas as pd
import pytest


# ---------- Task 1: 降雨诊断去重口径 ----------
def test_rainfall_diag_dedup_caliber(monkeypatch):
    """同刻多站/重复行 → 面雨量按逐时去重，证据注明口径与未归属行数。"""
    import inspection_analyzer as ia

    def fake_diag_sql(engine, sql, params=None):
        if "st_rsvr_r" in sql:
            return pd.DataFrame({"delta": [0.05]}), None            # 水位变幅不足
        if "st_pptn_r" in sql:
            return pd.DataFrame({"total": [120.0], "unattr": [8]}), None  # SQL 内去重后的口径
        return pd.DataFrame({"n": [1]}), None                       # 闸门无操作

    monkeypatch.setattr(ia, "_diag_sql", fake_diag_sql)
    out = ia._diagnose_pressure_outlier(engine=None)
    assert out["root_cause"] and "降雨入渗" in out["root_cause"]
    assert "逐时去重" in out["root_cause"]
    assert "120" in out["root_cause"] and "8 行未归属" in out["root_cause"]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/scada/powerelf-skills/powerelf-inspection && python3 -m pytest impl/test_report_units.py::test_rainfall_diag_dedup_caliber -v
```
预期：FAIL（现 root_cause 文本无"逐时去重"，且查询无 unattr 列 → KeyError 或断言失败）。

- [ ] **Step 3: 最小实现**

`_diagnose_pressure_outlier` 中 ② 同期降雨分支（1456-1467 行）整段替换为：

```python
        # ② 同期降雨事件（~25%）——逐时去重口径（spec §5 修复1：同刻多站/重复行防翻倍）
        df, code = _diag_sql(engine,
            "SELECT COALESCE(SUM(mx),0) AS total, COALESCE(SUM(unattrib),0) AS unattr FROM ("
            "  SELECT MAX(p) AS mx, SUM(st_id IS NULL) AS unattrib"
            "  FROM st_pptn_r WHERE deleted=0 AND tm >= NOW()-INTERVAL :h HOUR"
            "  GROUP BY tm) t", {"h": hours})
        if code:
            trace.append(f"{label} 降雨: {code}")
        else:
            total = float(df['total'].iloc[0] or 0)
            unattr = int(df['unattr'].iloc[0] or 0)
            note = (f"（窗口内 {unattr} 行未归属站点，按逐时去重）" if unattr
                    else "（按逐时去重）")
            if total >= 10:
                trace.append(f"{label} 面雨量 {total:.1f}mm{note}")
                return {"root_cause": f"同期降雨入渗→渗压抬升（面雨量约{total:.0f}mm{note}）",
                        "trace": trace}
            trace.append(f"{label} 面雨量 {total:.1f}mm 不足")
```

- [ ] **Step 4: 跑测试确认通过**

同 Step 2 命令。预期：PASS。

- [ ] **Step 5: 真实库 sanity + commit**

```bash
source ../_shared/bootstrap.sh && python3 - <<'EOF'
import sys; sys.path.insert(0, "impl")
from sqlalchemy import create_engine
import inspection_analyzer as ia
out = ia._diagnose_pressure_outlier(create_engine(__import__('os').environ['DB_URL']))
print(out["root_cause"]); print(out["trace"][:3])
EOF
```
预期：面雨量数值 ≤ 未去重 SUM（口径归正），trace 含未归属行数。

```bash
git add impl/inspection_analyzer.py impl/test_report_units.py
git commit -m "fix(inspection): 降雨诊断逐时去重口径——防同刻多站重复累计(spec修复1)"
```

---

### Task 2: 修复 2a —— 确定性读取 + 同刻多行收敛

**Files:**
- Modify: `impl/inspection_analyzer.py:214`（`read_sensor_data` 排序）；`analyze_pressure`（623-687，读字段与预处理）；新增模块级 `_latest_per_tm`
- Test: `impl/test_report_units.py`（追加）

**Interfaces:**
- Produces: `_latest_per_tm(df: DataFrame) -> DataFrame`——同一 `(st_id, tm)` 保留最大 `id` 行（后写覆盖语义），按 `(tm, st_id)` 升序返回；`df` 无 `id` 列时原样返回。Task 3/6 依赖此语义。

- [ ] **Step 1: 写失败测试**

`impl/test_report_units.py` 追加：

```python
# ---------- Task 2: 确定性读取 ----------
def test_latest_per_tm_deterministic():
    """同刻多行 → 保留最大 id；不再受服务器返回顺序影响。"""
    import inspection_analyzer as ia
    df = pd.DataFrame({
        "id": [34423, 35095, 34422, 35094],
        "st_id": [93, 93, 93, 93],
        "tm": pd.to_datetime(["2026-08-14 03:00", "2026-08-14 03:00",
                              "2026-08-14 02:00", "2026-08-14 02:00"]),
        "water_pressure": [471.886, 455.117, 469.486, 455.566],
    })
    out = ia._latest_per_tm(df)
    assert len(out) == 2
    assert out.iloc[-1]["water_pressure"] == pytest.approx(455.117)  # 后写(大id)胜
    assert out.iloc[0]["water_pressure"] == pytest.approx(455.566)


def test_pressure_no_false_jump_from_tie_rows(monkeypatch):
    """同刻并列行（爬坡尾行 vs 基线行）不再随机触发突变 finding。"""
    import inspection_analyzer as ia
    base = [455.1 + 0.1 * (i % 7) for i in range(24)]
    df = pd.DataFrame({
        "id": list(range(100, 124)) + [200],
        "st_id": [93] * 25,
        "tm": pd.to_datetime([f"2026-08-13 {h:02d}:00" for h in range(24)] + ["2026-08-13 23:00"]),
        "water_pressure": base + [471.9],  # 23:00 爬坡尾行，id=200 但小于基线块? 设 id=99 → 应被丢弃
    })
    df.loc[df.id == 200, "id"] = 99  # 旧写入行：同刻应被后写基线行覆盖
    monkeypatch.setattr(ia, "read_sensor_data", lambda *a, **k: df)
    monkeypatch.setattr(ia, "seasonal_check",
                        lambda *a, **k: {"in_season": False, "seasonal_median": None, "note": ""})
    monkeypatch.setattr(ia, "get_registry_threshold", lambda *a, **k: 5.0)
    out = ia.analyze_pressure(engine=None, days=7, thresholds={})
    jumps = [f for f in out["findings"] if "突变" in f.get("message", "")]
    assert not jumps  # 收敛后末两值 455.x，Δ<5kPa，不触发
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python3 -m pytest impl/test_report_units.py -k "latest_per_tm or tie_rows" -v
```
预期：FAIL（`_latest_per_tm` 不存在 → AttributeError）。

- [ ] **Step 3: 最小实现**

3a. `read_sensor_data` 内 SQL 排序（214 行）：

```python
    sql = (f"SELECT {fields} FROM {table} WHERE {where} "
           f"ORDER BY {time_field} DESC, id DESC LIMIT :limit")
```

3b. 模块级新增（放 `_change_finding` 之前）：

```python
def _latest_per_tm(df):
    """同刻多行确定性收敛（spec §5 修复2a）：同一 (st_id, tm) 保留最大 id 行
    （后写覆盖/订正的摄入语义）。消除"ORDER BY tm DESC + 稳定排序在并列时间戳里
    随机挑行"导致的不可复现'当前值'。单行时刻为无操作（评测合成数据零影响）；
    df 无 id 列时原样返回（保守降级）。"""
    if df.empty or "id" not in df.columns:
        return df
    return (df.sort_values(["st_id", "tm", "id"])
              .drop_duplicates(["st_id", "tm"], keep="last")
              .sort_values(["tm", "st_id"])
              .reset_index(drop=True))
```

3c. `analyze_pressure` 两处改动：读字段加 `id`；`for st_id` 循环内 `dropna` 之后、`latest = st_data.iloc[-1]` 之前插一行：

```python
    df = read_sensor_data(engine, "st_pressure_r",
                          "id, st_id, water_pressure, ext_pressure, ext_temperature, tm", days=days)
```

```python
        st_data = st_data.dropna(subset=['water_pressure'])
        st_data = _latest_per_tm(st_data)  # 修复2a：同刻收敛，"当前值"确定性
```

- [ ] **Step 4: 跑测试确认通过**

同 Step 2 命令 + 全文件 `python3 -m pytest impl/test_report_units.py -v`。预期：PASS（含 Task 1 用例不回归）。

- [ ] **Step 5: commit**

```bash
git add impl/inspection_analyzer.py impl/test_report_units.py
git commit -m "fix(inspection): 当前值确定性——同刻多行保留最大id行(spec修复2a)"
```

---

### Task 3: 修复 2b/3 —— 双值口径 + MAD spike 降级

**Files:**
- Modify: `impl/inspection_analyzer.py`：新增 `_dual_value`；`_change_finding`（350-372）加可选 `tms`；`analyze_pressure` MAD 分支（672-682）加 pattern/双值/spike 降级；突变 finding 挂 `dual` 字段
- Test: `impl/test_report_units.py`（追加）

**Interfaces:**
- Produces:
  - `_dual_value(values, tms, unit) -> {"peak": float, "peak_tm": str, "current": float, "receded": bool, "desc": str}`（回落判定带 `|latest − median| < 3.5×MAD` 且峰下标 < 末位）
  - finding 新增可选字段 `"pattern"`（spike/step/drift）与 `"dual"`（上述 dict）——Task 6 的 findings_ctx 直接消费。
- Consumes: 既有 `classify_timeseries(values)`（返回 `{"pattern","latest","window_max"}`）；`_PATTERN_LABELS`。

- [ ] **Step 1: 写失败测试**

追加：

```python
# ---------- Task 3: 双值口径 + spike 降级 ----------
def test_dual_value_receded_flag():
    import numpy as np
    import inspection_analyzer as ia
    vals = [455.0] * 20 + [471.9] + [455.1] * 5          # 中部尖峰已回落
    tms = pd.to_datetime([f"2026-08-13 {h%24:02d}:00" for h in range(26)])
    dv = ia._dual_value(vals, tms, "kPa")
    assert dv["peak"] == pytest.approx(471.9)
    assert dv["current"] == pytest.approx(455.1)
    assert dv["receded"] is True
    assert "已回落" in dv["desc"] and "峰值471.90kPa" in dv["desc"]


def test_mad_finding_spike_downgrade(monkeypatch):
    """MAD 命中但 latest 已回落 → pattern=spike → INFO，且 detail 含双值。"""
    import inspection_analyzer as ia

    class _FakeMad:
        def __init__(self, r): self.r = r
        def mad_anomaly(self, values, threshold=4.0, min_samples=10): return self.r

    vals = [455.0] * 20 + [471.9] + [455.1] * 5
    df = pd.DataFrame({
        "id": range(26), "st_id": [93] * 26,
        "tm": pd.to_datetime([f"2026-08-13 {h%24:02d}:00" for h in range(26)]),
        "water_pressure": vals,
    })
    monkeypatch.setattr(ia, "read_sensor_data", lambda *a, **k: df)
    monkeypatch.setattr(ia, "_anomaly", _FakeMad({"is_anomaly": True, "score": 56.8,
                                                  "median": 455.0}))
    monkeypatch.setattr(ia, "seasonal_check",
                        lambda *a, **k: {"in_season": False, "seasonal_median": None, "note": ""})
    out = ia.analyze_pressure(engine=None, days=7, thresholds={})
    mad = [f for f in out["findings"] if "统计异常" in f.get("message", "")]
    assert mad and mad[0]["level"] == "INFO"          # spike 降级
    assert mad[0].get("pattern") == "spike"
    assert "已回落" in mad[0]["detail"] and "dual" in mad[0]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python3 -m pytest impl/test_report_units.py -k "dual_value or spike_downgrade" -v
```
预期：FAIL（`_dual_value` 不存在）。

- [ ] **Step 3: 最小实现**

3a. `_change_finding` 之前新增：

```python
def _dual_value(values, tms, unit):
    """双值口径（spec §5 修复2b）：峰值+峰时刻｜当前值+回落标志。
    回落判定带：峰下标 < 末位 且 |latest − median| < 3.5×MAD（与 MAD 层 z=3~4 同口径）。"""
    vals = np.asarray(values, dtype=float)
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) or 1e-9
    i_pk = int(np.argmax(vals))
    peak, current = float(vals[i_pk]), float(vals[-1])
    receded = bool(i_pk < len(vals) - 1 and abs(current - med) < 3.5 * mad)
    peak_dt, peak_tm = None, ""
    if tms is not None and len(tms) == len(vals):
        t = tms.iloc[i_pk] if hasattr(tms, "iloc") else tms[i_pk]
        peak_dt = pd.Timestamp(t)          # 原始时间戳：Task 4 图表阴影区间用
        peak_tm = f" @ {peak_dt:%m-%d %H:%M}"
    flag = "已回落" if receded else "仍高位"
    return {"peak": peak, "peak_tm": peak_tm, "peak_dt": peak_dt,
            "current": current, "receded": receded,
            "desc": f"峰值{peak:.2f}{unit}{peak_tm}｜当前{current:.2f}{unit}（{flag}）"}
```

3b. `_change_finding` **增量**改造——该函数已含 spike→INFO 降级与 pattern 字段
（勘察确认），只做两处增量，不动既有 level/pattern 判定逻辑：

- 签名加可选参：`def _change_finding(values, prev, curr, *, st_id, unit, dim_label, tms=None):`
- 原 return dict 增加一个键、detail 追加一句（拼在既有 detail 字符串之后）：

```python
    dv = _dual_value(values, tms, unit)   # return 前计算
    # return dict 增加键: "dual": dv
    # detail 追加: f"；{dv['desc']}"
```

3c. `analyze_pressure` 突变调用（668-670）传 tms：

```python
                findings.append(_change_finding(
                    wp_values, wp_values[-2], wp_values[-1],
                    st_id=st_id, unit="kPa", dim_label="渗压计", tms=st_data["tm"]))
```

3d. MAD 分支（672-682）替换为：

```python
        # MAD异常检测（委托 lib/anomaly）+ 三分通道 + 双值口径（spec §5 修复2b/3）
        if len(wp_values) >= 10:
            _r = _anomaly.mad_anomaly(wp_values.tolist(), threshold=4.0, min_samples=10)
            if _r["is_anomaly"]:
                pat = classify_timeseries(wp_values.tolist())["pattern"]
                season = seasonal_check(engine, "st_pressure_r", "water_pressure", st_id, wp)
                level = "INFO" if (season["in_season"] or pat == "spike") else "WARNING"
                dv = _dual_value(wp_values, st_data["tm"], "kPa")
                findings.append({
                    "level": level, "pattern": pat, "dual": dv,
                    "message": (f"渗压计{st_id}: 统计异常 z_score={_r['score']:.1f} "
                                f"(峰值{dv['peak']:.2f}kPa, 当前{dv['current']:.2f}kPa"
                                f"{'，已回落' if dv['receded'] else ''})"),
                    "detail": f"{dv['desc']}；偏离近{days}天分布，需人工确认；{season['note']}"
                })
```

3e. `run_auto_diagnosis` 核对（不改动则确认）：其候选筛选已有 `pattern == 'spike'` 跳过逻辑；MAD finding 现在带 pattern 字段后自动纳入该跳过。若实现无此逻辑，在候选收集处加 `and f.get("pattern") != "spike"`。

- [ ] **Step 4: 跑测试确认通过**

```bash
python3 -m pytest impl/test_report_units.py -v
```
预期：全部 PASS（Task 1/2 不回归）。

- [ ] **Step 5: commit**

```bash
git add impl/inspection_analyzer.py impl/test_report_units.py
git commit -m "fix(inspection): 突变/MAD双值口径+MAD spike降级INFO(spec修复2b/3)"
```

---

### Task 4: charts.py —— 水利四色 + 4 张新图 + 自适应粒度

**Files:**
- Modify: `impl/charts.py`（新增常量与 4 函数，扩展 `render_charts` 与 `_read_series`）
- Test: `impl/test_report_units.py`（追加纯函数测试）

**Interfaces:**
- Produces:
  - `PALETTE: dict`（level→hex）；`RISK_CN: dict`（level→中文）；`granularity_for(days) -> ("hour"|"day"|"week", pandas_freq)`；`_title(name, days) -> str`
  - `chart_equipment_status(engine, out_dir) -> path|None`；`chart_alert_trend(engine, days, out_dir) -> path|None`；`chart_category_online(engine, out_dir) -> path|None`；`chart_anomaly_series(engine, days, findings_ctx, out_dir) -> [path]`
  - `render_charts(engine, days, analyses, out_dir, findings_ctx=None) -> dict`（向后兼容旧签名）
  - `_read_series(engine, table, value_col, days, st_id=None)`（新增可选 st_id 过滤）
- Consumes: Task 3 的 finding `dual` 字段（经 Task 6 的 findings_ctx；本任务先按契约编码，Task 6 接线）。

- [ ] **Step 1: 写失败测试**

追加：

```python
# ---------- Task 4: 图表纯函数 ----------
def test_palette_water_standard():
    from charts import PALETTE, RISK_CN
    assert PALETTE["CRITICAL"] == "#E53E3E" and PALETTE["WARNING"] == "#ED8936"
    assert PALETTE["INFO"] == "#3182CE" and PALETTE["OK"] == "#38A169"
    assert RISK_CN["CRITICAL"] == "重大" and RISK_CN["WARNING"] == "重要"
    assert RISK_CN["INFO"] == "提示"


def test_granularity_adaptive():
    from charts import granularity_for
    assert granularity_for(1)[0] == "hour"
    assert granularity_for(2)[0] == "hour"
    assert granularity_for(3)[0] == "day"
    assert granularity_for(7)[0] == "day"
    assert granularity_for(31)[0] == "day"
    assert granularity_for(32)[0] == "week"


def test_title_contains_period():
    from charts import _title
    t = _title("告警趋势", 7)
    assert t.startswith("告警趋势｜统计时段：") and "~" in t
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python3 -m pytest impl/test_report_units.py -k "palette or granularity or title" -v
```
预期：FAIL（ImportError/AttributeError）。

- [ ] **Step 3: 最小实现**

3a. `charts.py` 头部常量（import 区之后）：

```python
from datetime import datetime, timedelta  # 文件已导入则跳过

# ---- 水利四色规范（spec §2：红I/橙II/黄III保留/蓝IV + 正常绿）----
PALETTE = {"CRITICAL": "#E53E3E", "WARNING": "#ED8936", "INFO": "#3182CE",
           "OK": "#38A169", "YELLOW_RESERVED": "#ECC94B"}
RISK_CN = {"CRITICAL": "重大", "WARNING": "重要", "INFO": "提示", "OK": "正常"}


def granularity_for(days):
    """统计粒度随窗口自适应（spec §4）：N≤2 按小时、3~31 按日、>31 按周。"""
    if days <= 2:
        return "hour", "1h"
    if days <= 31:
        return "day", "1D"
    return "week", "1W"


def _title(name, days):
    end = datetime.now()
    start = end - timedelta(days=days)
    return f"{name}｜统计时段：{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"
```

3b. `_read_series` 加 st_id：

```python
def _read_series(engine, table, value_col, days, st_id=None):
    """只读近 days 天时序（deleted=0），可按测点过滤。返回 DataFrame[value, tm] 或空。"""
    try:
        cond = "AND st_id = :st_id" if st_id is not None else ""
        sql = (f"SELECT {value_col} AS value, tm FROM {table} "
               f"WHERE deleted = 0 AND tm >= NOW()-INTERVAL :days DAY {cond} "
               f"ORDER BY tm ASC")
        params = {"days": days} if st_id is None else {"days": days, "st_id": int(st_id)}
        return pd.read_sql(text(sql), engine, params=params)
    except Exception:
        return pd.DataFrame()
```

3c. 四个新图函数（文件末尾 `render_charts` 之前）：

```python
def chart_equipment_status(engine, out_dir):
    """图2：设备运行状态柱状（三分类；台账无'休眠'枚举，脚注注明）。"""
    path = _safe_path(out_dir, "equipment_status.png")
    try:
        rows = pd.read_sql(text(
            "SELECT status, COUNT(*) AS n FROM eq_equip_base WHERE deleted=0 "
            "GROUP BY status"), engine)
    except Exception:
        return None
    if rows.empty:
        return None
    label_map = {0: "离线", 1: "在线", 2: "异常"}
    color_map = {0: PALETTE["CRITICAL"], 1: PALETTE["OK"], 2: PALETTE["WARNING"]}
    rows["name"] = rows["status"].map(label_map)
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=110)
    ax.bar(rows["name"], rows["n"], color=[color_map.get(s, "#7f7f7f") for s in rows["status"]])
    for i, n in enumerate(rows["n"]):
        ax.text(i, n, str(int(n)), ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("设备数（台）")
    ax.set_title(_title("设备运行状态", 0).split("｜")[0] + "（台账快照）")
    ax.grid(axis="y", alpha=0.3)
    ax.text(0.99, -0.16, "注：台账状态仅有 离线0/在线1/异常2 三枚举，无'休眠'",
            transform=ax.transAxes, ha="right", fontsize=8, color="#666666")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_alert_trend(engine, days, out_dir):
    """图3：告警数量趋势折线（按 level_r 多线；粒度随窗口自适应）。"""
    path = _safe_path(out_dir, "alert_trend.png")
    unit, freq = granularity_for(days)
    try:
        rows = pd.read_sql(text(
            "SELECT gather_time, level_r FROM ew_info_message "
            "WHERE deleted=0 AND gather_time >= NOW()-INTERVAL :d DAY"),
            engine, params={"d": days})
    except Exception:
        return None
    if rows.empty:
        return None
    rows["gather_time"] = pd.to_datetime(rows["gather_time"])
    rows["bucket"] = rows["gather_time"].dt.floor(freq)
    pivot = rows.pivot_table(index="bucket", columns="level_r", aggfunc="size", fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 3.4), dpi=110)
    line_styles = ["-", "--", "-.", ":"]
    for i, col in enumerate(sorted(pivot.columns)):
        lv = str(col)
        ax.plot(pivot.index.to_pydatetime(), pivot[col],
                label=f"level {lv}", linestyle=line_styles[i % 4])
    ax.set_ylabel(f"告警数（条/{ '小时' if unit=='hour' else ('天' if unit=='day' else '周') }）")
    ax.set_title(_title("告警数量趋势", days))
    ax.legend()
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_category_online(engine, out_dir):
    """图7：各类别设备在线率横向条形（定位通信/供电薄弱类别）。"""
    path = _safe_path(out_dir, "category_online.png")
    try:
        rows = pd.read_sql(text(
            "SELECT category, SUM(status=1) AS online, COUNT(*) AS total "
            "FROM eq_equip_base WHERE deleted=0 GROUP BY category ORDER BY category"),
            engine)
    except Exception:
        return None
    if rows.empty:
        return None
    rows["rate"] = rows["online"] / rows["total"] * 100
    fig, ax = plt.subplots(figsize=(8, max(2.5, 0.5 * len(rows))), dpi=110)
    colors = [PALETTE["OK"] if r >= 90 else (PALETTE["WARNING"] if r >= 70 else PALETTE["CRITICAL"])
              for r in rows["rate"]]
    ax.barh(rows["category"].astype(str), rows["rate"], color=colors)
    ax.set_xlabel("在线率（%）")
    ax.set_xlim(0, 105)
    ax.set_title("各专业类别设备在线率（台账快照）")
    for i, (r, t) in enumerate(zip(rows["rate"], rows["total"])):
        ax.text(min(r + 1, 100), i, f"{r:.0f}%（{int(t)}台）", va="center", fontsize=8)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_anomaly_series(engine, days, findings_ctx, out_dir):
    """图5/6：重点异常单测点时序——阈值线 + 异常区间灰色阴影（重大/重要强制配图）。
    findings_ctx 条目契约（Task 6 产出）：{fid, level, dim, station, st_id, table,
    value_col, unit, threshold(数值|None),
    dual:{peak, peak_tm, peak_dt(Timestamp|None), current, receded}}。"""
    out = []
    for f in findings_ctx or []:
        if f.get("level") not in ("CRITICAL", "WARNING"):
            continue
        table, col = f.get("table"), f.get("value_col")
        if not table or not col:
            continue
        df = _read_series(engine, table, col, days, st_id=f.get("st_id"))
        if df.empty:
            continue
        df["value"] = pd.to_numeric(df["value"], errors="coerce").dropna()
        if df.empty:
            continue
        path = _safe_path(out_dir, f"anomaly_{f['fid']}.png")
        fig, ax = plt.subplots(figsize=(9, 3.2), dpi=110)
        thr = f.get("threshold")
        if thr is not None:
            ax.axhline(float(thr), color=PALETTE["CRITICAL"], linestyle="--",
                       linewidth=1, label=f"阈值 {float(thr):g}{f.get('unit','')}")
        dual = f.get("dual") or {}
        peak_dt = dual.get("peak_dt")            # Task 3 _dual_value 提供
        if peak_dt is not None:
            span = timedelta(hours=3)
            ax.axvspan(peak_dt - span, peak_dt + span, color="#999999", alpha=0.3,
                       label="异常区间")
        flag = ("（已回落）" if dual.get("receded") else "（仍高位）") if dual else ""
        ax.plot(df["tm"], df["value"], color="#1f77b4", linewidth=1.2,
                label=f"{f['station']}{flag}")   # 修复2c：回落标志进图例
        ax.set_ylabel(f"{f.get('unit','')}")
        ax.set_title(_title(f"{f['fid']} {f['dim']}·{f['station']}", days))
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        out.append(path)
    return out
```

3d. `render_charts` 扩展（替换原函数体末尾 return 前加新图挂载）：

```python
def render_charts(engine, days, analyses, out_dir, findings_ctx=None):
    """统一入口：返回 {section_key: [ {path, title} ]}，供 generate_report 接线。"""
    result = {}
    trends = chart_trends(engine, days, out_dir)
    if trends:
        result["trends"] = trends
    sev = chart_severity(analyses, out_dir)
    if sev:
        result["severity"] = [{"path": sev, "title": "异常分布"}]
    off = chart_offline(engine, out_dir)
    if off:
        result["offline"] = [{"path": off, "title": "离线全景（双口径）"}]
    corr = chart_correlation(engine, days, out_dir)
    if corr:
        result["correlation"] = [{"path": corr, "title": "水位-渗压联动"}]
    # P0 新增 4 图（spec §4）
    eq = chart_equipment_status(engine, out_dir)
    if eq:
        result["equipment_status"] = [{"path": eq, "title": "设备运行状态"}]
    alert = chart_alert_trend(engine, days, out_dir)
    if alert:
        result["alert_trend"] = [{"path": alert, "title": "告警趋势"}]
    cat = chart_category_online(engine, out_dir)
    if cat:
        result["category_online"] = [{"path": cat, "title": "各类别在线率"}]
    ano = chart_anomaly_series(engine, days, findings_ctx, out_dir)
    if ano:
        result["anomaly_series"] = [{"path": p, "title": "重点异常时序"} for p in ano]
    return result
```

3e. `chart_severity` 饼图颜色换水利四色（127 行 colors dict 替换）：

```python
        colors = {"CRITICAL": PALETTE["CRITICAL"], "WARNING": PALETTE["WARNING"],
                  "INFO": PALETTE["INFO"]}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python3 -m pytest impl/test_report_units.py -v
```
预期：全部 PASS。

- [ ] **Step 5: 出图 sanity + commit**

```bash
source ../_shared/bootstrap.sh && python3 - <<'EOF'
import sys; sys.path.insert(0, "impl")
from sqlalchemy import create_engine
import charts
eng = create_engine(__import__('os').environ['DB_URL'])
print(charts.chart_equipment_status(eng, "/tmp/insp-charts"))
print(charts.chart_alert_trend(eng, 7, "/tmp/insp-charts"))
print(charts.chart_category_online(eng, "/tmp/insp-charts"))
EOF
```
预期：三个路径打印，PNG 可打开（无乱码方框）。

```bash
git add impl/charts.py impl/test_report_units.py
git commit -m "feat(inspection): 水利四色+设备状态/告警趋势/类别在线率/重点异常时序4图(spec§4)"
```

---

### Task 5: render_report.py —— 八章节纯渲染层

**Files:**
- Create: `impl/render_report.py`
- Modify: `references/report-template.md`（重写为八章节骨架）
- Test: `impl/test_report_units.py`（追加）

**Interfaces:**
- Consumes: findings_ctx 契约（Task 4 Step 3c 注释 + Task 6 装配）；analyses 结构（`{category, status?, findings:[{level,message,detail,pattern?,dual?}], stats?}`）。
- Produces: `render_report(context: dict) -> str`（八章节 markdown）；`RISK_LABEL`；`device_class(dim)`；`closure_actions(f)`；`normal_summary(context)`；`risk_assessment(context)`。Task 6 消费 `render_report`。

- [ ] **Step 1: 写失败测试**

追加：

```python
# ---------- Task 5: 八章节渲染 ----------
def _demo_context():
    return {
        "generated_at": "2026-08-14 18:00", "run_id": "insp-demo", "days": 7,
        "period": "2026-08-07 18:00 ~ 2026-08-14 18:00",
        "dims": {"total": 15, "with_data": 15},
        "equip": {"total": 128, "online": 72, "offline": 54, "abnormal": 2},
        "risk": {"critical": 1, "warning": 8, "info": 1},
        "conclusion": "存在突出风险：GNSS 测点 97 位移速率超限",
        "findings_ctx": [
            {"fid": "F001", "dim": "位移监测", "station": "GNSS 测点 97",
             "level": "CRITICAL", "occurred_at": "2026-08-14 03:00", "receded": False,
             "pattern": "drift", "device_class": "工况类",
             "message": "位移速率 1.200mm/d", "detail": "超 1.0mm/d 阈值",
             "chart": "reports/anomaly_F001.png"},
            {"fid": "F002", "dim": "设备状态", "station": "全库设备",
             "level": "WARNING", "occurred_at": "-", "receded": False,
             "pattern": "step", "device_class": "设备类",
             "message": "离线率 42.2%", "detail": "54/128", "chart": None},
        ],
        "dim_stats_md": {"equipment": "| 正常72 | 离线54 | 异常2 |", "alerts": "| I级 3 |",
                          "mad": "| 93 | z=56.8 已回落 |", "corr": "水位-渗压联动",
                          "special": "水情正常；白蚁正常"},
        "normal_md": "13 个维度无异常，覆盖测点约 120 台",
        "charts_md": "![设备运行状态](reports/equipment_status.png)",
        "offline_overview": "（三口径表）", "coverage": "（覆盖清单）",
        "data_notes": "全部维度有数据", "qa_checklist": "Ready to share",
        "alert_table_md": "| 等级\\日 | 08-13 | 08-14 |\n|---|---|---|\n| I级 | 2 | 1 |",
    }


def test_render_report_sections_and_three_questions():
    from render_report import render_report
    md = render_report(_demo_context())
    assert "## 一、报告基础信息" in md and "## 八、附件" in md
    assert "严重程度" in md and "初步根因" in md and "下一步行动" in md  # 三问结构
    assert md.index("F001") < md.index("F002")            # 风险降序：CRITICAL 在前
    assert "已回落" in md or "仍高位" in md                 # 回落标志
    assert "一般" in md and "恒为 0" in md                  # 四档口径注明
    assert "启发式" in md                                   # 设备/工况分类注明


def test_render_risk_ordering():
    from render_report import render_report, RISK_LABEL
    assert RISK_LABEL["CRITICAL"][0] == "重大"
    md = render_report(_demo_context())
    assert md.index("🔴 重大") < md.index("🟠 重要")
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python3 -m pytest impl/test_report_units.py -k "render" -v
```
预期：FAIL（`render_report` 模块不存在 → ModuleNotFoundError）。

- [ ] **Step 3: 实现 `impl/render_report.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""八章节巡检报告纯渲染层（spec §3）。无 DB 访问——所有数据由 analyzer 装配进 context。

context 契约（generate_report 装配）：
  generated_at/run_id/days/period(str)/dims{total,with_data}/
  equip{total,online,offline,abnormal}/risk{critical,warning,info}/conclusion(str)/
  findings_ctx[{fid,dim,station,level,occurred_at,receded,pattern,device_class,
                message,detail,chart}]（已按 level 降序传入则保持原序，否则本层排序）/
  dim_stats_md{equipment,alerts,mad,corr,special}/normal_md/charts_md/
  offline_overview/coverage/data_notes/qa_checklist/alert_table_md
"""
import os as _os

RISK_LABEL = {"CRITICAL": ("重大", "🔴"), "WARNING": ("重要", "🟠"),
              "INFO": ("提示", "🔵"), "OK": ("正常", "🟢")}
_LEVEL_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2, "OK": 3}

# 设备/工况启发式（spec §3：报告中注明启发式）：设备状态维度→设备类，其余→工况类
DEVICE_CLASS_BY_DIM = {"设备状态"}

_TEMPLATE_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                               "..", "references", "report-template.md")


def device_class(dim):
    return "设备类" if dim in DEVICE_CLASS_BY_DIM else "工况类"


def closure_actions(f):
    """下一步处置行动（spec §3 第七章节规则模板）。"""
    if f["level"] == "CRITICAL":
        return "紧急处置：24 小时内现场核查，处置后复核确认"
    if f["level"] == "WARNING":
        return ("计划检修：本周内安排运维检查（设备类）"
                if f.get("device_class") == "设备类" else "持续观测：72 小时内复核趋势")
    return "纳入例行复测计划"


def three_question(f):
    """单条异常三问块。"""
    icon, cn = RISK_LABEL.get(f["level"], ("未知", "⚪"))
    flag = "已回落" if f.get("receded") else "仍高位"
    lines = [f"### {f['fid']} ｜{f['dim']}｜{f['station']} ｜ ⏰ {f.get('occurred_at','-')} ｜ {flag}",
             "",
             f"> **严重程度**：{icon} {cn}",
             f"> **初步根因**：{f.get('device_class','工况类')}类（启发式）——{f.get('detail','')}",
             f"> **下一步行动**：{closure_actions(f)}",
             ""]
    if f.get("chart"):
        lines.append(f"![{f['fid']} 时序]({f['chart']})")
        lines.append("")
    return "\n".join(lines)


def _header(ctx):
    e = ctx["equip"]
    return (f"## 一、报告基础信息\n\n"
            f"- 报告名称：水利设备智能巡检报告\n"
            f"- 巡检时段：{ctx['period']}（近 {ctx['days']} 天）\n"
            f"- run_id：{ctx['run_id']} ｜ 生成时间：{ctx['generated_at']}\n"
            f"- 巡检范围：全部监测设备 {e['total']} 台（在线 {e['online']} · "
            f"离线 {e['offline']} · 异常 {e['abnormal']}）\n"
            f"- 覆盖维度：{ctx['dims']['total']} 维（有数据 {ctx['dims']['with_data']}）\n"
            f"- 执行方式：自动化智能巡检 + 5 层判定体系（阈值→变化率→趋势→MAD→关联）\n")


def _overview(ctx):
    r = ctx["risk"]
    return (f"## 二、总体概况\n\n"
            f"| 风险分级 | 数量 |\n|---|---|\n"
            f"| 🔴 重大 | {r['critical']} |\n| 🟠 重要 | {r['warning']} |\n"
            f"| 🟡 一般 | 0 |\n| 🔵 提示 | {r['info']} |\n\n"
            f"> 注：'一般'档本系统暂无对应级别（三档判定 CRITICAL/WARNING/INFO），恒为 0；"
            f"黄色档为水利四色规范保留档。\n\n"
            f"**整体结论**：{ctx['conclusion']}\n")


def _anomalies(ctx):
    fs = sorted(ctx.get("findings_ctx", []),
                key=lambda f: _LEVEL_ORDER.get(f.get("level"), 9))
    body = "\n".join(three_question(f) for f in fs) or "本轮巡检未发现异常。"
    return f"## 三、异常清单（逐条三问，按风险降序）\n\n{body}\n"


def _dim_stats(ctx):
    d = ctx.get("dim_stats_md", {})
    return (f"## 四、分维度统计分析\n\n"
            f"### 4.1 设备状态统计（三分类，无'休眠'枚举）\n\n{d.get('equipment','')}\n\n"
            f"### 4.2 巡检周期告警统计\n\n{d.get('alerts','')}\n\n"
            f"### 4.3 MAD 异常统计\n\n{d.get('mad','')}\n\n"
            f"### 4.4 多指标关联分析\n\n{d.get('corr','')}\n\n"
            f"### 4.5 专项监测小结\n\n{d.get('special','')}\n")


def _assessment(ctx):
    fs = ctx.get("findings_ctx", [])
    crit = [f for f in fs if f["level"] == "CRITICAL"]
    short = "短期：未见未回落的重大异常，维持常规监测。"
    if any(not f.get("receded") for f in crit):
        short = "短期：存在未回落的重大异常（见第三章），风险可能持续或扩大，优先处置。"
    long_terms = []
    mad_receded = [f for f in fs if f.get("pattern") == "spike"]
    if mad_receded:
        long_terms.append("已回落的瞬时尖峰疑似传感器毛刺，建议安排复测标定")
    offline = [f for f in fs if "离线率" in f.get("message", "")]
    if offline:
        long_terms.append("离线率偏高提示通信/供电系统性问题，建议专项排查")
    long_md = "；".join(long_terms) if long_terms else "未见明确长期隐患信号"
    return (f"## 六、综合风险研判\n\n- {short}\n- 长期：{long_md}。\n\n"
            f"> 以上研判由 findings 事实规则拼装，未做超出数据的推断。\n")


def _closure(ctx):
    fs = sorted(ctx.get("findings_ctx", []),
                key=lambda f: _LEVEL_ORDER.get(f.get("level"), 9))
    urgent = [f for f in fs if f["level"] == "CRITICAL"]
    repair = [f for f in fs if f["level"] == "WARNING" and f.get("device_class") == "设备类"]
    watch = [f for f in fs if f["level"] == "WARNING" and f.get("device_class") != "设备类"]
    fmt = lambda lst: "\n".join(f"- {f['fid']} {f['station']}：{f['message']}" for f in lst) or "-（无）"
    return (f"## 七、任务跟踪与闭环\n\n"
            f"**紧急处置（24h 内）**\n{fmt(urgent)}\n\n"
            f"**计划检修（本周内，需运维/备件资源）**\n{fmt(repair)}\n\n"
            f"**持续观测（72h 复核）**\n{fmt(watch)}\n\n"
            f"复查要求：重大 24h、重要 72h 各一次复核巡检；校准类建议联系第三方计量机构。\n")


def _appendix(ctx):
    return (f"## 八、附件\n\n### 图表索引\n\n{ctx.get('charts_md','')}\n\n"
            f"### 原始告警统计表（等级×时段时间交叉表）\n\n{ctx.get('alert_table_md','')}\n\n"
            f"### 设备状态（三口径分层）\n\n{ctx.get('offline_overview','')}\n\n"
            f"### 数据覆盖清单\n\n{ctx.get('coverage','')}\n\n"
            f"### Data Notes\n\n{ctx.get('data_notes','')}\n\n{ctx.get('qa_checklist','')}\n")


_FALLBACK = ("# 水利设备智能巡检报告\n\n{header}\n{overview}\n{anomalies}\n"
             "{dim_stats}\n{{normal_md}}\n{assessment}\n{closure}\n{appendix}")


def render_report(context):
    """八章节主渲染：外置骨架模板优先，缺失/渲染失败回退内置（模板坏不毁报告）。"""
    blocks = {
        "header": _header(context), "overview": _overview(context),
        "anomalies": _anomalies(context), "dim_stats": _dim_stats(context),
        "normal_md": f"## 五、正常测点汇总（精简）\n\n{context.get('normal_md','')}\n",
        "assessment": _assessment(context), "closure": _closure(context),
        "appendix": _appendix(context),
    }
    try:
        with open(_TEMPLATE_PATH, encoding="utf-8") as fh:
            tpl = fh.read()
        return tpl.format(**blocks)
    except (OSError, KeyError, IndexError, ValueError):
        return _FALLBACK.format(**blocks)
```

同时重写 `references/report-template.md` 为骨架：

```markdown
# 水利设备智能巡检报告

{header}
{overview}
{anomalies}
{dim_stats}
{normal_md}
{assessment}
{closure}
{appendix}

---
*报告由智能巡检系统自动生成（渲染：impl/render_report.py）*
```

（注意：旧模板的 `{sections}` 等占位符全部废弃——旧 `_render_report_markdown` 将在 Task 6 停用，无其他消费方。）

- [ ] **Step 4: 跑测试确认通过**

```bash
python3 -m pytest impl/test_report_units.py -v
```
预期：全部 PASS。

- [ ] **Step 5: commit**

```bash
git add impl/render_report.py references/report-template.md impl/test_report_units.py
git commit -m "feat(inspection): 八章节纯渲染层 render_report.py + 骨架模板(spec§3)"
```

---

### Task 6: generate_report 装配接线 + CLI 摘要块

**Files:**
- Modify: `impl/inspection_analyzer.py`：`generate_report`（1798-1953）装配 findings_ctx/告警统计/类别在线率/结论，改调 `render_report.render_report`；`main()`（2175-）`--output` 写文件 + stdout 摘要块
- Test: `impl/test_inspection.py`（追加 DB 门卫冒烟）

**Interfaces:**
- Consumes: Task 3 finding 的 `pattern`/`dual`；Task 4 `render_charts(..., findings_ctx)`；Task 5 `render_report(context)`。
- Produces: `generate_report(engine, days, limit, auto_diagnosis) -> (report_md, analyses)` 签名不变（内部产出增强）；`_build_findings_ctx(analyses, days) -> list`（新增，Task 8 复用）；CLI `--output <path>` 写文件且 stdout 打印摘要块。

- [ ] **Step 1: 写失败测试（DB 门卫式，追加到 test_inspection.py 末尾）**

（`skip_no_db`/`_engine()` 沿用本文件既有定义；engine 构造若名为其他，照抄本文件现行写法）

```python
@skip_no_db
def test_generate_report_eight_sections():
    """八章节齐全 + '一般'档注明 + 摘要与明细自洽（真实库，窗口 7 天）。"""
    from inspection_analyzer import generate_report
    report, analyses = generate_report(_engine(), days=7, auto_diagnosis=False)
    for sec in ["一、报告基础信息", "二、总体概况", "三、异常清单", "四、分维度统计分析",
                "五、正常测点汇总", "六、综合风险研判", "七、任务跟踪与闭环", "八、附件"]:
        assert sec in report, f"缺章节: {sec}"
    assert "恒为 0" in report
    crit = sum(1 for a in analyses for f in a.get("findings", [])
               if f.get("level") == "CRITICAL")
    assert (f"| 🔴 重大 | {crit} |") in report   # 概览计数 ≡ 明细


@skip_no_db
def test_report_window_follows_days():
    """时间范围参数化：days=1 与 days=30 的时段文案/粒度随 N 变（防 7 硬编码）。"""
    from inspection_analyzer import generate_report
    r1, _ = generate_report(_engine(), days=1, auto_diagnosis=False)
    r30, _ = generate_report(_engine(), days=30, auto_diagnosis=False)
    assert "近 1 天" in r1 and "近 30 天" in r30
    assert "近 7 天" not in r1
```

- [ ] **Step 2: 跑测试确认失败**

```bash
source ../_shared/bootstrap.sh && python3 -m pytest impl/test_inspection.py -k "eight_sections or window_follows" -v
```
预期：FAIL（现报告无八章节标题）。

- [ ] **Step 3: 实现**

3a. `generate_report` 内、`generate_report` 之前新增装配函数：

```python
# 维度→(表, 值列, 单位)：重点异常时序图数据锚点（Task 4 chart_anomaly_series 消费）
_DIM_ANCHOR = {
    "渗压监测": ("st_pressure_r", "water_pressure", "kPa"),
    "位移监测": ("dsm_dfr_srvrds_srhrds", "speed_gh", "mm/d"),
    "水库水情": ("st_rsvr_r", "rz", "m"),
    "渗流监测": ("st_percolation_r", "percolation", "L/s"),
}


def _build_findings_ctx(engine, analyses):
    """findings_ctx 装配（Task 4/5 契约）：fid/dim/station/level/时间/回落/分类/图表锚点。
    station 从 message 前缀提取（'渗压计93:' → '渗压计 93'），保持报告可读；
    阈值经 get_registry_threshold 查注册表（查不到→None，图上不画阈值线）。"""
    import re as _re
    ctx, i = [], 0
    for a in analyses:
        dim = a.get("category", "未知")
        for f in a.get("findings", []):
            if f.get("level") == "OK":
                continue
            i += 1
            msg = f.get("message", "")
            m = _re.match(r"([一-龥\w]+?)(\d+(?:\.\d+)?)[：:]", msg)
            station = f"{m.group(1)} {m.group(2)}" if m else dim
            st_id = int(float(m.group(2))) if m else None
            dual = f.get("dual") or {}
            anchor = _DIM_ANCHOR.get(dim)
            thr = None
            if anchor and st_id is not None:
                try:
                    thr = get_registry_threshold(engine, anchor[0], anchor[1], st_id)
                except Exception:
                    thr = None
            ctx.append({
                "fid": f"F{i:03d}", "dim": dim, "station": station,
                "level": f.get("level", "INFO"),
                "occurred_at": (dual.get("peak_tm", "").replace(" @ ", "")
                                or f.get("occurred_at", "-")),
                "receded": bool(dual.get("receded")),
                "pattern": f.get("pattern"),
                "device_class": ("设备类" if dim == "设备状态" else "工况类"),
                "message": msg, "detail": f.get("detail", ""),
                "st_id": st_id,
                "table": anchor[0] if anchor else None,
                "value_col": anchor[1] if anchor else None,
                "unit": anchor[2] if anchor else "",
                "threshold": thr,
                "dual": dual,
                "chart": None,  # 图表路径由 render 后回填
            })
    return ctx
```

> 注：`get_registry_threshold` 的参数顺序以 analyzer 内既有调用点为准
> （grep 一次照抄），异常兜底 None。
```

3b. `generate_report` 内，`charts_md` 生成段（1905-1920）替换为（先装配 ctx 再传图）：

```python
    # P0：findings_ctx 装配（八章节/重点异常图数据锚点）
    findings_ctx = _build_findings_ctx(engine, analyses)

    # T8+P0 图表：PNG 输出到 <skill>/reports/，失败不影响报告主体
    # （render_charts 的 import 沿用 T8 既有接线，此处仅加 findings_ctx 参数）
    charts_md = ""
    try:
        _skill_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        charts_dir = _os.path.join(_skill_root, "reports")
        chart_sets = render_charts(engine, days, analyses, charts_dir,
                                   findings_ctx=findings_ctx)
        parts, fid_chart = [], {}
        for _items in chart_sets.values():
            for it in _items:
                rel = _os.path.relpath(it["path"], _skill_root).replace(_os.sep, "/")
                parts.append(f"![{it['title']}]({rel})")
                fid = _os.path.basename(it["path"]).replace("anomaly_", "").replace(".png", "")
                fid_chart[fid] = rel
        for fc in findings_ctx:               # 三问条目回填单点图路径
            if fc["fid"] in fid_chart:
                fc["chart"] = fid_chart[fc["fid"]]
        if parts:
            charts_md = "\n\n".join(parts) + "\n"
    except Exception as e:
        logger.warning("图表生成失败（不影响报告主体）: %s", e)
```

3c. `generate_report` 内新增两个统计查询（放 offline_md 渲染之前）与结论句（替换原 `recommendations` 段为闭环节交给渲染层，同时组装 context）：

```python
    # P0：告警统计（等级×频次 + 交叉表）——gather_time 为该表时间列
    alerts_stats_md, alert_table_md = "", ""
    try:
        _al = pd.read_sql(text(
            "SELECT level_r, COUNT(*) AS n FROM ew_info_message "
            "WHERE deleted=0 AND gather_time >= NOW()-INTERVAL :d DAY "
            "GROUP BY level_r"), engine, params={"d": days})
        if not _al.empty:
            _lv_cn = {"1": "I级(红)", "2": "II级(橙)", "3": "III级(黄)", "4": "IV级(蓝)"}
            rows = [f"| {_lv_cn.get(str(r.level_r), r.level_r)} | {int(r.n)} |"
                    for r in _al.itertuples()]
            alerts_stats_md = ("| 预警等级 | 条数 |\n|---|---|\n" + "\n".join(rows)
                               + f"\n\n合计：{int(_al['n'].sum())} 条（近 {days} 天）")
            _ax = pd.read_sql(text(
                "SELECT DATE_FORMAT(gather_time, '%Y-%m-%d') AS d, level_r, COUNT(*) AS n "
                "FROM ew_info_message WHERE deleted=0 "
                "AND gather_time >= NOW()-INTERVAL :d DAY GROUP BY d, level_r"),
                engine, params={"d": days})
            days_col = sorted(_ax["d"].unique())
            head = "| 等级\\日期 | " + " | ".join(days_col) + " |"
            sep = "|---" * (len(days_col) + 1) + "|"
            body = []
            for lv in sorted(_ax["level_r"].unique()):
                cell = {r.d: int(r.n) for r in _ax[_ax.level_r == lv].itertuples()}
                body.append(f"| {_lv_cn.get(str(lv), lv)} | "
                            + " | ".join(str(cell.get(d, 0)) for d in days_col) + " |")
            alert_table_md = "\n".join([head, sep] + body)
    except Exception as e:
        logger.warning("告警统计查询失败（不影响报告主体）: %s", e)

    # P0：整体结论（规则模板）
    crit_msgs = [f for a in analyses for f in a.get("findings", [])
                 if f.get("level") == "CRITICAL"]
    if crit_msgs:
        conclusion = "存在突出风险：" + crit_msgs[0].get("message", "")
    elif warnings:
        conclusion = "工程运行总体平稳，存在需关注事项（见异常清单）。"
    else:
        conclusion = "工程运行总体平稳。"

    # 修复1 配套（spec §5）：st_pptn_r 未归属站点行进 Data Notes
    # （data_notes 为 generate_report 既有变量；若为列表改为 join 后追加）
    try:
        _nu = pd.read_sql(text(
            "SELECT COUNT(*) AS n FROM st_pptn_r "
            "WHERE deleted=0 AND st_id IS NULL AND tm >= NOW()-INTERVAL :d DAY"),
            engine, params={"d": days})
        n_null = int(_nu["n"].iloc[0] or 0)
        if n_null:
            data_notes += (f"\n- 数据质量：近 {days} 天 st_pptn_r 有 {n_null} 行 "
                           "st_id 为 NULL（未归属站点），降雨类证据已按逐时去重口径处理。")
    except Exception:
        pass
```

3d. context 组装与渲染（替换 1936-1951 的 `_render_report_markdown({...})` 调用）：

```python
    # P0：正常测点汇总 + 八章节渲染（Task 5 render_report）
    ok_dims = [a.get("category") for a in analyses
               if not any(f.get("level") in ("CRITICAL", "WARNING")
                          for f in a.get("findings", []))]
    normal_md = (f"{len(ok_dims)}/{len(analyses)} 个维度无异常"
                 + (f"（{'、'.join(ok_dims[:6])}{'…' if len(ok_dims) > 6 else ''}）"
                    if ok_dims else ""))
    try:
        _eqs = pd.read_sql(text("SELECT SUM(status=1) AS online, COUNT(*) AS total "
                                "FROM eq_equip_base WHERE deleted=0"), engine)
        normal_md += (f"；设备层面：在线 {int(_eqs['online'].iloc[0] or 0)}"
                      f" / {int(_eqs['total'].iloc[0] or 0)} 台。")
    except Exception:
        normal_md += "。"

    from render_report import render_report as _rr
    # generated_at/run_id 复用 generate_report 既有变量（旧版 context 已装配过，
    # 变量名以现码为准照抄，不要新造）
    period_start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M')
    period_end = datetime.now().strftime('%Y-%m-%d %H:%M')
    report = _rr({
        "generated_at": now, "run_id": run_id, "days": days,
        "period": f"{period_start} ~ {period_end}",
        "dims": {"total": len(analyses),
                 "with_data": sum(1 for a in analyses if a.get("status") != "无数据")},
        "equip": _equip_snapshot(engine),
        "risk": {"critical": critical, "warning": warnings, "info": info_count},
        "conclusion": conclusion,
        "findings_ctx": findings_ctx,
        "dim_stats_md": {"equipment": offline_md or "（设备状态统计见附件三口径）",
                          "alerts": alerts_stats_md or "（窗口内无告警记录）",
                          "mad": _mad_summary(analyses), "corr": _corr_summary(analyses),
                          "special": _special_summary(analyses)},
        "normal_md": normal_md, "charts_md": charts_md,
        "offline_overview": offline_md, "coverage": coverage_md,
        "data_notes": data_notes, "qa_checklist": qa_checklist,
        "alert_table_md": alert_table_md or "（无告警记录）",
    })
    return report, analyses
```

并新增三个小装配函数（放 `_build_findings_ctx` 之后；`info_count` 在统计段补一行
`info_count = sum(1 for a in analyses for f in a.get('findings', []) if f.get('level') == 'INFO')`）：

```python
def _equip_snapshot(engine):
    try:
        row = pd.read_sql(text("SELECT COUNT(*) AS total, SUM(status=1) AS online, "
                               "SUM(status=0) AS offline, SUM(status=2) AS abnormal "
                               "FROM eq_equip_base WHERE deleted=0"), engine).iloc[0]
        return {"total": int(row["total"] or 0), "online": int(row["online"] or 0),
                "offline": int(row["offline"] or 0), "abnormal": int(row["abnormal"] or 0)}
    except Exception:
        return {"total": 0, "online": 0, "offline": 0, "abnormal": 0}


def _mad_summary(analyses):
    rows = [f"- {f.get('message','')}" for a in analyses if a.get("category") == "MAD统计异常"
            for f in a.get("findings", []) if f.get("level") != "OK"]
    return "\n".join(rows) or "- 窗口内未检出 MAD 统计异常"


def _corr_summary(analyses):
    rows = [f"- {f.get('message','')}" for a in analyses if a.get("category") == "多指标关联异常"
            for f in a.get("findings", []) if f.get("level") != "OK"]
    return "\n".join(rows) or "- 窗口内未检出多指标关联异常"


def _special_summary(analyses):
    lines = []
    for a in analyses:
        cat = a.get("category", "")
        if cat in ("MAD统计异常", "多指标关联异常", "设备状态", "告警分析"):
            continue
        bad = [f for f in a.get("findings", []) if f.get("level") in ("CRITICAL", "WARNING")]
        state = "异常" if bad else "正常"
        lines.append(f"- {cat}：{state}" + (f"（{bad[0].get('message','')}）" if bad else ""))
    return "\n".join(lines)
```

3e. `main()` 的 `--output` 分支：CLI 已支持 `--output` 写文件（既有行为保留），
在写文件成功之后**追加摘要块打印**（修复2c：重大项带回落标志）：

```python
            # 变量取 main 内既有名（report/analyses/critical/warnings/status；
            # info_count 若无则在计数处补一行统计）
            crit_list = [f for a in analyses for f in a.get("findings", [])
                         if f.get("level") == "CRITICAL"]
            print(f"[inspection] 状态: {status} | 报告: {_out} | "
                  f"重大 {critical} / 重要 {warnings} / 提示 {info_count}")
            for f in crit_list[:5]:
                _flag = ""
                if f.get("dual"):
                    _flag = "（已回落）" if f["dual"].get("receded") else "（仍高位）"
                print(f"[inspection] 重大项: {f.get('message','')}{_flag}")
```

无 `--output` 时维持现状（整份报告打印 stdout，评测兼容）。

- [ ] **Step 4: 跑测试确认通过**

```bash
source ../_shared/bootstrap.sh && python3 -m pytest impl/test_inspection.py -k "eight_sections or window_follows" -v
python3 -m pytest impl/test_report_units.py -v
```
预期：PASS。

- [ ] **Step 5: commit**

```bash
git add impl/inspection_analyzer.py impl/test_inspection.py
git commit -m "feat(inspection): generate_report八章节装配+findings_ctx+CLI摘要块(spec§3/§6)"
```

---

### Task 7: SKILL.md —— 双交付路由 + 时间范围解析规则

**Files:**
- Modify: `powerelf-inspection/SKILL.md:143-151`（工具命令区）+ 输出契约段追加

**Interfaces:**
- Consumes: Task 6 的 `--output` 行为。
- Produces: agent 路由规则文本（Hermes 侧经 `~/.hermes/skills/powerelf` symlink 即时生效，无需部署）。

- [ ] **Step 1: 修改工具命令区（143-151 行）**

```markdown
#### 1. 传感器巡检分析（15维度）

**完整巡检请求（默认路径——双交付）**：时间范围从用户问题解析为 N 天，一步出八章节报告：

```bash
python3 impl/inspection_analyzer.py --db "$DB_URL" --days <N> --output reports/insp-<YYYYMMDD>-<N>d.md
```

时间范围解析（agent 负责，analyzer 只收数值）："近 X 天"→X；"昨日/昨天"→1；
"本周"→距周一天数；"本月"→当月累计天数；"近一周"→7；未指明→7。
stdout 摘要块（状态/报告路径/重大项）直接作为聊天回复素材——回复=摘要+报告路径。

程序消费/评测场景：

```bash
python3 impl/inspection_analyzer.py --db "$DB_URL" --days 7 --json          # envelope 契约输出
python3 impl/inspection_analyzer.py --db "$DB_URL" --legacy-json           # 旧版裸数组（过渡）
python3 impl/inspection_analyzer.py --db "$DB_URL" --no-auto-diagnosis     # 关闭自动诊断链
```
```

- [ ] **Step 2: 输出契约段（164 行 envelope 说明之前）追加双交付契约**

```markdown
#### 双交付契约（P0）

用户请求"完整巡检/巡检报告"时：必须以 `--output` 生成八章节报告文件并在回复中给出
路径；聊天回复=摘要（重大/重要清单+整体结论）+ 报告路径。禁止只回 envelope 摘要。
`--json` 仅供程序消费，不作为面向用户的交付。
```

- [ ] **Step 3: 验证 + commit**

```bash
source ../_shared/bootstrap.sh && python3 impl/inspection_analyzer.py --db "$DB_URL" --days 7 --output reports/insp-smoke.md && head -30 reports/insp-smoke.md
```
预期：摘要块打印 + 报告头部 30 行为八章节格式。

```bash
git add SKILL.md
git commit -m "docs(inspection): SKILL双交付路由+时间范围解析规则(spec§6)"
```

---

### Task 8: 验收四闸（冒烟 ×3 窗口 / 全量评测 / 契约冻结）

**Files:**
- 无新文件；产出验收记录 `docs/inspection-report-p0-acceptance.md`

**Interfaces:**
- Consumes: 全部前序任务。
- Produces: 验收记录文档（含评测分数对比、三窗口冒烟结论、hermes 实跑证据）。

- [ ] **Step 1: 三窗口真实库冒烟**

```bash
source ../_shared/bootstrap.sh
for D in 1 7 30; do
  python3 impl/inspection_analyzer.py --db "$DB_URL" --days $D --output reports/insp-accept-$D.md || echo "EXIT=$? days=$D"
done
grep -c "近 1 天" reports/insp-accept-1.md; grep -c "近 30 天" reports/insp-accept-30.md
ls reports/anomaly_F*.png 2>/dev/null | head
```
预期：三份报告 exit 0/2；时段文案随 N；重点异常图落盘。

- [ ] **Step 2: 契约冻结校验**

```bash
# 先存改造前基线字段集（改造前跑一次），再对照改造后输出
python3 impl/inspection_analyzer.py --db "$DB_URL" --days 7 --json > /tmp/env.json; ec=$?
python3 - <<'EOF'
import json
d = json.load(open("/tmp/env.json"))
need = {"run_id", "generated_at", "days", "status", "summary", "findings", "dimensions"}
missing = need - set(d)
assert not missing, f"envelope 字段缺失: {missing}"
print("envelope OK:", sorted(d))
EOF
echo "exit=$ec"   # 0 或 2（检出异常），语义与改造前一致
python3 -m pytest impl/test_inspection.py -v
```
预期：envelope 必备字段齐全（need 集合以改造前实际基线输出为准抄写）；
既有 40 用例不回归；退出码语义不变。

- [ ] **Step 3: 全量评测重跑（47 + EVAL10）**

```bash
cd /home/scada/powerelf-skills && python3 docs/hermes_eval_runner.py --only-set inspection-eval-cases && python3 docs/hermes_eval_runner.py --only-set inspection-eval-criteria
```
预期：综合分 ≥ 0.755（基线 20260813-202128）。若个别用例因修复 1-3 翻转：逐条人工审
（预期方向：渗压尖峰类用例可能由 WARNING→INFO，属口径修正非退化），把审定结论写进验收记录。

- [ ] **Step 4: Hermes 端到端实跑（双交付验证）**

```bash
hermes chat -s powerelf-inspection -q "对全部设备执行一次完整智能巡检：覆盖近 7 天所有监测维度" --source p0-accept-$(date +%H%M) -Q
```
预期：回复含八章节报告路径 + 摘要（对照 spec §6 双交付契约）。

- [ ] **Step 5: 写验收记录 + commit**

`docs/inspection-report-p0-acceptance.md` 内容：三窗口冒烟结果、评测分数与基线对比、
翻转用例审定、hermes 实跑 session_id 与返回摘录。

```bash
git add docs/inspection-report-p0-acceptance.md reports/ 2>/dev/null; git add docs/inspection-report-p0-acceptance.md
git commit -m "test(inspection): P0验收四闸记录——三窗口冒烟/评测基线/契约冻结/端到端"
```

---

## 任务依赖

Task 1/2/3 顺序执行（同一文件递进修复）；Task 4、5 可与 1-3 并行（不同文件）；
Task 6 依赖 3+4+5；Task 7 依赖 6；Task 8 收尾依赖全部。
