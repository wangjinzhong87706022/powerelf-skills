# Powerelf Skills 深度代码评审 — 综合主报告

- **评审日期**：2026-07-29 ~ 2026-07-30
- **评审版本**：HEAD `e99d2ed` → `b75ecce`（branch `review/2026-07-29-skills-deep`），working tree dirty（`_shared/lib/db.py`、`_shared/references/schema.md` 有未提交改动）
- **评审范围**：5 主 skill + `_shared/` 共享层
- **总 finding 数**：**91**（2 Blocker + 16 High + 38 Medium + 35 Low）
- **子报告数**：6 份（见 §7 索引）
- **评审人**：Claude（Task 1-6 子 agent + Task 7 opus 综合）

---

## §0 总览

### 0.1 Finding 分布矩阵

| Skill | Blocker | High | Medium | Low | 加权分 (B×4+H×3+M×2+L×1) |
|-------|:-------:|:----:|:------:|:---:|:-------------------------:|
| powerelf-data-governance | 0 | 4 | 10 | 8 | **40** |
| powerelf-inspection | 1 | 5 | 8 | 7 | **42** |
| powerelf-early-warning | 0 | 1 | 3 | 7 | **16** |
| powerelf-monitor | 0 | 1 | 4 | 5 | **16** |
| powerelf-chatbi | 0 | 3 | 8 | 5 | **30** |
| _shared | 1 | 2 | 5 | 3 | **23** |
| **合计** | **2** | **16** | **38** | **35** | **167** |

### 0.2 Per-Skill 质量评分（0-10）

| Skill | 评分 | 缺陷密度 (findings/kLOC) | 关键因素 |
|-------|:----:|:------------------------:|----------|
| powerelf-early-warning | **7.5** | 14.0 | 纯文档，0 代码风险；主要扣分：路由表完全缺失（H1） |
| powerelf-monitor | **7.0** | 42.6 | 纯文档，路由表最完整；扣分：frontmatter 不一致 + tags 覆盖不足 |
| powerelf-chatbi | **6.5** | 13.6 | 7 层安全护栏优秀；扣分：DoS/文件写出安全缺口 + JOIN 键错误 |
| powerelf-data-governance | **5.5** | 3.1 | 评分公式 doc-code 完美一致；扣分：测试覆盖 18% + SQL f-string 注入面 + 幽灵表名 |
| _shared | **5.5** | 3.6 | db.py 工程质量高；扣分：schema.md 铁律自相矛盾（B1）+ hook 死代码 |
| powerelf-inspection | **4.5** | 4.9 | lib/ 内核层质量高；**严重扣分**：Blocker 编译错误（整个引擎不可用）+ 裸 except + 质量评分分母错误 |

### 0.3 正面发现摘要

| 发现 | 涉及 skill |
|------|-----------|
| 评分公式 doc-code 完美一致 | governance（35%+10%+40%+15%）、inspection（30+25+25+20） |
| MAD 阈值 doc-code 完美一致 | governance、inspection |
| lib/ 纯函数内核 + 完整单测 | inspection（78 tests PASS） |
| 7 层 SQL 安全护栏 | chatbi（defense-in-depth 最佳实践） |
| 单一事实源模式成功落地 | _shared/algorithms/（monitor + inspection 薄指针） |
| schema.md 735 行覆盖 27+ 张表 | _shared（6 张主力表经 SHOW CREATE TABLE 校准） |
| db.py .env 自加载 + 端口防呆 + 只读护栏 | _shared（3 个有代码的 skill 共同基础） |
| routing 4 节齐全 | monitor（commit `413a94c` 建立的模板）、chatbi、inspection、governance |

---

## §1 系统性 Blocker（跨报告 Blocker 列表）

共 **2 个 Blocker**，分属不同 skill，但影响范围均为跨 skill。

### B-1: inspection_analyzer.py IndentationError — 整个 15 维度引擎不可用

- **来源**：[inspection §1](reviews/review-powerelf-inspection.md)
- **位置**：`powerelf-inspection/impl/inspection_analyzer.py:415-416`
- **描述**：第 415-416 行是第 413-414 行的残余重复片段（`"detail": "偏离历史分布"` + `})`），多 8 空格缩进。`py_compile` 直接报错。**整个 15 维度分析引擎无法导入、无法运行**，所有集成测试全部 skip。
- **跨 skill 影响**：inspection 是 governance 的下游消费者（governance 检测异常 → inspection 做复合分析），引擎不可用使整条链路断裂。
- **修复**：删除第 415-416 行（2 行残余代码）。

### B-2: schema.md 铁律与自身 4 张表 DDL 自相矛盾 — "唯一事实源"地位受损

- **来源**：[_shared §1 B1](reviews/review-shared.md) + [chatbi §3 M8](reviews/review-powerelf-chatbi.md)
- **位置**：`_shared/references/schema.md:17-36`（铁律）vs `:335-345`/`:349-358`/`:454-465`/`:469-477`（4 张表 DDL）
- **描述**：schema.md 铁律第 3 条声称"所有监测表都有 `eq_id`(BIGINT)"，但同文件 `rei_gate_r` / `rei_pump_r` / `st_soil_moisture_r` / `st_termite_monitor_r` 4 张表的 DDL 段完全缺少 `eq_id` / `eq_code` / `deleted` / `tenant_id` 框架列。`_shared/rules/gate-pump-status.md` 列出这些表有 `eq_id`/`eq_code`（与铁律一致），证明 DDL 段是旧版 SL323 简版未更新。
- **跨 skill 影响**：全部 5 个 skill 引用 schema.md。chatbi `few_shots.md` 3 个 JOIN 键错误（chatbi M1）的根因在此；inspection `read_sensor_data()` 查询这 4 张表时假设 `eq_id` 存在，DDL 不补 = 修复路径不可落地。
- **修复**：用 `SHOW CREATE TABLE` 校准 4 张表 DDL，补全框架列。

---

## §2 系统性 High（跨报告 High 列表，按根因去重）

共 **16 个 High**，去重后归为 **6 个根因类**（注：为呈现共性，部分类纳入相关 Medium / 实证观察，并非每行均为独立 High finding；各类标题已标注实际 High 计数）。

### 根因类 A: SQL 安全 defense-in-depth 缺口（4 个 High）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| chatbi | H1 | FORBIDDEN_KEYWORDS 遗漏 `SLEEP`/`BENCHMARK`（DoS 向量） |
| chatbi | H2 | FORBIDDEN_KEYWORDS 遗漏 `INTO OUTFILE`/`INTO DUMPFILE`（文件写出） |
| governance | H2 | lib/ SQL f-string 内插无运行时校验（impl/ 有白名单但 lib/ 没有） |
| inspection | H5 | `read_sensor_data()` 无标识符白名单校验 |

**共性**：5 个 skill 中 3 个有代码的 skill（governance / inspection / chatbi）都存在 SQL 消毒缺口。chatbi 的 7 层护栏最严密但仍有 4 个遗漏词；governance 和 inspection 的 lib/ 层缺乏与 impl/ 层同等级的白名单防护。

### 根因类 B: 查询缺失 `deleted=0` 过滤（2 个 High）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| governance | H1 | `lib/report.py:386` UNION ALL 无 `WHERE deleted=0`（日报测站数虚高） |
| inspection | H1 | `read_sensor_data()` 全量传感器查询缺失 `deleted=0`（9 个分析函数受影响） |

**共性**：schema.md 铁律第 2 条"必须 `WHERE deleted=0`"，但 2 个最大 skill 的核心查询函数都遗漏了。这是文档纪律与代码实践脱节的典型案例。（inspection H2 质量评分分母 bug 与 deleted=0 无关，已移至下方"额外 High"。）

### 根因类 C: `related_skills` frontmatter 不完整（3 个 High）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| monitor | H1 | frontmatter `related_skills` 缺 `powerelf-chatbi`（body "When NOT to Use" 有列 4 个，frontmatter 只列 3 个） |
| early-warning | §5 行 72 | frontmatter `related_skills` 只列 2 个（缺 inspection + chatbi） |
| inspection | frontmatter 实证 | frontmatter `related_skills` 列 3 个（缺 chatbi） |

**实证交叉验证**：

| Skill | frontmatter related_skills | 完整? |
|-------|---------------------------|:-----:|
| governance | `[early-warning, monitor, chatbi, inspection]` | ✅ 4/4 |
| chatbi | `[governance, monitor, inspection, early-warning]` | ✅ 4/4 |
| inspection | `[governance, early-warning, monitor]` | ❌ 3/4（缺 chatbi） |
| monitor | `[governance, early-warning, inspection]` | ❌ 3/4（缺 chatbi） |
| early-warning | `[governance, monitor]` | ❌ 2/4（缺 inspection + chatbi） |

**共性**：`powerelf-chatbi` 是最新加入的 skill，3 个旧 skill 的 frontmatter 都漏了它。hermes 路由在"依赖元数据"通道会错过 chatbi 指针。只有 governance 和 chatbi 自身形成了完整 4 元组闭环。

### 根因类 D: 测试覆盖严重不足（2 个 High）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| governance | H3 | lib/ 测试覆盖率 ~18%（5046 LOC 产线 vs 902 LOC 测试），report.py 884 LOC 无测试 |
| chatbi | M3 | L6(超时) / L7(只读事务) 0 个测试用例（22 个测试只覆盖 L1-L5） |

### 根因类 E: 代码/文档不一致导致功能错误（2 个 High）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| inspection | H3 | 3 处裸 `except:`（inspection_tool.py:355,444,460），commit `8c6f133` 已修 governance 但 inspection 遗漏 |
| inspection | H4 | GNSS 表名不一致（analyzer 用 `dsm_dfr_srvrds_srhrds`，registry 白名单用 `srm_gnss_data_day`） |

### 根因类 F: 路由表结构缺失（1 个 High）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| early-warning | H1 | SKILL.md 完全缺失 4 节路由表（适用场景/When NOT to Use/Related Skills/共享引用 _shared） |

**跨 skill 对比**：

| Skill | 4 节路由表 | 状态 |
|-------|:---------:|------|
| monitor | ✅ | commit `413a94c` 建立模板 |
| chatbi | ✅ | commit `cc4b90d` 对齐 |
| inspection | ✅ | 原有 |
| governance | ✅ | 原有（3 节 + 快速查找） |
| early-warning | ❌ | **完全缺失** |

### 额外 High（非跨报告系统性）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| inspection | H2 | 质量评分缺陷率分母用错（`real_checkobj` vs `real_objitem`，虚高 3-10 倍）——单 skill 代码逻辑 bug，非跨报告根因 |
| chatbi | H3 | L5 强制 LIMIT 只检测存在性、不检查上限值（`LIMIT 999999999` 可过） |
| _shared | H1 | `hooks/block_raw_pymysql.py` 87 行完善 hook 无 `.claude` 配置（死代码） |
| _shared | H2 | `rules/gate-pump-status.md` vs `schema.md` 列定义冲突（25+ 列 vs 8/13 列） |

---

## §3 系统性 Medium（按主题聚类）

共 **38 个 Medium**，归为 **7 个主题类**。

### 主题 1: "自我进化"机制形式化无运行证据（5+ skills 共性）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| monitor | M3 | feedback-log 空 + parameters.md 全 2026-05-30（61 天无调整） |
| early-warning | L3 | feedback-log 空 + parameters 全 2026-05-30 |
| chatbi | L1 | feedback-log 空 + parameters 全 2026-05-30（61 天） |
| inspection | L2(派生) | feedback-log 空 + parameters 全 2026-05-31/06-01 |
| governance | L2 | parameters 全 2026-05-30（60 天） |

**实证**：5 个 skill 的 `evolution/feedback-log.md` 全部为空（"暂无记录"），`parameters.md` 全部参数的"最后调整"日期停留在 2026-05-30 前后（距今 60+ 天）。README 和 SKILL.md 宣传的"自我进化"机制有完善的格式模板和流程设计，但 **0 次实际触发**。

**影响评估**：这是"机制设计 ≠ 机制运行"的典型 gap。当前不影响功能正确性，但长期会使参数漂移失修、反馈闭环断裂。

> **严重度校准注（终审发现）**：同一系统性问题在 5 skill 中严重度不一致——仅 **monitor M3 标 Medium**，其余 4 skill（early-warning L3 / chatbi L1 / inspection L2 / governance L2）均为 **Low**。monitor 自身的定级理由"小 skill 影响面相对小"方向反了（影响面小应指向 Low，而非 Medium），且 monitor 报告正文已显式引用"对比 early-warning sub-report L3（同样问题）"——即 monitor 自己也认其为 Low 级问题。鉴于"0 触发、无功能影响"，**建议修复时将 monitor M3 对齐降为 L3**（计数随之 4M/5L → 3M/6L，总数 10 不变），使 5 skill 严重度统一为 Low。本表暂保留 monitor M3 原定级以不动已复核的计数，仅在此标注分歧。

### 主题 2: schema.md 不一致的级联传播（4-5 个 finding 链）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| _shared | B1 | 4 张表 DDL 缺框架列（与铁律矛盾） |
| _shared | H2 | rules/gate-pump-status.md vs schema.md 列定义冲突 |
| _shared | M2 | data-profiling.md 白名单含 11 张幽灵表名 |
| chatbi | M8 | 4 张表 DDL 不完整阻塞 few_shots JOIN 键修复 |
| chatbi | M1 | 3 个 few_shots 示例 JOIN 键与 schema.md 铁律矛盾 |
| governance | H4 | ALLOWED_TABLES 含 10 个幽灵表名 |

**级联链**：schema.md B1（铁律 ↔ DDL 矛盾）→ chatbi M8（DDL 不补 = 修复不可落地）→ chatbi M1（few_shots JOIN 键错误传播给 agent）。同一根因在不同层产生不同症状。

### 主题 3: `metadata.hermes.tags` 覆盖不足（4 个 skill）

| 子报告 | Finding | 缺漏 |
|--------|---------|------|
| monitor | M4 | 缺 `rainfall`/`gate-pump`/`trend`/`forecast`（5/8 类别未覆盖） |
| early-warning | L4 | 缺 `dam`/`trend`/`video-ai` |
| chatbi | L5 | description 缺 `knowledge-base`/`data-analysis` |
| inspection | L3 | description 含"实时监测"造成路由误导 |

**共性**：tags 与 description 应形成"双通道兜底"——description 抓主类（≤57 字符窗口），tags 补子类。当前 4 个 skill 的 tags 都有缺漏，hermes 纯 tags 匹配时会落空。

### 主题 4: SQL 占位符/方言混用（3 个 skill）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| governance | M5 | impl/ 用 `:param`（SQLAlchemy），lib/ 用 `%s`（PyMySQL），跨模块不一致 |
| early-warning | M3 | `find_in_set()` 锁定 MySQL，无跨 DB 抽象 |
| inspection | M5 | `predict_defect_trend()` 用 raw string 而非 `text()` 包装 |

### 主题 5: 文档声称 vs 代码实现脱节（多个 skill）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| governance | M1 | SKILL.md "禁止 conn.execute" vs lib/ 全程 raw pymysql |
| governance | M3 | algorithms/ 2 份文档（孤立森林/DBSCAN/Kriging）全仓库无实现，未标"规划中" |
| inspection | M4 | 趋势阈值 doc-code 严重不一致（规则文档 ≥12 次 vs 代码 ≥6 次） |
| inspection | M6 | analyze_percolation() 内联 MAD 而非委托 lib/anomaly.mad_anomaly() |
| inspection | M7 | lib/ 5 层异常判定框架在 impl/ 中从未被调用（"死代码"） |
| early-warning | M1 | `ew_type` 枚举未覆盖趋势预警（trend-rules 无对应 ew_type） |

### 主题 6: untracked 文件 / 工程卫生

| 子报告 | Finding | 描述 |
|--------|---------|------|
| governance | M6 | references/ 全目录（13 文件）untracked，SKILL.md 引用的链接全部 404 |
| governance | M7 | scripts/classify_offline_by_duration.py untracked（SKILL.md 核心入口） |
| _shared | §7 | 15 文件 + 1 目录 untracked（1 A + 7 B + 8 C 分类） |

### 主题 7: 其他 Medium（单 skill 内部）

| 子报告 | Finding | 描述 |
|--------|---------|------|
| governance | M4 | rei_gate_r/rei_pump_r 的 st_id 语义不确定，UNION ALL COUNT 可能错误 |
| governance | M8 | overview.py 入口无白名单校验 |
| governance | M9 | report.py f-string 直接 execute() 无注释标注安全 |
| governance | M10 | offline_detector.py 阈值 key 不匹配（st_type vs 表名），假离线告警 6 倍 |
| inspection | M3 | inspection_tool.py 复制了 registry.py 全部函数（150 行重复） |
| inspection | M8 | predict_defect_trend() 用 sklearn 而非 lib/defect_predict.linear_trend() |
| early-warning | M2 | silenceTime 单位与 Redis TTL 自相矛盾（分钟 vs 秒，缺 ×60） |
| chatbi | M2 | GNSS point_id 占位符类型错误（varchar vs INT） |
| chatbi | M4 | LIMIT 检测正则在字符串字面量/注释中假阳性 |
| chatbi | M5 | ew_camera_info 表不在 schema.md 中 |
| chatbi | M6 | eq_equip_offline_record 列名与 schema 摘要不一致 |
| chatbi | M7 | L4 系统库黑名单被反引号绕过 |
| _shared | M1 | db.py get_sqlalchemy_url 密码明文嵌入 URL |
| _shared | M3 | _shared/ 缺少版本追踪机制 |
| _shared | M4 | bootstrap.py 使用 Python 3.10+ 语法（不兼容 3.9） |
| _shared | M5 | api-auth.md tenant-id 硬编码为 1 |

---

## §4 单 skill 内部问题（集中度分析）

### governance — 问题集中在 lib/ 层

governance 是仓库最大的 skill（~7k LOC Python），finding 主要分布在：
- **lib/ 测试覆盖**（H3）：8/17 模块无测试，5046 LOC 产线 vs 902 LOC 测试
- **lib/ SQL 安全**（H2）：lib/ 缺乏 impl/ 同等级白名单
- **lib/ 文档矛盾**（M1）：SKILL.md "禁止 conn.execute" vs lib/ 全程 raw pymysql
- **untracked 文件**（M6/M7）：references/ + scripts/ 未 commit

**正面**：impl/ 层质量好（白名单防护、评分公式完美一致、MAD 阈值一致、py_compile 全过）。

### inspection — 问题集中在 impl/ 引擎层

inspection 是第二大 skill（~4.3k LOC Python），架构分 lib/（纯函数内核）+ impl/（引擎层）：
- **impl/ 编译错误**（B-1）：整个引擎不可用
- **impl/ 查询缺陷**（H1/H2）：deleted=0 遗漏 + 质量评分分母错误
- **impl/ 裸 except**（H3）：3 处
- **impl/ 重复代码**（M3）：150 行从 registry.py 完整复制
- **lib/ 框架未消费**（M7）：5 层异常判定只有 2 层被 impl/ 使用

**正面**：lib/ 内核层是仓库质量最高的代码（纯函数、类型提示齐全、78 单测 PASS）。

### early-warning — 问题集中在路由层

early-warning 是最小的 skill 之一（0.8k LOC 纯文档）：
- **路由表缺失**（H1）：4 节路由表完全没有，是唯一的 High
- **文档内不一致**（M1/M2）：ew_type 枚举缺口 + silenceTime 单位矛盾
- **tags 覆盖不足**（L4）：缺 3 个标签

**正面**：5 规则 + 3 策略结构完善，阈值设计精巧（动态等级、多测点或关系、沉默期+屏蔽双机制）。

### monitor — 问题集中在 frontmatter 一致性

monitor 是最小的 skill（0.2k LOC 纯文档）：
- **frontmatter ↔ body 不一致**（H1）：related_skills 缺 chatbi
- **"12 类" vs 14 行**（M1）：doc-doc 不一致
- **tags 覆盖不足**（M4）：5/8 类别未覆盖

**正面**：routing 4 节最齐全、monitor↔inspection 分工段最干净、schema 字段标注准确。

### chatbi — 问题集中在安全层和文档层

chatbi 代码密度最高（344 行 Python）：
- **安全缺口**（H1/H2/H3）：黑名单遗漏 4 个关键词 + LIMIT 无上限检查
- **JOIN 键错误**（M1）：3 个 few_shots 示例 JOIN 键错
- **测试盲区**（M3）：L6/L7 零测试

**正面**：7 层护栏架构最佳实践、related_skills 完整 4 元组、22 个测试覆盖 L1-L5。

---

## §5 跨报告关联矩阵

下表标记每个跨报告系统性问题的涉及 skill（● = 直接 finding，○ = 间接受影响，· = 不受影响）：

> **行数说明**：本矩阵共 **14 行** = **11 个跨报告系统性模式**（4 个 High 根因类 A/B/C/D + 5 个 Medium 主题 1/2/3/4/6 + 2 个本次新发现 version-footer / hook 死代码）+ **2 个 Blocker 条目**（B-1 inspection 编译错误、B-2 schema 铁律矛盾）+ **1 个仅单 skill 的 High**（F early-warning 路由表缺失，为纵览完整一并列入）。§0/§8.1 所称"11 个跨报告系统性模式"即前 11 行。

| 系统性问题 | governance | inspection | early-warning | monitor | chatbi | _shared |
|-----------|:----------:|:----------:|:-------------:|:-------:|:------:|:-------:|
| B-2: schema.md 铁律自相矛盾 | ○ | ○ | · | · | ● | ● |
| B-1: inspection_analyzer 编译错误 | ○ | ● | · | · | · | · |
| A: SQL 安全 defense-in-depth 缺口 | ● | ● | · | · | ● | · |
| B: deleted=0 过滤遗漏 | ● | ● | · | · | · | · |
| C: related_skills frontmatter 不完整 | · | ● | ● | ● | · | · |
| D: 测试覆盖不足 | ● | · | · | · | ● | · |
| F: 4 节路由表缺失 | · | · | ● | · | · | · |
| 主题 1: feedback-log 全空 | ● | ● | ● | ● | ● | · |
| 主题 2: schema 不一致级联 | ● | · | · | · | ● | ● |
| 主题 3: tags 覆盖不足 | · | ● | ● | ● | ● | · |
| 主题 4: SQL 方言混用 | ● | ● | ● | · | · | · |
| 主题 6: untracked 文件 | ● | · | · | · | · | ● |
| 额外: version/date footer 缺失 | ● | ● | ● | ● | ● | · |
| 额外: hook 死代码 | ○ | ○ | ○ | ○ | ○ | ● |

**关键观察**：

1. **feedback-log 全空**是唯一一个覆盖全部 5 个主 skill 的系统性问题（100% 覆盖率）。
2. **schema.md 铁律矛盾**虽只 _shared 和 chatbi 直接报出 finding，但 governance + inspection 作为 schema.md 的重度消费者间接受影响（agent 生成 SQL 时参考的 DDL 可能不准）。
3. **related_skills 不完整**影响 3/5 skill，缺漏目标一致（`powerelf-chatbi`），说明 chatbi 加入后旧 skill 未同步更新。
4. **tags 覆盖不足**影响 4/5 skill，只有 governance 的 tags 相对完整（10 个标签覆盖核心能力）。
5. **version/date footer 缺失**是本次综合分析新发现的第 10 个跨报告模式——5/5 skill 的 SKILL.md 末尾均无版本号或最后更新日期（详见 §6）。

---

## §6 全局一致性矩阵

### 6.1 routing table（4 节约定）

| Skill | 适用场景 | When NOT to Use | Related Skills | 共享引用(_shared) | 完整? |
|-------|:-------:|:---------------:|:--------------:|:-----------------:|:-----:|
| governance | ✅ | ✅ | ✅ | ✅(via references/) | ✅ |
| inspection | ✅ | ✅ | ✅ | ✅ | ✅ |
| early-warning | ❌ | ❌ | ❌ | ❌ | **❌** |
| monitor | ✅ | ✅ | ✅ | ✅ | ✅ |
| chatbi | ✅ | ✅ | ✅ | ✅ | ✅ |

**结论**：4/5 skill 已对齐 4 节路由表约定，**early-warning 是唯一完全缺失的**。

### 6.2 frontmatter tags 完整性

| Skill | tags 数量 | 核心能力覆盖 | 缺漏 |
|-------|:---------:|:-----------:|------|
| governance | 10 | ✅ 全面 | — |
| inspection | 4 | ⚠️ 部分 | 缺 quality-assessment/defect-prediction/route-optimization |
| early-warning | 5 | ⚠️ 部分 | 缺 dam/trend/video-ai |
| monitor | 6 | ⚠️ 部分 | 缺 rainfall/gate-pump/trend/forecast |
| chatbi | 5 | ⚠️ 部分 | description 缺 knowledge-base/data-analysis |

### 6.3 frontmatter related_skills 闭环

| Skill → 列出 | gov | insp | ew | mon | chatbi | 完整? |
|-------------|:---:|:----:|:--:|:---:|:------:|:-----:|
| governance | — | ✅ | ✅ | ✅ | ✅ | ✅ 4/4 |
| inspection | ✅ | — | ✅ | ✅ | ❌ | ❌ 3/4 |
| early-warning | ✅ | ❌ | — | ✅ | ❌ | ❌ 2/4 |
| monitor | ✅ | ✅ | ✅ | — | ❌ | ❌ 3/4 |
| chatbi | ✅ | ✅ | ✅ | ✅ | — | ✅ 4/4 |

**闭环缺口**：chatbi 被 3 个 skill 遗漏（inspection / early-warning / monitor）。governance 和 chatbi 是唯一形成完整 4 元组的。

### 6.4 evolution/feedback-log.md 状态

| Skill | 文件存在? | 有记录? | parameters 最后调整 | 距今天数 |
|-------|:--------:|:------:|:------------------:|:-------:|
| governance | ✅ | ❌ 空 | 2026-05-30 | 61 |
| inspection | ✅ | ❌ 空 | 2026-05-31 | 60 |
| early-warning | ✅ | ❌ 空 | 2026-05-30 | 61 |
| monitor | ✅ | ❌ 空 | 2026-05-30 | 61 |
| chatbi | ✅ | ❌ 空 | 2026-05-30 | 61 |

**结论**：**5/5 skill 的"自我进化"机制全部 0 触发**。格式模板完善、流程设计合理，但无任何运行证据。这是全仓库最普遍的 systemic gap。

### 6.5 SKILL.md version/date footer

| Skill | 末尾有 version? | 末尾有日期? |
|-------|:--------------:|:----------:|
| governance | ❌ | ❌ |
| inspection | ❌ | ❌ |
| early-warning | ❌ | ❌ |
| monitor | ❌ | ❌ |
| chatbi | ❌ | ❌ |

**结论**：**5/5 skill 的 SKILL.md 末尾均无版本号或最后更新日期**。frontmatter 有 `version: 2.0.0` 但文档尾部无对应印证。这是本次综合分析新发现的跨报告模式（未在 brief Step 3 的 9 个模式中列出）。

### 6.6 `_shared` 引用方式一致性

| Skill | 引用方式 | 统一? |
|-------|---------|:-----:|
| governance | `../_shared/...`（相对路径）+ lib/db.py shim（importlib 动态加载） | ✅ |
| inspection | `../_shared/...`（相对路径）+ lib/db.py shim | ✅ |
| early-warning | `../_shared/api-auth.md`（相对路径，仅 1 处） | ✅ |
| monitor | `../_shared/...`（相对路径，rules/ + algorithms/） | ✅ |
| chatbi | `../_shared/...`（相对路径）+ impl 中 from db import | ✅ |

**结论**：引用方式统一为相对路径，无绝对路径混用。✅

---

## §7 修复优先级

### P0 — 立即修复（影响功能正确性或跨 skill 系统性 High）

| # | Finding | 来源 | 工作量 | 影响面 |
|---|---------|------|:------:|--------|
| P0-1 | inspection_analyzer.py:415-416 IndentationError | inspection B-1 | **2 行删除** | 整个 15 维度引擎恢复可用 |
| P0-2 | schema.md 4 张表 DDL 补全框架列 | _shared B-2 + chatbi M8 | `SHOW CREATE TABLE` × 4 | 解锁 chatbi M1 + inspection H1 修复路径 |
| P0-3 | chatbi FORBIDDEN_KEYWORDS 加 4 个词 | chatbi H1+H2 | **4 行追加** | 堵住 DoS + 文件写出缺口 |
| P0-4 | early-warning SKILL.md 补 4 节路由表 | early-warning H1 | 参考 monitor 模板 | hermes 路由正确性 |
| P0-5 | related_skills frontmatter 补齐 chatbi | monitor H1 + inspection + early-warning | **3 个 SKILL.md 各加 1 词** | hermes 元数据路由闭环 |
| P0-6 | hooks/block_raw_pymysql.py 配置 + 入 git | _shared H1 | settings.json + git add | 5 个 skill 统一启用 pymysql 防护 |

**P0 总工作量估计**：~2 小时（含 SHOW CREATE TABLE 实测 + 文档编辑 + settings.json 配置）

### P1 — 本周修复（单 skill High + 高频触发 Medium）

| # | Finding | 来源 | 工作量 |
|---|---------|------|:------:|
| P1-1 | read_sensor_data() 加 deleted=0 | inspection H1 | 1 行 |
| P1-2 | 质量评分分母 real_checkobj → real_objitem | inspection H2 | 2 行 |
| P1-3 | inspection_tool.py 3 处裸 except | inspection H3 | 3 行 |
| P1-4 | GNSS 表名统一为 dsm_dfr_srvrds_srhrds | inspection H4 | 白名单更新 |
| P1-5 | read_sensor_data() 加白名单校验 | inspection H5 | 复用 registry.py |
| P1-6 | lib/report.py UNION ALL 加 deleted=0 | governance H1 | 1 行 |
| P1-7 | lib/ SQL 白名单校验 | governance H2 | 函数入口守卫 |
| P1-8 | chatbi L5 LIMIT 数值上限检查 | chatbi H3(代码层) | 正则提取 + 替换 |
| P1-9 | few_shots #13/#14/#15 JOIN 键修正 | chatbi M1 | 3 处 SQL 修改 |
| P1-10 | chatbi L4 反引号绕过修复 | chatbi M7 | 1 行 regex |
| P1-11 | chatbi L6/L7 补 mock 测试 | chatbi M3 | 2 个测试用例 |
| P1-12 | references/ + scripts/ git add | governance M6+M7 | git add + commit |
| P1-13 | ALLOWED_TABLES 删除 10 个幽灵表名 | governance H4 | 白名单清理 |

### P2 — 本月修复（其余 Medium）

| # | 主题 | 涉及 finding | 工作量 |
|---|------|-------------|:------:|
| P2-1 | tags 覆盖补齐（4 个 skill） | monitor M4 + early-warning L4 + chatbi L5 + inspection L3 | 各加 2-4 个 tag |
| P2-2 | feedback-log 加初始占位记录（5 个 skill） | 主题 1（§3） | 每个 1 行 |
| P2-3 | parameters.md 增加"触发来源"列 | 主题 1（§3） | 表头修改 |
| P2-4 | silenceTime × 60 单位修正 | early-warning M2 | 1 行 + 伪代码 |
| P2-5 | ew_type 枚举补趋势预警行 | early-warning M1 | 表追加 1 行 |
| P2-6 | SKILL.md "禁止 conn.execute" 与 lib/ 实际对齐 | governance M1 | 文档修订 |
| P2-7 | algorithms/ 未实现文档标"规划中" | governance M3 | 2 个文件加标注 |
| P2-8 | 趋势阈值三方统一（rules/SKILL.md/code） | inspection M4 | 三方对齐 |
| P2-9 | lib/anomaly.py 5 层框架标"roadmap"或让 impl/ 消费 | inspection M7 | 文档标注 |
| P2-10 | inspection_tool.py 删除 registry.py 重复代码 | inspection M3 | 删 150 行 |
| P2-11 | analyze_percolation() 改调 lib/anomaly.mad_anomaly() | inspection M6 | 函数调用替换 |
| P2-12 | monitor "12 类" → "14 类" | monitor M1 | 数字修改 |
| P2-13 | monitor 共享引用段补 reservoir | monitor M2 | 1 行 |
| P2-14 | untracked 文件统一处置（7 删除 + 7 归档） | _shared §7 | 脚本清理 |
| P2-15 | data-profiling.md 白名单对齐实际表名 | _shared M2 | 表名更新 |
| P2-16 | SKILL.md 末尾加 version/date footer（5 个 skill） | 额外模式 | 各加 1 行 |

### P3 — 待评估（Low + nice-to-have）

| # | 主题 | 涉及 finding 数 |
|---|------|:--------------:|
| P3-1 | description 前 57 字符路由词优化 | 5（每 skill 1 个） |
| P3-2 | evolution/parameters.md 增加时序预测参数 | 2 |
| P3-3 | __pycache__ 确认 .gitignore 覆盖 | 2 |
| P3-4 | tenant_id 硬编码说明 | 2 |
| P3-5 | 占位符风格文档说明 | 2 |
| P3-6 | 其他文档微调（TOW→TWO / 视频AI行 / 重启恢复 / 库容校准等） | ~21 |

**优先级统计**：

| 级别 | finding 数 | 占比 | 估计工时 |
|------|:---------:|:----:|:-------:|
| P0 | 6 项（覆盖 12+ findings） | — | ~2 小时 |
| P1 | 13 项 | — | ~1 天 |
| P2 | 16 项 | — | ~3-5 天 |
| P3 | ~30 项 | — | 按需 |

---

## §8 综合建议

### 8.1 Executive Summary

本次评审覆盖 5 个主 skill + `_shared/` 共享层，共发现 **91 个问题**（2 Blocker + 16 High + 38 Medium + 35 Low），识别出 **11 个跨报告系统性模式**。

**仓库整体健康度**：架构设计良好（单一事实源、7 层护栏、纯函数内核），但 **实现与文档之间存在系统性脱节**。核心矛盾是：文档层面声称的纪律（deleted=0 铁律、禁止 raw pymysql、铁律框架列）在代码层面未被严格执行；同时"自我进化"机制虽有完善的格式模板，但 0 次实际触发。

**最高风险**：
1. **inspection 引擎完全不可用**（B-1）：2 行残余代码导致 15 维度分析引擎无法运行。修复最简单（删 2 行），影响最大（恢复整个巡检功能）。
2. **schema.md 铁律自相矛盾**（B-2）：作为 5 个 skill 的"唯一事实源"，其内部不一致会级联传播到所有下游 SQL 生成和 JOIN 逻辑。

**最大亮点**：
1. inspection 的 lib/ 内核层（纯函数 + 78 单测 + 类型提示齐全）
2. chatbi 的 7 层安全护栏（defense-in-depth 最佳实践）
3. _shared 的单一事实源模式（algorithms/ 已成功消除跨 skill 重复）
4. governance 的评分公式 doc-code 完美一致

### 8.2 建议用户后续动作

1. **立即**（P0，~2 小时）：
   - 删除 inspection_analyzer.py:415-416（恢复引擎）
   - `SHOW CREATE TABLE` 校准 4 张表 DDL（解锁 JOIN 键修复）
   - chatbi FORBIDDEN_KEYWORDS 加 4 个词
   - early-warning 补 4 节路由表
   - 3 个 skill 的 related_skills 加 chatbi
   - hooks/ 入 git + 配置 settings.json

2. **本周**（P1，~1 天）：
   - inspection/governance 的 deleted=0 修复
   - inspection 裸 except + GNSS 表名统一
   - chatbi LIMIT 上限检查 + 反引号修复 + 补测试
   - governance references/ + scripts/ 入 git
   - ALLOWED_TABLES 幽灵表名清理

3. **本月**（P2，~3-5 天）：
   - 5 个 skill 的 tags 覆盖补齐
   - 5 个 skill 的 feedback-log 初始占位记录
   - 文档-代码不一致批量修复（silenceTime / ew_type / 趋势阈值 / 禁止 conn.execute）
   - untracked 文件清理（7 删除 + 7 归档）
   - 5 个 skill 的 SKILL.md 末尾加 version/date footer

4. **转 issue 跟踪**：
   - "自我进化"机制激活（需要产品级决策：是否引入自动调优触发点）
   - lib/ 测试覆盖率提升（需要排期 + 预算）
   - SQL 占位符/方言统一（需要架构决策：统一为 SQLAlchemy 还是 PyMySQL）

### 8.3 子报告索引

| # | 子报告 | Findings | 路径 |
|---|--------|:--------:|------|
| 1 | governance | 22 (0B/4H/10M/8L) | `reviews/review-powerelf-data-governance.md` |
| 2 | inspection | 21 (1B/5H/8M/7L) | `reviews/review-powerelf-inspection.md` |
| 3 | early-warning | 11 (0B/1H/3M/7L) | `reviews/review-powerelf-early-warning.md` |
| 4 | monitor | 10 (0B/1H/4M/5L) | `reviews/review-powerelf-monitor.md` |
| 5 | chatbi | 16 (0B/3H/8M/5L) | `reviews/review-powerelf-chatbi.md` |
| 6 | _shared | 11 (1B/2H/5M/3L) | `reviews/review-shared.md` |
