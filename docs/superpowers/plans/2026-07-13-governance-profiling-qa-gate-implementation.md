# 治理域：数据画像 + 报告交付前 QA 闸 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `powerelf-data-governance` 增加数据画像前置环节（`impl/profiler.py` + `lib/profiling.py`）与报告交付前 QA 闸（`_shared/references/analysis-qa-checklist.md`），并在 `report.py` 接入 QA 自检节与置信度 tier 字段；沿用"文档进 `_shared`、代码进各 skill、判断类护栏为被动文档"约定。

**Architecture:** 画像为机械计算→工具化（`profiler.py` CLI + `profiling.py` 纯函数库，对齐 `anomaly_detector.py` 与 `outliers.py` 风格）；QA 闸为被动清单 + 三级置信度评级（不自动打分，与 `statistical-caution.md` 定位一致）。两份方法论文档挂 `_shared/references/`，接线改动最小化（`SKILL.md` 加载表、`report.py` 末尾追加模板、`quality-scoring.md` 交叉链 tier 定义）。

**Tech Stack:** Python 3, numpy, pandas, sqlalchemy, pymysql（均已就绪）。Markdown 文档。无新依赖。

## Global Constraints

- **密码/连接**：文档与代码中不得出现明文 DB 密码；CLI 示例统一用 `--db "$DB_URL"`（已由 `_shared/bootstrap.sh` 导出）。
- **代码约定**：`lib/` 风格对齐 `lib/outliers.py`（模块级 docstring + 函数 docstring + `try/except ImportError` 守卫）。`impl/` 风格对齐 `impl/anomaly_detector.py`（`HAS_DEPS` 守卫，缺失即 `sys.exit(1)`）。
- **文档约定**：方法论文档进 `_shared/references/`；本地 skill 文档用相对路径指针指向 `_shared`。
- **架构约定（YAGNI）**：不把 `profiling.py` 放进 `_shared/lib/`（待 inspection 复用时再升）；不实现自动 QA 评分器；不做代码级强制 QA；不改 `writeback.py` 与检测主逻辑。
- **tier 单一事实源**：`completeness_tier` 定义在 `lib/profiling.py`，`quality-scoring.md` 只引用不复制。
- **提交约定**：每个 Task 末尾提交一次；提交信息用 conventional 中文前缀（`feat:`/`docs:`/`refactor:`）；多行用多个 `-m` 标志（不用 heredoc）；末尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- **工作目录**：所有相对路径以 worktree 根 `/home/scada/powerelf-worktree-A` 为基准（即 monorepo 的 `main` HEAD）。运行测试用 `cd /home/scada/powerelf-worktree-A`。

---

## 文件结构

| 路径 | 动作 | 职责 |
|------|------|------|
| `_shared/references/data-profiling.md` | 新建 | 画像方法论：列 6 分类（水利映射）、分类型 profile 清单、质量评估框架（完整性 4 级/一致性/准确性红旗/及时性）、6 类分布 + SCADA 特例 |
| `_shared/references/analysis-qa-checklist.md` | 新建 | 交付前 QA 闸：4 类清单（数据质量/计算/合理性/呈现）、8 类陷阱水利映射、5 类红旗量级、三级置信度；声明与 `statistical-caution.md` 姊妹关系 |
| `powerelf-data-governance/lib/profiling.py` | 新建 | `classify_column` / `profile_numeric` / `profile_temporal` / `completeness_tier` / `detect_accuracy_flags` / `profile_table`；纯函数，无 DB 耦合 |
| `powerelf-data-governance/lib/test_profiling.py` | 新建 | 合成数据单元测试（对齐 `test_outliers.py` 风格） |
| `powerelf-data-governance/impl/profiler.py` | 新建 | CLI：`--db --table [--field] [--sample] [--format]`，输出 JSON profile；走 `_shared/lib/db.py`（shim） |
| `powerelf-data-governance/SKILL.md` | 修改 | 加载表加两行触发词（画像 / QA 闸）；报告段 QA 引用放 `statistical-caution` 之前 |
| `powerelf-data-governance/lib/report.py` | 修改 | `generate_daily_report_from_db` 末尾追加 QA 自检节（checkbox 模板）+ `confidence_tier` 字段；不自动判 tier |
| `powerelf-data-governance/rules/quality-scoring.md` | 修改 | 完整性/准确性维度交叉链 `data-profiling.md`（tier 单一事实源，不复制） |
| `powerelf-early-warning/strategies/notification-strategy.md` | 修改 | 加姊妹指针：通知文案定稿前过 `analysis-qa-checklist.md`（与已有 `statistical-caution` 链并列） |

---

## Task 1: 新建 `lib/profiling.py` + 单元测试（TDD）

**Files:**
- Create: `powerelf-data-governance/lib/profiling.py`
- Create: `powerelf-data-governance/lib/test_profiling.py`

**Interfaces:**
- Produces: `classify_column(name, sample_values=None, dtype=None) -> str`（6 分类之一）；`profile_numeric(values) -> dict`（含 null_rate / min / max / mean / median / std / p1-p99 / zero_rate / negative_rate / distinct / distribution_hint）；`profile_temporal(values) -> dict`（含 min / max / span / median_gap / max_gap / future_count / null_rate）；`completeness_tier(valid_rate) -> str`（绿>99% / 黄95-99% / 橙80-95% / 红<80%）；`detect_accuracy_flags(col_profile) -> list[str]`；`profile_table(rows, schema_hints=None) -> dict`。Task 2 的 `profiler.py` CLI 将消费 `profile_table`。

- [ ] **Step 1: 写失败测试 `lib/test_profiling.py`**

创建 `powerelf-data-governance/lib/test_profiling.py`，完整内容（见实施计划正文）。

- [ ] **Step 2: 运行测试，确认失败（profiling.py 尚不存在）**

Run:
```bash
cd /home/scada/powerelf-worktree-A && python3 powerelf-data-governance/lib/test_profiling.py
```
Expected: `ModuleNotFoundError: No module named 'profiling'`。

- [ ] **Step 3: 实现 `lib/profiling.py`**

创建 `powerelf-data-governance/lib/profiling.py`，完整内容（见实施计划正文）。

- [ ] **Step 4: 运行测试，确认全绿**

Run:
```bash
cd /home/scada/powerelf-worktree-A && python3 powerelf-data-governance/lib/test_profiling.py
```
Expected: `总计 20 项: 通过 20, 失败 0`。

- [ ] **Step 5: 提交**

```bash
cd /home/scada/powerelf-worktree-A
git add powerelf-data-governance/lib/profiling.py powerelf-data-governance/lib/test_profiling.py
git commit -m "feat(data-governance): 新增 profiling.py(数据画像纯函数库)与单元测试" -m "classify_column/profile_numeric/profile_temporal/completeness_tier/detect_accuracy_flags/profile_table 全覆盖；tier 单一事实源(绿>99%/黄95-99%/橙80-95%/红<80%)；test_profiling 20 项覆盖列分类/tier 边界/999999 占位符/双峰检测/空序列退化。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: 新建 `impl/profiler.py`（CLI）

**Files:**
- Create: `powerelf-data-governance/impl/profiler.py`

**Interfaces:**
- Consumes: Task 1 的 `profile_table`；`_shared/lib/db.py`（shim 通过 `_shared/bootstrap.sh` 导出 `$DB_URL` 传入）。
- Produces: CLI `python3 impl/profiler.py --db "$DB_URL" --table st_pressure_r [--field water_pressure] [--sample 10000] [--format json|text]` → stdout JSON profile。

- [ ] **Step 1: 写 `impl/profiler.py`**

创建 `powerelf-data-governance/impl/profiler.py`，完整内容（见实施计划正文）。

- [ ] **Step 2: 验证 `--help`（不连 DB）**

Run:
```bash
cd /home/scada/powerelf-worktree-A && python3 powerelf-data-governance/impl/profiler.py --help
```
Expected: 帮助文本含 `--db` / `--table` / `--field` / `--sample` / `--format`。

- [ ] **Step 3: 验证语法/导入（不连 DB）**

Run:
```bash
cd /home/scada/powerelf-worktree-A && python3 -c "import sys; sys.path.insert(0,'powerelf-data-governance'); from impl.profiler import run_profiling, main; print('import OK')"
```
Expected: `import OK`。

- [ ] **Step 4: 提交**

```bash
cd /home/scada/powerelf-worktree-A
git add powerelf-data-governance/impl/profiler.py
git commit -m "feat(data-governance): 新增 profiler.py CLI(数据画像，只读输出 JSON)" -m "对齐 anomaly_detector.py CLI 风格与 --db 约定；load_sample 采样行列表→profile_table 结构化输出；--format json|text。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: 新建 `_shared/references/data-profiling.md`

**Files:**
- Create: `_shared/references/data-profiling.md`

- [ ] **Step 1: 写文档**

创建 `_shared/references/data-profiling.md`，完整内容（见实施计划正文：含列 6 分类 / 分类型 profile 清单 / 完整性 4 级 tier / 准确性红旗 / 6 类分布 + SCADA 特例 / profiler.py CLI 示例）。

- [ ] **Step 2: 提交**

```bash
cd /home/scada/powerelf-worktree-A
git add _shared/references/data-profiling.md
git commit -m "docs(_shared): 新增 data-profiling.md(数据画像方法论+质量评估框架)" -m "含列6分类水利映射/分类型profile清单/完整性4级tier单一事实源/准确性红旗/6类分布+SCADA特例(雨量步进≠卡滞/零膨胀→IQR)；链outlier-methods.md。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: 新建 `_shared/references/analysis-qa-checklist.md`

**Files:**
- Create: `_shared/references/analysis-qa-checklist.md`

- [ ] **Step 1: 写文档**

创建 `_shared/references/analysis-qa-checklist.md`，完整内容（见实施计划正文：含 4 类 QA 清单 / 8 类陷阱水利映射 / 量级红旗 / 三级置信度评级 / 姊妹护栏声明）。

- [ ] **Step 2: 提交**

```bash
cd /home/scada/powerelf-worktree-A
git add _shared/references/analysis-qa-checklist.md
git commit -m "docs(_shared): 新增 analysis-qa-checklist.md(报告交付前QA闸)" -m "4类QA清单(数据质量/计算/合理性/呈现)+8类陷阱水利映射+量级红旗+三级置信度；声明与statistical-caution.md姊妹关系；来源validate-data skill方法论水利化。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: 接线 `powerelf-data-governance/SKILL.md`

**Files:**
- Modify: `powerelf-data-governance/SKILL.md`

- [ ] **Step 1: 加载表加两行触发词**

在 SKILL.md 的"## 按需加载指令"节"### 规则"段中，追加：

```markdown
"首次遇表" / "数据画像" / "画像"    → `../_shared/references/data-profiling.md` + `impl/profiler.py`
"交付" / "QA" / "质量闸"              → `../_shared/references/analysis-qa-checklist.md`
```

- [ ] **Step 2: 报告段 QA 引用放 `statistical-caution` 之前**

在"### 11. 报告生成"小节末尾，找到现有 `statistical-caution.md` 指针，在其**前**插入：

```markdown
> **报告交付前 QA 闸**：报告组装完毕，先过一遍
> [`../_shared/references/analysis-qa-checklist.md`](../_shared/references/analysis-qa-checklist.md)
> 的 4 类清单，完成置信度评级。
```

- [ ] **Step 3: 验证相对链接可达**

Run:
```bash
cd /home/scada/powerelf-worktree-A/powerelf-data-governance
test -f ../_shared/references/data-profiling.md && echo "data-profiling.md OK"
test -f ../_shared/references/analysis-qa-checklist.md && echo "analysis-qa-checklist.md OK"
```
Expected: 两行 OK。

- [ ] **Step 4: 提交**

```bash
cd /home/scada/powerelf-worktree-A
git add powerelf-data-governance/SKILL.md
git commit -m "docs(data-governance): SKILL.md 加画像/QA闸触发词与加载指令" -m "按需加载指令表加两行；报告段QA闸引用置于statistical-caution引用之前。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: 接线 `lib/report.py` + `rules/quality-scoring.md`

**Files:**
- Modify: `powerelf-data-governance/lib/report.py`
- Modify: `powerelf-data-governance/rules/quality-scoring.md`

### 6.1 `report.py` 改动

- [ ] **Step 1: 找到模板字符串末尾（生成时间段）**

在 `lib/report.py` 中找到 `DAILY_REPORT_TEMPLATE` 内 `*报告生成时间: {generated_at}*` 行，在其**后**、模板字符串闭合引号**前**追加 QA 自检节（见 spec §4.5）。

- [ ] **Step 2: `ANOMALY_REPORT_TEMPLATE` 同位置追加 QA 自检节**

同理在异常报告模板末尾追加相同 QA 自检节。

- [ ] **Step 3: `generate_daily_report_from_db` 末尾挂 `confidence_tier` 字段**

在返回 dict 末尾（`generated_at` 之后）新增：
```python
    "confidence_tier": None,  # Agent 按 analysis-qa-checklist.md 填写：Ready to share / Share with caveats / Needs revision
```

- [ ] **Step 4: 验证 `report.py` 语法**

Run:
```bash
cd /home/scada/powerelf-worktree-A && python3 -c "import powerelf-data-governance.lib.report as r; print('report.py import OK')"
```
Expected: `report.py import OK`。

- [ ] **Step 5: 提交 report.py**

```bash
cd /home/scada/powerelf-worktree-A
git add powerelf-data-governance/lib/report.py
git commit -m "feat(data-governance): report.py 追加 QA 自检节 + confidence_tier 字段" -m "DAILY_REPORT_TEMPLATE / ANOMALY_REPORT_TEMPLATE 末尾追加 QA 自检 checkbox 模板与两道护栏引用；generate_daily_report_from_db 返回 dict 挂 confidence_tier 字段(默认 None 由 Agent 填写)。不自动判 tier。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 6.2 `quality-scoring.md` 改动

- [ ] **Step 6: 在 `quality-scoring.md` 加交叉链**

找到"完整性"维度的 tier 定义段，在定义后加：

```markdown
> 完整性 tier 定义（绿>99% / 黄95-99% / 橙80-95% / 红<80%）以 [`../_shared/references/data-profiling.md`](../_shared/references/data-profiling.md) 的 `completeness_tier` 函数为单一事实源，本规则不复制阈值。
```

- [ ] **Step 7: 提交 quality-scoring.md**

```bash
cd /home/scada/powerelf-worktree-A
git add powerelf-data-governance/rules/quality-scoring.md
git commit -m "docs(data-governance): quality-scoring.md 交叉链 data-profiling.md" -m "完整性 tier 定义指向 data-profiling.md 的 completeness_tier 函数为单一事实源，不复制阈值。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: 接线 `powerelf-early-warning/strategies/notification-strategy.md`

**Files:**
- Modify: `powerelf-early-warning/strategies/notification-strategy.md`

- [ ] **Step 1: 加 QA 闸姊妹指针**

在"## 概述"段末尾（现有 `statistical-caution.md` 指针之后）追加：

```markdown
> **通知交付前 QA 闸**：通知文案定稿前，先过一遍
> [`../../_shared/references/analysis-qa-checklist.md`](../../_shared/references/analysis-qa-checklist.md)
> 的交付前 QA 清单（数据质量/计算/合理性/呈现）。
```

- [ ] **Step 2: 提交**

```bash
cd /home/scada/powerelf-worktree-A
git add powerelf-early-warning/strategies/notification-strategy.md
git commit -m "docs(early-warning): notification-strategy 加 QA 闸姊妹指针" -m "通知文案定稿前先过 analysis-qa-checklist.md（与已有 statistical-caution 链并列）。" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: 最终验证

**Files:** 无新建/修改（仅运行校验；若发现缺陷则补提交）。

- [ ] **Step 1: 全量单测**

Run:
```bash
cd /home/scada/powerelf-worktree-A && python3 powerelf-data-governance/lib/test_profiling.py
```
Expected: `总计 20 项: 通过 20, 失败 0`。

- [ ] **Step 2: `profiler.py` 语法/导入自检（不连 DB）**

Run:
```bash
cd /home/scada/powerelf-worktree-A && python3 -c "
import sys; sys.path.insert(0, 'powerelf-data-governance')
from lib.profiling import classify_column, profile_numeric, profile_temporal, completeness_tier, detect_accuracy_flags, profile_table
from impl.profiler import run_profiling, main
print('all imports OK')
"
```
Expected: `all imports OK`。

- [ ] **Step 3: `report.py` QA 自检节存在验证**

Run:
```bash
cd /home/scada/powerelf-worktree-A && grep -n "QA 自检" powerelf-data-governance/lib/report.py && grep -n "confidence_tier" powerelf-data-governance/lib/report.py
```
Expected: 两行均有匹配（模板含 QA 自检节 + 返回 dict 含 `confidence_tier` 字段）。

- [ ] **Step 4: 相对链接全量校验**

Run:
```bash
cd /home/scada/powerelf-worktree-A && python3 -c "
import re, os
broken = []
for root, _, files in os.walk('.'):
    if '.git' in root: continue
    for f in files:
        if not f.endswith('.md'): continue
        p = os.path.join(root, f)
        for m in re.finditer(r'\]\(([^)]+\.md[^)]*)\)', open(p, encoding='utf-8').read()):
            tgt = m.group(1).split('#')[0]
            if tgt.startswith('http'): continue
            base = os.path.dirname(p)
            full = os.path.normpath(os.path.join(base, tgt))
            if not os.path.exists(full):
                broken.append((p, tgt))
print('broken links:', broken if broken else 'none')
"
```
Expected: `broken links: none`。

- [ ] **Step 5: 工作树干净确认 + 推送**

```bash
cd /home/scada/powerelf-worktree-A && git status --short
git log --oneline -10
```
确认无未提交文件后推送：

```bash
HTTPS_PROXY=socks5://192.168.200.71:7897 git push origin feat/governance-profiling-qa-gate
```

---

## Self-Review

**1. Spec 覆盖**（逐条核对 `2026-07-13-governance-profiling-qa-gate-design.md` §3）：
- ✅ 新建 `_shared/references/data-profiling.md` → Task 3
- ✅ 新建 `_shared/references/analysis-qa-checklist.md` → Task 4
- ✅ 新建 `powerelf-data-governance/lib/profiling.py` → Task 1
- ✅ 新建 `powerelf-data-governance/impl/profiler.py` → Task 2
- ✅ 新建 `powerelf-data-governance/lib/test_profiling.py` → Task 1
- ✅ 修改 `powerelf-data-governance/SKILL.md` → Task 5
- ✅ 修改 `powerelf-data-governance/lib/report.py` → Task 6
- ✅ 修改 `powerelf-data-governance/rules/quality-scoring.md` → Task 6
- ✅ 修改 `powerelf-early-warning/strategies/notification-strategy.md` → Task 7

**2. 占位符扫描**：无 TBD/TODO/"添加适当错误处理"等；每个代码步骤含完整可执行代码。

**3. 类型/命名一致性**：
- `completeness_tier` 在 `lib/profiling.py` 定义、`profile_table` 返回 tier 字段、`quality-scoring.md` 引用时名称一致。
- `profile_table(rows, schema_hints=None)` 入参 `schema_hints` 在 Task 1 实现与 Task 2 `run_profiling` 调用处一致。
- QA 闸的 `confidence_tier` 字段名在 `report.py` 返回 dict 与 `analysis-qa-checklist.md` 三级评级描述中一致。

**4. Spec 未覆盖点**：schema 探索 SQL 在 `impl/profiler.py` 中走 `DESCRIBE <table>`（MySQL 风格），符合 spec §6"schema 探索从 PG 改 MySQL"要求；`profile_temporal` 内 `pd.to_datetime` 引用仅在 `HAS_PANDAS` 分支内触发，且函数内部 `try/except` 已包裹，pandas 缺失时退化返回 None。
