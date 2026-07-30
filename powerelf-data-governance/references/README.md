# References 索引

> 本目录包含 powerelf-data-governance skill 的补充文档。
> **按需加载**：仅在需要时读取对应文件。

---

## 快速参考

| 文件 | 内容 | 适用场景 |
|------|------|---------|
| [quick-reference.md](quick-reference.md) | 数据库连接、核心数据表、常用 SQL、离线阈值、分级阈值 | 快速查找表结构、列名、阈值 |

---

## 分析指南

| 文件 | 内容 | 适用场景 |
|------|------|---------|
| [analysis-guide.md](analysis-guide.md) | 12 种分析方法的 API 和使用说明 | 需要深度分析时（异常/缺失/离线/评分等） |

---

## 规则文件

| 文件 | 内容 | 适用场景 |
|------|------|---------|
| [offline-detection.md](../rules/offline-detection.md) | 离线检测规则（三态判定、分级、MTTR、批量分级） | 离线检测任务 |
| [anomaly-detection.md](../rules/anomaly-detection.md) | MAD 异常检测规则（分指标阈值） | 异常检测任务 |
| [missing-detection.md](../rules/missing-detection.md) | 缺失检测规则（期望周期数、模式识别） | 缺失检测任务 |
| [interpolation.md](../rules/interpolation.md) | 智能插值规则（四策略自适应） | 插值填补任务 |
| [quality-scoring.md](../rules/quality-scoring.md) | 质量评分规则（四维度加权） | 质量评分任务 |

---

## 最佳实践

| 文件 | 内容 | 适用场景 |
|------|------|---------|
| [best-practices.md](best-practices.md) | Pitfalls、Validation Gate、边界规则 | 交付前 QA、避免常见错误 |

---

## 使用建议

### 何时加载 references/

1. **快速查询**（如"有多少设备离线？"）
   - 仅加载 `quick-reference.md`（如果需要查表结构）

2. **深度分析**（如"帮我分析异常原因"）
   - 加载 `analysis-guide.md` + 相关规则文件

3. **交付报告**（如"生成数据质量日报"）
   - 加载 `best-practices.md`（QA 闸）

---

**返回**: [SKILL.md](../SKILL.md)
