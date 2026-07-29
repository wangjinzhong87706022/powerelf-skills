# Powerelf Skills 深度代码评审 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/superpowers/specs/2026-07-29-skills-deep-review-design.md` 设计，对 5 个主 skill + `_shared` 共享层做只读深度代码评审，产出 1 份总报告 + 6 份子报告到 `reviews/`，不修改任何被评审文件。

**Architecture:** 7 阶段顺序执行（5 skill 顺序 → _shared → 跨 skill 横向 + 总报告）。每个阶段读 1 个 skill 的全部相关文件 + 跑 4 维度检查项 + 写 1 份子报告。最后 1 个任务做跨 skill 横向对比 + 总报告。`reviews/` 目录由 Task 0 创建。

**Tech Stack:** 仅静态分析（`Read`、`grep`、`py_compile`、`python -c` 启发式）；不连真实数据库。报告用 Markdown。

## Global Constraints（每个任务隐含遵守）

- **只读评审**：本轮**不修改任何被评审文件**（SKILL.md / rules / algorithms / impl / tests / _shared 全部）。所有改动仅限创建 `reviews/*.md` 报告文件 + 一个 `reviews/` 目录。
- **范围**：5 个主 skill（`powerelf-data-governance` / `-early-warning` / `-monitor` / `-inspection` / `-chatbi`）+ `_shared/`。**不评审**：`chatbi/`（遗留）、`monitor/`（遗留）、`early-warning/`、`early-warning-v3/`、`darwin-skill/`、`.github/`、`.superpowers/`、`skill-creator-workspace/`、`.claude/`、`docs/`（spec 与 plan 自身除外）。
- **报告位置**：`reviews/` 目录（仓库根下）。**默认不 commit** —— 7 份报告默认不进入 git；用户在评审完成后决定是否 commit / 推分支 / 转 issue。
- **4 维度**：每个有代码的 skill 子报告必须 4 维度都覆盖（代码级 / 文档-代码一致 / SQL Schema / 架构）；纯文档 skill（early-warning / monitor）只覆盖"文档-代码一致"和"架构"两维度，并显式标注"无代码维度"。
- **严重度**：每个 finding 必须有 `Blocker` / `High` / `Medium` / `Low` 之一，且至少含维度 + 文件:行 + 描述 + 建议。
- **untracked 盘点**：Task 1（governance）显式列出所有 untracked / modified 文件并给出处置（保留 / 移入 tests / 删除 + 理由）；Task 8（_shared）补查 `st128*.py`、`report*.py` 是不是调试残留。
- **commit 粒度**：每个 Task 结束后**默认不 commit**（与"默认不 commit 报告"一致）；若用户在中途改主意，单独指令。
- **工作树记录**：Task 9（总报告）§0 记录 `git rev-parse HEAD` + `git status --porcelain | wc -l` 显式版本戳。

---

## File Structure

**新建（`reviews/` 目录，7 个报告）：**
- `reviews/REVIEW.md` — 总报告，跨 skill 横向 + finding 排序
- `reviews/review-powerelf-data-governance.md` — governance 子报告（含 untracked 盘点结论）
- `reviews/review-powerelf-inspection.md` — inspection 子报告
- `reviews/review-powerelf-early-warning.md` — early-warning 子报告
- `reviews/review-powerelf-monitor.md` — monitor 子报告
- `reviews/review-powerelf-chatbi.md` — chatbi 子报告
- `reviews/review-shared-lib.md` — _shared 子报告（含 untracked 调试脚本补查）

**修改：** 无。

**删除：** 无。

---

## Task 0: 创建 `reviews/` 目录 + 记录基线

**Files:** Create: `reviews/.gitkeep`（仅占位，避免空目录被删；不放入任何报告）

- [ ] **Step 1: 创建目录**

Run: `mkdir -p reviews && touch reviews/.gitkeep`
Expected: `reviews/` 目录存在且为空。

- [ ] **Step 2: 记录基线 commit 与 working tree 状态**

Run:
```bash
echo "HEAD: $(git rev-parse HEAD)" > /tmp/review-baseline.txt
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> /tmp/review-baseline.txt
echo "Untracked: $(git status --porcelain | grep '^??' | wc -l)" >> /tmp/review-baseline.txt
echo "Modified:  $(git status --porcelain | grep '^ M' | wc -l)" >> /tmp/review-baseline.txt
cat /tmp/review-baseline.txt
```
Expected: 3 行输出（HEAD hash、ISO 时间、untracked 计数、modified 计数）。**这个文件不进 git**；只是供 Task 9 在总报告 §0 使用。

- [ ] **Step 3: 不 commit**

确认 `git status` 仍显示 working tree 有原 untracked / modified 改动（除 `reviews/.gitkeep` 外不应有变化）。

---

## Task 1: 评审 `powerelf-data-governance` — 写子报告 1/6

**Files:** Create: `reviews/review-powerelf-data-governance.md`；Read: `powerelf-data-governance/SKILL.md` + `powerelf-data-governance/rules/*.md` (5) + `powerelf-data-governance/algorithms/*.md` (3) + `powerelf-data-governance/impl/*.py` (全部) + `powerelf-data-governance/lib/*.py` (如有) + `powerelf-data-governance/tests/*.py` (如有) + `powerelf-data-governance/evolution/*.md` + `powerelf-data-governance/SKILL_OPTIMIZATION_*.md` + 工作树 untracked 整目录（`powerelf-data-governance/references/`、`scripts/`、`tests/`）

**Interfaces:**
- Consumes: `_shared/references/schema.md`（交叉验证 SQL 用）
- Produces: `reviews/review-powerelf-data-governance.md`（模板 8 节齐全：概览 / Blockers / High / Medium / Low / 文档-代码一致性矩阵 / SQL Schema 用表 / untracked 处置 / 正面发现）

- [ ] **Step 1: 读 SKILL.md**

Read: `powerelf-data-governance/SKILL.md`
提取：声明的规则数、算法数、入口描述、引用 `_shared` 路径、路由表节。

- [ ] **Step 2: 列 `rules/` 与 `algorithms/` 实际文件**

Run: `ls -la powerelf-data-governance/rules/ powerelf-data-governance/algorithms/`
Expected: 5 + 3 文件，文件名记下。

- [ ] **Step 3: 全文读 `rules/*.md`（5 个）**

Read: 全部 5 个 `rules/*.md`
提取：每个规则描述的阈值、判断步骤、引用算法。

- [ ] **Step 4: 全文读 `algorithms/*.md`（3 个）**

Read: 全部 3 个 `algorithms/*.md`
提取：算法步骤、参数、阈值、引用公式。

- [ ] **Step 5: 编译并扫 `impl/*.py` + `lib/*.py`**

Run:
```bash
python3 -m py_compile powerelf-data-governance/impl/*.py 2>&1 | tee /tmp/gov-pycompile.log
ls powerelf-data-governance/impl/ powerelf-data-governance/lib/ 2>/dev/null
grep -nE "except:" powerelf-data-governance/impl/*.py powerelf-data-governance/lib/*.py 2>/dev/null
grep -nE "f\".*SELECT|f\".*WHERE|f\".*INSERT|\".*%s.*SELECT" powerelf-data-governance/impl/*.py 2>/dev/null
```
Expected: py_compile 全过（governance 最近 8c6f133 修过裸 except）；裸 except 与 SQL 注入面列出。

- [ ] **Step 6: 读 `tests/`（如有）**

Run: `ls powerelf-data-governance/tests/ 2>/dev/null && find powerelf-data-governance/tests -name "*.py" -exec wc -l {} +`
Expected: 文件清单 + LOC；与 impl LOC 算覆盖率（粗略）。

- [ ] **Step 7: 读 `evolution/` + 根目录优化文档**

Read: `powerelf-data-governance/evolution/*.md`、`powerelf-data-governance/SKILL_OPTIMIZATION_PLAN.md`、`powerelf-data-governance/SKILL_OPTIMIZATION_SUMMARY.md`
提取：参数表当前值、待办改进。

- [ ] **Step 8: 维度 1（代码级）finding 列表**

基于 Step 5 输出，列出：py 编译错误 / 裸 except / SQL 注入面 / 测试覆盖率。

- [ ] **Step 9: 维度 2（文档-代码一致）finding 列表**

对照 Step 1 SKILL.md 与 Step 3-4 rules/algorithms：阈值数值漂移、声明的"5 规则 3 算法"vs 实际文件数、"已实现"vs 代码状态。

- [ ] **Step 10: 维度 3（SQL Schema）finding 列表**

对照 Step 4-5 SQL 字符串与 `_shared/references/schema.md`：表名/列名/JOIN 字段是否一致；占位符 `%s` vs `?` 一致。

- [ ] **Step 11: 维度 4（架构）finding 列表**

对照 README"5 规则+3 算法"声明：frontmatter 格式、`_shared` 引用方式、路由表节齐全度、缺哪些子目录。

- [ ] **Step 12: 盘点工作树 untracked / modified 治理 skill 范围文件**

Run:
```bash
git status --porcelain | grep -E "powerelf-data-governance"
ls powerelf-data-governance/references/ 2>/dev/null
ls powerelf-data-governance/scripts/ 2>/dev/null
ls powerelf-data-governance/tests/ 2>/dev/null
```
对每个 untracked / modified 文件给"保留 / 移入 tests / 删除"建议 + 理由（前 30 行内容摘要）。

- [ ] **Step 13: 写 `reviews/review-powerelf-data-governance.md`**

按 spec §5.2 模板 8 节齐全。Finding 表统一格式：
```
| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
```

- [ ] **Step 14: 验证子报告完整**

自检清单：
- [ ] 8 节齐全（概览 / Blockers / High / Medium / Low / 一致性矩阵 / SQL 表 / untracked / 正面）
- [ ] 每个 finding 都有 5 字段（严重度 / 维度 / 位置 / 描述 / 建议）
- [ ] 4 维度都有 ≥1 finding 或显式"无"标注
- [ ] untracked 处置表每行有"处置 + 理由"

- [ ] **Step 15: 不 commit**

---

## Task 2: 评审 `powerelf-inspection` — 写子报告 2/6

**Files:** Create: `reviews/review-powerelf-inspection.md`；Read: `powerelf-inspection/SKILL.md` + `powerelf-inspection/rules/*.md` (10) + `powerelf-inspection/algorithms/*.md` (如有) + `powerelf-inspection/impl/*.py` (全部) + `powerelf-inspection/lib/*.py` (全部) + `powerelf-inspection/tests/*.py` (如有) + `powerelf-inspection/evolution/*.md` + `powerelf-inspection/references/*.md` + `powerelf-inspection/autoresearch/` (如有)

**Interfaces:**
- Consumes: Task 1 governance 报告（避免重复列"governance 引用 inspection"的链接 404 —— Task 1 已盘 governance 视角，Task 2 盘 inspection 视角）；`_shared/references/schema.md`
- Produces: `reviews/review-powerelf-inspection.md`

- [ ] **Step 1: 读 SKILL.md**

Read: `powerelf-inspection/SKILL.md`
提取：声明的规则数、模式数（实时 vs 深度）、入口描述、路由表。

- [ ] **Step 2: 列 rules/algorithms/impl/lib 实际文件**

Run: `ls -la powerelf-inspection/rules/ powerelf-inspection/algorithms/ powerelf-inspection/impl/ powerelf-inspection/lib/ powerelf-inspection/references/`

- [ ] **Step 3: 全文读 `rules/*.md`（10 个）**

Read: 全部 10 个 `rules/*.md`
提取：每个规则描述的阈值、调用算法、引用 `lib/` 模块。

- [ ] **Step 4: 全文读 `references/*.md`**

Read: `powerelf-inspection/references/*.md`（pitfalls / few_shots / business_rules / data-model / api-reference 等）
提取：与最近提交（`a8d8c48` lib/quality C1/C2/H1、`49f5dca` DD1/C3、`425621f` pitfalls、`368aae9` business_rules 等）声明对齐情况。

- [ ] **Step 5: 编译并扫 `impl/*.py` + `lib/*.py`**

Run:
```bash
python3 -m py_compile powerelf-inspection/impl/*.py powerelf-inspection/lib/*.py 2>&1 | tee /tmp/ins-pycompile.log
grep -nE "except:" powerelf-inspection/impl/*.py powerelf-inspection/lib/*.py 2>/dev/null
grep -nE "f\".*SELECT|f\".*WHERE|\".*%s.*SELECT" powerelf-inspection/impl/*.py 2>/dev/null
```
预期 inspection 之前修过大量裸 except（`f3f50c8` 去重 3×MAD），但仍有审计价值。

- [ ] **Step 6: 读 `tests/`（CI 阻断脚本）**

Run: `ls powerelf-inspection/tests/ && find powerelf-inspection/tests -name "test_*.py" -exec wc -l {} +`
Run: `grep -l "st_id" powerelf-inspection/tests/*.py 2>/dev/null`
预期：78 tests PASS（最近 `80141b7`），但可能存在 skip 守卫或集成测试孤岛。

- [ ] **Step 7: 读 `evolution/`**

Read: `powerelf-inspection/evolution/*.md`
提取：参数表、反馈日志条目数。

- [ ] **Step 8: 维度 1 finding**

基于 Step 5-6：编译错、裸 except、SQL 注入、测试覆盖、CI 阻断脚本本身是否有 bug。

- [ ] **Step 9: 维度 2 finding**

对照 Step 1 SKILL.md 与 Step 3-4："10 规则 + 2 模式"声明 vs 实际；Holt-Winters/Mann-Kendall 等算法在 SKILL.md 宣传但代码不存在的部分（参考 inspection-refactor spec §1）。

- [ ] **Step 10: 维度 3 finding**

对照 Step 4-5 SQL 与 `_shared/references/schema.md`：inspection 大量 `st_*` 表 SQL 是否在 schema.md 全部存在；JOIN 键（`eq_id` / `stcd` / `st_id`）是否一致。

- [ ] **Step 11: 维度 4 finding**

对照 README 声明：inspection 的 frontmatter 格式、是否引用 `_shared` 文档、路由表齐全度。

- [ ] **Step 12: 写 `reviews/review-powerelf-inspection.md`**

按 spec §5.2 模板 8 节。

- [ ] **Step 13: 验证子报告完整**

同 Task 1 Step 14 清单。

- [ ] **Step 14: 不 commit**

---

## Task 3: 评审 `powerelf-early-warning` — 写子报告 3/6

**Files:** Create: `reviews/review-powerelf-early-warning.md`；Read: `powerelf-early-warning/SKILL.md` + `powerelf-early-warning/rules/*.md` (5) + `powerelf-early-warning/strategies/*.md` (3) + `powerelf-early-warning/evolution/*.md`

**Interfaces:**
- Produces: `reviews/review-powerelf-early-warning.md`
- 注：本 skill **无 Python 代码**（`find powerelf-early-warning -name "*.py"` 0 文件）。维度 1（代码级）和维度 3（SQL Schema）显式标注"无"；重点维度 2 + 维度 4。

- [ ] **Step 1: 读 SKILL.md**

Read: `powerelf-early-warning/SKILL.md`
提取：声明的"5 规则 + 3 策略"、路由表、是否引用 `_shared`、是否引用 monitor 或 governance。

- [ ] **Step 2: 列 `rules/` 与 `strategies/` 实际文件**

Run: `ls -la powerelf-early-warning/rules/ powerelf-early-warning/strategies/`

- [ ] **Step 3: 全文读 `rules/*.md` (5) + `strategies/*.md` (3)**

Read: 全部
提取：阈值、视频 AI 报警、通知分发的具体逻辑描述。

- [ ] **Step 4: 读 `evolution/`**

Read: `powerelf-early-warning/evolution/*.md`

- [ ] **Step 5: 维度 1（代码级）—— 显式"无"**

在报告中 §0 概览里加一行：`代码覆盖: 0 py 文件（纯文档 skill）`，并在 §1-4 标注"代码级 finding: 无（无 Python 实现可评）"。

- [ ] **Step 6: 维度 2 finding（重点）**

SKILL.md 与 rules/strategies 的描述一致性、阈值数值漂移、"已实现"vs"规划"标记。

- [ ] **Step 7: 维度 3（SQL Schema）—— 显式"无"**

同样在报告中标注"SQL finding: 无"。

- [ ] **Step 8: 维度 4 finding（重点）**

与 README 声明的"5 规则 + 3 策略"对得上、frontmatter 格式、路由表 4 节齐全度（适用场景 / When NOT to Use / Related Skills / `_shared` 引用）、是否与 `powerelf-monitor` / `powerelf-data-governance` 形成路由闭环。

- [ ] **Step 9: 写 `reviews/review-powerelf-early-warning.md`**

模板 8 节，但 §5（一致性矩阵）简化为"声明 vs 实际"两列表；§6（SQL 用表）显式"无"。

- [ ] **Step 10: 验证完整 + 不 commit**

---

## Task 4: 评审 `powerelf-monitor` — 写子报告 4/6

**Files:** Create: `reviews/review-powerelf-monitor.md`；Read: `powerelf-monitor/SKILL.md` + `powerelf-monitor/rules/*.md` (5) + `powerelf-monitor/algorithms/*.md` (3) + `powerelf-monitor/evolution/*.md`

**Interfaces:**
- Produces: `reviews/review-powerelf-monitor.md`
- 同 Task 3，**无 Python 代码**（0.2k LOC 纯文档）。

- [ ] **Step 1: 读 SKILL.md**

Read: `powerelf-monitor/SKILL.md`
提取：声明的"5 规则 + 3 算法"、12 类监测端点描述、是否引用 `_shared`、是否与 inspection 重复内容（参考 inspection-refactor spec §1: SKILL.md L221-320 实时监测模式 ≈ 逐字复制 monitor）。

- [ ] **Step 2: 列 rules/algorithms**

Run: `ls -la powerelf-monitor/rules/ powerelf-monitor/algorithms/`

- [ ] **Step 3: 全文读 rules + algorithms**

Read: 全部
提取：12 类监测规则描述（`st_*` 表覆盖）。

- [ ] **Step 4: 读 evolution/**

Read: `powerelf-monitor/evolution/*.md`

- [ ] **Step 5: 维度 1（代码级）—— 显式"无"**

§0 标注"无 Python 实现"；§1-4 标注"代码级: 无"。

- [ ] **Step 6: 维度 2 finding（重点）**

SKILL.md 描述与 rules/algorithms 一致性、阈值漂移。

- [ ] **Step 7: 维度 3（SQL Schema）—— 显式"无代码但有逻辑引用"**

虽然无 Python 代码，但 rules/algorithms 中**会引用 `st_*` 表名**（描述性的）。列出所有引用的 `st_*` 表，与 `_shared/references/schema.md` 交叉，标"是否在 schema.md 存在"。

- [ ] **Step 8: 维度 4 finding（重点）**

frontmatter、12 类监测描述与 _shared 路由闭环、`inspection` 引用 monitor 的部分是否对齐。

- [ ] **Step 9: 写 `reviews/review-powerelf-monitor.md`**

模板 8 节，§6 SQL 用表填"rules/algorithms 引用的 st_* 表 + schema.md 存在性"。

- [ ] **Step 10: 验证完整 + 不 commit**

---

## Task 5: 评审 `powerelf-chatbi` — 写子报告 5/6

**Files:** Create: `reviews/review-powerelf-chatbi.md`；Read: `powerelf-chatbi/SKILL.md` + `powerelf-chatbi/rules/*.md` (3) + `powerelf-chatbi/impl/*.py` (2) + `powerelf-chatbi/evolution/*.md` + `powerelf-chatbi/references/*.md`

**Interfaces:**
- Consumes: `_shared/references/schema.md`
- Produces: `reviews/review-powerelf-chatbi.md`
- 注：chatbi 涉及 SQL 生成（核心能力），SQL Schema 维度是重点。

- [ ] **Step 1: 读 SKILL.md**

Read: `powerelf-chatbi/SKILL.md`
提取：3 规则（意图分类 / 图表选择 / SQL 生成）、20+ 业务表声明、路由表。

- [ ] **Step 2: 列 rules/impl 实际文件**

Run: `ls -la powerelf-chatbi/rules/ powerelf-chatbi/impl/ powerelf-chatbi/references/`

- [ ] **Step 3: 全文读 `rules/*.md` (3)**

Read: 全部
提取：意图分类字典、图表选择规则、SQL 生成模板。

- [ ] **Step 4: 编译并扫 `impl/*.py`**

Run:
```bash
python3 -m py_compile powerelf-chatbi/impl/*.py 2>&1
grep -nE "except:" powerelf-chatbi/impl/*.py 2>/dev/null
grep -nE "f\".*SELECT|\".*%s.*SELECT" powerelf-chatbi/impl/*.py 2>/dev/null
```
预期 chatbi 是 SQL 生成器，注入面是核心。

- [ ] **Step 5: 读 references/**

Read: `powerelf-chatbi/references/*.md`

- [ ] **Step 6: 读 evolution/**

Read: `powerelf-chatbi/evolution/*.md`

- [ ] **Step 7: 维度 1 finding**

SQL 注入面（**重点**：chatbi 是 LLM 生成 SQL 给数据库跑的，注入面比一般 skill 大）、裸 except、测试覆盖。

- [ ] **Step 8: 维度 2 finding**

SKILL.md 声明的"3 规则 / 20+ 业务表"vs 实际规则文件、图表选择规则覆盖范围。

- [ ] **Step 9: 维度 3 finding（重点）**

chatbi 生成的 SQL 与 `_shared/references/schema.md` 的对齐：20+ 表是否都在 schema.md、JOIN 字段、列名。

- [ ] **Step 10: 维度 4 finding**

frontmatter、路由表、与 `_shared` 引用。

- [ ] **Step 11: 写 `reviews/review-powerelf-chatbi.md`**

模板 8 节。

- [ ] **Step 12: 验证完整 + 不 commit**

---

## Task 6: 评审 `_shared` 共享层 — 写子报告 6/6（含 untracked 调试脚本补查）

**Files:** Create: `reviews/review-shared-lib.md`；Read: `_shared/lib/db.py` + `_shared/lib/*.py` (全部) + `_shared/bootstrap.sh` + `_shared/api-auth.md` + `_shared/references/schema.md` + `_shared/algorithms/*.py` + `_shared/algorithms/*.md` (如有) + `_shared/rules/*.md` (如有) + `_shared/evolution/*.md` (如有)

**Interfaces:**
- Consumes: Task 1-5 全部子报告（特别是各 skill 在维度 3 引用 schema.md 的 finding）
- Produces: `reviews/review-shared-lib.md`

- [ ] **Step 1: 读 SKILL.md — 无，但有 README 描述**

Run: `cat _shared/README* 2>/dev/null; ls _shared/`
预期：`_shared/` 无 SKILL.md，靠 README/根 README 描述。

- [ ] **Step 2: 编译并扫 `lib/*.py`**

Run:
```bash
python3 -m py_compile _shared/lib/*.py 2>&1
grep -nE "except:" _shared/lib/*.py 2>/dev/null
grep -nE "POWERELF_DB_|SRM_DB_|getenv|os.environ" _shared/lib/*.py 2>/dev/null
```
预期 `_shared/lib/db.py` 是 modified 状态（工作树改动），审其改动是否破坏向后兼容（`SRM_DB_*` 后备）。

- [ ] **Step 3: 重点审 `_shared/lib/db.py` 的 modified 改动**

Run: `git diff _shared/lib/db.py | head -100`
Run: `git diff _shared/references/schema.md | head -100`
提取：与原 HEAD 比，改了什么？是否破坏 `POWERELF_DB_*` 优先级、是否破坏 `SRM_DB_*` 后备（参考 MEMORY.md `powerelf-db-credentials-location.md` 提到的历史 bug 模式）。

- [ ] **Step 4: 读 `bootstrap.sh` + `api-auth.md`**

Read: 全部
提取：DB_URL 导出逻辑、Authorization 头格式、tenant-id 处理。

- [ ] **Step 5: 读 `references/schema.md` 与工作树改动**

Read: `_shared/references/schema.md`
Run: `git diff _shared/references/schema.md | head -100`
提取：st_* 表清单、列定义、索引。modified 部分是否破坏表结构引用一致。

- [ ] **Step 6: 读 `algorithms/` 与 `rules/`**

Run: `ls _shared/algorithms/ _shared/rules/`
Read: 全部
提取：MAD / 水位变化率 / 位移速率 / 水库 / 雨情 等共享原语。

- [ ] **Step 7: 维度 1 finding（db.py / algorithms 重点）**

DB 连接层安全性（注入 / 凭据泄漏 / 端口解析 bug 模式）、裸 except、向后兼容。

- [ ] **Step 8: 维度 2 finding**

shared 文档（README 描述）与实际 `lib/` `algorithms/` `rules/` 列表的一致性。

- [ ] **Step 9: 维度 3 finding（schema 准确性，重点）**

schema.md 与 Task 1-5 各 skill 用到的 st_* 表交叉，列出：每个 skill 引用、schema.md 是否存在、列名是否一致。

- [ ] **Step 10: 维度 4 finding**

shared 层是否被 5 skill 全部引用、引用方式（`../_shared/...` vs 绝对路径）是否统一。

- [ ] **Step 11: 补查 untracked 调试脚本**

Run:
```bash
ls -la _shared/check_st128*.py _shared/report_128.py _shared/report_anomalies.py 2>/dev/null
for f in _shared/check_st128*.py _shared/report_128.py _shared/report_anomalies.py; do
  echo "=== $f ==="
  head -10 "$f" 2>/dev/null
done
```
对每个文件给"保留 / 移入 tests / 删除"建议 + 理由（前 10 行内容摘要）。

- [ ] **Step 12: 补查 untracked `.md` 报告**

Run: `ls -la _shared/*.md | grep -v "^.*\.md$" 2>/dev/null`  # 实际为 `git status --porcelain | grep _shared`
Run: `for f in _shared/hermes_*.md _shared/optimization_*.md _shared/real_world_*.md _shared/routing_*.md _shared/skill_optimization_*.md _shared/test_verification_*.md _shared/verification_*.md; do echo "=== $f ==="; head -5 "$f" 2>/dev/null; done`
对每个 .md 报告给"保留 / 移入 docs/ / 删除"建议 + 理由。

- [ ] **Step 13: 写 `reviews/review-shared-lib.md`**

模板 8 节，§7 untracked 处置表覆盖本任务所有盘点（db.py 改动 + schema.md 改动 + st128*.py / report*.py / *.md 报告）。

- [ ] **Step 14: 验证完整 + 不 commit**

---

## Task 7: 跨 skill 横向对比 + 写总报告

**Files:** Create: `reviews/REVIEW.md`；Read: 6 份子报告全文

**Interfaces:**
- Consumes: 6 份子报告（`reviews/review-powerelf-*.md` + `reviews/review-shared-lib.md`）
- Produces: `reviews/REVIEW.md`（模板 7 节：元信息 / Blockers / High / Medium / Low / 横向发现 / 正面发现 / 索引）

- [ ] **Step 1: 汇总所有 finding**

从 6 份子报告抽 finding 表，列：严重度 + 维度 + skill + 文件:行 + 描述。
预期 ~30-100 finding。

- [ ] **Step 2: 按严重度 + 维度排序**

严重度内降序、维度内按 skill 字母序。

- [ ] **Step 3: 横向 5.1 — 命名 / 格式不一致**

对比 5 个 SKILL.md 的 frontmatter / 元数据格式；规则文件命名风格。

- [ ] **Step 4: 横向 5.2 — _shared 引用方式**

Run: `grep -nE "_shared|\.\./_shared" powerelf-*/SKILL.md powerelf-*/rules/*.md powerelf-*/impl/*.py 2>/dev/null | head -50`
判断：相对路径 vs 绝对路径 vs 环境变量，统一吗？

- [ ] **Step 5: 横向 5.3 — README 与实际文件数偏差**

README 声明：
- governance: 5 规则 + 3 算法
- early-warning: 5 规则 + 3 策略
- monitor: 5 规则 + 3 算法（12 类监测）
- inspection: 10 规则 + 2 模式
- chatbi: 3 规则

Run: `for d in powerelf-data-governance powerelf-early-warning powerelf-monitor powerelf-inspection powerelf-chatbi; do echo "$d: rules=$(ls $d/rules/ 2>/dev/null | wc -l) algorithms=$(ls $d/algorithms/ 2>/dev/null | wc -l) strategies=$(ls $d/strategies/ 2>/dev/null | wc -l)"; done`
对每个 skill 给"声明 vs 实际"对照。

- [ ] **Step 6: 横向 5.4 — 工作树 untracked 处置汇总**

从 Task 1（governance untracked）和 Task 6（_shared untracked）抽所有处置建议，按 skill 汇总。

- [ ] **Step 7: 正面发现**

从 6 份子报告的"§8 正面发现"汇总，列：保留的护栏、好的设计、最近提交的好实践。

- [ ] **Step 8: 写 `reviews/REVIEW.md` §0 元信息**

模板：
```markdown
## 0. 元信息
- 评审日期: 2026-07-29
- HEAD: <git rev-parse HEAD>
- Working tree: <N untracked, M modified>（从 Task 0 Step 2 抽取）
- 评审范围: 5 主 skill + _shared
- 评审维度: 4 个 (代码级 / 文档一致 / SQL schema / 架构)
- 总 finding 数: N (blocker X / high Y / med Z / low W)
- 评审者: Claude (with superpowers:brainstorming → writing-plans)
- spec: docs/superpowers/specs/2026-07-29-skills-deep-review-design.md
- plan: docs/superpowers/plans/2026-07-29-skills-deep-review-implementation.md
```

- [ ] **Step 9: 写 §1-4 finding 表**

每节一张表，列：严重度（节标题已含） / 维度 / skill / 文件:行 / 描述 / 建议。

- [ ] **Step 10: 写 §5 横向发现 + §6 正面发现 + §7 索引**

§7 索引 6 个子报告 + 链 `reviews/review-powerelf-*.md`。

- [ ] **Step 11: 验证总报告完整**

自检：
- [ ] 7 节齐全（元信息 / Blockers / High / Medium / Low / 横向 / 正面 / 索引）—— 注：模板 7 节含索引
- [ ] finding 总数 = 6 子报告 finding 加总
- [ ] 严重度计数 = blocker X / high Y / med Z / low W 在 §0 标注
- [ ] §0 HEAD / working tree 计数已填
- [ ] §7 索引 6 个文件路径都正确

- [ ] **Step 12: 不 commit**

---

## Task 8: 收尾 — 不 commit，请用户决定

- [ ] **Step 1: 确认 7 份报告齐全**

Run: `ls -la reviews/`
Expected: 6 子报告 + REVIEW.md + `.gitkeep` = 7 个 md 文件 + 1 个 .gitkeep。

- [ ] **Step 2: 全部 finding 总数交叉验证**

从总报告 §0 取 finding 总数；用 grep 数子报告里 finding 行数：
```bash
grep -c "^| .* | .* | .* |" reviews/review-*.md reviews/REVIEW.md
```
预期：每个子报告 finding 数 + 总报告（自身 finding 数是 §0 总数）= 一致。

- [ ] **Step 3: 报告用户 + 询问 commit / 推分支 / 转 issue**

向用户报告：
- 评审完成，7 份报告在 `reviews/`
- 总 finding 数与分布
- 默认未 commit

询问：
- 是否 commit 到 main / 推分支 / 转 GitHub issue
- 是否需要写"修复" spec（如果 finding 数量大、需分批修）

---

## Self-Review（写完后自审）

写完后，检查：

1. **Spec 覆盖**：
   - 7 阶段 ↔ Task 0-7+8 (7 个评审任务 + Task 0 创建 + Task 8 收尾) ✓
   - 4 维度 ↔ Task 1/2/5/6 显式列 4 维度步骤；Task 3/4 标注"无代码维度" ✓
   - 1 总 + 6 子 ↔ Task 1-6 各 1 子 + Task 7 总 ✓
   - untracked 盘点 ↔ Task 1 Step 12 + Task 6 Step 11-12 ✓
   - 严重度 + 维度 + 位置 + 描述 + 建议 ↔ Task 1 Step 13-14 模板 ✓

2. **占位符扫描**：无 TBD / TODO / "类似 Task X"。每个 Step 都有具体命令或 Read 路径。

3. **类型一致**：无类型问题（评审计划不涉及代码类型）。

4. **任务规模**：每个 Task 是 1 份子报告或 1 份总报告；最大 Task 1 governance 16k LOC 但步骤细化为 15 步。Task 7 总报告 12 步。

5. **可中断性**：每个 Task 独立 deliverable，可在任何 Task 后暂停，下次接着做。
