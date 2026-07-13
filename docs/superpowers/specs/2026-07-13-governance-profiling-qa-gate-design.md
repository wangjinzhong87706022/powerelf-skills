# 设计：治理域 数据画像（explore-data）+ 报告交付前 QA 闸（validate-data）

- **日期**：2026-07-13
- **目标仓库**：`powerelf-skills` monorepo（权威源 `/home/scada/powerelf-skills`）
- **主受影响 skill**：`powerelf-data-governance`
- **次受影响 skill**：`powerelf-early-warning`（仅引用 QA 闸文档）
- **来源**：复用 `knowledge-work-plugins/data` 中 `explore-data`（数据画像）与 `validate-data`（交付前 QA 闸）skill 的方法论
- **路线图位置**：外部通用数据技能 → powerelf 复用路线图 **A 簇（治理域）**，A→B→C 三簇之首；承接 `2026-07-10-outlier-methods-design.md` §9 的后续建议

## 1. 背景与动机

`2026-07-10-outlier-methods-design.md` §9 明确建议"评估把 explore-data（数据画像）、validate-data（报告
QA 闸）作为独立 spec 推进"。本 spec 落实该建议，并作为复用路线图首簇（A 簇：治理域）。两块各补一个
data-governance 现有短板：

- **数据画像**：当前遇到新表/新测点时 Agent 靠手写 SQL 摸结构，缺"首次遇表先画像、得到完整性
  tier/分布/红旗，再决定怎么检测"这一前置环节。
- **交付前 QA 闸**：报告（`generate_report.py`）产出后直接交付，缺"数字和逻辑站不站得住"的最后一道
  审——典型如"水位异常率 55%"（分母被离线设备放大）、指标定义前后不一致、插值结果未标置信度等无人把关。

形态沿用 outlier-methods spec 确立的约定：**方法论文档进 `_shared/`、可运行代码进 skill、判断类护栏
为纯被动文档**。

## 2. 范围

### 做
- `_shared/references/` 增 `data-profiling.md`（画像方法论 + 质量评估框架，水利化）。
- `_shared/references/` 增 `analysis-qa-checklist.md`（交付前 QA 闸 + 三级置信度，水利化）。
- `powerelf-data-governance/lib/` 增 `profiling.py`（纯函数画像库）。
- `powerelf-data-governance/impl/` 增 `profiler.py`（CLI，输出 JSON profile）。
- 接线：`SKILL.md` 加触发词、`report.py` 加 QA 自检节 + 置信度 tier、`quality-scoring.md` 交叉链
  画像 tier、early-warning `notification-strategy.md` 加 QA 闸姊妹链。

### 不做（YAGNI）
- ❌ 把 `profiling.py` 放进 `_shared/lib/`（维持"文档进 _shared、代码进各 skill"约定；待 inspection
  也要用时再升）。
- ❌ 自动 QA 评分器 `impl/qa_check.py`（方案③，QA 是判断题，自动打分易假精度，与
  statistical-caution.md 既有定位冲突）。
- ❌ 把 statistical-analysis 剩余未吸收部分（假设检验等）纳入本 spec（statistical-analysis 状态为
  ✅ 已实施，不扩范围）。
- ❌ 代码级强制 QA（被动文档 + Agent 自判，与既有护栏一致）。
- ❌ 改 `writeback.py` 或检测主逻辑（只在报告环节前置 QA 审、在检测环节前置画像）。

## 3. 文件变更清单

### 新建
| 路径 | 内容 |
|------|------|
| `_shared/references/data-profiling.md` | 列 6 分类（水利映射）、分类型 profile 清单、质量评估框架（完整性4级/一致性/准确性红旗/及时性）、6 类分布 + SCADA 特例（雨量步进≠卡滞） |
| `_shared/references/analysis-qa-checklist.md` | 交付前 QA 4 类清单（数据质量/计算/合理性/呈现，逐条水利化）、8 类陷阱水利映射、5 类红旗量级 smell test、三级置信度评级；声明与 statistical-caution.md 姊妹关系 |
| `powerelf-data-governance/lib/profiling.py` | `classify_column` / `profile_numeric` / `profile_temporal` / `completeness_tier` / `detect_accuracy_flags` / `profile_table` |
| `powerelf-data-governance/impl/profiler.py` | CLI：`--db --table [--field] [--sample] [--format]`，输出 JSON profile |
| `powerelf-data-governance/lib/test_profiling.py` | 单测：合成 rows → 断言分类/tier/红旗（风格对齐 `test_outliers.py`） |

### 修改
| 路径 | 改动 |
|------|------|
| `powerelf-data-governance/SKILL.md` | 加载表加两行：首次遇表/画像 → 读 `data-profiling.md` + 调 `profiler.py`；报告交付前 → 过 `analysis-qa-checklist.md` |
| `powerelf-data-governance/lib/report.py` | `generate_daily_report_from_db` 末尾追加"QA 自检"节（清单 checkbox）+ 挂 `confidence_tier`；QA 引用置于已有 statistical-caution 引用之前 |
| `powerelf-data-governance/rules/quality-scoring.md` | 完整性/准确性维度交叉链 `data-profiling.md`（tier 定义单一事实源，不复制） |
| `powerelf-early-warning/strategies/notification-strategy.md` | 加姊妹指针：通知文案定稿前过 `_shared/references/analysis-qa-checklist.md`（与已有 statistical-caution 链并列） |

## 4. 组件设计

### 4.1 `lib/profiling.py` 接口

纯函数、吃 rows 序列、返回 dict，无 DB 耦合（DB 访问只在 `impl/profiler.py`）。对齐 `lib/outliers.py`
的返回风格。

```python
def classify_column(name, sample_values=None, dtype=None):
    """列 → identifier/temporal/metric/dimension/text/boolean/structural。
    水利语义：eq_id/stcd→identifier；*_time/create_time→temporal；
    water_pressure/rz/rainfall→metric；状态/开关量→boolean。"""

def profile_numeric(values):
    """→ {count, null_rate, min, max, mean, median, std,
       p1,p5,p25,p50,p75,p95,p99, zero_rate, negative_rate, distinct,
       distribution_hint(正态/右偏/左偏/双峰/幂律/均匀)}"""

def profile_temporal(values):
    """→ {min, max, span, median_gap, max_gap, future_count, null_rate}"""

def completeness_tier(valid_rate):
    """有效值率 → 绿(>99%)/黄(95-99%)/橙(80-95%)/红(<80%)。单一事实源，
    quality-scoring.md 复用此定义。"""

def detect_accuracy_flags(col_profile):
    """占位符(0/-1/999999 聚集)、默认值聚集、陈旧(时间列 max 过旧)、
    不可能值(超出 schema.md 语义范围) → flags[]。"""

def profile_table(rows, schema_hints=None):
    """逐列 classify → 分类型 profile → 汇总 table-level completeness_tier + flags。"""
```

### 4.2 `impl/profiler.py`

对齐 `anomaly_detector.py` 的 CLI 风格与 `--db "$DB_URL"` 约定。

```bash
source ../_shared/bootstrap.sh
python3 impl/profiler.py --db "$DB_URL" --table st_pressure_r \
    [--field water_pressure] [--sample 10000] [--format json|text]
```

- 连接走 `_shared/lib/db.py`（shim），`DESCRIBE <table>` 取列+类型，`--sample` 做 `LIMIT`（或随机采样）。
- 输出 JSON：
  ```json
  {"table":"st_pressure_r","row_count":...,"time_range":{...},"sample_size":...,
   "columns":[{"name":..,"type":..,"classification":..,"null_rate":..,"numeric_stats":{...}}],
   "completeness_tier":"绿","flags":[...],"generated_at":...}
  ```
- `--field` 指定时只深度画像该列（省 token）。
- **只读，不写库。**

### 4.3 `data-profiling.md` 结构

1. 何时画像：首次遇表 / 新测点接入 / 质量评分前
2. 列 6 分类 + 水利映射表（eq_id/stcd/create_time/water_pressure/rz/开关量）
3. 分类型 profile 清单（数值/时间/字符串/布尔各自的必查项）
4. 质量评估框架：完整性 4 级（tier 单一事实源）、一致性、准确性红旗、及时性
5. 6 类分布识别 + SCADA 特例（雨量步进式读数 ≠ 卡滞，链 `outlier-methods.md`；零膨胀长尾 → IQR 而非 MAD，链 `outlier-methods.md`）
6. 可执行伴侣：`powerelf-data-governance/impl/profiler.py`

### 4.4 `analysis-qa-checklist.md` 结构

1. **何时过**：报告组装完、交付前（在 `statistical-caution.md` 之前）
2. **4 类 QA 清单**（逐条水利化）：
   - 数据质量（源新鲜度 / null 处理 / 去重 / 过滤标注）
   - 计算（聚合粒度 / 分母正确性 / 日期对齐 / JOIN 多对多 / 指标定义一致 / 小计=总计）
   - 合理性（量级 smell test / 趋势连续 / 交叉引用自洽 / 边界）
   - 呈现（零基 / 数字格式 / caveat 透明含插值标注 / 可复现）
3. **8 类陷阱水利映射**：join 爆炸→测点-设备-厂站多对多；时区错配→多源时间戳；分母漂移→在线设备数变化；不完整周期→汛期/日比较；平均的平均；选择偏差；幸存者；其它统计
4. **5 类红旗量级**：水位/雨量/渗压/GNSS 各自合理范围（链 `mad.md` 阈值表作 smell test 基准）
5. **三级置信度评级**：Ready to share / Share with caveats / Needs revision
6. **姊妹关系声明**：QA=数字逻辑对不对；statistical-caution=结论措辞过不过；报告依次过两道

### 4.5 `report.py` 接线

`generate_daily_report_from_db` 末尾、return 前：
- 插入"QA 自检"节模板（4 类 checkbox），由调用方 Agent 填；
- 挂 `confidence_tier` 字段（默认 null，Agent 按 checklist 填三级之一）；
- 文档头加指针：先过 `analysis-qa-checklist.md`，再过 `statistical-caution.md`。
- **不自动判定 tier**（被动，与既有护栏一致）。

## 5. 数据流

```
[首次遇表 / 画像]                              [报告交付]
      │                                             │
      ▼                                             ▼
读 data-profiling.md                            报告组装完
      │                                             │
      ▼                                             ▼
impl/profiler.py --db --table                依次过两道护栏:
      │  ▼                                        ① analysis-qa-checklist.md (数字/逻辑)
      │ JSON profile                              ② statistical-caution.md   (措辞)
      │ (tier/分布/红旗)                               │
      │  │                                           ▼
      └─► 喂给 missing/anomaly/quality-scoring   挂 confidence_tier + QA自检节
          作检测/评分上下文                      ─────► 交付
```

**画像与检测均只读；QA 为被动审；无新增写库路径。**

## 6. 错误处理

- `profiler.py`：DB 不可达 → 非零退出 + 清晰提示（沿用 `db.py`）；空表 → profile 正常返回、tier=红、
  null_rate=1；字段不存在 → 提示"先读 `_shared/references/schema.md`"；`--sample` 过大自动降级。
- `profile_numeric` 退化：全相同值 → std=0、distinct=1，不报错；样本 <10 → 标注 low_confidence。
- QA 清单：被动，不做代码级强制；Agent 自判填 tier；缺数据项标"无法核验"而非误报通过。

## 7. 测试

- **单测** `lib/test_profiling.py`（对齐 `test_outliers.py`）：合成 rows 序列 → 断言列分类（eq_id→
  identifier 等）、null_rate、tier 判定（>99%→绿、<80%→红）、红旗检测（植入 999999 占位符应被
  flag）、分布提示。纯函数无 DB，可入 CI。
- **文档验证**：(a) 外部条目逐条映射审查——确认无 Snowflake/BigQuery/PG 方言泄漏；(b) 干跑——取一份
  既有治理报告，按 QA 清单走一遍，确认能抓出 1 个植入错误（如 `create_time` 误写 `data_time`、异常率
  分母含离线设备）。
- **链接完整性**（grep 脚本）：两份新文档被 `SKILL.md` + `report.py` + `quality-scoring.md` 引用；
  表结构/字段无复制（凡 schema 必须指向 `schema.md`）。
- **冒烟**（手动 runbook，非 CI 阻塞）：`source ../_shared/bootstrap.sh && python3 impl/profiler.py
  --db "$DB_URL" --table st_pressure_r` 在真实库产出合理 JSON，人工核对 tier/红旗。

## 8. 关键决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 整合范围 | A 簇：画像 + QA 闸 | 补 data-governance 前置画像与后置 QA 两块短板，内聚于治理域 |
| 画像形态 | 文档 + 可执行 profiler | 画像是机械计算→工具化（对齐"调工具优先"）；探索性、高复用 |
| QA 形态 | 被动清单 + 三级评级（不自动打分） | QA 是判断题，自动评分假精度；与 statistical-caution.md 既有定位一致 |
| profiler 落点 | governance `impl/lib/`（不进 `_shared/lib`） | 维持"代码进各 skill"约定；待 inspection 复用时再升 `_shared` |
| QA 文档落点 | `_shared/references/`（跨域） | governance 报告 + early-warning 通知都交付分析，均可复用 |
| report.py 改动 | 追加 QA 自检节，不自动判 tier | 保持被动；Agent 填 tier，避免假精度 |

## 9. 后续（不在本 spec 内）

- **B 簇（chatbi 增强）**：`sql-queries`/`write-query` → chatbi SQL 纪律（CTE / 禁 `SELECT *` /
  `EXISTS` / 分区裁剪）；可视化三件套 → chatbi 图表选择。
- **C 簇（元工具）**：`data-context-extractor` → schema 文档模板 / 可能的打包脚本。
- **跨簇**：profiling 若被 inspection 也需要，升 `_shared/lib/profiling.py` + 各 skill shim。
- **QA 自动化**：若被动清单在实战中反复漏检同一类问题，再评估定向自动化（仅那一条），而非整体评分器。
