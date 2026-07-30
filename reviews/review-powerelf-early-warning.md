# powerelf-early-warning 评审 — 2026-07-29

## 0. 概览

| 项 | 值 |
|---|---|
| Skill | `powerelf-early-warning` |
| 评审版本 | HEAD `ba9e971`（branch `review/2026-07-29-skills-deep`，working tree clean for `powerelf-early-warning/`） |
| 代码覆盖 | **0 py 文件**（纯文档 skill：1 SKILL.md + 5 rules/*.md + 3 strategies/*.md + 2 evolution/*.md = 11 md，~783 LOC） |
| 总 LOC | ~783（md only） |
| 评审日期 | 2026-07-29 |
| 评审人 | Claude (sub-agent, Task 3/6) |

**摘要**：`powerelf-early-warning` 是仓库中体量最小的 skill（0.8k LOC 纯文档），设计上"规则内嵌、按需加载、自我进化"三件套与 governance / monitor 同源。结构清晰（5 规则 + 3 策略 + 2 进化文件）、SQL 描述中规中矩、`ew_type` 表和参数注册表对齐良好。**主要问题集中在 SKILL.md 入口级路由表缺失**（与 monitor/inspection/chatbi 三个 skill 已在 `413a94c` / `cc4b90d` 之后补齐的"4 节路由表"约定不一致），导致 README 强调的"按需加载"机制在 early-warning 上是断裂的：Agent 没有显式的"何时用、何时不用"判定表，路由可能误命中"实时监控"或"巡检"。其余 finding 主要是文档内不一致（`ew_type` 枚举未覆盖趋势预警 / `silenceTime` 单位与 Redis TTL 自相矛盾 / `TOW` 拼写错误等），无 Blocker，无代码安全问题（无代码可评）。**强烈建议与 monitor/inspection/chatbi 对齐补 4 节路由表**（影响路由正确性，是 High 级问题）。

---

## 1. Blockers

**无 Blocker**（无 Python 代码可评，无 SQL 可评，无运行时可触发严重故障）。

---

## 2. High

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| High | 架构 | `SKILL.md` 全文（缺章节） | **SKILL.md 缺 4 节路由表**：与 `powerelf-monitor`（commit `413a94c` "加适用场景/When NOT to Use 路由表 + _shared 引用节"）、`powerelf-chatbi`（commit `cc4b90d`）、`powerelf-inspection`（已有）等同源 skill 一致的"**适用场景 / When NOT to Use / Related Skills / 共享引用(_shared)**" 4 节路由表，early-warning **完全没有**。当前 SKILL.md 只有"按需加载指令"（§按需加载指令，line 58-68）作为路由近似，且粒度过粗（只覆盖 8 个关键词组，没有"实时监控/数据治理/纯查询"的反向路由）。后果：(a) README 强调"按需加载、轻量入口"，但入口缺乏反向路由，Agent 拿到"今天水位正常吗？"会优先匹配"阈值预警"而非 monitor 的"实时监控"；(b) Related Skills 在 frontmatter 只列了 `powerelf-data-governance, powerelf-monitor`，但 SKILL.md 正文没显式 Related Skills 段，monitor 的"阈值/告警判定"明确指向 early-warning 形成路由闭环，反向 early-warning 没有"实时看盘"→monitor 的指针；(c) `_shared/api-auth.md` 只在末尾 API 附录 line 115 一笔带过，没有专门的"共享引用"段。 | 与 `powerelf-monitor/SKILL.md` 对齐补 4 节：1) "## 适用场景"列 5 大预警类型 + 视频 AI 报警 + 通知分发场景；2) "## When NOT to Use"表反向指 monitor（实时看盘）/ governance（数据质量）/ chatbi（纯查询）；3) "## Related Skills" 列出 monitor / governance / inspection / chatbi 四方关系；4) "## 共享引用（_shared）"段列出 `_shared/references/api-auth.md` 等。可参考 monitor/SKILL.md:20-39 模板。 |

---

## 3. Medium

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Medium | 文档-代码一致 | `SKILL.md:32-42` vs `rules/trend-rules.md` 全文 | **`ew_type` 枚举未覆盖趋势预警**。SKILL.md:32-42 表声明 `ew_type` 共 7 个值（0=水位/1=水质/2=雨量/3=开关变化/4=开关量/5=大坝安全/6=洪水），但 `rules/` 下 5 个规则文件中，threshold-rules(0/1/2/6)、state-change-rules(3)、switch-rules(4)、dam-rules(5) 都有对应 `ew_type`，**唯独 trend-rules（趋势预警）在 §ew_type 枚举 表中无对应行**。SKILL.md §能力概览 (line 52) 把 trend-rules 列为第 5 个规则模块，但 `ew_type` 落点悬空——后端在创建"趋势预警"规则时 `ew_type` 该填什么无文档依据，可能复用 0/1/2 中的一个造成"一条水位数据被两种规则同时跑"的歧义。 | 在 `ew_type` 枚举表追加 `7 \| 趋势预警 \| trend-rules (QS)`（或后端已分配的编号），并在 `rules/trend-rules.md` 顶部补一句"`ew_type = 7`"以闭合；否则需在 SKILL.md §能力概览 表格中明确"趋势预警复用阈值预警的 ew_type 0/1/2"。 |
| Medium | 文档-代码一致 | `strategies/silence-period.md:11` + `:21` | **`silenceTime` 单位与 Redis TTL 自相矛盾**。`:11` 明确声明 `silenceTime（单位：分钟）`；`:21` 写"通知发送完成后，写入 Redis Key，过期时间 = silenceTime"。**Redis TTL 是秒**，若 Agent 按文档直译会写入 30 秒过期的 key（"水位预警 沉默期 30 分钟" 实际只有 30 秒），沉默期机制完全失效，洪水期间同一水位预警会每 30 秒重发一次。SKILL.md §核心数据表 (line 28) `ew_notice_tactics` 字段定义为 `silence_time(min)`，即 `silenceTime` 确实是"分钟"——文档逻辑闭环里少了一次 `× 60` 转换。 | 改 `:21` 为 `Redis Key 过期时间 = silenceTime * 60`（单位：秒），并加一行伪代码强调换算。 |
| Medium | 架构 | `strategies/notification-strategy.md:28-29` | **SQL `find_in_set()` 锁定 MySQL**：策略匹配用 `find_in_set(#{level}, ewLevel)` 和 `find_in_set(#{ewRulesType}, ewRulesType)`，这是 MySQL 专属函数。schema.md 是 MySQL DDL 因此当前可用，但 `ewLevel` / `ewRulesType` 实际是逗号分隔字符串（"1,2,3"），**MySQL 5.7 的 `find_in_set` 不走索引会全表扫描**，如果 `ew_notice_tactics` 表行数 >1k 后策略匹配会变成性能瓶颈。跨 DB 抽象层缺失（governance/inspection 已经在用参数化 SQL + IN 列表风格，early-warning 仍走 MySQL 方言）。 | (a) 短期：在 `notification-strategy.md` 加注释说明"find_in_set 是 MySQL 方言，若切 PostgreSQL 需改为 `STRING_TO_ARRAY(ewLevel, ',') @> ARRAY[?]`"；(b) 长期：建议把 `ewLevel` / `ewRulesType` 拆为子表 `ew_notice_tactics_level`（`tactics_id`, `ew_level`），走标准 JOIN + 索引。 |

---

## 4. Low

| 严重度 | 维度 | 文件:行 | 描述 | 建议 |
|--------|------|---------|------|------|
| Low | 文档-代码一致 | `rules/threshold-rules.md:13` + `:31` | **`TOW` 拼写错误**：line 13 表中"10 种条件枚举"将 `>=` 命名为 `TOW`，line 31 又重复"TOW/FIVE 只使用 min"。正确拼写应为 `TWO`（数字 2 的英文）。文档中无任何代码可对照（无 py 文件），但若后端 Java 枚举名沿用文档为 `TOW`（typo 传染），调用方传 `condition="TWO"` 时会出现"枚举值不存在"运行时报错。 | 把 line 13 和 line 31 的 `TOW` 全部改为 `TWO`，并加一行"原后端枚举如为 TOW（typo），需同步重构以免破坏 API 兼容性"。 |
| Low | 文档-代码一致 | `rules/trend-rules.md:55-63` | **趋势预警无等级映射表，例子里"I 级"无解释**。trend-rules.md 只描述"连续 N 次 + 变化率 > 阈值 → 触发趋势预警"，但 **trend 自身的等级如何映射到 I/II/III/IV 不明确**。line 63 例子里直接写"触发趋势预警（I 级）"——I 级从哪来？line 32 表格中"水位连续上升可能表示洪水"按阈值预警规则洪水是 I 级，但 trend 文档没建立这套映射。Agent 落地时会把所有趋势预警都判为 I 级或所有都不分级。 | (a) 在 trend-rules.md 末尾加"## 趋势预警等级映射"表，按指标类型 + 变化率分档；(b) 或者在 evolution/parameters.md 增加 4 个"趋势等级阈值"参数（与现有"变化率阈值-水位"等并列）。 |
| Low | 文档-代码一致 | `rules/threshold-rules.md:46` + `rules/dam-rules.md:60` + `rules/trend-rules.md:1` | **"— 新增" 标记无版本/日期**。3 处都用"— 新增"标记新功能（动态等级调整 / 方向性分析 / 趋势预警），但**没有标注版本号或引入日期**。git log 显示这三个都是 `e60dd67` "初始化" 一次性提交时就在的，所以"新增"是相对仓库初始化而言还是相对某个 v1→v2 升级不明确。`evolution/feedback-log.md` 一直为空，参数表最后调整日期全为 `2026-05-30`，自演化机制无运行证据。 | (a) 把"— 新增"改为"— v2.0.0（2026-07-10）"显式打版本；(b) 在 evolution/feedback-log.md 加一条"v2.0.0 初始发布"占位记录，建立反馈循环起点。 |
| Low | 架构 | `SKILL.md:10` `metadata.hermes.tags` | **`metadata.hermes.tags` 缺 `dam` / `trend` / `video-ai` 标签**。description 字段实际长度 52 字符（实测：`水利工程预警系统：阈值预警、开关量预警、状态变化预警、大坝安全预警、趋势预警。规则引擎内嵌，可独立判断。`），整条均落在 57 字符路由窗口内（窗口 57 > 实际 52），5 类规则词（阈值/开关量/状态变化/大坝/趋势）全部命中。**但 tags 字段**（当前为 `[water-conservancy, early-warning, alarm, notification, threshold]`）**缺 `dam` / `trend` / `video-ai`**。对比 `powerelf-monitor/SKILL.md:10` tags 已含 `dam`——同源 skill 的路由标签一致性未对齐。若用户问"大坝位移异常"，`description` 包含"大坝"可兜底；但 hermes 若仅用 tags 匹配则会落到 monitor。 | 在 tags 中追加 `dam` / `trend` / `video-ai`（与 monitor 对齐），使 description + tags 形成"双通道"路由兜底。 |
| Low | 文档-代码一致 | `evolution/parameters.md:38` | **"规则缓存时间 86400秒" 与 §核心数据表无对应字段**。`ew_notice_tactics` 表字段定义（SKILL.md line 28）只有 `silence_time(min)` 没有"规则缓存时间"。"规则缓存时间 86400秒" 这条参数没有落地表，是漂在文档里的孤立配置。 | 要么删除该行（沉默期机制不需要独立缓存），要么在 SKILL.md §核心数据表 `ew_info_rules` 旁注明 `cache_ttl_sec` 字段。 |
| Low | 文档-代码一致 | `rules/state-change-rules.md:19` | **"原始实现使用 Redis 存储上次值，Agent 版本使用本地状态机"但未说明持久化与重启恢复**。若 Agent 进程重启，本地状态机的"上次值"丢失，所有测点会被判定为"首次触发"产生一次大规模误报。threshold/dam/switch 三种规则都无状态（每次重算），唯独 state-change 必须有持久化或明确"重启即重置"语义。 | 加一段"## 重启恢复策略"：要么持久化到 SQLite/JSON 文件，要么显式声明"重启后第一次采集不触发状态变化预警（首次建立基线）"。 |
| Low | 架构 | `SKILL.md:50-52` | **能力概览表把"视频 AI 报警"放在"通知分发"标题下但内容缺位**：line 30 `ew_camera_info` 是独立的核心数据表（视频 AI 报警），line 50-52 能力概览表的"通知分发"行只写"strategies/notification-strategy.md"未提视频 AI 报警。视频 AI 报警有自己的端点（`/earlywaring/camera-info/page`）和 `ew_type` 落点（未在 §ew_type 枚举列出），与"通知分发"完全不同的链路。 | 在能力概览表新增一行"视频 AI 报警 \| `strategies/camera-ai-alarm.md` \| 视频帧 AI 识别报警"，并补一个 strategies/camera-ai-alarm.md（当前不存在）。 |

---

## 5. 文档-代码一致性矩阵（声明 vs 实际）

| SKILL.md / README 声明 | 实际文件状态 | 一致? | 备注 |
|----------------------|-------------|-------|------|
| 5 规则模块 | `rules/` 目录下恰好 5 个 .md 文件（dam / state-change / switch / threshold / trend） | ✅ | 完全匹配 |
| 3 策略模块 | `strategies/` 目录下恰好 3 个 .md 文件（notification-strategy / silence-period / warning-shield） | ✅ | 完全匹配 |
| 自我进化：parameters.md + feedback-log.md | `evolution/` 目录 2 文件齐全 | ✅ | 但 feedback-log 空，无运行证据 |
| 核心数据表 7 张 | SKILL.md §核心数据表 列出 7 张（ew_info_rules, ew_info_rules_dam, ew_info_message, ew_notice_record, ew_notice_tactics, ew_notice_tactics_user, ew_camera_info） | ✅ | 完全匹配 |
| `ew_type` 枚举 7 个值（0-6） | rules/ 中 threshold(0/1/2/6) + state-change(3) + switch(4) + dam(5) 共 6 个映射，**trend 无对应** | ❌ | 见 Medium M1 |
| 5 规则 + 3 策略 = 8 子模块 | 能力概览表（SKILL.md:46-55）也列 8 行 | ✅ | 完全匹配 |
| 路由表 4 节（适用场景 / When NOT to Use / Related Skills / 共享引用 _shared） | **SKILL.md 完全没有这 4 节**；只有"按需加载指令"近似 Related Skills | ❌ | 见 High H1 |
| 动态等级（超标 10/30/60%） | threshold-rules.md 公式 + parameters.md 表完全一致 | ✅ | doc-doc 一致 |
| 趋势参数（连续 3-5 / 变化率 0.5-15%） | trend-rules.md 表 + parameters.md 表完全一致 | ✅ | doc-doc 一致 |
| 沉默期（15-120 分钟） | silence-period.md + parameters.md 一致 | ✅ | doc-doc 一致 |
| 屏蔽机制 + isIgnore + Redis Key | warning-shield.md 自洽 | ✅ | 单文件自洽 |
| `silenceTime` 单位 | 文档自相矛盾（声明分钟但 Redis TTL 直接用） | ❌ | 见 Medium M2 |
| `related_skills` 列出 governance + monitor | frontmatter:11 确实列了 2 个 | ⚠️ | 漏 inspection（inspection 业务闭环中"告警确认"环节会调 early-warning）和 chatbi（chatbi SQL 查询"哪些设备有告警"也走 early-warning） |
| 视频 AI 报警有独立端点 | API 附录列出 `/earlywaring/camera-info/page` 和 `/earlywaring/camera-info/confirm` | ✅ | 但能力概览表未列 video AI 报警模块（见 Low） |

---

## 6. SQL/Schema 用表

**SQL finding: 无**（无 Python 实现，无 .sql 文件，无 `--db` 直连入口；本 skill 全部走 REST API 通过 `_shared/api-auth.md` 鉴权）。

文档中提及的 SQL（仅 `strategies/notification-strategy.md:26-30` 策略匹配伪 SQL）：

| 文档中提及的表 | schema.md 存在? | 操作 | 占位符 | 备注 |
|---------------|----------------|------|--------|------|
| ew_notice_tactics | 需查 schema 确认（早 warning 表，未在 _shared/references/schema.md 共享层中，疑似业务专属） | SELECT | `#{level}`, `#{ewRulesType}` | 文档伪 SQL，仅作说明；实际由后端 Java/MyBatis 实现 |
| ew_notice_tactics_user | 同上 | 隐式 JOIN | — | 文档未提 JOIN，由后端实现 |
| ew_info_rules | 同上 | UPDATE (confirm) | — | 文档未列 SQL，由 API 附录承载 |
| ew_info_message | 同上 | UPDATE (confirm) | — | 同上 |
| ew_camera_info | 同上 | UPDATE (confirm) | — | 同上 |
| Redis Key: `EW_NOTICE_TACTICS_KEYS_SILENT:{tacticsId}` | 缓存层（不在 schema.md 范围） | SET / EXISTS / DEL | TTL=silenceTime | 见 Medium M2（单位矛盾） |
| Redis Key: `CLEAN_EW_RULES_KEYS_CONFIRM:{ruleId}` | 缓存层 | SET / EXISTS / DEL | TTL=剩余时长 | warning-shield.md 自洽 |

> **说明**：`_shared/references/schema.md` 是 `st_*` 监测表的单一事实源，**不覆盖 `ew_*` 业务表**。`ew_*` 表的 DDL 应当另有出处（可能是后端 Java 项目的 Flyway/Liquibase 迁移脚本，或另一个内部 wiki）。本评审按"无 SQL 可评"处理，但 Wave 2 `_shared` 评审可顺带查 schema.md 是否应当扩展覆盖 `ew_*` 表。

---

## 7. untracked 处置建议

`powerelf-early-warning/` 目录下 **0 untracked 文件、0 modified 文件**（`git status --short -- powerelf-early-warning/` 输出为空）。所有 11 个文件（1 SKILL.md + 5 rules + 3 strategies + 2 evolution）均已 tracked，最后一次提交为 `b314e1d docs(early-warning): notification-strategy 加 QA 闸姊妹指针`（2026-07-14 左右）。

**无需处置**。

---

## 8. 正面发现

1. **5 规则 + 3 策略目录结构与声明完全对齐**：README、SKILL.md §能力概览、实际 `rules/` 5 文件 + `strategies/` 3 文件三处一致，无虚标。命名清晰（YZ/KG/ZGB/DAM-YZ/QS 五种 Bean 名见各 rules/*.md 顶部"Bean名"标注，后端工程师可零成本对接）。
2. **阈值预警 10 种条件枚举设计完整**：threshold-rules.md 10 种条件（ZERO/ONE/TOW/THREE/FOUR/FIVE/SIX/SEVEN/EIGHT/NINE）覆盖 `=` / `!=` / `>=` / `<=` / 闭区间 / 开区间 / 半开区间等所有常见比较模式，预警描述模板（line 88-96）按条件生成不同措辞，避免"用一种模板套所有条件"的粗糙实现。
3. **动态等级调整设计精巧**：超标比例（10%/30%/60%）分档 + `max(配置等级, 动态等级)` 取更严重，parameters.md 给出"合理范围 5-15% / 20-40% / 50-80%"便于后续 A/B 调优。是 governance 评分引擎之外的"另一套自适应机制"。
4. **大坝预警多测点机制描述清晰**：dam-rules.md 显式说明"多测点之间是**或关系**、触发测点数量必须 >= triggerNumber"，解决了"10 个测点中 1 个异常该不该告警"的常见设计歧义。`evolution/parameters.md` 默认 `triggerNumber=3, range 1-10` 合理。
5. **沉默期 + 屏蔽双机制分工明确**：silence-period.md 末尾"与屏蔽的区别"表给出清晰对比（沉默期=自动到期/屏蔽=手动设置截止时间），两者互补不冲突，是工程上很干净的解耦。
6. **核心数据表 7 张列举完整且字段标注准确**：SKILL.md:22-30 列出 7 张 `ew_*` 表 + 关键字段 + 注释（如 `notice_type(1=短信/2=邮件/3=站内/4=声光/5=微信/6=钉钉)`），Agent 可直接据此理解业务模型。
7. **通知分发策略的 QA 闸姊妹指针**：notification-strategy.md:7-13 主动引用 `_shared/references/statistical-caution.md` 和 `analysis-qa-checklist.md`（commit `b314e1d` "加 QA 闸姊妹指针"），与 governance/inspection 共享的"过 QA 闸"约定一致，体现"按需加载 + 跨 skill 复用 _shared"的架构思想。
8. **趋势预警是 v2 的真正新意**：trend-rules.md 解决"缓慢但持续"异常的传统阈值盲区，且按指标（rz 渗压 渗流 GNSS）分档给出不同阈值（变化率 0.5%-15%），不是"一套参数走天下"，工程化程度高。
9. **与 _shared/api-auth.md 鉴权约定一致**：SKILL.md:115 显式指向 `_shared/api-auth.md` 共享鉴权头，与 monitor/chatbi 同源，没有各 skill 自定义鉴权。
10. **evolution/parameters.md 参数注册表结构整齐**：4 个分组（动态等级 / 趋势 / 沉默期 / 规则缓存 / 大坝）覆盖所有可调参数，"合理范围"列便于后续调参时知道安全边界。
