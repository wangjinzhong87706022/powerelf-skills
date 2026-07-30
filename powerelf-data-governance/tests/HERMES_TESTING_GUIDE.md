# 在 Hermes 环境下测试验证指南

## 测试目标

验证批量离线分级脚本在 Hermes 环境下的实际表现：
1. **功能性验证**：脚本是否能正确执行
2. **性能验证**：对比优化前后的耗时、调用次数
3. **路由验证**：Hermes 是否按需加载（只加载必要内容）

---

## 测试方案

### 方案 1：直接执行批量脚本（快速验证）

**步骤 1：打开 Hermes Chat**
```bash
hermes chat -s powerelf-data-governance
```

**步骤 2：发送测试查询**
```
帮我分级所有离线设备
```

**步骤 3：观察输出**
- ✅ **预期结果**：Hermes 应识别"离线分级"意图，直接调用 `scripts/classify_offline_by_duration.py`
- ✅ **预期耗时**：< 30 秒（含 LLM 推理）
- ✅ **预期调用次数**：1-2 次工具调用

**步骤 4：查看性能指标**
```bash
# 查看最新 session 的指标
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
sqlite3 ~/.hermes/state.db "SELECT datetime(started_at, 'unixepoch', 'localtime'), (ended_at - started_at) as duration, tool_call_count, message_count, output_tokens FROM sessions WHERE id = '$SESSION_ID';"
```

---

### 方案 2：对比测试（推荐，量化优化效果）

**步骤 1：执行优化前基准测试（模拟旧方案）**

在 Hermes Chat 中发送：
```
请逐台检测离线设备：先查 eq_equip_base 中所有 status=0 的设备，然后对每台设备执行离线检测（使用 impl/offline_detector.py），最后统计分级结果。
```

记录指标：
- 耗时
- 工具调用次数
- 输出 tokens

**步骤 2：执行优化后测试（新方案）**

在 Hermes Chat 中发送：
```
帮我分级所有离线设备（使用批量脚本）
```

预期行为：
- Hermes 识别意图 → 加载 `rules/offline-detection.md`
- 看到"批量分级"章节 → 调用 `scripts/classify_offline_by_duration.py`
- 一次调用返回完整结果

记录指标：
- 耗时
- 工具调用次数
- 输出 tokens

**步骤 3：对比总结**

| 指标 | 优化前（基准） | 优化后 | 提升 |
|------|--------------|--------|------|
| 耗时 | 222 秒 | ? 秒 | ?× |
| 工具调用 | 17 次 | ? 次 | ?%↓ |
| 输出 tokens | 12,811 | ? | ?%↓ |

---

### 方案 3：自动化测试脚本（一键对比）

使用提供的测试脚本：

```bash
cd /home/scada/powerelf-skills/powerelf-data-governance/tests

# 方法 A：使用 bash 脚本（交互式）
bash test_on_hermes.sh

# 方法 B：手动记录后对比
hermes chat -s powerelf-data-governance -q "帮我分级所有离线设备"
```

---

## 性能基准参考

### 优化前基准（session 20260728_084051_fca604）

| 指标 | 数值 |
|------|------|
| 墙钟耗时 | **222 秒**（3.7 分钟） |
| 工具调用 | **17 次** |
| Assistant 消息 | 18 条 |
| 输出 tokens | **12,811** |
| 中途停顿 | 24 秒 + 49 秒 |

### 优化后预期

| 指标 | 预期值 | 状态 |
|------|--------|------|
| 墙钟耗时 | **< 30 秒** | 🎯 |
| 工具调用 | **1-2 次** | 🎯 |
| 输出 tokens | **< 3,000** | 🎯 |
| 中途停顿 | **< 5 秒** | 🎯 |

---

## 验证检查清单

### 功能性验证

- [ ] **脚本可执行**：`hermes chat` 能成功调用 `classify_offline_by_duration.py`
- [ ] **输出正确**：脚本返回完整的 Markdown 表格（含分级汇总 + 详细列表）
- [ ] **分级准确**：CRITICAL / ERROR / WARNING / INFO 分类正确
- [ ] **格式支持**：Markdown / CSV / JSON 三种格式均可用

### 性能验证

- [ ] **耗时达标**：< 30 秒（含 LLM 推理）
- [ ] **调用次数达标**：1-2 次
- [ ] **无中途停顿**：不出现 24s / 49s 级别的停顿
- [ ] **prefill 节省**：专项任务上下文 < 15KB（对比完整 SKILL.md 的 50KB）

### 路由验证

- [ ] **意图识别正确**："离线分级" → 识别为离线检测场景
- [ ] **按需加载**：只加载 `rules/offline-detection.md`，不加载完整 SKILL.md
- [ ] **工具选择正确**：调用批量脚本，而非逐站循环

---

## 常见问题排查

### Q1：Hermes 没有调用批量脚本，而是逐站循环

**可能原因**：
1. Hermes 未识别"批量分级"意图
2. Hermes 未加载 `rules/offline-detection.md` 中的"批量分级"章节

**排查步骤**：
```bash
# 检查 session 的工具调用记录
SESSION_ID=<your_session_id>
sqlite3 ~/.hermes/state.db "SELECT timestamp, role, tool_name FROM messages WHERE session_id = '$SESSION_ID' AND role = 'tool' ORDER BY timestamp;"
```

**解决方案**：
- 明确告诉 Hermes："使用批量脚本 `classify_offline_by_duration.py`"
- 或优化 `rules/offline-detection.md` 的"批量分级"章节表述

---

### Q2：批量脚本执行失败

**排查步骤**：
```bash
# 1. 检查脚本权限
ls -l powerelf-data-governance/scripts/classify_offline_by_duration.py

# 2. 手动运行测试
cd powerelf-data-governance
source ../_shared/bootstrap.sh
python3 scripts/classify_offline_by_duration.py --db "$DB_URL" | head -20

# 3. 查看错误日志
sqlite3 ~/.hermes/state.db "SELECT content FROM messages WHERE session_id = '$SESSION_ID' AND role = 'tool' AND content LIKE '%Traceback%';"
```

---

### Q3：性能未达预期

**可能原因**：
1. **LLM 推理过慢**：模型本身性能问题（非脚本问题）
2. **上下文过大**：仍加载了完整 SKILL.md
3. **网络延迟**：数据库查询慢

**排查步骤**：
```bash
# 1. 查看上下文大小
sqlite3 ~/.hermes/state.db "SELECT input_tokens FROM sessions WHERE id = '$SESSION_ID';"

# 2. 查看是否加载了完整 SKILL.md
sqlite3 ~/.hermes/state.db "SELECT content FROM messages WHERE session_id = '$SESSION_ID' AND content LIKE '%SKILL.md%';"

# 3. 对比单次工具调用耗时
sqlite3 ~/.hermes/state.db "SELECT timestamp FROM messages WHERE session_id = '$SESSION_ID' AND role = 'tool' ORDER BY timestamp LIMIT 5;"
```

---

## 高级验证：Route 验证

### 验证意图识别

在 Hermes Chat 中测试以下 query，观察是否识别为"离线检测"场景：

| 测试 Query | 预期分类 | 预期加载内容 |
|-----------|---------|------------|
| "帮我分级所有离线设备" | 离线检测 | `rules/offline-detection.md` |
| "有哪些设备离线了？" | 离线检测 | `rules/offline-detection.md` |
| "统计离线设备分布" | 离线检测 | `rules/offline-detection.md` |
| "数据质量怎么样？" | 综合场景 | 完整 SKILL.md |

**验证方法**：
```bash
# 查看 session 加载了哪些文件
sqlite3 ~/.hermes/state.db "SELECT content FROM messages WHERE session_id = '$SESSION_ID' AND role = 'system';"
```

---

## 自动化测试脚本

### 一键执行（方案 1：快速验证）

```bash
#!/bin/bash
# 一键测试脚本

SESSION_QUERY="帮我分级所有离线设备"

echo "启动 Hermes Chat..."
hermes chat -s powerelf-data-governance -q "$SESSION_QUERY" --quiet

# 等待 10 秒让 session 写入
sleep 10

# 提取最新 session 指标
LATEST_SESSION=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
echo "查看 session: $LATEST_SESSION"

sqlite3 ~/.hermes/state.db -header -column "
SELECT datetime(started_at, 'unixepoch', 'localtime') as start_time,
       ROUND((ended_at - started_at), 2) as duration_sec,
       tool_call_count,
       message_count,
       output_tokens
FROM sessions
WHERE id = '$LATEST_SESSION';
"
```

### 一键对比测试（方案 2：量化优化效果）

```bash
#!/bin/bash
# 先测旧方案
echo "=== 测试旧方案（逐站检测）==="
hermes chat -s powerelf-data-governance -q "请逐台检测离线设备：对 eq_equip_base 中 status=0 的每台设备执行离线检测" --quiet
sleep 10
OLD_SESSION=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
OLD_METRICS=$(sqlite3 ~/.hermes/state.db "SELECT ROUND((ended_at - started_at), 2), tool_call_count, output_tokens FROM sessions WHERE id = '$OLD_SESSION';")

echo "旧方案: $OLD_METRICS"

# 等待 1 分钟让 session 结束
sleep 60

# 再测新方案
echo "=== 测试新方案（批量分级）==="
hermes chat -s powerelf-data-governance -q "帮我分级所有离线设备" --quiet
sleep 10
NEW_SESSION=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
NEW_METRICS=$(sqlite3 ~/.hermes/state.db "SELECT ROUND((ended_at - started_at), 2), tool_call_count, output_tokens FROM sessions WHERE id = '$NEW_SESSION';")

echo "新方案: $NEW_METRICS"

# 对比
echo "=== 性能对比 ==="
echo "旧方案: $OLD_METRICS"
echo "新方案: $NEW_METRICS"
```

---

## 结果验证标准

### ✅ 通过标准

| 检查项 | 通过标准 |
|--------|---------|
| 工具调用次数 | ≤ 2 次 |
| 耗时 | ≤ 30 秒 |
| 输出 tokens | ≤ 3,000 |
| 中途停顿 | 无 > 5 秒的停顿 |

### ⚠️ 需优化标准

| 检查项 | 预警标准 |
|--------|---------|
| 工具调用次数 | 3-5 次 |
| 耗时 | 30-60 秒 |
| 输出 tokens | 3,000-8,000 |
| 中途停顿 | 有 5-10 秒的停顿 |

### ❌ 失败标准

| 检查项 | 失败标准 |
|--------|---------|
| 工具调用次数 | > 5 次 |
| 耗时 | > 60 秒 |
| 输出 tokens | > 8,000 |
| 中途停顿 | 有 > 10 秒的停顿 |

---

## 总结

**推荐测试流程**：

1. **快速验证**（5 分钟）：使用 `test_on_hermes.sh` 脚本
2. **详细对比**（15 分钟）：执行方案 2 的对比测试
3. **深入分析**（30 分钟）：查看 state.db，分析消息时间线

**关键验证点**：
- ✅ 批量脚本是否被调用
- ✅ 耗时是否 < 30 秒
- ✅ 调用次数是否 ≤ 2 次
- ✅ 输出是否包含完整的分级结果
