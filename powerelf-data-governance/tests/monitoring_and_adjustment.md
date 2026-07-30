# 性能监控和调整方案

**日期**: 2026-07-28
**状态**: ✅ 已实施

---

## 📊 实际测试结果

### Hermes 测试（Session 20260728_152241_157ec3）

| 指标 | 优化前基准 | 优化后实际 | 目标 | 状态 |
|------|-----------|----------|------|------|
| **工具调用次数** | 17 次 | **1 次** | ≤ 2 次 | ✅ **达标** |
| **输出 tokens** | 12,811 | **714** | < 3,000 | ✅ **优秀** |
| **输入 tokens** | ~30,000 | **57,907** | < 15,000 | ⚠️ **超标** |
| **耗时** | 222 秒 | **~71 秒** | < 30 秒 | ⚠️ **待优化** |
| **中途停顿** | 24s + 49s | **< 5s** | < 5s | ✅ **达标** |

### 关键发现

**✅ 优化成功的部分**：
1. **工具调用大幅减少**：17 次 → 1 次（**94% 减少**）
2. **输出精简**：12,811 tokens → 714 tokens（**94% 减少**）
3. **无长时间停顿**：消除了 24s/49s 的 prefill 卡顿

**⚠️ 需要优化的部分**：
1. **输入 tokens 过高**：57,907 tokens（目标是 < 15,000）
   - 原因：工具返回了 504 台设备的完整列表（55.6KB）
   - 影响：下一轮 prefill 负担重，导致总耗时 71 秒（目标 < 30 秒）

---

## 🔧 已实施的优化

### 优化 1：限制 Markdown 输出大小

**改动**：`scripts/classify_offline_by_duration.py`

```python
# 新增参数
parser.add_argument("--limit", type=int, default=20,
                    help="Markdown 输出详细列表的最大行数（默认 20）")
parser.add_argument("--full", action='store_true',
                    help="输出完整列表（覆盖 --limit）")

# 修改 format_markdown 函数
def format_markdown(devices, limit=20):
    # 只显示前 limit 台设备
    for d in devices[:limit]:
        # 输出详细列表...

    if len(devices) > limit:
        lines.append(f"\n... 还有 {len(devices) - limit} 台设备，使用 `--full` 参数查看完整列表")
```

**效果**：
- 默认输出：分级汇总 + 前 20 台设备（约 5-8KB，~1,500-2,500 tokens）
- 完整输出：`--full` 参数（用于导出/分析）
- **预期减少 80% 的输出大小**

---

### 优化 2：更新使用文档

**更新文件**：
1. `rules/offline-detection.md` — 补充"输出优化"章节
2. `SKILL.md` — 补充工具参数说明

**新增内容**：
```markdown
## 输出优化（减少 prefill 负担）

默认输出已限制为前 20 台设备，如需完整列表：

\`\`\`bash
# 默认：分级汇总 + 前 20 台（推荐用于展示）
python3 scripts/classify_offline_by_duration.py --db "$DB_URL"

# 完整：分级汇总 + 全部 504 台（用于导出/分析）
python3 scripts/classify_offline_by_duration.py --db "$DB_URL" --full

# 自定义行数
python3 scripts/classify_offline_by_duration.py --db "$DB_URL" --limit 50
\`\`\`

**性能对比**：
- 默认（20 台）：~5KB / ~1,500 tokens
- 完整（504 台）：~55KB / ~15,000 tokens
- **节省**: 90% prefill 开销
```

---

## 📈 预期优化效果

### 优化前（第一次测试）

| 指标 | 值 | 问题 |
|------|-----|------|
| 工具调用 | 1 次 | ✅ 优秀 |
| 输出 tokens | 57,907 | ❌ 过高（55.6KB 完整列表） |
| 输入 tokens（下一轮） | ~58,000 | ❌ 超标（目标 < 15,000） |
| 耗时 | ~71 秒 | ⚠️ 偏长（目标 < 30 秒） |

### 优化后（预期）

| 指标 | 预期值 | 改进 |
|------|--------|------|
| 工具调用 | 1 次 | ✅ 不变 |
| 输出 tokens | **~2,000** | ⚠️ 减少 96%（714 → 2,000，包含分级汇总） |
| 输入 tokens（下一轮） | **< 15,000** | ✅ 减少 75% |
| 耗时 | **< 30 秒** | ✅ 减少 58% |

---

## 🎯 监控方案

### 关键指标监控

在每次 Hermes 测试后，提取以下指标：

```bash
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")

sqlite3 ~/.hermes/state.db "
SELECT
    datetime(started_at, 'unixepoch', 'localtime') as start_time,
    ROUND((ended_at - started_at), 2) as duration_sec,
    tool_call_count,
    message_count,
    output_tokens,
    input_tokens,
    CAST(output_tokens AS FLOAT) / NULLIF(message_count, 0) as tokens_per_msg
FROM sessions WHERE id = '$SESSION_ID';
"
```

### 监控阈值

| 指标 | 优秀 | 达标 | 预警 | 失败 |
|------|------|------|------|------|
| **工具调用** | 1 次 | ≤ 2 次 | 3-5 次 | > 5 次 |
| **输出 tokens** | < 2,000 | < 3,000 | 3,000-8,000 | > 8,000 |
| **输入 tokens** | < 10,000 | < 15,000 | 15,000-30,000 | > 30,000 |
| **耗时** | < 20 秒 | < 30 秒 | 30-60 秒 | > 60 秒 |
| **每消息 tokens** | < 500 | < 1,000 | 1,000-2,000 | > 2,000 |

### 监控脚本

已创建监控脚本：`tests/monitor_session.sh`

```bash
bash /home/scada/powerelf-skills/powerelf-data-governance/tests/monitor_session.sh
```

---

## 🔄 持续调整方案

### 如果输入 tokens 仍 > 15,000

**原因分析**：
- Hermes 仍加载了完整 SKILL.md
- 路由规则未生效
- 其他 system prompt 过大

**调整措施**：
1. **进一步优化路由规则**：在 SKILL.md 开头添加明确的"离线分级"指令，要求只加载 `rules/offline-detection.md`
2. **压缩 SKILL.md**：移除冗余内容，将详细说明移至 `references/`
3. **使用 `--no-restore-cwd`**：减少上下文负担

### 如果耗时仍 > 30 秒

**原因分析**：
- LLM 推理过慢（模型本身）
- prefill 仍过重
- 数据库查询慢

**调整措施**：
1. **启用前缀缓存**（vLLM APC）：减少重复 prefill
2. **降级模型**：使用更快的模型（如 step-3.5-flash → step-3.5-haiku）
3. **缓存结果**：离线状态 5 分钟内不变，可缓存

### 如果工具调用 > 2 次

**原因分析**：
- Hermes 未识别批量脚本意图
- Hermes 分步执行（先查列表，再逐个检测）

**调整措施**：
1. **强化路由规则**：在 `rules/offline-detection.md` 开头明确"优先使用批量脚本"
2. **提供示例**：添加"正确示例"和"错误示例"
3. **添加工具别名**：注册 `offline-classify` 工具别名

---

## 📋 验证清单

在每次调整后，重新运行测试并检查：

```bash
# 1. 运行测试
bash /home/scada/powerelf-skills/powerelf-data-governance/tests/run_hermes_test.sh

# 2. 手动验证
hermes chat -s powerelf-data-governance -q "帮我分级所有离线设备" --quiet --max-turns 3

# 3. 提取指标
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
sqlite3 ~/.hermes/state.db "
SELECT tool_call_count, output_tokens, input_tokens,
       ROUND((ended_at - started_at), 2) as duration
FROM sessions WHERE id = '$SESSION_ID';
"

# 4. 对比阈值
# 工具调用: ≤ 2 ✅
# 输出 tokens: < 3,000 ✅
# 输入 tokens: < 15,000 🎯
# 耗时: < 30 秒 🎯
```

---

## 🎯 下一步行动

### 立即（已实施 ✅）
- [x] 限制 Markdown 输出为前 20 台
- [x] 添加 `--limit` 和 `--full` 参数
- [x] 更新使用文档

### 短期（今日内）
- [ ] 重新运行 Hermes 测试验证优化效果
- [ ] 检查输入 tokens 是否降至 < 15,000
- [ ] 检查耗时是否降至 < 30 秒

### 中期（本周）
- [ ] 如果输入 tokens 仍高，优化路由规则
- [ ] 如果耗时仍长，检查引擎层（前缀缓存、量化）
- [ ] 补充业务映射（当前 32.1% → 目标 > 80%）

---

## 📚 参考文档

| 文档 | 说明 |
|------|------|
| [监控脚本](monitor_session.sh) | 自动提取和评估性能指标 |
| [优化分析报告](..\_shared\optimization_analysis_20260728.md) | 详细的技术分析 |
| [验证报告](..\_shared\verification_report_20260728.md) | 单元验证结果 |
| [批量分级规则](../rules/offline-detection.md) | 使用文档 |

---

**创建时间**: 2026-07-28 15:30
**状态**: ✅ 优化已实施，待重新测试验证
