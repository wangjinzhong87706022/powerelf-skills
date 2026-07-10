# 设计：离群检测增强（IQR + 百分位法）+ 统计护栏

- **日期**：2026-07-10
- **目标仓库**：`powerelf-skills` monorepo（权威源 `/home/scada/powerelf-skills`）
- **主受影响 skill**：`powerelf-data-governance`
- **次受影响 skill**：`powerelf-early-warning`（仅引用护栏文档）
- **来源**：复用 `knowledge-work-plugins/data` 中 `statistical-analysis` skill 的离群方法与统计护栏方法论

## 1. 背景与动机

`powerelf-data-governance` 当前异常检测只有 **MAD（中位绝对差）** 一种稳健方法。MAD 适合正态/缓变指标
（水位、GNSS、渗压），但对**偏态分布**（雨量、流量，零膨胀、长尾）并非最优。`knowledge-work-plugins`
的 `statistical-analysis` skill 提供了 IQR（四分位距）与百分位法两种互补的稳健离群检测，以及一套
"统计结论措辞护栏"（相关≠因果、Simpson、幸存者偏差等），powerelf 目前完全没有后者。

本设计把这两块以"文档进 `_shared`、可运行代码进 skill、护栏为纯文档+指针"的方式整合进来。

## 2. 范围

### 做
- 在 `_shared/algorithms/` 增 IQR + 百分位算法文档（与 `mad.md` 并列的单一事实源）。
- 在 `powerelf-data-governance/lib/` 增可运行的 `outliers.py`（`detect_iqr` / `detect_percentile`）。
- `impl/anomaly_detector.py` 增 `--method mad|iqr|percentile`（默认 mad，向后兼容）。
- `_shared/references/` 增 `statistical-caution.md`（护栏 + 合并的结论措辞自检清单）。
- early-warning 与 data-governance 各加一句指向护栏文档的指针。

### 不做（YAGNI）
- ❌ 多方法 composite 投票/交叉判定（方案乙，留待后续统一抽象"多检测器投票"）。
- ❌ 把可运行代码放进 `_shared/lib/`（维持"文档进 _shared、代码进各 skill"的既有约定）。
- ❌ 修改 `writeback.py` 或报告生成主逻辑（仅在报告环节加护栏指针）。
- ❌ 为 IQR/百分位建 per-indicator 阈值表（用标准 1.5×IQR / p1·p99 默认，需要时再加）。
- ❌ 代码级强制护栏（对自由文本结论脆弱，不采用）。

## 3. 文件变更清单

### 新建
| 路径 | 内容 |
|------|------|
| `_shared/algorithms/outlier-methods.md` | IQR / 百分位算法文档：三法对比、方法选择指南、公式、Python 片段、与 MAD 的互补关系、卡滞检测注意 |
| `_shared/references/statistical-caution.md` | 统计护栏：相关≠因果、多重比较/Bonferroni、Simpson、幸存者偏差、生态谬误、假精度 + 结论措辞自检清单（6–8 条 checkbox） |
| `powerelf-data-governance/lib/outliers.py` | `detect_iqr(values, k=1.5)` + `detect_percentile(values, low=1, high=99)` |

### 修改
| 路径 | 改动 |
|------|------|
| `powerelf-data-governance/impl/anomaly_detector.py` | 加 `--method`（choices=mad/iqr/percentile，default=mad）；`--threshold` 语义随方法；按 method 分派到 `mad.py` / `outliers.py`；输出 JSON 增 `method` 字段 |
| `powerelf-data-governance/SKILL.md` | 工具命令段补充 `--method` 用法与各方法 threshold 语义；报告段加护栏指针 |
| `powerelf-early-warning/strategies/notification-strategy.md` | 加一句指针：生成结论文案前查 `_shared/references/statistical-caution.md` |
| `_shared/algorithms/mad.md` | 加一行"姊妹方法"交叉链接到 `outlier-methods.md` |

## 4. 组件设计

### 4.1 `lib/outliers.py` 接口

对齐现有 `lib/mad.py` 的 `detect_anomalies(values, threshold)` 签名与返回结构（含 `anomaly_count` /
`anomaly_indices`），便于 `anomaly_detector` 统一格式化输出。

```python
def detect_iqr(values, k=1.5):
    """IQR 离群检测。k = IQR 倍数（1.5 标准 / 3.0 激进）。
    返回 {q1, q3, iqr, lower_bound, upper_bound, anomaly_count, anomaly_indices}。"""

def detect_percentile(values, low=1, high=99):
    """百分位法。low/high 为尾部百分位边界。
    返回 {low_bound, high_bound, anomaly_count, anomaly_indices}。"""
```

### 4.2 `anomaly_detector.py` 改动

- 新增参数 `--method`，choices=`[mad, iqr, percentile]`，**default=`mad`** → 现有命令零改动、完全向后兼容。
- `--threshold` 语义随方法（写入 `--help` 与 `outlier-methods.md`）：
  | method | --threshold 含义 | 默认 |
  |--------|------------------|------|
  | mad | 修正 Z 阈值 | 4.0（不变） |
  | iqr | IQR 倍数 k | 1.5（3.0 激进） |
  | percentile | 尾部百分位 p（取 p 与 100-p） | 1（即 p1/p99） |
- 分派逻辑：
  - `mad` → `mad.detect_anomalies(values, threshold)`
  - `iqr` → `outliers.detect_iqr(values, k=threshold or 1.5)`
  - `percentile` → `outliers.detect_percentile(values, low=threshold or 1, high=100-(threshold or 1))`
- 输出 JSON 增加 `method` 字段（溯源）；其余字段与格式不变。

### 4.3 `outlier-methods.md` 结构

1. 三法对比表（适用分布 / 稳健性 / 参数 / 计算成本）
2. 方法选择指南：水位·GNSS·渗压 → MAD；雨量·流量（偏态） → IQR；海量快速筛查 → 百分位
3. IQR：公式 + Python（k=1.5/3.0；样本 <10 不检）
4. 百分位法：p1/p99；简单但对非典型分布无理论保证
5. 与 MAD 的关系：互补非替代；composite 交叉验证明确标注为"后续增强"
6. 卡滞检测注意：雨量步进式读数，链接 `_shared/references/schema.md`

### 4.4 `statistical-caution.md` 结构

- 相关 ≠ 因果（反向因果 / 混杂 / 巧合；附措辞模板："用 X 的用户留存高 30%" ≠ "X 导致…"）
- 多重比较问题（Bonferroni：α / 测试数；需注明跑了多少测试）
- Simpson 悖论（分 segment 后结论是否反转）
- 幸存者偏差（谁不在数据集里）
- 生态谬误（群体结论 ≠ 个体）
- 假精度（给区间而非点估计；"约 5%" 胜过 "4.73%"）
- **结论措辞自检清单**（6–8 条 checkbox，合并自原方案②的嵌入式清单）

## 5. 数据流

```
anomaly_detector
  → 读取 --table --field --st-id --days 序列
  → dropna / to_numeric
  → 按 --method 分派
       mad        → lib/mad.detect_anomalies(values, threshold)
       iqr        → lib/outliers.detect_iqr(values, k)
       percentile → lib/outliers.detect_percentile(values, low, high)
  → 统一格式化（带 method 标签）
  → 输出（JSON / 文本）
```

**只检测，不写库。** 数据回写仍走独立 `lib/writeback.py`，本次不改。

## 6. 错误处理

- 未知 `--method` → argparse `choices` 直接拦截。
- 样本数 < 10 → 告警并跳过检测（与 `mad.py` 一致）。
- 空序列 / 全相同值 → IQR=0 时下界=上界=中位数，判定无离群（退化，不报错）。
- `--threshold` 越界（如 iqr `k ≤ 0`）→ 告警但继续。

## 7. 测试

- **单元测试** `powerelf-data-governance/lib/test_outliers.py`：构造含已知离群点的合成数组，断言
  `detect_iqr` / `detect_percentile` 命中正确索引、边界值正确（风格参考
  `powerelf-inspection/impl/test_inspection.py`）。
- **冒烟测试**：对 `st_rsvr_r.rz` 分别执行 `--method iqr` 与 `--method percentile`，确认输出 JSON 含
  `method` 字段、`anomaly_indices` 合理；并确认不带 `--method` 时行为与改造前完全一致（向后兼容）。
- **链路校验**：`notification-strategy.md` → `statistical-caution.md`、`mad.md` ↔ `outlier-methods.md`
  相对链接可达。

## 8. 关键决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 整合范围 | A：离群法 + 护栏 | 命中 data-governance/early-warning 真实短板，纯增量低风险 |
| 交付形态 | ② 文档进 _shared + 代码进 skill | 保持既有架构约定；① 太轻不增强实际检测，③ 为一法破界不划算 |
| 护栏形态 | ① 被动文档 + 合并轻量清单 | 匹配"规则内嵌、Agent 自判"风格；代码级强制对自由文本脆弱 |
| CLI 集成 | 方案甲 单方法互斥 | 简单、向后兼容；composite 投票留待统一抽象 |
| 默认 method | mad | 向后兼容，现有命令零改动 |

## 9. 后续（不在本 spec 内）

- 多检测器 composite 投票（MAD + IQR 交叉判定），届时统一抽象"多检测器投票"框架。
- per-indicator 的 IQR/百分位阈值表（若标准默认在实际数据上误报率偏高）。
- 评估是否把 `knowledge-work-plugins` 的 `explore-data`（数据画像）、`validate-data`（报告 QA 闸）
  作为独立 spec 推进。
