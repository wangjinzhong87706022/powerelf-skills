# powerelf-inspection 重构为聚焦巡检 skill — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `powerelf-inspection` 重构为聚焦巡检 skill：去重对齐 `_shared`/`powerelf-monitor`、接入 `_shared/references/` QA 护栏套件、修复内核 Bug、瘦身 `lib/` 并接线给 `impl/`。

**Architecture:** 以 `impl/` 为运行真相；把重复的检测原语（MAD ×3、2-sigma ×2、连续趋势 ×5）抽进 `lib/` 纯函数内核并接线；删除与 monitor 逐字重复的实时监测模式（划线=时间模式：实时→monitor，离线回顾→inspection）；接入 `_shared` 成熟护栏（QA 闸/路由表/Pitfalls/few_shots）。两套质量评分（inspection 任务维度 / governance 数据维度）并存，接口处用 data-quality tier 连接。

**Tech Stack:** Python 3 + pandas/numpy/sqlalchemy/pymysql/scikit-learn；`_shared/lib/db.py` 单一 DB 源；pytest 纯函数单测；markdown 规则/参考文档。

## Global Constraints（每个任务隐含遵守）

- **只读**：本轮无任何 DB 写路径（不加 writeback）；所有 SQL 只读。
- **DB 单一源**：连接走 `_shared/lib/db.py`（各 skill 的 `lib/db.py` 是转发 shim）；CLI 统一 `source ../_shared/bootstrap.sh` 后用 `$DB_URL`。
- **SQL 铁律**：表名/列名/时间列必须**白名单校验**后拼接；值参数用占位符绑定；**禁止 `{占位符}`**（`WHERE st_id={st_id}` 这类一律改 JOIN-by-name 或参数化）；关联键 `eq_id`(bigint)/`stcd`(varchar)/`st_id` 易混，用前对照 `_shared/references/schema.md`。
- **schema 单一源**：所有 `st_*` 表结构引用 `_shared/references/schema.md`，不复制 DDL。
- **commit 粒度**：每个任务结束 commit 一次；commit message 末尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- **测试**：`lib/` 纯函数单测脱离 DB（CI 阻断）；`impl/` 集成测试带 skip-if-unavailable 守卫（联库才跑）。
- **POWERELF_SKILLS_ROOT**：shim 已支持；文档要给标准导入片段。

---

## File Structure

**新建：**
- `powerelf-inspection/lib/report.py` — 统一报告（MD/JSON/HTML + QA 闸 + confidence_tier + data-quality caveat），镜像 governance `lib/report.py` 模式。
- `powerelf-inspection/lib/test_anomaly.py` / `test_quality.py` / `test_defect_predict.py` / `test_route_opt.py` — 纯函数单测（含 Bug 回归）。
- `powerelf-inspection/impl/registry.py` — 从 `inspection_tool.py` 抽出的数据采集层（`sys_data_source_registry` 读取 + 数据源匹配 + 参数化采集）。
- `powerelf-inspection/references/few_shots.md` — JOIN-by-name 真 SQL。
- `powerelf-inspection/references/business_rules.md` — 带溯源领域字典。
- `powerelf-inspection/references/pitfalls.md` — inspection 专属 7 类陷阱。
- `_shared/rules/gate-pump-status.md` + `_shared/rules/gnss-deformation.md` — 从 monitor 提升。

**修改：** `SKILL.md`、`lib/{anomaly,quality,defect_predict,route_opt,db}.py`、`impl/{inspection_analyzer,inspection_tool,test_inspection}.py`、`references/{data-model,api-reference}.md`、`powerelf-monitor/SKILL.md`。

**删除：** 根目录 `inspection/`、`references/database-schema.md`、`SKILL.md` 实时监测模式段、`lib/` 内重复原语。

---

## Phase P0 — 清理（无逻辑改动，每期可独立合并）

### Task P0-T1: 删除 stale `inspection/` 目录

**Files:** Delete: `inspection/`（整个）

- [ ] **Step 1: 确认无引用**

Run: `grep -rn "inspection/SKILL\|inspection/lib\|powerelf/lib/db.py" --include="*.md" --include="*.py" . | grep -v "^./inspection/" | grep -v "^./powerelf-inspection/"`
Expected: 无输出（或仅历史 spec 引用，记录下来）。`powerelf/lib/db.py` 是该副本 SKILL.md 引用的不存在路径，确认仓库内无真实依赖。

- [ ] **Step 2: 删除**

Run: `git rm -r inspection/ 2>/dev/null || rm -rf inspection/`（该目录未跟踪，用 `rm -rf`）

- [ ] **Step 3: 校验 skill 仍可被发现**

Run: `ls powerelf-inspection/SKILL.md && head -3 powerelf-inspection/SKILL.md`
Expected: 规范 skill 入口存在，`name: powerelf-intelligent-inspection`。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore(inspection): 删除 stale inspection/ 副本

规范 skill 为 powerelf-inspection/；该副本 lib 代码重复、SKILL.md 指向不存在的 powerelf/lib/db.py。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P0-T2: 删除重复 schema 引用 → 指针

**Files:** Delete: `powerelf-inspection/references/database-schema.md`；Modify: `powerelf-inspection/references/data-model.md`、`SKILL.md`

- [ ] **Step 1: 找所有指向本地 database-schema.md 的引用**

Run: `grep -rn "database-schema" powerelf-inspection/`
Expected: 列出 SKILL.md 与 data-model.md 中的引用点。

- [ ] **Step 2: 删除本地副本**

Run: `rm powerelf-inspection/references/database-schema.md`

- [ ] **Step 3: 改引用为 `_shared` 指针**

在 `references/data-model.md` 顶部加：
```markdown
> 表结构（DDL/字段/关联键）单一事实源：[`../../_shared/references/schema.md`](../../_shared/references/schema.md)。本文件仅描述巡检业务实体关系，不复制 DDL。
```
在 `SKILL.md` 把指向 `references/database-schema.md` 的链接改为 `../_shared/references/schema.md`。

- [ ] **Step 4: 校验无悬空链接**

Run: `grep -rn "database-schema" powerelf-inspection/`
Expected: 无输出。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(inspection): schema 引用去重，指向 _shared 单一事实源

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P0-T3: 删除 SKILL.md 实时监测模式段 → 路由交接

**Files:** Modify: `powerelf-inspection/SKILL.md`

- [ ] **Step 1: 定位实时监测模式段**

Run: `grep -n "实时监测模式\|实时监测算法\|按需加载指令\|GET /monitor" powerelf-inspection/SKILL.md`
Expected: 定位 L221–320 区间（## 实时监测模式 … 到 ## 自演化机制 之前）。

- [ ] **Step 2: 删除整段，替换为交接块**

将该整段替换为：
```markdown
## 实时监测（→ powerelf-monitor）

实时/当前值、12 类监测趋势、REST 看盘、预警触发由 **`powerelf-monitor`** 负责（详见其 SKILL.md）。本 skill 仅做**离线巡检回顾分析**（定时批处理、DB 直连、昨日窗口、日报 + 复合工况 + 巡检考核）。两者经 `_shared/`（算法/规则/schema）共享基底、经路由表交互，无代码 import。

| 你想要的 | 用哪个 skill |
|---|---|
| 某站**当前**水位/最新值、实时趋势看盘、预警 | powerelf-monitor |
| **昨日/本周/本月**巡检回顾、日报、复合工况、巡检质量考核 | powerelf-inspection（本 skill） |

相关算法（MAD/水位变化率/位移速率/时序预测/趋势检测/水库·雨情分析）见 `../_shared/algorithms/` 与 `../_shared/rules/`，两 skill 同源引用。
```

- [ ] **Step 3: 校验残留**

Run: `grep -n "GET /monitor\|按需加载指令\|12 大监测类型\|12 类监测" powerelf-inspection/SKILL.md`
Expected: 无输出（监测表/端点/指令已交 monitor）。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor(inspection): 删除与 monitor 重复的实时监测模式段，改为路由交接

划线=时间模式：实时→monitor，离线回顾→inspection。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P0-T4: 提升 gate-pump-status.md + gnss-deformation.md 到 `_shared/rules/`

**Files:** Create: `_shared/rules/gate-pump-status.md`、`_shared/rules/gnss-deformation.md`（从 `powerelf-monitor/rules/` 复制）；Modify: `powerelf-monitor/rules/*.md`→指针、`powerelf-inspection/SKILL.md` 引用

- [ ] **Step 1: 复制到 _shared**

Run:
```bash
cp powerelf-monitor/rules/gate-pump-status.md _shared/rules/gate-pump-status.md
cp powerelf-monitor/rules/gnss-deformation.md _shared/rules/gnss-deformation.md
```

- [ ] **Step 2: monitor 原文件改为指针**

把 `powerelf-monitor/rules/gate-pump-status.md` 内容替换为：
```markdown
# 闸门/泵站工情状态规则（指针）

已提升至单一事实源 [`../../_shared/rules/gate-pump-status.md`](../../_shared/rules/gate-pump-status.md)（inspection 与 monitor 共享）。
```
对 `gnss-deformation.md` 同样处理。

- [ ] **Step 3: inspection SKILL 引用 _shared 版**

在 inspection SKILL.md 的闸门/泵站/GNSS 相关处，规则指向改为 `../_shared/rules/gate-pump-status.md` / `gnss-deformation.md`。

- [ ] **Step 4: 校验两 skill 同源**

Run: `ls _shared/rules/gate-pump-status.md _shared/rules/gnss-deformation.md && grep -L "指针" powerelf-monitor/rules/gate-pump-status.md`
Expected: _shared 下两文件存在；monitor 版已是指针。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(_shared): 提升 gate-pump/gnss-deformation rule 到 _shared，monitor+inspection 同源

第 2 个 skill (inspection) 需要，按升 _shared 规则处理（doc-only，低风险）。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P0-T5: monitor SKILL.md 对称编辑

**Files:** Modify: `powerelf-monitor/SKILL.md`

- [ ] **Step 1: related_skills 加 inspection**

把 `related_skills: [powerelf-data-governance, powerelf-early-warning]` 改为 `[powerelf-data-governance, powerelf-early-warning, powerelf-inspection]`。

- [ ] **Step 2: 加分工段 + 路由条目**

在 monitor SKILL.md 适当位置加：
```markdown
## 与 powerelf-inspection 的分工

monitor = **实时**（当前/在线、REST、看盘、预警触发）；inspection = **离线回顾**（昨日窗口批处理、DB 直连、日报 + 复合工况 + 巡检考核）。同读 st_* 表，时间模式/触发/产出/消费者不同。离线巡检回顾/日报/巡检质量考核 → 用 `powerelf-inspection`。
```

- [ ] **Step 3: 校验**

Run: `grep -n "powerelf-inspection" powerelf-monitor/SKILL.md`
Expected: related_skills + 分工段各出现。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "docs(monitor): related_skills 加 inspection + 对称分工段

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase P1 — 修真实 Bug（live impl，立即生效）

> P1 只修 `impl/` 中**独立于 lib 重构**的 live bug（C3/H2/H3/H4）。C1/C2/H1/DD1/DD2/M1-M4 在 P2 随 lib 瘦身+接线修（那时 lib 成为可测纯函数）。

### Task P1-T1: 修 C3 — 相关性 `all([])==True` 空真

**Files:** Modify: `powerelf-inspection/impl/inspection_analyzer.py:1038`；Test: `powerelf-inspection/impl/test_inspection.py`（加 skip 守卫见 P4，此处先加纯函数化的小测试或回归断言）

> 说明：C3 在 `analyze_correlation` 内联。P2 会把判定抽进 lib；P1 先就地修空真，保证 live 行为正确。

- [ ] **Step 1: 写失败测试（纯函数复刻该判定逻辑）**

创建 `powerelf-inspection/lib/test_anomaly.py`（P2 会扩充；此处先放 C3 回归）：
```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

def _inq_falling_buggy(inq_trend):
    # 复刻 inspection_analyzer.py:1038 的旧逻辑（含 bug）
    return all(inq_trend[i] < inq_trend[i-1] for i in range(1, len(inq_trend)) if inq_trend[i-1] > 0)

def test_c3_all_zero_flow_not_falling():
    # 夜间入库流量全 0 → 旧逻辑 all([])==True 误判下降
    assert _inq_falling_buggy([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]) is True  # 暴露 bug
```

- [ ] **Step 2: 运行确认 bug**

Run: `python3 -m pytest powerelf-inspection/lib/test_anomaly.py::test_c3_all_zero_flow_not_falling -v`
Expected: PASS（测试断言旧逻辑**确实**返回 True，即暴露了 bug；这是基线锚点）。

- [ ] **Step 3: 修 inspection_analyzer.py:1038**

把：
```python
        inq_falling = all(inq_trend[i] < inq_trend[i-1] for i in range(1, len(inq_trend)) if inq_trend[i-1] > 0)
```
改为：
```python
        # 仅在有非零流量可比时才判定下降；全零/无可比项不算下降（修 C3 空真）
        comparable = [i for i in range(1, len(inq_trend)) if inq_trend[i-1] > 0]
        inq_falling = bool(comparable) and all(
            inq_trend[i] < inq_trend[i-1] for i in comparable
        )
```

- [ ] **Step 4: 更新测试断言修复后行为**

把 test 改为验证修复语义（新逻辑：全零→False）：
```python
def _inq_falling_fixed(inq_trend):
    comparable = [i for i in range(1, len(inq_trend)) if inq_trend[i-1] > 0]
    return bool(comparable) and all(inq_trend[i] < inq_trend[i-1] for i in comparable)

def test_c3_all_zero_flow_not_falling():
    assert _inq_falling_fixed([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]) is False  # 修复后不再误判
    assert _inq_falling_fixed([5.0, 4.0, 3.0, 2.0, 1.0, 0.5]) is True   # 真下降仍检出
```

- [ ] **Step 5: 运行通过**

Run: `python3 -m pytest powerelf-inspection/lib/test_anomaly.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(inspection): C3 相关性 all([])==True 空真，全零流量不再误判水位↑入库↓

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P1-T2: 修 H3 — 裸 except:pass → 记日志

**Files:** Modify: `powerelf-inspection/impl/inspection_analyzer.py`（read_sensor_data:120-123, load_thresholds:61-64/77-80/63-64, read_* helpers:133/159/172/183/196）

- [ ] **Step 1: 加 logging 模块**

在 `inspection_analyzer.py` 顶部 import 区加：
```python
import logging
logger = logging.getLogger("inspection_analyzer")
```

- [ ] **Step 2: read_sensor_data 失败记日志（原 line 122-123）**

把：
```python
    except Exception as e:
        return pd.DataFrame()
```
改为：
```python
    except Exception as e:
        logger.warning("read_sensor_data 失败 table=%s fields=%s: %s", table, fields, e)
        return pd.DataFrame()
```

- [ ] **Step 3: read_* helpers 逐个改**

对 `read_warning_rules`(133)、`read_inspections`(159)、`read_defects`(172)、`read_equipment`(183)、`read_alerts`(196) 的 `except:` 改为 `except Exception as e:` + `logger.warning("<func> 失败: %s", e)` + 保留 `return pd.DataFrame()`。

- [ ] **Step 4: load_thresholds 两处 except:pass 改记日志**

`load_thresholds` 内 `except: pass`（解析 ew_info_rules extend 的 61-62、解析 registry 的 77-78、外层 63-64/79-80）改为：
```python
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                logger.warning("解析 ew_info_rules 失败 rule=%s: %s", rule.get('id'), e)
```
（外层 DB 异常同理记 warning 并继续。）

- [ ] **Step 5: 联库冒烟验证不再静默**

Run: `source ../_shared/bootstrap.sh && python3 -c "import logging; logging.basicConfig(level=logging.WARNING); import sys; sys.path.insert(0,'impl'); import inspection_analyzer as ia; from sqlalchemy import create_engine; e=create_engine('$DB_URL'); print(ia.read_sensor_data(e,'__not_a_table__','id',days=1).shape)"`
Expected: 打印 `(0, 0)` 且日志输出 `read_sensor_data 失败 table=__not_a_table__ ...`（不再静默）。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(inspection): H3 裸 except:pass 改记日志，DB/解析异常不再静默吞

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P1-T3: 修 H4 — 2-sigma 参数法 → 稳健 MAD

**Files:** Modify: `powerelf-inspection/impl/inspection_analyzer.py:250`（water）、`443`（percolation）

> P2 会把这些 MAD 调用统一到 lib；P1 先就地换成稳健 MAD（与同文件 pressure/mad_anomaly 的 MAD 口径一致），消除偏态误报。

- [ ] **Step 1: 写偏态回归测试**

追加到 `lib/test_anomaly.py`：
```python
def test_h4_mad_vs_2sigma_on_skewed():
    # 右偏序列：一个远离的极端值。2-sigma 受均值拉动可能漏检；MAD 稳健。
    vals = [1.0]*20 + [9.0]   # 21 个，最后一个为离群
    import numpy as np
    median = float(np.median(vals[:-1])); mad = float(np.median(np.abs(np.array(vals[:-1])-median)))*1.4826
    z = abs(vals[-1]-median)/mad if mad>0 else 0.0
    assert z > 4.0  # MAD 检出
```

- [ ] **Step 2: 运行确认 MAD 检出**

Run: `python3 -m pytest powerelf-inspection/lib/test_anomaly.py::test_h4_mad_vs_2sigma_on_skewed -v`
Expected: PASS。

- [ ] **Step 3: 替换 water 的 2-sigma（line 245-255）**

把：
```python
        if rz > rz_mean + 2 * rz_values.std():
            findings.append({... "统计异常，需确认" ...})
```
改为：
```python
        # 稳健 MAD（替换 2-sigma：水位偏态，参数法易误报/漏报；修 H4）
        if len(rz_values) >= 10:
            _rz = rz_values.values
            _median = float(np.median(_rz))
            _mad = float(np.median(np.abs(_rz - _median))) * 1.4826
            if _mad > 0:
                _z = abs(rz - _median) / _mad
                if _z > 3.0:
                    findings.append({
                        "level": "WARNING",
                        "message": f"测站{st_id}: 当前水位{rz:.2f}m MAD统计异常 z={_z:.1f} (中位数{_median:.2f}m)",
                        "detail": "偏离历史分布，需确认"
                    })
```
（删除不再用的 `rz_max = rz_values.max()` 若无其它引用；保留 `rz_min/rz_mean` 若后续无引用则一并清。）

- [ ] **Step 4: 替换 percolation 的 2-sigma（line 437-448）**

把 `mean/std/2*std` 块同样换成上述稳健 MAD（阈值 3.0，label 改"渗流量"）。

- [ ] **Step 5: 联库冒烟**

Run: `source ../_shared/bootstrap.sh && python3 impl/inspection_analyzer.py --db "$DB_URL" --days 30 --json | python3 -c "import sys,json; d=json.load(sys.stdin); print([a['category'] for a in d])"`
Expected: 15 维度正常运行，无报错。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(inspection): H4 水位/渗流 2-sigma 改稳健 MAD，消除偏态误报

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P1-T4: 修 H2 — collect_from_source SQL 参数化 + 标识符白名单

**Files:** Modify: `powerelf-inspection/impl/inspection_tool.py:149-185`（P2 抽到 registry.py；P1 先就地修注入面）

- [ ] **Step 1: 加白名单常量**

在 `inspection_tool.py` 顶部加：
```python
# 标识符白名单（防 SQL 注入：table/fields/time_field 来自 sys_data_source_registry，DB 可写）
_ALLOWED_TABLES = {
    "st_river_r","st_rsvr_r","st_pressure_r","st_percolation_r","st_pptn_r",
    "rei_gate_r","rei_pump_r","eq_equip_base","eq_equip_defect","ew_camera_info",
    "srm_gnss_data_day","srm_robot_data_day","srm_illegal_acts",
}
_ALLOWED_TIME_FIELDS = {"tm", "create_time", "discovery_time", None}

def _validate_identifiers(table, fields, time_field):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table}")
    if time_field is not None and time_field not in _ALLOWED_TIME_FIELDS:
        raise ValueError(f"非法时间列: {time_field}")
    # fields 仅允许 [A-Za-z0-9_,]
    import re
    if not re.fullmatch(r"[A-Za-z0-9_]+(,[A-Za-z0-9_]+)*", fields or ""):
        raise ValueError(f"非法字段列表: {fields}")
```

- [ ] **Step 2: 在 collect_from_source 开头校验**

`collect_from_source` 函数体首行加：
```python
    _validate_identifiers(table, fields, time_field)
```

- [ ] **Step 3: 运行已有 collect 冒烟（合法路径不破）**

Run: `source ../_shared/bootstrap.sh && python3 -c "import sys; sys.path.insert(0,'impl'); import inspection_tool as it; from sqlalchemy import create_engine; e=create_engine('$DB_URL'); reg=it.get_builtin_registry(); s=reg[reg.name=='水位监测'].iloc[0]; print(it.collect_from_source(e,s,st_id=1))"`
Expected: 正常返回（或 `error: 缺少.../无数据`，但不抛 `非法表名`）。

- [ ] **Step 4: 注入被拒测试**

Run: `python3 -c "import sys; sys.path.insert(0,'impl'); import inspection_tool as it;
s={'name':'x','source_table':'st_river_r; DROP--','query_fields':'z','time_field':'tm','default_hours':24}
from sqlalchemy import create_engine
try:
    it.collect_from_source(create_engine('sqlite://'),s,st_id=1); print('NOT BLOCKED')
except ValueError as e: print('BLOCKED', e)"`
Expected: `BLOCKED 非法表名...`。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "fix(inspection): H2 collect_from_source 标识符白名单校验，封 SQL 注入面

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase P2 — lib 瘦身 + 接线 impl（结构核心）

> 设计澄清：spec 说"L4 委托 governance MAD"。但跨 skill import governance/lib/mad.py 路径脆弱、耦合两个 skill；Option 2 不滑向全域整合。故本轮把 inspection 内的 3 份 MAD **合并为 1 份对齐 `_shared/algorithms/mad.md` 的本地纯函数**（去重 3→1、修正），跨 skill 升 `_shared/lib/` 推迟到 ROADMAP。correlation 同理。

### Task P2-T1: lib/anomaly.py — 抽 `mad_anomaly` + `consecutive_monotonic` 纯函数

**Files:** Modify: `powerelf-inspection/lib/anomaly.py`；Test: `powerelf-inspection/lib/test_anomaly.py`

- [ ] **Step 1: 写失败测试**

追加到 `test_anomaly.py`：
```python
import anomaly

def test_mad_anomaly_detects_outlier():
    assert anomaly.mad_anomaly([1.0]*19 + [9.0], threshold=4.0)["is_anomaly"] is True

def test_mad_anomaly_min_samples():
    assert anomaly.mad_anomaly([1.0, 2.0], threshold=4.0)["is_anomaly"] is False  # 样本不足

def test_mad_anomaly_zero_mad():
    assert anomaly.mad_anomaly([5.0]*20, threshold=4.0)["is_anomaly"] is False  # mad=0 不报

def test_consecutive_monotonic_rise():
    r = anomaly.consecutive_monotonic([1,2,3,4,5,6], "rise", 6)
    assert r["is_trend"] is True and r["count"] == 5

def test_consecutive_monotonic_break():
    assert anomaly.consecutive_monotonic([1,2,3,2,1,0], "rise", 3)["is_trend"] is False
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest powerelf-inspection/lib/test_anomaly.py -v`
Expected: 新测试 FAIL（`module 'anomaly' has no attribute 'mad_anomaly'`）。

- [ ] **Step 3: 实现**

在 `anomaly.py` 加（用 numpy；无 numpy 时回退 statistics，与现有一致）：
```python
def mad_anomaly(values: List[float], threshold: float = 4.0, min_samples: int = 4) -> Dict[str, Any]:
    """稳健 MAD 离群检测（对齐 _shared/algorithms/mad.md）。values 末位为当前值，其余为历史窗口。"""
    if len(values) < min_samples:
        return {"is_anomaly": False, "score": 0.0}
    try:
        import numpy as _np
        hist = _np.asarray(values[:-1], dtype=float)
        current = float(values[-1])
    except Exception:
        hist = values[:-1]; current = values[-1]
        median = statistics.median(hist)
        mad = statistics.median([abs(v - median) for v in hist]) * 1.4826
    else:
        median = float(_np.median(hist))
        mad = float(_np.median(_np.abs(hist - median))) * 1.4826
    if mad == 0:
        return {"is_anomaly": False, "score": 0.0}
    z = abs(current - median) / mad
    return {"is_anomaly": z > threshold, "score": round(z, 4),
            "median": round(median, 4), "mad": round(mad, 4)}

def consecutive_monotonic(values: List[float], direction: str, min_consecutive: int) -> Dict[str, Any]:
    """从末尾数连续单调（direction='rise'/'fall'）；返回 {is_trend, count}。"""
    if len(values) < 2:
        return {"is_trend": False, "count": 0}
    count = 0
    for i in range(len(values) - 1, 0, -1):
        if direction == "rise" and values[i] > values[i - 1]:
            count += 1
        elif direction == "fall" and values[i] < values[i - 1]:
            count += 1
        else:
            break
    return {"is_trend": count >= min_consecutive, "count": count}
```

- [ ] **Step 4: 运行通过**

Run: `python3 -m pytest powerelf-inspection/lib/test_anomaly.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(inspection): lib/anomaly 抽 mad_anomaly + consecutive_monotonic 纯函数

对齐 _shared/algorithms/mad.md；为去重 impl 内 3×MAD/2-sigma/连续趋势 做准备。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P2-T2: lib/anomaly.py — 修 M2/M1/layer1 校验，委托新原语

**Files:** Modify: `powerelf-inspection/lib/anomaly.py`

- [ ] **Step 1: 写回归测试**

追加：
```python
def test_layer4_delegates_to_mad():
    # layer4 现委托 mad_anomaly，等价行为
    assert anomaly.layer4_mad_statistical([1.0]*19+[9.0], threshold=4.0)["is_anomaly"] is True

def test_layer2_reports_breaching_threshold_m1():
    # abs 触发但 rel 未触发时，应报 abs（修 M1：不再无条件报 rel）
    r = anomaly.layer2_change_rate(100.0, 99.0)  # abs=1, rel≈0.01
    wl = r["water_level"]  # abs=0.5, rel=0.05 → abs 触发(1>0.5), rel 不触发
    assert wl["is_anomaly"] is True

def test_layer1_rejects_malformed_extend():
    rules = [{"extend": "{\"content\":[null]}", "level_r": 3}]  # content[0]=null
    assert anomaly.layer1_threshold(100.0, rules) == []  # 不触发，不抛
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest powerelf-inspection/lib/test_anomaly.py -v`
Expected: M1/layer1 测试 FAIL。

- [ ] **Step 3: 改 layer4_mad_statistical 委托**

把 `layer4_mad_statistical` 体替换为：
```python
def layer4_mad_statistical(values, threshold=4.0):
    return mad_anomaly(values, threshold=threshold, min_samples=4)
```

- [ ] **Step 4: 改 layer2 修 M1（报实际触发的阈值）**

把 `layer2_change_rate` 内：
```python
        rate = rel_change if t.get("rel") else abs_change
        threshold = t.get("rel") if t.get("rel") else t.get("abs")
```
改为（报实际触发的那个；都触发则报更严的 rel）：
```python
        abs_t, rel_t = t.get("abs"), t.get("rel")
        abs_trig = abs_t is not None and abs_change > abs_t
        rel_trig = rel_t is not None and rel_change > rel_t
        if rel_trig:
            rate, threshold = rel_change, rel_t
        elif abs_trig:
            rate, threshold = abs_change, abs_t
        else:
            rate, threshold = (rel_change if rel_t else abs_change), (rel_t or abs_t)
```

- [ ] **Step 5: 改 layer1 加 extend 校验**

把 `layer1_threshold` 内：
```python
        extend = json.loads(rule["extend"])
        condition = extend["condition"]
        raw_threshold = extend["content"][0]
```
改为：
```python
        try:
            extend = json.loads(rule["extend"]) if isinstance(rule.get("extend"), str) else rule.get("extend")
            condition = extend.get("condition", ">")
            content = extend.get("content") or []
            raw_threshold = content[0] if len(content) > 0 else None
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue  # 跳过格式坏的规则（B5 阈值存在性/健壮性）
```

- [ ] **Step 6: 运行通过**

Run: `python3 -m pytest powerelf-inspection/lib/test_anomaly.py -v`
Expected: 全 PASS。

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "fix(inspection): lib layer4 委托 mad_anomaly(M2), layer2 报实际触发阈值(M1), layer1 extend 校验

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P2-T3: lib/anomaly.py — 修 C3(layer5 空守护) + DD1(置信度公式)

**Files:** Modify: `powerelf-inspection/lib/anomaly.py`

- [ ] **Step 1: 写测试**

追加：
```python
def test_layer5_empty_indicators_not_anomaly():
    assert anomaly.layer5_correlation([])["is_anomaly"] is False

def test_confidence_formula_dd1():
    # 文档公式：0.3×阈值 + 0.2×数据质量 + 0.2×趋势 + 0.2×历史 + 0.1×上下文
    layers = {
        1: {"is_anomaly": True, "confidence": 0.9},   # 阈值层触发
        3: {"is_anomaly": True, "confidence": 0.8},   # 趋势层触发
    }
    r = anomaly.composite_anomaly_judge(layers)
    assert 0.0 < r["confidence"] <= 1.0
    assert set(r["triggered_layers"]) <= {1,2,3,4,5}
```

- [ ] **Step 2: 运行确认**

Run: `python3 -m pytest powerelf-inspection/lib/test_anomaly.py -v`
Expected: layer5 空测试可能已 PASS；confidence 测试视现状。

- [ ] **Step 3: layer5 加空守护**

`layer5_correlation` 起始加：
```python
    if not indicator_pairs:
        return {"is_anomaly": False, "description": "no indicators"}
```

- [ ] **Step 4: composite_anomaly_judge 实现文档置信度公式（DD1）**

把函数体的置信度计算替换为文档公式。每个触发层贡献一个 0-1 子分，按文档权重汇总：
```python
def composite_anomaly_judge(layer_results):
    # 文档公式（DD1）：0.3×阈值 + 0.2×数据质量 + 0.2×趋势 + 0.2×历史 + 0.1×上下文
    # 层→因子映射：L1阈值 / L4数据质量(MAD) / L3趋势 / L2历史(变化率) / L5上下文(相关性)
    FACTOR_WEIGHT = {1: 0.30, 4: 0.20, 3: 0.20, 2: 0.20, 5: 0.10}
    triggered, factor_scores = [], {}
    for layer_num in range(1, 6):
        entry = layer_results.get(layer_num)
        if entry is None:
            continue
        entries = entry if isinstance(entry, list) else [entry]
        confs = [e.get("confidence", 0.5) for e in entries
                 if isinstance(e, dict) and (e.get("is_anomaly") or e.get("triggered"))]
        if confs:
            triggered.append(layer_num)
            factor_scores[layer_num] = max(confs)
    weight_present = sum(FACTOR_WEIGHT[l] for l in triggered)
    confidence = (sum(FACTOR_WEIGHT[l] * factor_scores[l] for l in triggered) / weight_present) if weight_present else 0.0
    names = {1:"threshold",2:"change_rate",3:"trend",4:"MAD",5:"correlation"}
    return {
        "is_anomaly": confidence > 0.5 or len(triggered) >= 2,
        "confidence": round(confidence, 4),
        "triggered_layers": triggered,
        "description": f"Anomaly via {', '.join(names[l] for l in triggered)}" if triggered else "No anomaly",
    }
```

- [ ] **Step 5: 运行通过**

Run: `python3 -m pytest powerelf-inspection/lib/test_anomaly.py -v`
Expected: 全 PASS。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(inspection): DD1 composite 置信度按文档公式实现 + layer5 空守护(C3)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P2-T4: lib/quality.py — 修 C1(自定义权重) + C2(缺陷率分母) + H1(语义)

**Files:** Modify: `powerelf-inspection/lib/quality.py`；Test: `powerelf-inspection/lib/test_quality.py`

- [ ] **Step 1: 写失败测试**

创建 `test_quality.py`：
```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import quality

def test_c1_custom_weights_coherent():
    # 自定义权重下 total 仍落在 0-100 且与权重一致
    r = quality.compute_quality_score(0.97, 0.97, 0.03, 0.97,
            weights={"completion":0.4,"timeliness":0.2,"defect_rate":0.2,"coverage":0.2})
    assert 0 <= r["total_score"] <= 100
    # 默认权重满分场景
    r2 = quality.compute_quality_score(0.97, 0.97, 0.03, 0.97)
    assert r2["total_score"] >= 90 and r2["grade"] == "A"

def test_c2_defect_rate_denominator():
    # 缺陷发现率 = bad_num / real_objitem（非 plan_checkobj）
    rate = quality.compute_defect_discovery_rate(defects_found=5, real_checkitems=500)
    assert abs(rate - 0.01) < 1e-9

def test_h1_check_percent_documented():
    # 敲定：check_percent 语义=完成率（默认处置），文档/代码/schema 对齐
    assert quality.CHECK_PERCENT_SEMANTICS == "completion"
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest powerelf-inspection/lib/test_quality.py -v`
Expected: C1（自定义权重 total 可能超 100 或无意义）、C2（签名不符）、H1（常量不存在）FAIL。

- [ ] **Step 3: 修 compute_quality_score 自定义权重分支（C1）**

把 `if weights:` 分支替换为（按各自满分归一再加权 ×100）：
```python
    _MAX = {"completion":30.0,"timeliness":25.0,"defect_rate":25.0,"coverage":20.0}
    if weights:
        total_score = sum(
            (raw_scores[dim] / _MAX[dim]) * w.get(dim, 0) * 100.0 for dim in raw_scores
        )
    else:
        total_score = sum(raw_scores.values())
```

- [ ] **Step 4: 修缺陷率签名（C2）**

把：
```python
def compute_defect_discovery_rate(defects_found: int, total_checks: int) -> float:
```
改为：
```python
def compute_defect_discovery_rate(defects_found: int, real_checkitems: int) -> float:
    """缺陷发现率 = 缺陷数 / 实际巡检项数（real_objitem）。详见 quality-assessment.md。"""
    if real_checkitems <= 0:
        return 0.0
    return defects_found / real_checkitems
```

- [ ] **Step 5: 加 H1 语义常量**

模块顶部加：
```python
# check_percent 字段语义（H1 默认处置：完成率；详见 references/business_rules.md）
CHECK_PERCENT_SEMANTICS = "completion"
```

- [ ] **Step 6: 运行通过**

Run: `python3 -m pytest powerelf-inspection/lib/test_quality.py -v`
Expected: 全 PASS。

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "fix(inspection): lib/quality C1 自定义权重归一 + C2 缺陷率分母 real_objitem + H1 语义常量

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P2-T5: impl/inspection_tool.py 接线 lib/quality（删内联评分 D4 + 落实 C2/H1）

**Files:** Modify: `powerelf-inspection/impl/inspection_tool.py:192-287`

- [ ] **Step 1: 加 lib 导入**

`inspection_tool.py` 顶部加：
```python
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib"))
import quality as _quality
```

- [ ] **Step 2: SELECT 加 real_objitem 列**

> 先在 `_shared/references/schema.md` 核对 `business_check_task` 实际巡检项列名（预期 `real_checkobj`；若不同用 schema 名）。Run: `grep -n -A40 "business_check_task" _shared/references/schema.md | grep -i "checkobj\|objitem"`

把 `calc_inspection_quality` 的 SELECT 列表加上实际巡检项列（以下用 `real_checkobj`，按 schema 校正）：
```sql
        SELECT id, name, status, plan_checknum, real_checknum,
               plan_checkobj, real_checkobj, bad_num, check_percent,
               plan_time, begin_time, end_time, exceed_time
```

- [ ] **Step 3: 缺陷率分母改 real_checkobj（C2）**

把：
```python
    total_items = tasks['plan_checkobj'].sum() if 'plan_checkobj' in tasks.columns else tasks['real_checknum'].sum()
    total_defects = tasks['bad_num'].sum()
    defect_rate = total_defects / total_items if total_items > 0 else 0
```
改为：
```python
    total_defects = tasks['bad_num'].sum()
    real_items = tasks['real_checkobj'].sum() if 'real_checkobj' in tasks.columns else 0
    defect_rate = _quality.compute_defect_discovery_rate(int(total_defects), int(real_items))
```

- [ ] **Step 4: 分段评分改调 lib（删 D4 内联副本）**

把内联 `score_completion/score_timeliness/score_defect/score_coverage` 大段（line 228-268）替换为：
```python
    qs = _quality.compute_quality_score(completion_rate, timeliness_rate, defect_rate, coverage_rate)
    score_completion = qs["dimension_scores"]["completion"]["score"]
    score_timeliness = qs["dimension_scores"]["timeliness"]["score"]
    score_defect = qs["dimension_scores"]["defect_rate"]["score"]
    score_coverage = qs["dimension_scores"]["coverage"]["score"]
    score = qs["total_score"]
```
（保留返回 dict 结构不变，仅改计算来源。）

- [ ] **Step 5: 联库冒烟**

Run: `source ../_shared/bootstrap.sh && python3 impl/inspection_tool.py --mode quality --db "$DB_URL" --start 2026-01-01 --end 2026-12-31`
Expected: 正常输出 JSON，含 score/grade/score_breakdown。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(inspection): inspection_tool 评分接线 lib/quality，删内联副本(D4)，落实 C2 分母

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P2-T6: impl/inspection_analyzer.py 接线 lib 原语（去重 3×MAD/连续趋势）

**Files:** Modify: `powerelf-inspection/impl/inspection_analyzer.py`

- [ ] **Step 1: 加 lib 导入**

顶部加：
```python
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lib"))
import anomaly as _anomaly
```

- [ ] **Step 2: 替换 pressure 的内联 MAD（line 388-399）**

把：
```python
        if len(wp_values) >= 10:
            median = np.median(wp_values)
            mad = np.median(np.abs(wp_values - median)) * 1.4826
            if mad > 0:
                z_score = abs(wp - median) / mad
                if z_score > 4:
                    findings.append({...})
```
改为：
```python
        _r = _anomaly.mad_anomaly(wp_values.tolist(), threshold=4.0, min_samples=10)
        if _r["is_anomaly"]:
            findings.append({
                "level": "WARNING",
                "message": f"渗压计{st_id}: 统计异常 z_score={_r['score']:.1f} (当前{wp:.2f}kPa, 中位数{_r['median']:.2f}kPa)",
                "detail": "偏离历史分布，需人工确认"
            })
```

- [ ] **Step 3: 替换 analyze_mad_anomaly 的内联 MAD（line 985-1004）**

把 `median/mad/z_score` 内联块改为：
```python
            _r = _anomaly.mad_anomaly(values.tolist(), threshold=mad_threshold, min_samples=20)
            if _r["is_anomaly"]:
                findings.append({
                    "level": "WARNING",
                    "message": f"{label}测站{st_id}: MAD统计异常 z={_r['score']:.1f} (阈值{mad_threshold}, 当前{float(values[-1]):.2f}, 中位数{_r['median']:.2f})",
                    "detail": f"偏离历史分布，基于{len(values)}个数据点的MAD检测"
                })
```

- [ ] **Step 4: 连续趋势判定统一用 consecutive_monotonic**

把 water(232/238)、pressure(370)、displacement(507) 的 `all(recent[i] > recent[i-1] ...)` 模式替换。例（pressure line 368-375）：
```python
        if len(wp_values) >= 7:
            if _anomaly.consecutive_monotonic(wp_values[-7:].tolist(), "rise", 6)["is_trend"]:
                findings.append({
                    "level": "WARNING",
                    "message": f"渗压计{st_id}: 渗压连续上升 ({wp_values[-7]:.2f}kPa → {wp:.2f}kPa)",
                    "detail": "持续上升趋势，可能存在渗漏，需现场检查"
                })
```
（water 用 rise/fall 各一次；displacement 用 rise。逐个替换，保留各自文案。）

- [ ] **Step 5: 联库冒烟全维度**

Run: `source ../_shared/bootstrap.sh && python3 impl/inspection_analyzer.py --db "$DB_URL" --days 30 --json | python3 -c "import sys,json;d=json.load(sys.stdin);print(len(d),'维度')"`
Expected: 15 维度，无异常退出。

- [ ] **Step 6: 校验仅 1 份 MAD 实现**

Run: `grep -n "np.median(np.abs" powerelf-inspection/impl/inspection_analyzer.py powerelf-inspection/lib/anomaly.py`
Expected: 仅 `lib/anomaly.py` 出现（impl 内联已删）。

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(inspection): analyzer 接线 lib mad_anomaly/consecutive_monotonic，去重 3×MAD/连续趋势(D3)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P2-T7: 抽采集层到 impl/registry.py（最小分离 S4）

**Files:** Create: `powerelf-inspection/impl/registry.py`；Modify: `powerelf-inspection/impl/inspection_tool.py`

- [ ] **Step 1: 创建 registry.py，迁移采集相关函数**

把 `inspection_tool.py` 的 `load_registry`、`get_builtin_registry`、`match_data_sources`、`collect_from_source`、`_ALLOWED_TABLES`、`_ALLOWED_TIME_FIELDS`、`_validate_identifiers` 整体移到 `impl/registry.py`。

- [ ] **Step 2: inspection_tool.py 改 import**

```python
from registry import load_registry, get_builtin_registry, match_data_sources, collect_from_source, show_registry, demo_collect
```
（`show_registry`/`demo_collect` 若也迁移则一并 import；保留 CLI 调用不变。）

- [ ] **Step 3: 冒烟 registry/collect 模式**

Run: `source ../_shared/bootstrap.sh && python3 impl/inspection_tool.py --mode registry --db "$DB_URL"`
Expected: 正常打印注册表（或回退内置默认）。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor(inspection): 抽采集层到 impl/registry.py（最小分离 S4），隔离 H2 注入面

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P2-T8: 自建 lib/report.py（镜像 governance 模式）

**Files:** Create: `powerelf-inspection/lib/report.py`；Modify: `impl/inspection_analyzer.py:generate_report`、`impl/inspection_tool.py:generate_report`

- [ ] **Step 1: 创建 lib/report.py 骨架**

```python
"""统一巡检报告组装：分节 → MD/JSON/HTML + 嵌 QA 闸 + 挂 confidence_tier + 附 data-quality caveat。
镜像 governance lib/report.py 模式（本轮自建，不升 _shared，见 ROADMAP）。"""
from typing import Any, Dict, List

_QA_CHECKLIST = """## 交付前 QA 自检（见 ../_shared/references/analysis-qa-checklist.md）
- [ ] 关联键(eq_id/stcd/st_id)已核验
- [ ] ew_info_rules 阈值数据存在性已确认
- [ ] 传感器故障 vs 真异常已区分（消费 data-quality tier）
- [ ] business_check 状态码(1/2/3)正确
- [ ] 缺陷率已用 data-quality tier 校正
置信度评级: Ready / With caveats / Needs revision → {confidence_tier}
"""

def render_report(title: str, sections: List[Dict[str, Any]], *,
                  confidence_tier: str = "Needs revision",
                  data_quality_caveat: str = "") -> str:
    md = f"# {title}\n\n"
    for s in sections:
        md += f"## {s['category']}\n\n{s.get('body','')}\n\n"
    if data_quality_caveat:
        md += f"> ⚠️ 数据质量 caveat: {data_quality_caveat}\n\n"
    md += _QA_CHECKLIST.format(confidence_tier=confidence_tier)
    return md

def to_json(sections: List[Dict[str, Any]], confidence_tier: str) -> Dict[str, Any]:
    import json
    return {"sections": sections, "confidence_tier": confidence_tier}
```

- [ ] **Step 2: inspection_analyzer.generate_report 末尾接 QA 闸**

在 `generate_report` 返回前，用 `render_report` 包一层或在 report 末尾追加 `_QA_CHECKLIST`（最小改动：`report += _QA_CHECKLIST.format(confidence_tier="With caveats")`，import `from report import _QA_CHECKLIST` via sys.path）。

- [ ] **Step 3: 冒烟**

Run: `source ../_shared/bootstrap.sh && python3 impl/inspection_analyzer.py --db "$DB_URL" --days 7 | tail -20`
Expected: 报告末尾出现「交付前 QA 自检」节。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(inspection): 自建 lib/report.py（镜像 governance），报告嵌 QA 闸 + confidence_tier

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P2-T9: 修 M3(defect_predict 阈值) + M4(route_opt haversine) + lib/db.py 补导出

**Files:** Modify: `lib/defect_predict.py`、`lib/route_opt.py`、`lib/db.py`；Test: `lib/test_defect_predict.py`、`lib/test_route_opt.py`

- [ ] **Step 1: 写测试**

`test_defect_predict.py`：
```python
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
import defect_predict as dp
def test_m3_hotspot_thresholds_documented():
    # 阈值标注为启发式（非普适），且函数可跑
    assert hasattr(dp, "HOTSPOT_THRESHOLDS")  # 显式常量 + 注释说明启发式
```
`test_route_opt.py`：
```python
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
import route_opt as ro
def test_m4_haversine_used():
    pts = [{"lng":120.0,"lat":32.0},{"lng":120.01,"lat":32.01},{"lng":120.5,"lat":32.5}]
    clusters = ro.cluster_points(pts, k=2)  # 应使用 haversine 而非裸经纬度
    assert len(clusters) <= 2
```

- [ ] **Step 2: M3 — 把硬编码阈值提为带注释常量**

在 `defect_predict.py` 顶部加：
```python
# 启发式阈值（M3：未经标定，仅参考；建议按历史分布校准）
HOTSPOT_THRESHOLDS = {"high": 0.3, "medium": 0.1}
```
把 bayesian_hotspot 内 `>0.3`/`>0.1` 改为引用该常量。

- [ ] **Step 3: M4 — cluster_points 改用 haversine**

把 KMeans 的 `fit` 输入从裸 `[lon,lat]` 改为用文件内已有的 `_haversine` 距离做预计算的距离矩阵（`sklearn.cluster.AgglomerativeClustering(metric="precomputed")`），或对经纬度做投影。最小改动：用 `AgglomerativeClustering(n_clusters=k, metric="precomputed", linkage="average")` + `_haversine` 矩阵。

- [ ] **Step 4: lib/db.py 补导出 get_readonly_sqlalchemy_url**

把 shim 末尾加：
```python
get_readonly_sqlalchemy_url = getattr(_mod, "get_readonly_sqlalchemy_url", None)
```
并加入 `__all__`。

- [ ] **Step 5: 运行通过**

Run: `python3 -m pytest powerelf-inspection/lib/ -v`
Expected: 全 PASS。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(inspection): M3 hotspot 阈值显式化 + M4 route_opt 用 haversine + db shim 补只读 URL

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase P3 — SKILL 重结构 + _shared 护栏采用（docs）

### Task P3-T1: SKILL.md 加 When NOT to Use 路由表 + Related Skills

**Files:** Modify: `powerelf-inspection/SKILL.md`

- [ ] **Step 1: 在“When to Use”后插入**

```markdown
## When NOT to Use

| 你想要的 | 应使用 |
|---|---|
| 某站当前水位/流量实时值、趋势看盘 | `powerelf-chatbi` / `powerelf-monitor` |
| 数据质量（异常/缺失/离线/卡滞/插值） | `powerelf-data-governance` |
| 阈值/告警判定与分发 | `powerelf-early-warning` |
| 实时 12 类监测、REST、预警触发 | `powerelf-monitor` |
```
Related Skills 段补 `powerelf-monitor`。

- [ ] **Step 2: 校验**

Run: `grep -n "When NOT to Use\|powerelf-monitor" powerelf-inspection/SKILL.md`
Expected: 两处均出现。

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "docs(inspection): 加 When NOT to Use 路由表 + Related Skills 补 monitor

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P3-T2: references/pitfalls.md（7 类）

**Files:** Create: `powerelf-inspection/references/pitfalls.md`；Modify: `SKILL.md`（引用）

- [ ] **Step 1: 创建 pitfalls.md**（内容按 spec §5.4 七类：占位符污染 / 关联键 / GNSS 表名 / extend JSON / 泵站 varchar / 传感器故障 vs 真极端 / 双数据库；每类含❌/✅示例）

- [ ] **Step 2: SKILL.md 加 Pitfalls 段 + 指针**

加一节“## Pitfalls（高频错误）”列 7 类标题 + 指向 `references/pitfalls.md`。

- [ ] **Step 3: 校验**

Run: `grep -n "占位符\|关联键\|GNSS 表名" powerelf-inspection/references/pitfalls.md`
Expected: 7 类齐全。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "docs(inspection): 加 references/pitfalls.md（7 类 inspection 专属陷阱）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P3-T3: references/few_shots.md（JOIN-by-name，禁占位符）

**Files:** Create: `powerelf-inspection/references/few_shots.md`；Modify: `SKILL.md`

- [ ] **Step 1: 创建 few_shots.md**

至少 4 个真 SQL（按名 JOIN，无 `{}`）：① 某站水位历史；② 某设备缺陷清单；③ ew_info_rules 阈值存在性校验；④ business_check_task 完成率统计。每条标“来源: 实际 schema”。

- [ ] **Step 2: SKILL.md 引用 + POWERELF_SKILLS_ROOT 标准导入片段**

加：
```markdown
## 标准导入片段（POWERELF_SKILLS_ROOT）
\`\`\`python
import os, sys
sys.path.insert(0, os.path.join(os.environ['POWERELF_SKILLS_ROOT'], '_shared', 'lib'))
from db import get_connection, get_sqlalchemy_url
\`\`\`
```

- [ ] **Step 3: 校验无占位符**

Run: `grep -n "{" powerelf-inspection/references/few_shots.md | grep -v "json\|extend"`
Expected: 无 `{st_id}` 类占位符。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "docs(inspection): 加 few_shots.md（JOIN-by-name）+ POWERELF_SKILLS_ROOT 导入片段

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P3-T4: references/business_rules.md（带溯源字典）+ Validation Gate + depth-mode + _shared 引用 + 修漂移

**Files:** Create: `powerelf-inspection/references/business_rules.md`；Modify: `SKILL.md`

- [ ] **Step 1: business_rules.md**（任务状态 1/2/3、ew_type 0–4、type_flag、route.type 10/20/30/40、wptn 4/5/6、eq_equip_base.status 0/1/2、check_percent 语义=完成率[H1 默认]，每项标来源）

- [ ] **Step 2: SKILL.md 加 Validation Gate + depth-mode + _shared 引用 + 修漂移**

- Validation Gate：引用 `../_shared/references/analysis-qa-checklist.md` + inspection 专属 5 项（见 P2-T8）。
- depth-mode：精简（只返数值）/标准（+1-2 关联指标）/详细（多维度+图+异常检测）。
- 引用 `_shared/references/`：schema、sql-discipline、analysis-qa-checklist、statistical-caution、data-profiling。
- 修漂移：Holt-Winters/ARIMA/LSTM、Mann-Kendall、自演化 → 标“roadmap（见 ROADMAP）”；趋势阈值对齐 code（渗压≥7/GNSS≥5/水≥6，DD2）；更正“24 测试/92 题”为实际数。

- [ ] **Step 3: 校验 _shared 引用齐全**

Run: `grep -n "analysis-qa-checklist\|statistical-caution\|sql-discipline\|data-profiling" powerelf-inspection/SKILL.md`
Expected: 4 个均出现。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "docs(inspection): business_rules 字典 + Validation Gate + depth-mode + _shared 引用 + 修文档漂移

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P3-T5: 连接 data-quality tier → 缺陷率校正

**Files:** Modify: `lib/quality.py`、`references/business_rules.md`

- [ ] **Step 1: 在 lib/quality.py 加 tier 感知的缺陷率函数**

```python
def adjusted_defect_count(raw_defects: int, sensor_fault_flags: list) -> int:
    """剔除被判为传感器故障/卡滞/离线导致的假缺陷（消费 governance data-quality tier，read-only）。"""
    return max(0, raw_defects - sum(1 for f in sensor_fault_flags if f))
```
加测试（`test_quality.py`）：raw=10, flags=[True]*3 → 7。

- [ ] **Step 2: business_rules.md 记录该连接点**

- [ ] **Step 3: 运行 + Commit**

Run: `python3 -m pytest powerelf-inspection/lib/test_quality.py -v` → PASS。
```bash
git add -A && git commit -m "feat(inspection): 缺陷率消费 data-quality tier 剔除传感器故障假缺陷（连接点，read-only）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase P4 — 测试（真覆盖）

### Task P4-T1: lib 纯函数单测补齐（CI 阻断）

**Files:** `powerelf-inspection/lib/test_*.py`

- [ ] **Step 1: 补齐 edge cases** — 除零、空序列、全相同值、样本不足、类型异常。每个 `test_*.py` 至少覆盖公开函数。
- [ ] **Step 2: 全量跑**

Run: `python3 -m pytest powerelf-inspection/lib/ -v`
Expected: 全 PASS。

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "test(inspection): lib 纯函数单测补齐（CI 阻断，脱离 DB）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P4-T2: 重写 impl/test_inspection.py（skip 守卫 + 调 analyzer + 无数据不 pass）

**Files:** Modify: `powerelf-inspection/impl/test_inspection.py`

- [ ] **Step 1: 加 DB 可用性守卫**

文件顶部：
```python
import os
_DB = os.environ.get("DB_URL")
pytest = None
try:
    import pytest
except ImportError:
    pytest = None
_RUN = pytest is not None and _DB is not None
skip_no_db = pytest.mark.skipif(not _RUN, reason="无 DB_URL 或 pytest，跳过集成测试") if pytest else (lambda f: f)
```
每个 `_check_*`/test 加 `@skip_no_db`。

- [ ] **Step 2: "无数据" 改 skip/inconclusive**

把 `if df.empty: return {"pass": True}` 类改为 `pytest.skip("无数据")`。

- [ ] **Step 3: 测试改调 analyzer 函数（不重算逻辑）**

例：`_check_pressure_trend` 改为 `r = ia.analyze_pressure(engine, days); assert "findings" in r`，而非自己重算 7 点上升。

- [ ] **Step 4: 更正用例数**

把 header 的 "24"/"92" 改为实际 `len(cases)`。

- [ ] **Step 5: 运行**

Run: `python3 -m pytest powerelf-inspection/impl/test_inspection.py -v`（无 DB → 全 skip；有 DB → 跑集成）
Expected: 无 DB 时全 skip（非假通过）。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "test(inspection): 重写集成测试，加 skip 守卫 + 调 analyzer + 无数据不 pass + 更正用例数

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task P4-T3: 文档/链接 grep 校验脚本（CI）

**Files:** Create: `powerelf-inspection/scripts/check_docs.sh`

- [ ] **Step 1: 写脚本**

```bash
#!/usr/bin/env bash
# 校验：_shared 引用齐全、规则无占位符、schema 单一源、few_shots 无 {}
set -e
cd "$(dirname "$0")/.."
grep -rq "analysis-qa-checklist\|statistical-caution\|sql-discipline\|data-profiling\|_shared/references/schema" SKILL.md
! grep -rn "{st_id}\|{equipment_code}" rules/ references/ || { echo "ERR: 占位符"; exit 1; }
[ ! -f references/database-schema.md ] || { echo "ERR: 本地 schema 副本仍在"; exit 1; }
! grep -E "\{(st_id|dt|code)" references/few_shots.md || { echo "ERR: few_shots 含占位符"; exit 1; }
echo "doc check OK"
```

- [ ] **Step 2: 运行 + Commit**

Run: `bash powerelf-inspection/scripts/check_docs.sh` → `doc check OK`。
```bash
git add -A && git commit -m "test(inspection): 文档/链接 grep 校验脚本（CI）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review（写完后自查，已执行）

**1. Spec 覆盖：**
- 去重对齐 _shared/monitor → P0-T2/T3/T4/T5、P2-T6 ✓
- 接入 QA 护栏套件 → P3-T1/T2/T3/T4 ✓
- 修内核 Bug：C1→P2-T4、C2→P2-T4/T5、C3→P1-T1/P2-T3、H1→P2-T4、H2→P1-T4/P2-T7、H3→P1-T2、H4→P1-T3、DD1→P2-T3、DD2→P3-T4、M1→P2-T2、M2→P2-T1/T2、M3→P2-T9、M4→P2-T9 ✓
- lib 瘦身+接线 → P2 全 ✓
- 两评分并存+连接 → P3-T5 ✓
- 删 stale inspection/ → P0-T1 ✓
- report.py 自建 → P2-T8 ✓
- 测试四层 → P4 + P1/P2 内联测试 ✓
- 待确认项 H1/DD2 默认处置 → P2-T4/P3-T4 + ROADMAP §三 ✓

**2. 占位符扫描：** 已避免“TBD/TODO/类似上面”；代码步骤均含真实代码或精确行号替换。✓

**3. 类型/命名一致：** `mad_anomaly`/`consecutive_monotonic`/`composite_anomaly_judge`/`compute_quality_score`/`compute_defect_discovery_rate(defects_found, real_checkitems)`/`CHECK_PERCENT_SEMANTICS`/`HOTSPOT_THRESHOLDS`/`adjusted_defect_count`/`render_report` 在定义与引用处一致。✓

**一处需实现时确认：** P2-T5 Step 2 的 `real_checkobj` 列名须对照 `_shared/references/schema.md` 核对后使用（spec 标注待确认，默认 `real_checkobj`）。
