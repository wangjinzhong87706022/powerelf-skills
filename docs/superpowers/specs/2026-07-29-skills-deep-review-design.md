# 设计：Powerelf Skills 深度代码评审

- **日期**：2026-07-29
- **目标仓库**：`powerelf-skills` monorepo（权威源 `/home/scada/powerelf-skills`，主分支 `main`）
- **评审目标**：5 个主 skill（`powerelf-data-governance` / `-early-warning` / `-monitor` / `-inspection` / `-chatbi`）+ `_shared/` 共享层
- **明确不在范围**：4 个遗留 skill（`chatbi` / `monitor` / `early-warning` / `early-warning-v3`）、`darwin-skill`（独立上游）、`.github/workflows`、`.superpowers`、`skill-creator-workspace`
- **驱动**：用户请求"针对本项目的 skills 做深度代码评审"；与上一个 spec `2026-07-16-inspection-refactor-design.md` 的"对 inspection 深度代码评审 + 差距分析"做法同源
- **路线图位置**：本次评审只产出报告，不做修改；后续修复属于另一 spec + 计划

## 1. 背景与动机

仓库最近一周提交密集（20+ commits），尤其 `powerelf-data-governance` 三连修改（`5fce818` DDL 全量校准 / `44715ea` 补 Pitfalls 等 4 节 / `8c6f133` 修 scoring 文档不一致 + 裸 except + 补测试）。同时：

- 工作树有 **未提交改动**（`_shared/lib/db.py`、`_shared/references/schema.md`、`powerelf-data-governance/SKILL.md`）
- 工作树有 **30+ untracked 文件**：5 个 `_shared/st128*.py` + `report_128.py` / `report_anomalies.py` 调试脚本、6 份 `_shared/*.md` 验证报告、`powerelf-data-governance/SKILL_OPTIMIZATION_PLAN.md` 等、`powerelf-data-governance/references/` 整目录、`powerelf-data-governance/scripts/` 整目录、`powerelf-data-governance/tests/` 整目录、`darwin-skill/` 整目录
- 5 个主 skill 体量、风格、是否有 Python 实现差异极大：governance 16k LOC 含 48 py；early-warning / monitor 是 0.2-0.8k LOC 纯文档

需要一个**统一尺度的深度评审**，把发现归类、定位、可修复，为后续清理 / 修复 / 提交决策提供依据。

## 2. 目标与非目标

### 做
- 7 阶段执行：5 个 skill 逐个深审 → `_shared` 收尾 → 跨 skill 横向对比 + 总报告
- 4 维度检查：代码级（正确性+安全+测试） / 文档-代码一致性 / SQL Schema 准确性 / 架构跨 skill 一致性
- 产出 1 份总报告 + 6 份子报告，放 `reviews/` 目录（不污染 `_shared`）
- 显式盘点所有 untracked / modified 文件，给出"保留 / 移入 tests / 删除"处置建议
- 每个 finding 至少标注：严重度（Blocker/High/Med/Low）+ 维度 + 文件:行 + 描述 + 建议

### 不做
- 不修改任何被评审文件（只读评审；修复属于后续单独工作）
- 不跑实际数据库（SQL 只做静态分析 + 与 `schema.md` 对照）
- 不去碰 darwin-skill、4 个遗留 skill、`.github/workflows`、`.superpowers`、`skill-creator-workspace`
- 不写"修复"的实现计划（writing-plans 之后的事，且需用户单独发起）

## 3. 阶段与顺序

按 7 个阶段走，3 个 wave。顺序执行（非并行），保持上下文连贯 + 节省 token。

**Wave 1 — 5 个主 skill 深审**

| 阶段 | Skill | 体量 | 子报告 |
|------|-------|------|--------|
| 1.1 | `powerelf-data-governance` | 48 py / 35 md / 16k LOC | `reviews/review-powerelf-data-governance.md` |
| 1.2 | `powerelf-inspection` | 15 py / 30 md / 8k LOC | `reviews/review-powerelf-inspection.md` |
| 1.3 | `powerelf-early-warning` | 0 py / 11 md / 0.8k LOC | `reviews/review-powerelf-early-warning.md` |
| 1.4 | `powerelf-monitor` | 0 py / 11 md / 0.2k LOC | `reviews/review-powerelf-monitor.md` |
| 1.5 | `powerelf-chatbi` | 2 py / 7 md / 1.2k LOC | `reviews/review-powerelf-chatbi.md` |

每个阶段内部读取顺序：`SKILL.md` → `rules/*.md` → `algorithms/*.md` → `impl/*.py`（如有）→ `tests/` → `evolution/`。**阶段 1.1 显式盘点 untracked 文件**，区分"是有效产物"还是"调试残留"，并把"判断结论"带到后续 1.2-1.5 复用。

**Wave 2 — _shared 共享层**

| 阶段 | 内容 | 子报告 |
|------|------|--------|
| 2.1 | `lib/db.py`、`bootstrap.sh`、`api-auth.md` | `reviews/review-shared-lib.md` |
| 2.2 | `references/schema.md` vs Wave 1 各 skill 用到的 `st_*` 表交叉验证 | 同上 |
| 2.3 | `algorithms/`、`rules/` | 同上 |

**Wave 3 — 跨 skill 一致性 + 总报告**

| 阶段 | 内容 | 主报告 |
|------|------|--------|
| 3.1 | 横向对比：SKILL.md frontmatter / 目录结构 / 入口风格 / 路由表 / `_shared` 引用方式 | `reviews/REVIEW.md` |
| 3.2 | 汇总所有 finding，按严重度 + 维度 + 位置排序，输出正面发现 | 同上 |

## 4. 检查项（4 维度）

### 4.1 代码级：正确性+安全+测试
1. Python 语法 / 导入错误（`py_compile` 所有 `.py`）
2. 裸 `except:`、吞错
3. SQL 字符串拼接 / f-string 内插（注入面）
4. 明文密钥 / 硬编码 URL / IP / token
5. `--db` URL 解析、env var 注入面
6. 类型提示完整性
7. 死代码 / 未引用函数
8. 测试覆盖：每个 `algorithms/*.py` 和 `impl/*.py` 是否有对应 `tests/test_*.py`
9. untracked 的 `st128*.py` / `report*.py` 是不是调试残留

工具：`py_compile`、grep、ruff 启发式人工审视。

### 4.2 文档-代码一致性
1. SKILL.md 提到的"X 算法阈值 Y"在 `algorithms/X.py` 里数值是否一致
2. SKILL.md 列的"N 个规则"在 `rules/` 是否全有
3. 算法步骤描述与代码执行顺序是否对得上
4. "已实现 / 规划中"标记与代码实际状态
5. 跨 skill 引用（如 governance 引用 inspection）的链接是否 404
6. examples 段 SQL 能否真跑

工具：Read + grep 交叉。

### 4.3 SQL / Schema 准确性
1. SQL 中的表名、列名与 `schema.md` 是否一致
2. JOIN 字段是否在两边都有索引定义
3. 时间字段类型（DATETIME vs TIMESTAMP）一致
4. 占位符（`%s` vs `?`）一致（PyMySQL 用 `%s`）
5. 写操作 / 危险 SQL（DELETE/UPDATE/DROP）有无防护

工具：grep + 文本 diff。

### 4.4 架构 / 跨 skill 一致性
1. 5 个 SKILL.md 的 frontmatter / 元数据格式统一？
2. 5 个都有 `rules/` / `algorithms/` / `evolution/`？缺哪些？
3. "适用场景 / When NOT to Use / Related Skills" 路由表（README + 最近 commit 显示是新增约定）每个 skill 都有？
4. `_shared` 引用方式是 `../_shared/...` 还是绝对路径？统一吗？
5. 5 个 skill 都有 `SKILL.md` 入口（无重名）
6. README 列的"5 规则 + 3 算法"数量与实际 `rules/` `algorithms/` 目录文件数对得上

工具：结构 diff。

## 5. 报告结构

### 5.1 总报告 `reviews/REVIEW.md`

```
# Powerelf Skills 深度代码评审 — 2026-07-29

## 0. 元信息
## 1. 阻塞级发现 (Blocker)
## 2. 高优先级 (High)
## 3. 中优先级 (Medium)
## 4. 低优先级 (Low)
## 5. 横向发现 (跨 skill)
   5.1 命名 / 格式不一致
   5.2 _shared 引用方式
   5.3 README 与实际文件数偏差
   5.4 工作树 untracked 处置建议
## 6. 正面发现 (do well)
## 7. 详细子报告索引
```

### 5.2 Per-skill 子报告 `reviews/review-<skill>.md`

```
# <Skill> 评审 — 2026-07-29

## 0. 概览
## 1. Blockers
## 2. High
## 3. Medium
## 4. Low
## 5. 文档-代码一致性矩阵
## 6. SQL/Schema 用表
## 7. untracked 处置建议
## 8. 正面发现
```

## 6. 验收标准（Done Definition）

1. ✅ 5 个主 skill 都出了子报告，模板 8 节齐全
2. ✅ `_shared` 出了子报告，覆盖 `lib/` + `references/` + `algorithms/` + `rules/`
3. ✅ `REVIEW.md` 总报告存在，7 节齐全，finding 总数与子报告加总一致
4. ✅ 所有 finding 至少标注：严重度（Blocker/High/Med/Low）+ 维度 + 文件:行 + 描述 + 建议
5. ✅ 工作树所有 untracked / modified 文件都被显式盘点（"保留 / 移入 tests / 删除"三选一 + 理由）
6. ✅ 所有 4 维度在每个有代码的 skill 子报告里都至少出现 1 个 finding 或显式标注"无"
7. ✅ 未做：修改任何被评审文件（只读评审；修改属于后续"修复"阶段，由用户另行决定）

## 7. 报告产物

放 `reviews/`（仓库根下新目录，**默认不 commit**；评审结束后由用户决定是否 commit / 推分支 / 转 issue）：

- `reviews/REVIEW.md`
- `reviews/review-powerelf-data-governance.md`
- `reviews/review-powerelf-inspection.md`
- `reviews/review-powerelf-early-warning.md`
- `reviews/review-powerelf-monitor.md`
- `reviews/review-powerelf-chatbi.md`
- `reviews/review-shared-lib.md`

## 8. 不在范围

- 4 个遗留 skill：`chatbi/`、`monitor/`、`early-warning/`、`early-warning-v3/`
- `darwin-skill/`（独立上游，README 明确）
- `.github/workflows/`、`.superpowers/`、`skill-creator-workspace/`、`.claude/`、`docs/`
- 实际数据库执行 / 真实连接测试
- 任何代码或文档的修改

## 9. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 评审耗 token 多（33k LOC） | 顺序执行保持上下文；只读不修改；按需 grep 而不全读 |
| 评审过程发现需立即修的 blocker | 评审报告中**只列不改**；交由用户决定修复时机 |
| untracked 文件被误判为"删除" | 阶段 1.1 盘点时贴具体内容摘要 + 头几行，给用户否决窗口 |
| 跨 skill 引用造成"漏改" | 阶段 2.2 显式交叉验证 schema，阶段 3.1 显式横向对比 |
| 工作树改动造成评审与 HEAD 不一致 | 总报告 §0 显式记录评审版本（`git rev-parse HEAD` + working tree dirty 标记） |

## 10. 后续

评审完成后（不在本 spec 范围）：
- 用户决定：commit 报告 / 推分支 / 转 issue / 写"修复" spec
- 修复规模若大，单独开 spec 走 brainstorming → writing-plans → executing-plans
- 修复规模若小，直接 commit + PR
