# 离群检测增强（IQR + 百分位）+ 统计护栏 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `powerelf-data-governance` 增加 IQR 与百分位两种离群检测方法（CLI `--method mad|iqr|percentile`，默认 mad 完全向后兼容），并在 `_shared` 增加统计结论措辞护栏文档。

**Architecture:** 文档进 `_shared`（跨 skill 单一事实源）、可运行代码进各 skill（既有约定）。新增 `lib/outliers.py` 提供 `detect_iqr`/`detect_percentile`，返回结构与 `anomaly_detector.py` 内联 `detect_anomalies` 的 dict 形态对齐（含 `anomaly_count`/`anomaly_indices`），便于 `run_detection` 统一格式化。`anomaly_detector.py` 增纯函数 `detect_by_method(method, values, threshold)` 做方法分派与阈值解析（可脱离 DB 单测），`run_detection` 调用它并按方法输出 `mad_analysis`/`iqr_analysis`/`percentile_analysis` 块 + 顶层 `method` 字段。护栏为纯文档 + 指针，不做代码级强制。

**Tech Stack:** Python 3, numpy 2.4.6, pandas 3.0.1, sqlalchemy 2.0.48（均已就绪）。Markdown 文档。无新依赖。

## Global Constraints

- **向后兼容（硬性）**：不带 `--method` 时，`anomaly_detector.py` 的输出与改造前**逐字段一致**，仅新增顶层 `method: "mad"` 字段。mad 路径继续走内联 `detect_anomalies`（不切换到 `lib/mad.py` 的滑动窗口版，二者返回结构不同）。
- **密码/连接**：文档与代码中不得出现明文 DB 密码；CLI 示例统一用 `--db "$DB_URL"`（已由 `_shared/bootstrap.sh` 导出）。
- **代码约定**：`lib/` 模块风格对齐 `lib/mad.py`（模块级 docstring + 函数 docstring + `try/except ImportError` 守卫）。`impl/` 风格对齐 `impl/anomaly_detector.py`（`HAS_DEPS` 守卫，缺失即 `sys.exit(1)`）。
- **文档约定**：算法文档进 `_shared/algorithms/`，护栏文档进 `_shared/references/`；本地 skill 文档用相对路径指针指向 `_shared`。
- **架构约定（YAGNI）**：不实现多方法 composite 投票；不把可运行代码放进 `_shared/lib/`；不改 `writeback.py` 与报告生成主逻辑；不为 IQR/百分位建 per-indicator 阈值表（用 1.5×IQR / p1·p99 默认）。
- **提交约定**：每个 Task 末尾提交一次；提交信息用 conventional 中文前缀（`feat:`/`docs:`/`refactor:`）；多行用多个 `-m` 标志（不用 heredoc）；末尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- **工作目录**：所有相对路径以 monorepo 根 `/home/scada/powerelf-skills` 为基准。运行测试用 `cd /home/scada/powerelf-skills`。

## 文件结构

| 路径 | 动作 | 职责 |
|------|------|------|
| `powerelf-data-governance/lib/outliers.py` | 新建 | `detect_iqr(values, k=1.5)` + `detect_percentile(values, low=1, high=99)`，返回含 `anomaly_count`/`anomaly_indices` 的 dict |
| `powerelf-data-governance/lib/test_outliers.py` | 新建 | 合成数据单元测试：outliers.py 两函数 + anomaly_detector 的 `detect_by_method` 分派/阈值解析 |
| `powerelf-data-governance/impl/anomaly_detector.py` | 修改 | 加 `import os` + 路径注入 + `from lib.outliers import ...`；新增 `detect_by_method`；`run_detection` 增 `method` 参数与方法分派；`comprehensive_judge` 增 `method_label` 参数（默认 `"MAD"` 保兼容）；`main` 增 `--method` |
| `_shared/algorithms/outlier-methods.md` | 新建 | IQR/百分位算法文档：三法对比、选择指南、公式、Python 片段、与 MAD 互补、卡滞注意 |
| `_shared/references/statistical-caution.md` | 新建 | 统计护栏：相关≠因果、多重比较、Simpson、幸存者偏差、生态谬误、假精度 + 结论措辞自检清单 |
| `_shared/algorithms/mad.md` | 修改 | 末尾加"姊妹方法"交叉链接到 `outlier-methods.md` |
| `powerelf-early-warning/strategies/notification-strategy.md` | 修改 | 加一句指针：生成结论文案前查 `statistical-caution.md` |
| `powerelf-data-governance/SKILL.md` | 修改 | 工具命令段补 `--method`；模块架构 lib/ 列表加 `outliers.py`；按需加载指令加 IQR/百分位；报告段加护栏指针 |

---

## Task 1: 新建 `lib/outliers.py` + 单元测试（TDD）

**Files:**
- Create: `powerelf-data-governance/lib/outliers.py`
- Create: `powerelf-data-governance/lib/test_outliers.py`

**Interfaces:**
- Produces: `detect_iqr(values, k=1.5) -> dict{q1,q3,iqr,lower_bound,upper_bound,anomaly_count,anomaly_indices,total_points}`；`detect_percentile(values, low=1, high=99) -> dict{low_bound,high_bound,anomaly_count,anomaly_indices,total_points}`。Task 2 的 `detect_by_method` 将消费这两个函数。

- [ ] **Step 1: 写失败测试 `lib/test_outliers.py`**

创建 `powerelf-data-governance/lib/test_outliers.py`，完整内容：

```python
#!/usr/bin/env python3
"""
outliers.py 单元测试 + anomaly_detector.detect_by_method 分派测试。
用法: cd powerelf-data-governance && python3 lib/test_outliers.py
不依赖数据库。仅 numpy 必需；detect_by_method 测试需 pandas+sqlalchemy（缺失则跳过）。
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))            # .../lib
_SKILL_ROOT = os.path.dirname(_HERE)                            # .../powerelf-data-governance
sys.path.insert(0, _HERE)                                       # -> from outliers import ...
sys.path.insert(0, _SKILL_ROOT)                                 # -> from impl.anomaly_detector import ...

from outliers import detect_iqr, detect_percentile

# detect_by_method 测试可选（需 anomaly_detector 的重依赖）
try:
    import pandas  # noqa: F401
    import sqlalchemy  # noqa: F401
    from impl.anomaly_detector import detect_by_method
    HAS_DETECTOR = True
except ImportError:
    HAS_DETECTOR = False


# ============================================================
# detect_iqr
# ============================================================

def test_iqr_finds_injected_outlier():
    """11 点序列 [1..10, 100]，100 应被检出，边界可手算。"""
    vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100]
    r = detect_iqr(vals, k=1.5)
    # numpy 线性插值：p25=3.5, p75=8.5, IQR=5.0, lower=-4.0, upper=16.0
    assert r["q1"] == 3.5, r
    assert r["q3"] == 8.5, r
    assert r["iqr"] == 5.0, r
    assert r["lower_bound"] == -4.0, r
    assert r["upper_bound"] == 16.0, r
    assert r["anomaly_indices"] == [10], r
    assert r["anomaly_count"] == 1, r
    assert r["total_points"] == 11, r


def test_iqr_degenerate_all_equal():
    """所有值相同 → IQR=0，无离群，不报错。"""
    r = detect_iqr([5, 5, 5, 5, 5], k=1.5)
    assert r["iqr"] == 0.0, r
    assert r["anomaly_count"] == 0, r
    assert r["anomaly_indices"] == [], r


def test_iqr_clean_array_no_outliers():
    """平稳序列无离群。"""
    vals = [10.0, 10.1, 9.9, 10.2, 9.8, 10.0, 10.1, 9.9, 10.0, 10.1]
    r = detect_iqr(vals, k=1.5)
    assert r["anomaly_count"] == 0, r


def test_iqr_invalid_k_falls_back():
    """k <= 0 回退到 1.5。"""
    r = detect_iqr([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], k=-1)
    assert r["anomaly_count"] == 1, r
    assert r["anomaly_indices"] == [10], r


def test_iqr_empty():
    r = detect_iqr([], k=1.5)
    assert r["anomaly_count"] == 0, r
    assert r["total_points"] == 0, r


# ============================================================
# detect_percentile
# ============================================================

def test_percentile_finds_injected_outlier():
    """50 个 10 + 一个 999；p99 落在 10 与 999 之间，999 被检出。"""
    vals = [10.0] * 50 + [999.0]
    r = detect_percentile(vals, low=1, high=99)
    # p1=10.0, p99=504.5 (线性插值)
    assert r["low_bound"] == 10.0, r
    assert r["high_bound"] == 504.5, r
    assert r["anomaly_indices"] == [50], r
    assert r["anomaly_count"] == 1, r
    assert r["total_points"] == 51, r


def test_percentile_uniform_tails():
    """[1..100] 均匀序列，p1/p99 边界外仅首尾两点。"""
    vals = list(range(1, 101))
    r = detect_percentile(vals, low=1, high=99)
    assert r["anomaly_indices"] == [0, 99], r
    assert r["anomaly_count"] == 2, r


def test_percentile_invalid_low_high_swaps():
    """low >= high 时回退到 1/99。"""
    r = detect_percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], low=80, high=20)
    # 不报错，且仍返回合法结构
    assert "anomaly_count" in r and "anomaly_indices" in r, r


def test_percentile_empty():
    r = detect_percentile([], low=1, high=99)
    assert r["anomaly_count"] == 0, r
    assert r["total_points"] == 0, r


# ============================================================
# detect_by_method（仅当重依赖可用）
# ============================================================

if HAS_DETECTOR:
    def test_dispatch_mad_default():
        r = detect_by_method("mad", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], threshold=None)
        assert r["method"] == "mad", r
        assert r["analysis_key"] == "mad_analysis", r
        assert 10 in r["result"]["anomaly_indices"], r
        assert r["score_label"] == "z_score", r

    def test_dispatch_iqr_default_threshold():
        r = detect_by_method("iqr", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], threshold=None)
        assert r["method"] == "iqr", r
        assert r["threshold"] == 1.5, r
        assert r["analysis_key"] == "iqr_analysis", r
        assert 10 in r["result"]["anomaly_indices"], r
        assert r["score_label"] is None, r

    def test_dispatch_iqr_explicit_k():
        r = detect_by_method("iqr", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], threshold=3.0)
        assert r["threshold"] == 3.0, r

    def test_dispatch_iqr_invalid_k_falls_back():
        r = detect_by_method("iqr", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], threshold=-2)
        assert r["threshold"] == 1.5, r

    def test_dispatch_percentile_default():
        r = detect_by_method("percentile", [10.0] * 50 + [999.0], threshold=None)
        assert r["method"] == "percentile", r
        assert r["threshold"] == 1, r
        assert r["analysis_key"] == "percentile_analysis", r
        assert 50 in r["result"]["anomaly_indices"], r
        assert r["score_label"] is None, r

    def test_dispatch_percentile_invalid_p_falls_back():
        r = detect_by_method("percentile", [10.0] * 50 + [999.0], threshold=60)
        assert r["threshold"] == 1, r

    def test_dispatch_unknown_method_raises():
        try:
            detect_by_method("zscore", [1, 2, 3], threshold=None)
            assert False, "应抛 ValueError"
        except ValueError:
            pass


# ============================================================
# 运行器
# ============================================================

def _run():
    import inspect
    g = globals()
    tests = [(n, f) for n, f in g.items() if n.startswith("test_") and callable(f)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ FAIL  {name}: {e}")
            failed += 1
    total = passed + failed
    print(f"\n总计 {total} 项: 通过 {passed}, 失败 {failed}")
    if not HAS_DETECTOR:
        print("(pandas/sqlalchemy 缺失，detect_by_method 测试已跳过)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_run())
```

- [ ] **Step 2: 运行测试，确认失败（outliers.py 尚不存在）**

Run:
```bash
cd /home/scada/powerelf-skills && python3 powerelf-data-governance/lib/test_outliers.py
```
Expected: 失败，首行 `ModuleNotFoundError: No module named 'outliers'`（或 `ImportError`）。detect_by_method 部分也会因 `impl.anomaly_detector` 无该函数而失败——本 Task 只关注 outliers 部分，detect_by_method 失败留到 Task 2。

- [ ] **Step 3: 实现 `lib/outliers.py`**

创建 `powerelf-data-governance/lib/outliers.py`，完整内容：

```python
"""
Outlier Detection Module (IQR + Percentile)
============================================

MAD 的互补离群检测方法，针对偏态分布（雨量、流量，零膨胀/长尾）。
MAD 适合正态/缓变指标（水位、GNSS、渗压）；IQR 与百分位法对偏态更稳健。

返回结构对齐 anomaly_detector.detect_anomalies() 的 dict 形态
（含 anomaly_count / anomaly_indices），便于 run_detection 统一格式化。

References:
  - _shared/algorithms/outlier-methods.md（单一事实源）
  - _shared/algorithms/mad.md（姊妹方法）
"""

try:
    import numpy as np
except ImportError:
    raise ImportError("outliers.py 需要 numpy: pip install numpy")


def detect_iqr(values, k=1.5):
    """IQR（四分位距）离群检测，对偏态分布稳健。

    边界: [Q1 - k*IQR, Q3 + k*IQR]，超出即离群。
      k=1.5 标准（温和）；k=3.0 激进（仅标记极端值）。

    Args:
        values: 数值序列（list / ndarray）。
        k: IQR 倍数，默认 1.5。k <= 0 视为非法，回退到 1.5。

    Returns:
        dict: {q1, q3, iqr, lower_bound, upper_bound,
               anomaly_count, anomaly_indices, total_points}
        IQR=0（所有值相同/四分位重合）时 lower=upper=中位水平，判定无离群。
    """
    arr = np.asarray(values, dtype=float)
    n = int(arr.size)
    if n == 0:
        return {"q1": None, "q3": None, "iqr": 0.0,
                "lower_bound": None, "upper_bound": None,
                "anomaly_count": 0, "anomaly_indices": [], "total_points": 0}
    if k is None or k <= 0:
        k = 1.5

    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr

    if iqr == 0:
        anomaly_indices = []
    else:
        mask = (arr < lower) | (arr > upper)
        anomaly_indices = np.where(mask)[0].tolist()

    return {
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(float(iqr), 4),
        "lower_bound": round(float(lower), 4),
        "upper_bound": round(float(upper), 4),
        "anomaly_count": len(anomaly_indices),
        "anomaly_indices": anomaly_indices,
        "total_points": n,
    }


def detect_percentile(values, low=1, high=99):
    """百分位法离群检测，最简单，适合海量快速筛查。

    边界: [p_low, p_high]，超出即离群。注意：此法总会标记尾部，对非典型分布
    无理论保证，适合快速筛查而非精确定量。

    Args:
        values: 数值序列。
        low: 下尾百分位（默认 1 -> p1）。
        high: 上尾百分位（默认 99 -> p99）。

    Returns:
        dict: {low_bound, high_bound, anomaly_count, anomaly_indices, total_points}
    """
    arr = np.asarray(values, dtype=float)
    n = int(arr.size)
    if n == 0:
        return {"low_bound": None, "high_bound": None,
                "anomaly_count": 0, "anomaly_indices": [], "total_points": 0}

    low = 0.0 if low is None else float(low)
    high = 100.0 if high is None else float(high)
    low = max(0.0, min(low, 100.0))
    high = max(0.0, min(high, 100.0))
    if low >= high:
        low, high = 1.0, 99.0

    low_bound = float(np.percentile(arr, low))
    high_bound = float(np.percentile(arr, high))

    mask = (arr < low_bound) | (arr > high_bound)
    anomaly_indices = np.where(mask)[0].tolist()

    return {
        "low_bound": round(low_bound, 4),
        "high_bound": round(high_bound, 4),
        "anomaly_count": len(anomaly_indices),
        "anomaly_indices": anomaly_indices,
        "total_points": n,
    }
```

- [ ] **Step 4: 运行 outliers 部分，确认通过（detect_by_method 仍失败属预期）**

Run:
```bash
cd /home/scada/powerelf-skills && python3 powerelf-data-governance/lib/test_outliers.py
```
Expected: 8 项 `test_iqr_*` / `test_percentile_*` 全部 ✅ PASS；`detect_by_method` 7 项 ❌ FAIL（`AttributeError: module 'impl.anomaly_detector' has no attribute 'detect_by_method'` 或导入失败）。总计 15 项，通过 8，失败 7。若 outliers 测试有失败，先修 `outliers.py` 再继续。

- [ ] **Step 5: 提交**

```bash
cd /home/scada/powerelf-skills
git add powerelf-data-governance/lib/outliers.py powerelf-data-governance/lib/test_outliers.py
git commit -m "feat(data-governance): 新增 outliers.py(IQR+百分位离群检测)与单元测试" -m "detect_iqr/detect_percentile 返回结构对齐 anomaly_detector 内联 detect_anomalies 的 dict 形态。测试覆盖注入离群点、退化(IQR=0)、空序列、非法参数回退。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: `anomaly_detector.py` 集成 `--method` + 分派单测

**Files:**
- Modify: `powerelf-data-governance/impl/anomaly_detector.py`（顶部 import 区、新增 `detect_by_method`、重写 `run_detection`、`comprehensive_judge` 增参、重写 `main` 与模块 docstring）
- Modify: `powerelf-data-governance/lib/test_outliers.py`（detect_by_method 测试已在上一步写好，本步让其转绿）

**Interfaces:**
- Consumes: Task 1 的 `detect_iqr` / `detect_percentile`。
- Produces: `detect_by_method(method, values, threshold) -> dict{method, threshold, result, analysis, analysis_key, score_label, score_source, method_label}`；`run_detection(..., method="mad")`；CLI `--method`。

- [ ] **Step 1: 修改模块 docstring（第 1-15 行）**

将 `powerelf-data-governance/impl/anomaly_detector.py` 顶部 docstring 的"用法"段替换为含 `--method` 的版本。old（第 2-14 行附近）：

```python
"""
MAD 异常检测算子（基于 rules/anomaly-detection.md）
直接调用，Agent 不需要自己写 SQL 或理解算法细节。

用法:
  python3 anomaly_detector.py --db "$DB_URL" \
    --table st_pressure_r --field water_pressure --threshold 4.0

  python3 anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --threshold 3.0 --st-id 128

  python3 anomaly_detector.py --db "$DB_URL" --table st_pptn_r --field p --threshold 5.0 --days 7

输出: JSON 格式的检测结果，包含 median, MAD, z_score, 异常点列表, 判定依据。
"""
```

new:

```python
"""
异常检测算子（MAD / IQR / 百分位，基于 rules/anomaly-detection.md 与
_shared/algorithms/outlier-methods.md）
直接调用，Agent 不需要自己写 SQL 或理解算法细节。

用法:
  # MAD（默认，正态/缓变指标：水位/GNSS/渗压）
  python3 anomaly_detector.py --db "$DB_URL" \
    --table st_pressure_r --field water_pressure --threshold 4.0

  # IQR（偏态指标：雨量/流量）；--threshold 为 IQR 倍数 k（默认 1.5）
  python3 anomaly_detector.py --db "$DB_URL" --table st_pptn_r --field p --method iqr

  # 百分位（快速筛查）；--threshold 为尾部百分位 p（默认 1 -> p1/p99）
  python3 anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --method percentile

  python3 anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --threshold 3.0 --st-id 128

--threshold 语义随 --method:
  mad         修正 Z 阈值（默认按字段自动选择）
  iqr         IQR 倍数 k（默认 1.5；3.0 激进）
  percentile  尾部百分位 p（默认 1，即 p1/p99）

输出: JSON 格式检测结果，含 method、分析块(mad_analysis/iqr_analysis/percentile_analysis)、
      异常点列表、综合判定。不带 --method 时与历史版本完全兼容（仅多 method 字段）。
"""
```

- [ ] **Step 2: 在 HAS_DEPS 块后插入路径注入与 outliers 导入**

定位第 17-30 行的 import 块与 `HAS_DEPS` 守卫。在 `except ImportError:` 块之后（第 30 行 `sys.exit(1)` 之后、`DEFAULT_THRESHOLDS` 注释之前）插入。先把第 17-19 行的 `import argparse / import json / import sys / from datetime import datetime` 中的 `import sys` 保留，并新增 `import os`。

old（第 17-19 行）：
```python
import argparse
import json
import sys
from datetime import datetime
```
new:
```python
import argparse
import json
import os
import sys
from datetime import datetime
```

然后在 `sys.exit(1)`（第 30 行）之后、`# =====...` 分指标注释（第 33 行）之前插入：

```python


# 把 skill 根加入 sys.path 以便 from lib.outliers import ...
_HERE = os.path.dirname(os.path.abspath(__file__))            # .../impl
_SKILL_ROOT = os.path.dirname(_HERE)                            # .../powerelf-data-governance
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)
from lib.outliers import detect_iqr, detect_percentile
```

- [ ] **Step 3: 给 `comprehensive_judge` 增加 `method_label` 参数（默认 "MAD"，保兼容）**

old（第 146-174 行的 `def comprehensive_judge` 函数体）：
```python
def comprehensive_judge(mad_result, change_rate_result, threshold):
    """综合判定（MAD + 变化率交叉验证）"""
    has_mad_anomaly = mad_result["anomaly_count"] > 0
    has_rate_anomaly = len(change_rate_result) > 0

    if has_mad_anomaly and has_rate_anomaly:
        return {
            "level": "CRITICAL",
            "confidence": "high",
            "message": "MAD异常 + 变化率超标，确认异常",
        }
    elif has_mad_anomaly and not has_rate_anomaly:
        return {
            "level": "WARNING",
            "confidence": "medium",
            "message": "MAD异常但变化率正常，可能异常，检查是否为正常波动峰值",
        }
    elif not has_mad_anomaly and has_rate_anomaly:
        return {
            "level": "INFO",
            "confidence": "low",
            "message": "MAD正常但变化率超标，可疑，标记待人工确认",
        }
    else:
        return {
            "level": "OK",
            "confidence": "high",
            "message": "MAD正常且变化率正常，数据在历史分布范围内",
        }
```

new:
```python
def comprehensive_judge(mad_result, change_rate_result, threshold, method_label="MAD"):
    """综合判定（离群检测 + 变化率交叉验证）。

    method_label 仅影响 message 文案（MAD/IQR/百分位）；默认 "MAD" 时输出与历史版本逐字一致。
    判定逻辑只依赖 anomaly_count，与具体检测方法无关。
    """
    has_mad_anomaly = mad_result["anomaly_count"] > 0
    has_rate_anomaly = len(change_rate_result) > 0

    if has_mad_anomaly and has_rate_anomaly:
        return {
            "level": "CRITICAL",
            "confidence": "high",
            "message": f"{method_label}异常 + 变化率超标，确认异常",
        }
    elif has_mad_anomaly and not has_rate_anomaly:
        return {
            "level": "WARNING",
            "confidence": "medium",
            "message": f"{method_label}异常但变化率正常，可能异常，检查是否为正常波动峰值",
        }
    elif not has_mad_anomaly and has_rate_anomaly:
        return {
            "level": "INFO",
            "confidence": "low",
            "message": f"{method_label}正常但变化率超标，可疑，标记待人工确认",
        }
    else:
        return {
            "level": "OK",
            "confidence": "high",
            "message": f"{method_label}正常且变化率正常，数据在历史分布范围内",
        }
```

- [ ] **Step 4: 新增 `detect_by_method` 纯函数（插在 `comprehensive_judge` 之后、`run_detection` 之前）**

在 `comprehensive_judge` 函数结束后、`def run_detection` 之前插入：

```python
def detect_by_method(method, values, threshold):
    """按 method 分派离群检测，返回统一结构（可脱离 DB 单测）。

    Args:
        method: "mad" | "iqr" | "percentile"
        values: 数值序列
        threshold: 用户传入的阈值（语义随 method）；None 表示用方法默认。

    Returns:
        dict:
          method        实际方法
          threshold     解析后实际使用的阈值
          result        检测结果 dict（含 anomaly_count/anomaly_indices）
          analysis      供输出 JSON 的分析摘要 dict
          analysis_key  输出 JSON 中分析块的字段名(mad_analysis/iqr_analysis/percentile_analysis)
          score_label   异常点详情里附带的分值字段名(mad="z_score"，其余 None)
          score_source  result 中分值列表的字段名(mad="z_scores"，其余 None)
          method_label  综合判定的文案标签(MAD/IQR/百分位)
    """
    if method == "mad":
        t = 4.0 if threshold is None else threshold
        result = detect_anomalies(values, t)
        total = result["total_points"]
        analysis = {
            "median": result["median"],
            "mad": result["mad"],
            "anomaly_count": result["anomaly_count"],
            "anomaly_rate": f"{result['anomaly_count']/total*100:.1f}%" if total else "0.0%",
        }
        return {"method": "mad", "threshold": t, "result": result,
                "analysis": analysis, "analysis_key": "mad_analysis",
                "score_label": "z_score", "score_source": "z_scores",
                "method_label": "MAD"}

    elif method == "iqr":
        k = threshold
        if k is None or k <= 0:
            k = 1.5
        result = detect_iqr(values, k=k)
        total = result["total_points"]
        analysis = {
            "q1": result["q1"], "q3": result["q3"], "iqr": result["iqr"],
            "lower_bound": result["lower_bound"], "upper_bound": result["upper_bound"],
            "anomaly_count": result["anomaly_count"],
            "anomaly_rate": f"{result['anomaly_count']/total*100:.1f}%" if total else "0.0%",
        }
        return {"method": "iqr", "threshold": k, "result": result,
                "analysis": analysis, "analysis_key": "iqr_analysis",
                "score_label": None, "score_source": None,
                "method_label": "IQR"}

    elif method == "percentile":
        p = threshold
        if p is None or p <= 0 or p >= 50:
            p = 1
        result = detect_percentile(values, low=p, high=100 - p)
        total = result["total_points"]
        analysis = {
            "low_bound": result["low_bound"], "high_bound": result["high_bound"],
            "anomaly_count": result["anomaly_count"],
            "anomaly_rate": f"{result['anomaly_count']/total*100:.1f}%" if total else "0.0%",
        }
        return {"method": "percentile", "threshold": p, "result": result,
                "analysis": analysis, "analysis_key": "percentile_analysis",
                "score_label": None, "score_source": None,
                "method_label": "百分位"}

    raise ValueError(f"未知检测方法: {method}（可选: mad / iqr / percentile）")
```

- [ ] **Step 5: 重写 `run_detection`，增加 `method` 参数与方法分派**

old（第 177-258 行整段 `def run_detection`）：
```python
def run_detection(engine, table, field, threshold=None, st_id=None, days=30):
    """执行完整的 MAD 异常检测流程"""

    # 默认阈值
    if threshold is None:
        threshold = DEFAULT_THRESHOLDS.get(field, 4.0)

    # 加载数据
    df = load_data(engine, table, field, st_id, days)
    if df.empty:
        return {
            "status": "NO_DATA",
            "message": f"表 {table} 无数据（st_id={st_id}, days={days}）",
        }

    clean_series = pd.to_numeric(df[field], errors='coerce').dropna()
    values = clean_series.values
    if len(values) < 10:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": f"数据点不足: {len(values)}个（需要至少10个）",
            "data_points": len(values),
        }

    # MAD 检测
    mad_result = detect_anomalies(values, threshold)

    # 变化率检测
    change_rate_result = detect_change_rate(values, field)

    # 综合判定
    judgment = comprehensive_judge(mad_result, change_rate_result, threshold)

    # 构建异常点详情
    tm_cols = [c for c in df.columns if c != field]
    tm_col = tm_cols[0] if tm_cols else None
    anomaly_details = []
    for idx in mad_result["anomaly_indices"]:
        original_idx = clean_series.index[idx]
        detail = {
            "index": int(original_idx),
            "value": round(float(values[idx]), 4),
            "z_score": mad_result["z_scores"][idx],
        }
        if tm_col and original_idx in df.index:
            detail["time"] = str(df.loc[original_idx, tm_col])
        anomaly_details.append(detail)

    # 解释集
    explanation = (
        f"对 {table}.{field} 做 MAD 异常检测: "
        f"数据点{mad_result['total_points']}个, "
        f"中位数{mad_result['median']}, "
        f"MAD={mad_result['mad']}, "
        f"阈值={threshold}, "
        f"发现{mad_result['anomaly_count']}个异常点。"
        f"综合判定: {judgment['message']} (置信度{judgment['confidence']})"
    )

    return {
        "status": "OK",
        "table": table,
        "field": field,
        "st_id": st_id,
        "days": days,
        "threshold": threshold,
        "data_points": mad_result["total_points"],
        "mad_analysis": {
            "median": mad_result["median"],
            "mad": mad_result["mad"],
            "anomaly_count": mad_result["anomaly_count"],
            "anomaly_rate": f"{mad_result['anomaly_count']/mad_result['total_points']*100:.1f}%",
        },
        "change_rate_analysis": {
            "exceed_count": len(change_rate_result),
            "threshold": CHANGE_RATE_THRESHOLDS.get(field, 0.10),
            "exceed_details": change_rate_result[:5],  # 最多5条
        },
        "judgment": judgment,
        "anomaly_details": anomaly_details[:10],  # 最多10条
        "explanation": explanation,
    }
```

new:
```python
def run_detection(engine, table, field, threshold=None, st_id=None, days=30, method="mad"):
    """执行离群检测流程（MAD / IQR / 百分位）。

    method="mad" 时与历史版本完全兼容（仅输出多一个 method 字段）。
    """

    # 阈值解析：mad 走分指标默认；iqr/percentile 由 detect_by_method 兜底
    if method == "mad" and threshold is None:
        threshold = DEFAULT_THRESHOLDS.get(field, 4.0)
    # 越界告警（告警但继续，detect_by_method 会回退默认）
    if method == "iqr" and threshold is not None and threshold <= 0:
        print(f"[WARN] iqr 倍数 k={threshold} 非法(需>0)，回退到 1.5", file=sys.stderr)
    if method == "percentile" and threshold is not None and (threshold <= 0 or threshold >= 50):
        print(f"[WARN] percentile 尾部 p={threshold} 越界(需 0<p<50)，回退到 1", file=sys.stderr)

    # 加载数据
    df = load_data(engine, table, field, st_id, days)
    if df.empty:
        return {
            "status": "NO_DATA",
            "message": f"表 {table} 无数据（st_id={st_id}, days={days}）",
        }

    clean_series = pd.to_numeric(df[field], errors='coerce').dropna()
    values = clean_series.values
    if len(values) < 10:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": f"数据点不足: {len(values)}个（需要至少10个）",
            "data_points": len(values),
        }

    # 方法分派（纯函数，可单测）
    dispatch = detect_by_method(method, values, threshold)
    anom_result = dispatch["result"]
    analysis_key = dispatch["analysis_key"]
    analysis = dispatch["analysis"]
    score_label = dispatch["score_label"]
    score_source = dispatch["score_source"]
    method_label = dispatch["method_label"]
    resolved_threshold = dispatch["threshold"]

    # 变化率检测（对所有方法适用，互补）
    change_rate_result = detect_change_rate(values, field)

    # 综合判定（仅依赖 anomaly_count，方法无关）
    judgment = comprehensive_judge(anom_result, change_rate_result, resolved_threshold, method_label)

    # 构建异常点详情
    tm_cols = [c for c in df.columns if c != field]
    tm_col = tm_cols[0] if tm_cols else None
    anomaly_details = []
    for idx in anom_result["anomaly_indices"]:
        original_idx = clean_series.index[idx]
        detail = {
            "index": int(original_idx),
            "value": round(float(values[idx]), 4),
        }
        if score_label and score_source and score_source in anom_result:
            detail[score_label] = anom_result[score_source][idx]
        if tm_col and original_idx in df.index:
            detail["time"] = str(df.loc[original_idx, tm_col])
        anomaly_details.append(detail)

    # 解释集
    explanation = (
        f"对 {table}.{field} 做 {method_label} 离群检测: "
        f"数据点{anom_result['total_points']}个, "
        f"阈值={resolved_threshold}, "
        f"发现{anom_result['anomaly_count']}个离群点。"
        f"综合判定: {judgment['message']} (置信度{judgment['confidence']})"
    )

    return {
        "status": "OK",
        "table": table,
        "field": field,
        "st_id": st_id,
        "days": days,
        "method": method,
        "threshold": resolved_threshold,
        "data_points": anom_result["total_points"],
        analysis_key: analysis,
        "change_rate_analysis": {
            "exceed_count": len(change_rate_result),
            "threshold": CHANGE_RATE_THRESHOLDS.get(field, 0.10),
            "exceed_details": change_rate_result[:5],  # 最多5条
        },
        "judgment": judgment,
        "anomaly_details": anomaly_details[:10],  # 最多10条
        "explanation": explanation,
    }
```

- [ ] **Step 6: 重写 `main()`，增加 `--method` 参数**

old（第 261-273 行）：
```python
def main():
    parser = argparse.ArgumentParser(description="MAD 异常检测算子")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--table", required=True, help="传感器表名")
    parser.add_argument("--field", required=True, help="检测字段名")
    parser.add_argument("--threshold", type=float, default=None, help="MAD阈值（默认按字段自动选择）")
    parser.add_argument("--st-id", type=int, default=None, help="测站ID")
    parser.add_argument("--days", type=int, default=30, help="检测天数")
    args = parser.parse_args()

    engine = create_engine(args.db)
    result = run_detection(engine, args.table, args.field, args.threshold, args.st_id, args.days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

new:
```python
def main():
    parser = argparse.ArgumentParser(description="异常检测算子（MAD / IQR / 百分位）")
    parser.add_argument("--db", required=True, help="数据库连接")
    parser.add_argument("--table", required=True, help="传感器表名")
    parser.add_argument("--field", required=True, help="检测字段名")
    parser.add_argument("--method", choices=["mad", "iqr", "percentile"], default="mad",
                        help="离群检测方法: mad(默认,修正Z) / iqr(四分位距) / percentile(百分位)")
    parser.add_argument("--threshold", type=float, default=None,
                        help="阈值，语义随 --method: mad=修正Z(默认按字段) / iqr=IQR倍数k(默认1.5) / percentile=尾部百分位p(默认1→p1/p99)")
    parser.add_argument("--st-id", type=int, default=None, help="测站ID")
    parser.add_argument("--days", type=int, default=30, help="检测天数")
    args = parser.parse_args()

    engine = create_engine(args.db)
    result = run_detection(engine, args.table, args.field, args.threshold,
                           args.st_id, args.days, args.method)
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

- [ ] **Step 7: 运行全部单元测试，确认全绿**

Run:
```bash
cd /home/scada/powerelf-skills && python3 powerelf-data-governance/lib/test_outliers.py
```
Expected: 全部 15 项 ✅ PASS，`总计 15 项: 通过 15, 失败 0`。若 detect_by_method 项有失败，检查 `detect_by_method` 的 `score_label`/`score_source`/`analysis_key` 返回值与测试断言一致。

- [ ] **Step 8: 验证 `--help` 与向后兼容（不连 DB）**

Run:
```bash
cd /home/scada/powerelf-skills && python3 powerelf-data-governance/impl/anomaly_detector.py --help | head -20
```
Expected: 帮助文本含 `--method {mad,iqr,percentile}` 与 `--threshold` 的新语义说明。

Run（验证非法 method 被 argparse 拦截）:
```bash
cd /home/scada/powerelf-skills && python3 powerelf-data-governance/impl/anomaly_detector.py --db "x" --table st_rsvr_r --field rz --method zscore 2>&1 | tail -3
```
Expected: argparse 报错 `invalid choice: 'zscore'`，退出码 2。

- [ ] **Step 9: 提交**

```bash
cd /home/scada/powerelf-skills
git add powerelf-data-governance/impl/anomaly_detector.py powerelf-data-governance/lib/test_outliers.py
git commit -m "feat(data-governance): anomaly_detector 增加 --method mad|iqr|percentile" -m "新增纯函数 detect_by_method 做方法分派与阈值解析(可脱离 DB 单测)；run_detection 增 method 参数与方法感知分析块；comprehensive_judge 增 method_label 参数(默认 MAD 保逐字兼容)；CLI 增 --method。默认 mad 路径与历史输出逐字段一致，仅多 method 字段。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: 新建 `_shared/algorithms/outlier-methods.md`

**Files:**
- Create: `_shared/algorithms/outlier-methods.md`

- [ ] **Step 1: 写文档**

创建 `_shared/algorithms/outlier-methods.md`，完整内容：

````markdown
# 离群检测方法对比（IQR / 百分位 / MAD）

> 跨 skill 单一事实源。`powerelf-data-governance/impl/anomaly_detector.py` 的 `--method mad|iqr|percentile`
> 与 `lib/outliers.py` 实现均以本文档为准。姊妹方法见 [`mad.md`](mad.md)。

## 一、三法对比

| 方法 | 适用分布 | 稳健性 | 参数 | 计算成本 | 何时用 |
|------|----------|--------|------|----------|--------|
| **MAD**（修正 Z） | 正态 / 缓变 | 极高（基于中位数） | 修正 Z 阈值 3.0–5.0 | 低 | 水位、GNSS、渗压等近正态/缓变指标 |
| **IQR**（四分位距） | 偏态 / 长尾 | 高（基于分位数） | IQR 倍数 k=1.5(标准)/3.0(激进) | 低 | 雨量、流量等零膨胀/偏态分布 |
| **百分位法** | 任意 | 中（总会标记尾部） | 尾部百分位 p=1(p1/p99) | 极低 | 海量数据快速筛查，对分布无假设 |

选法口诀：**正态缓变用 MAD，偏态长尾用 IQR，海量筛查用百分位。**

## 二、IQR（四分位距法）

### 公式

```
Q1 = p25,  Q3 = p75,  IQR = Q3 - Q1
lower = Q1 - k * IQR
upper = Q3 + k * IQR
超出 [lower, upper] 即离群
```

- `k=1.5`：标准箱线图规则，温和（标记明显离群）。
- `k=3.0`：激进，仅标记极端值，减少误报。

### Python

```python
import numpy as np

def detect_iqr(values, k=1.5):
    arr = np.asarray(values, dtype=float)
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    lower, upper = q1 - k * iqr, q3 + k * iqr
    if iqr == 0:
        return []                      # 所有值相同，无离群
    mask = (arr < lower) | (arr > upper)
    return np.where(mask)[0].tolist()
```

### 注意

- **样本 < 10 不检测**（统计意义不足，`anomaly_detector` 已在上游拦截）。
- `IQR == 0`（四分位重合，常见于大量重复值）退化为"无离群"，不报错。
- 对极端偏态（如雨量 0 占 90%），IQR 仍可能把大量非零值判为离群——此时优先用百分位法或分段分析。

## 三、百分位法

### 公式

```
low_bound  = p_low   (默认 p1)
high_bound = p_high  (默认 p99)
超出 [low_bound, high_bound] 即离群
```

### Python

```python
import numpy as np

def detect_percentile(values, low=1, high=99):
    arr = np.asarray(values, dtype=float)
    low_bound, high_bound = np.percentile(arr, [low, high])
    mask = (arr < low_bound) | (arr > high_bound)
    return np.where(mask)[0].tolist()
```

### 注意

- **总会标记尾部**：p1/p99 在大样本下约标记 2% 的点。这是特性非缺陷——适合"快速筛查找候选"，不适合"精确定量异常率"。
- 对非典型分布（多峰、重尾）无理论保证。
- `low >= high` 时回退到 1/99（`lib/outliers.py` 已处理）。

## 四、与 MAD 的关系（互补，非替代）

- **MAD** 基于中位数与绝对偏差，对单峰近正态分布最优；对零膨胀/重尾分布，MAD 常被大量重复值拉到 0，退化为绝对差判断，灵敏度下降。
- **IQR** 基于分位数，不依赖中位数邻近结构，对偏态更稳。
- **百分位** 不假设分布形状，最通用但最粗。
- 三者不互斥：同一指标可分别用 MAD 与 IQR 跑，结果交集=高置信异常。**多方法 composite 投票** 为后续增强（见 spec §9），当前 CLI 为单方法互斥（方案甲）。

## 五、`anomaly_detector` CLI 语义

| `--method` | `--threshold` 含义 | 默认 | 输出分析块 |
|------------|---------------------|------|------------|
| `mad`（默认） | 修正 Z 阈值 | 按字段（rz=3.0 / p=5.0 / 渗压=4.0 / 默认 4.0） | `mad_analysis` |
| `iqr` | IQR 倍数 k | 1.5 | `iqr_analysis` |
| `percentile` | 尾部百分位 p（取 p 与 100-p） | 1（p1/p99） | `percentile_analysis` |

输出 JSON 顶层含 `method` 字段溯源；其余结构与 `mad` 路径一致（`change_rate_analysis`、`judgment`、`anomaly_details`、`explanation`）。

## 六、卡滞检测注意

雨量传感器是**步进式读数**（如 0.5mm 一跳），连续相同值属正常工况，不是卡滞。
- 用 IQR/百分位检测雨量时，大量 0 值会把非零降雨全推到上尾——需结合 `_shared/references/schema.md` 的字段语义判断是否合理。
- 卡滞判定应走独立的 `lib/stagnation.py`（tolerance / min_consecutive），不要用离群检测替代。
````

- [ ] **Step 2: 提交**

```bash
cd /home/scada/powerelf-skills
git add _shared/algorithms/outlier-methods.md
git commit -m "docs(_shared): 新增 outlier-methods.md(IQR/百分位/MAD 三法对比与选择指南)" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: 新建 `_shared/references/statistical-caution.md`

**Files:**
- Create: `_shared/references/statistical-caution.md`

- [ ] **Step 1: 写文档**

创建 `_shared/references/statistical-caution.md`，完整内容：

````markdown
# 统计结论措辞护栏

> 跨 skill 共享。生成任何统计结论文案前（日报、异常报告、预警 `statement`、
> `powerelf-early-warning` 通知模板）先过一遍本文档。
> 来源：复用 `knowledge-work-plugins/data` 的 statistical-analysis skill 方法论，适配水利场景。

## 一、相关 ≠ 因果

发现相关性时，显式考虑三种替代解释：
- **反向因果**：可能 B 导致 A，而非 A 导致 B。
- **混杂变量**：可能 C 同时导致 A 和 B。
- **巧合**：变量够多时，伪相关不可避免。

水利例：
- ✅ 可说："渗压上升与水位上升同步出现（r=0.82）"
- ❌ 不可说："水位上升导致渗压上升"（也可能是降雨这一混杂因素同时推高二者，需结合工况）

## 二、多重比较问题

同时检验多个假设时，仅凭概率就会有"显著"结果：
- 20 个指标各在 α=0.05 检验 → 约有 1 个假阳性。
- 若遍历多个测站/时段才找到"异常"，必须注明总共跑了多少次检验。

**Bonferroni 校正**：α / 测试数。例：10 个渗压计同检，单检验 α 应取 0.05/10 = 0.005。
报告里注明"共检验 N 个测站/指标"。

## 三、Simpson 悖论

聚合数据的趋势在分群后可能**反转**：
- 例：全库异常率下降，但每个分区异常率都上升——因为测站结构偏向了低异常率的分区。
- **自检**：关键结论在按站类型 / 流域 / 时段分群后是否仍然成立？

## 四、幸存者偏差

只能分析"留存"在数据集里的实体：
- 只分析在线设备，忽略了已报废/离线设备 → 设备质量评估偏乐观。
- 只分析有数据的时段，忽略了通信中断期 → 缺失模式本身可能携带信号。
- **自问**：谁不在这个数据集里？加进来会改变结论吗？

## 五、生态谬误

群体层面的结论不能套到个体：
- "该流域平均异常率 3%" ≠ "任一测站异常概率 3%"。
- "某厂商设备整体评分高" ≠ "该厂商任一型号都可靠"（型号间差异可能很大）。

## 六、假精度

避免过度精确：
- ❌ "下月渗压异常率将为 4.73%"
- ✅ "下月渗压异常率预计 4–6%（基于近 3 月趋势）"
- 给区间而非点估计；适当取整（"约 5%" 常比 "4.73%" 更诚实）。
- 水利监测数据本身有采集误差，保留过多小数无意义。

## 七、结论措辞自检清单

发布任何统计结论文案前，逐条核对：

- [ ] **相关 vs 因果**：是否把"相关"表述成了"导致"？是否排查了反向因果/混杂/巧合？
- [ ] **多重比较**：若做了多次检验，是否注明总数？是否需要 Bonferroni 校正？
- [ ] **分群一致性**：结论在关键分群（站类型/流域/时段）下是否仍然成立（Simpson）？
- [ ] **幸存者偏差**：数据集排除了谁？排除是否影响结论？
- [ ] **个体适用性**：群体结论是否被不当外推到个体（生态谬误）？
- [ ] **精度合理性**：是否给了区间而非过度精确的点值？小数位是否匹配数据采集精度？
- [ ] **样本量**：样本是否足够支撑该结论？小样本是否已声明"功效有限"？
- [ ] **业务显著性**：统计显著 ≠ 业务显著；是否说明了效应大小与业务影响？

> 护栏为被动文档 + Agent 自判，不做代码级强制（对自由文本结论脆弱）。
> 与 `_shared/algorithms/outlier-methods.md`、`_shared/algorithms/mad.md` 配合使用。
````

- [ ] **Step 2: 提交**

```bash
cd /home/scada/powerelf-skills
git add _shared/references/statistical-caution.md
git commit -m "docs(_shared): 新增 statistical-caution.md 统计结论措辞护栏与自检清单" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: 交叉链接（mad.md + notification-strategy.md）

**Files:**
- Modify: `_shared/algorithms/mad.md`（末尾加姊妹方法链接）
- Modify: `powerelf-early-warning/strategies/notification-strategy.md`（加护栏指针）

- [ ] **Step 1: `mad.md` 末尾加姊妹方法段**

在 `_shared/algorithms/mad.md` 的最后一行（第 118 行 `（雨量站建议 tolerance=0.5 或 min_consecutive=24）` 之后）追加：

```markdown

## 八、姊妹方法

MAD 适合正态/缓变指标。对偏态分布（雨量、流量）改用 IQR 或百分位法，三者对比与选择指南见
[`outlier-methods.md`](outlier-methods.md)。CLI 调用：`anomaly_detector.py --method iqr|percentile`。
生成统计结论文案时另见 [`../references/statistical-caution.md`](../references/statistical-caution.md)。
```

- [ ] **Step 2: `notification-strategy.md` 加护栏指针**

在 `powerelf-early-warning/strategies/notification-strategy.md` 的"## 概述"段（第 3-5 行）之后插入一节。old：

```markdown
## 概述

预警触发后的多通道通知分发机制。

## 通知流程
```

new：

```markdown
## 概述

预警触发后的多通道通知分发机制。

> **生成结论文案前**：`statement` / `alarmInfo` 等面向人的措辞涉及统计结论时，
> 先查 [`../../_shared/references/statistical-caution.md`](../../_shared/references/statistical-caution.md)
> 过一遍措辞自检清单（相关≠因果、假精度、幸存者偏差等）。

## 通知流程
```

- [ ] **Step 3: 验证相对链接可达**

Run:
```bash
cd /home/scada/powerelf-skills
test -f _shared/algorithms/outlier-methods.md && echo "mad.md -> outlier-methods.md OK"
test -f _shared/references/statistical-caution.md && echo "mad.md -> statistical-caution.md OK"
test -f _shared/references/statistical-caution.md && echo "notification -> statistical-caution.md OK"
```
Expected: 三行 OK。

- [ ] **Step 4: 提交**

```bash
cd /home/scada/powerelf-skills
git add _shared/algorithms/mad.md powerelf-early-warning/strategies/notification-strategy.md
git commit -m "docs: mad.md 加姊妹方法链接，notification-strategy 加统计护栏指针" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: 更新 `powerelf-data-governance/SKILL.md`

**Files:**
- Modify: `powerelf-data-governance/SKILL.md`（工具命令段、模块架构 lib/ 列表、按需加载指令、报告段护栏指针）

- [ ] **Step 1: 工具命令段补 `--method`**

old（第 100-108 行）：
```markdown
### MAD 异常检测
```bash
python3 impl/anomaly_detector.py \
  --db "$DB_URL" \
  --table st_pressure_r --field water_pressure --threshold 4.0

# 指定测站和时间
python3 impl/anomaly_detector.py --db "..." --table st_rsvr_r --field rz --threshold 3.0 --st-id 128 --days 7
```
```

new：
```markdown
### 异常检测（MAD / IQR / 百分位）
```bash
# MAD（默认；正态/缓变指标：水位/GNSS/渗压）。--threshold=修正Z阈值
python3 impl/anomaly_detector.py \
  --db "$DB_URL" \
  --table st_pressure_r --field water_pressure --threshold 4.0

# IQR（偏态指标：雨量/流量）。--threshold=IQR倍数k（默认1.5，3.0激进）
python3 impl/anomaly_detector.py --db "$DB_URL" --table st_pptn_r --field p --method iqr

# 百分位（海量快速筛查）。--threshold=尾部百分位p（默认1→p1/p99）
python3 impl/anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --method percentile

# 指定测站和时间
python3 impl/anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --threshold 3.0 --st-id 128 --days 7
```

`--method` 取 `mad`(默认) / `iqr` / `percentile`，`--threshold` 语义随方法（详见 `../_shared/algorithms/outlier-methods.md`）。
不带 `--method` 时与历史版本完全兼容。
```

- [ ] **Step 2: 模块架构 lib/ 列表加 `outliers.py`**

old（第 147-148 行）：
```markdown
├── mad.py                # MAD异常检测 + 变化率 + 综合判定
├── missing.py            # 缺失检测 + 模式识别
```

new：
```markdown
├── mad.py                # MAD异常检测 + 变化率 + 综合判定
├── outliers.py           # IQR/百分位离群检测（MAD 互补，偏态分布）
├── missing.py            # 缺失检测 + 模式识别
```

- [ ] **Step 3: 按需加载指令加 IQR/百分位**

old（第 270 行附近）：
```markdown
"异常"/"异常检测"/"MAD"   → rules/anomaly-detection.md + algorithms/mad-algorithm.md
```

new：
```markdown
"异常"/"异常检测"/"MAD"   → rules/anomaly-detection.md + algorithms/mad-algorithm.md
"IQR"/"百分位"/"离群"     → ../_shared/algorithms/outlier-methods.md + lib/outliers.py
```

- [ ] **Step 4: 报告段加护栏指针**

在"### 11. 报告生成"小节末尾（第 263 行 `python3 impl/generate_report.py --date 2026-05-15` 代码块之后、"## 按需加载指令"之前）插入：

```markdown

> **报告结论文案**：生成数据质量/异常报告中的统计结论时，先过一遍
> [`../_shared/references/statistical-caution.md`](../_shared/references/statistical-caution.md)
> 的措辞自检清单（相关≠因果、假精度、幸存者偏差等）。
```

- [ ] **Step 5: 验证 SKILL.md 引用的相对链接可达**

Run:
```bash
cd /home/scada/powerelf-skills/powerelf-data-governance
test -f ../_shared/algorithms/outlier-methods.md && echo "outlier-methods.md OK"
test -f ../_shared/references/statistical-caution.md && echo "statistical-caution.md OK"
```
Expected: 两行 OK。

- [ ] **Step 6: 提交**

```bash
cd /home/scada/powerelf-skills
git add powerelf-data-governance/SKILL.md
git commit -m "docs(data-governance): SKILL.md 补 --method 用法、outliers.py 架构、护栏指针" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: 最终验证

**Files:** 无新建/修改（仅运行校验；若发现缺陷则补提交）。

- [ ] **Step 1: 全量单元测试**

Run:
```bash
cd /home/scada/powerelf-skills && python3 powerelf-data-governance/lib/test_outliers.py
```
Expected: `总计 15 项: 通过 15, 失败 0`。

- [ ] **Step 2: anomaly_detector 语法/导入自检**

Run:
```bash
cd /home/scada/powerelf-skills && python3 -c "import sys; sys.path.insert(0,'powerelf-data-governance'); from impl.anomaly_detector import run_detection, detect_by_method, comprehensive_judge; print('import OK')"
```
Expected: `import OK`。

- [ ] **Step 3: 向后兼容验证（合成数据，不连 DB）**

Run:
```bash
cd /home/scada/powerelf-skills && python3 -c "
import sys; sys.path.insert(0,'powerelf-data-governance')
from impl.anomaly_detector import detect_by_method
vals=[1,2,3,4,5,6,7,8,9,10,100]
# mad 路径
m=detect_by_method('mad',vals,None)
assert m['method']=='mad' and m['analysis_key']=='mad_analysis' and m['score_label']=='z_score'
assert 10 in m['result']['anomaly_indices']
# iqr 路径
i=detect_by_method('iqr',vals,None)
assert i['method']=='iqr' and i['threshold']==1.5 and i['analysis_key']=='iqr_analysis'
assert 10 in i['result']['anomaly_indices']
# percentile 路径
p=detect_by_method('percentile',[10.0]*50+[999.0],None)
assert p['method']=='percentile' and p['threshold']==1 and 50 in p['result']['anomaly_indices']
print('backward-compat + dispatch OK')
"
```
Expected: `backward-compat + dispatch OK`。

- [ ] **Step 4: 相对链接全量校验**

Run:
```bash
cd /home/scada/powerelf-skills && python3 -c "
import re, os
links=[]
for root,_,files in os.walk('.'):
    if '.git' in root: continue
    for f in files:
        if not f.endswith('.md'): continue
        p=os.path.join(root,f)
        for m in re.finditer(r'\]\(([^)]+\.md[^)]*)\)', open(p,encoding='utf-8').read()):
            tgt=m.group(1).split('#')[0]
            if tgt.startswith('http'): continue
            base=os.path.dirname(p)
            full=os.path.normpath(os.path.join(base,tgt))
            if not os.path.exists(full):
                links.append((p,tgt))
print('broken links:', links if links else 'none')
"
```
Expected: `broken links: none`。若有破损链接，修复后补提交。

- [ ] **Step 5: 可选 DB 冒烟测试（需要 DB 环境）**

> 仅当 `POWERELF_DB_*` 环境变量已配置且可连库时执行；否则跳过（标注"跳过：无 DB 环境"）。

Run:
```bash
cd /home/scada/powerelf-skills/powerelf-data-governance
source ../_shared/bootstrap.sh
echo "=== mad (默认，向后兼容) ==="
python3 impl/anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --days 30 | python3 -c "import sys,json; d=json.load(sys.stdin); print('method=',d.get('method'),'has mad_analysis=', 'mad_analysis' in d, 'count=', d.get('mad_analysis',{}).get('anomaly_count'))"
echo "=== iqr ==="
python3 impl/anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --method iqr --days 30 | python3 -c "import sys,json; d=json.load(sys.stdin); print('method=',d.get('method'),'has iqr_analysis=', 'iqr_analysis' in d, 'count=', d.get('iqr_analysis',{}).get('anomaly_count'))"
echo "=== percentile ==="
python3 impl/anomaly_detector.py --db "$DB_URL" --table st_rsvr_r --field rz --method percentile --days 30 | python3 -c "import sys,json; d=json.load(sys.stdin); print('method=',d.get('method'),'has percentile_analysis=', 'percentile_analysis' in d, 'count=', d.get('percentile_analysis',{}).get('anomaly_count'))"
```
Expected: 三段均打印 `method= mad/iqr/percentile`，对应 `has xxx_analysis= True`，`count=` 为整数。若 DB 无数据返回 `NO_DATA`，亦算通过（说明链路通）。

- [ ] **Step 6: 推送（连同未推送的 spec 提交一起）**

确认工作树干净且全部提交后：
```bash
cd /home/scada/powerelf-skills && git log --oneline -8
git status --short
git push origin main
```
Expected: push 成功，远程含 spec 提交 `cd1fa58` 与本次 6 个实施提交。

---

## Self-Review

**1. Spec 覆盖**（逐条核对 spec §3 文件变更清单）：
- ✅ 新建 `_shared/algorithms/outlier-methods.md` → Task 3
- ✅ 新建 `_shared/references/statistical-caution.md` → Task 4
- ✅ 新建 `powerelf-data-governance/lib/outliers.py`（`detect_iqr`/`detect_percentile`）→ Task 1
- ✅ 修改 `impl/anomaly_detector.py`（`--method`、分派、`method` 字段、`--threshold` 语义）→ Task 2
- ✅ 修改 `SKILL.md`（`--method` 用法 + 报告段护栏指针）→ Task 6
- ✅ 修改 `notification-strategy.md`（护栏指针）→ Task 5
- ✅ 修改 `_shared/algorithms/mad.md`（姊妹方法交叉链接）→ Task 5
- ✅ 测试 `lib/test_outliers.py`（合成数据 + 边界 + 烟雾）→ Task 1（outliers）+ Task 2（dispatch）+ Task 7 Step 5（DB 烟雾）
- ✅ 链路校验 → Task 7 Step 4

**2. 占位符扫描**：无 TBD/TODO/"添加适当错误处理"等；每个代码步骤含完整可执行代码。

**3. 类型/命名一致性**：
- `detect_by_method` 返回键 `score_label`/`score_source`/`analysis_key`/`method_label` 在 Task 2 实现、Task 1 测试断言、Task 7 Step 3 验证脚本中一致使用。
- `detect_iqr`/`detect_percentile` 返回 `anomaly_count`/`anomaly_indices`/`total_points` 在 Task 1 实现、测试、Task 2 `detect_by_method` 消费处一致。
- `run_detection(..., method="mad")` 签名在 Task 2 定义、Task 7 Step 2 导入校验一致。
- `comprehensive_judge(..., method_label="MAD")` 默认值保证 mad 路径与历史逐字一致。

**4. 向后兼容关键点**：
- mad 路径继续用内联 `detect_anomalies`（不切换 `lib/mad.py`）。
- `comprehensive_judge` 默认 `method_label="MAD"` → 文案逐字不变。
- 输出仅新增顶层 `method` 字段；`mad_analysis` 键名/结构不变；`anomaly_details` 的 `z_score` 键不变。
- `--method` 默认 `mad`，不带该参数时 CLI 行为不变。
