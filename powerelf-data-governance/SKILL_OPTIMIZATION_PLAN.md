# SKILL.md 优化方案

**当前大小**: 731 行，36KB（过大）
**目标大小**: < 15KB（减少 58%）
**优化策略**: 将详细内容移至 references/ 子文件

---

## 📊 当前章节分析

### 必须保留（核心指令）

| 章节 | 行数 | 大小 | 说明 |
|------|------|------|------|
| ⚠️ 强制指令 | 38 | 1KB | **最高优先级** |
| 写代码前必读 | 61 | 2KB | 高频翻车点 |
| 工具命令 | 69 | 3KB | 实际工具使用 |

### 可压缩（精简版）

| 章节 | 行数 | 当前大小 | 目标大小 | 说明 |
|------|------|---------|---------|------|
| 路由规则 | 70 | 3KB | **0.5KB** | 已证明未生效，改为简单指令 |
| When to Use | 17 | 0.5KB | 保持 | 必要 |
| 数据库连接 | 43 | 1.5KB | **0.5KB** | 可精简示例 |
| 核心数据表 | 14 | 0.5KB | 保持 | 必要 |

### 可移除（移至 references/）

| 章节 | 行数 | 大小 | 优先级 | 建议 |
|------|------|------|--------|------|
| 模块架构 | 10 | 0.3KB | 低 | 移至 references/architecture.md |
| 能力概览 | 17 | 0.5KB | 低 | 移至 references/capabilities.md |
| 核心分析能力 | 72 | 3KB | 低 | 移至 references/analysis-capabilities.md |
| 按需加载指令 | 86 | 3KB | 低 | 已失效，移至 references/ |
| 边界规则 | 18 | 0.5KB | 低 | 移至 references/boundaries.md |
| 巡检前检查清单 | 9 | 0.3KB | 低 | 移至 references/checklists.md |
| 离线分析任务推荐流程 | 14 | 0.5KB | 中 | 保留（与强制指令相关） |
| 输出模板 | 23 | 1KB | 低 | 移至 references/templates.md |
| Workflow | 31 | 1KB | 中 | 保留核心步骤 |
| 数据输入 | 13 | 0.5KB | 低 | 移至 references/data-sources.md |
| 自我进化 | 6 | 0.2KB | 低 | 移至 references/evolution.md |
| 机器学习算法 | 11 | 0.5KB | 低 | 移至 references/ml-algorithms.md |
| API 附录 | 12 | 0.5KB | 低 | 移至 references/api.md |
| Pitfalls | 10 | 0.3KB | 中 | 保留（高频错误） |
| Validation Gate | 12 | 0.5KB | 中 | 保留（QA 闸） |
| 输出深度模式 | 8 | 0.3KB | 低 | 移至 references/depth-mode.md |
| 共享引用 | 15 | 0.5KB | 低 | 移至 references/shared.md |
| Related Skills | 3 | 0.1KB | 中 | 保持 |

### 总计

| 类别 | 行数 | 大小 | 处理 |
|------|------|------|------|
| **必须保留** | 182 | 7KB | 不变 |
| **可压缩** | 131 | 5KB | 压缩至 2KB |
| **可移除** | 418 | 17KB | 移至 references/ |
| **总计** | **731** | **36KB** | **目标: < 15KB** |

---

## 🎯 优化方案

### 方案 A：激进优化（目标: ~12KB）

**策略**：
1. 保留前 5 个核心章节（强制指令 + 路由 + 必读 + When to Use + 工具命令）
2. 压缩数据库连接和核心数据表
3. 移除所有详细章节到 references/
4. 创建 references/README.md 索引

**优点**：
- ✅ 大幅减少 system prompt（36KB → 12KB = 67% 减少）
- ✅ 预计 input tokens: 55,980 → **< 15,000**

**缺点**：
- ❌ 需要创建多个 references/ 文件
- ❌ Agent 需要额外加载 references/

### 方案 B：保守优化（目标: ~20KB）

**策略**：
1. 保留更多章节在 SKILL.md
2. 只移除最冗长的 2-3 个章节
3. 压缩其他章节

**优点**：
- ✅ 改动最小
- ✅ 减少 references/ 文件数量

**缺点**：
- ⚠️ 优化效果有限（36KB → 20KB = 44% 减少）

### 方案 C：混合优化（推荐，目标: ~15KB）

**策略**：
1. 保留核心章节（强制指令 + 路由 + 必读 + When to Use + 工具命令 + Workflow）
2. 将详细内容分组移至 references/：
   - `references/quick-reference.md`（核心数据表 + 数据库连接）
   - `references/analysis-guide.md`（核心分析能力 + 能力概览）
   - `references/best-practices.md`（Pitfalls + Validation Gate + 边界规则）
3. 创建 references/README.md 索引

**优点**：
- ✅ 平衡了精简和完整性
- ✅ 创建的 references/ 文件较少（3-4 个）
- ✅ 预计达到目标（15KB）

---

## 📋 推荐实施步骤

### 第 1 步：创建 references/ 文件

1. `references/quick-reference.md`
   - 核心数据表（简化）
   - 数据库连接（精简示例）

2. `references/analysis-guide.md`
   - 核心分析能力（从 SKILL.md 复制）
   - 能力概览（从 SKILL.md 复制）

3. `references/best-practices.md`
   - Pitfalls
   - Validation Gate
   - 边界规则

4. `references/README.md`
   - 索引所有 references/ 文件
   - 说明何时加载哪个文件

### 第 2 步：精简 SKILL.md

1. 移除已移至 references/ 的章节
2. 压缩剩余章节（移除冗余示例）
3. 添加 references/ 索引

### 第 3 步：测试验证

运行 Hermes 测试，检查 input tokens 是否降至 < 15,000。

---

## 🚀 立即开始实施

**推荐方案**：方案 C（混合优化）

**预计效果**：
- SKILL.md: 36KB → **15KB**（58% 减少）
- Input tokens: 55,980 → **< 15,000**（73% 减少）
- 耗时: 222 秒 → **< 60 秒**（进一步改善）

是否立即开始实施？
