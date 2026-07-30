# 🚀 Hermes 测试验证 — 快速开始

## 测试目标

验证批量离线分级脚本在 Hermes 环境下的实际表现，确认：
- ✅ **功能性**：脚本能正确执行，分级结果准确
- ✅ **性能**：耗时 < 30 秒，工具调用 ≤ 2 次
- ✅ **路由**：Hermes 识别意图并调用批量脚本

---

## 前置条件

- ✅ Hermes Agent v0.19.0 已安装
- ✅ powerelf-data-governance skill 已启用
- ✅ 数据库连接正常（`POWERELF_DB_*` 环境变量已配置）

---

## 测试方案（三选一）

### ⭐ 方案 1：一键自动测试（推荐，5 分钟）

**最简单的验证方式，自动执行并生成报告**：

```bash
bash /home/scada/powerelf-skills/powerelf-data-governance/tests/run_hermes_test.sh
```

**功能**：
- ✅ 检查前置条件
- ✅ 自动执行 Hermes Chat
- ✅ 提取性能指标
- ✅ 对比优化前后的基准
- ✅ 评估是否达标

**预期输出**：
```
[1/5] 检查前置条件...
✅ Hermes 已安装
✅ state.db 存在
✅ powerelf-data-governance skill 已启用
✅ 批量脚本存在
✅ DB_URL 已配置

[2/5] 检查数据库连接...

[3/5] 启动 Hermes Chat...
Skill: powerelf-data-governance
Query: 帮我分级所有离线设备
正在执行...
✅ Hermes Chat 执行完成 (耗时: 15秒)

[4/5] 提取性能指标...

[5/5] 性能对比
优化前基准:
  耗时: 222 秒
  工具调用: 17 次
  输出 tokens: 12,811

当前测试结果:
  耗时: 15 秒
  工具调用: 1 次
  输出 tokens: 2,150

提升倍数:
  速度: 14.8×
  调用次数减少: 94.1%
  Token 减少: 83.2%

✅ 测试通过！批量脚本优化成功
```

---

### ⭐⭐ 方案 2：手动测试（详细对比，15 分钟）

**手动执行两次测试，直观对比效果**：

#### 步骤 1：执行新方案（批量分级）

```bash
# 启动 Hermes Chat
hermes chat -s powerelf-data-governance

# 在 Hermes Chat 中发送：
> 帮我分级所有离线设备
```

**预期输出**（< 30 秒）：
```markdown
## 离线设备分级分析结果

**统计时间**: 2026-07-28 15:30
**离线设备总数**: 504 台

### 分级汇总

- **CRITICAL**（严重离线（>24 小时））: 79 台
- **ERROR**（长期离线（4-24 小时））: 150 台
- **WARNING**（短期离线（1-4 小时））: 160 台
- **INFO**（轻度离线（<1 小时））: 115 台

### 详细列表

| 严重级别 | 设备名称 | 设备编码 | 离线时长(h) | ...
```

#### 步骤 2：提取性能指标

```bash
# 获取最新 session ID
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")

# 查看性能指标
sqlite3 ~/.hermes/state.db "
SELECT datetime(started_at, 'unixepoch', 'localtime') as start,
       ROUND((ended_at - started_at), 2) as duration_sec,
       tool_call_count,
       output_tokens
FROM sessions WHERE id = '$SESSION_ID';
"
```

#### 步骤 3：查看工具调用详情

```bash
# 查看工具调用记录
sqlite3 ~/.hermes/state.db "
SELECT timestamp,
       tool_name,
       substr(content, 1, 80) as preview
FROM messages
WHERE session_id = '$SESSION_ID' AND role = 'tool'
ORDER BY timestamp;
"
```

**预期结果**：应只有 1-2 条工具调用记录，调用 `classify_offline_by_duration.py`

---

### ⭐⭐⭐ 方案 3：完整对比测试（30 分钟）

**验证两次测试，量化优化效果**：

#### 测试 1：旧方案（逐站检测）— 作为基准

```bash
# 在一个终端执行
hermes chat -s powerelf-data-governance -q "请逐台检测离线设备：对 eq_equip_base 中 status=0 的每台设备执行离线检测"
```

记录指标（从 state.db 提取）：
- 耗时：___ 秒
- 工具调用：___ 次
- 输出 tokens：___

#### 测试 2：新方案（批量分级）— 验证优化

```bash
# 等待 1 分钟后执行
hermes chat -s powerelf-data-governance -q "帮我分级所有离线设备"
```

记录指标（从 state.db 提取）：
- 耗时：___ 秒
- 工具调用：___ 次
- 输出 tokens：___

#### 对比总结

| 指标 | 旧方案（基准） | 新方案（预期） | 实际提升 |
|------|--------------|--------------|---------|
| 耗时 | 222 秒 | < 30 秒 | ?× |
| 工具调用 | 17 次 | 1-2 次 | ?%↓ |
| 输出 tokens | 12,811 | < 3,000 | ?%↓ |

---

## 验收标准

| 指标 | 达标 | 预警 | 失败 |
|------|------|------|------|
| **耗时** | < 30 秒 | 30-60 秒 | > 60 秒 |
| **工具调用** | ≤ 2 次 | 3-5 次 | > 5 次 |
| **输出 tokens** | < 3,000 | 3,000-8,000 | > 8,000 |
| **中途停顿** | 无 | 5-10 秒 | > 10 秒 |

---

## 常见问题排查

### ❌ Hermes 没有调用批量脚本

**可能原因**：
1. Hermes 未识别"批量分级"意图
2. Hermes 未加载 `rules/offline-detection.md` 的"批量分级"章节

**排查步骤**：
```bash
# 1. 查看 system prompt（是否包含路由规则）
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
sqlite3 ~/.hermes/state.db "SELECT content FROM messages WHERE session_id = '$SESSION_ID' AND role = 'system';" | grep -A 3 "批量分级"

# 2. 查看工具调用记录
sqlite3 ~/.hermes/state.db "SELECT tool_name FROM messages WHERE session_id = '$SESSION_ID' AND role = 'tool';"
```

**解决方案**：
- 明确告诉 Hermes："使用 scripts/classify_offline_by_duration.py"
- 检查 `rules/offline-detection.md` 的"批量分级"章节是否清晰

---

### ❌ 批量脚本执行失败

**排查步骤**：
```bash
# 1. 手动测试脚本
source /home/scada/powerelf-skills/_shared/bootstrap.sh
python3 /home/scada/powerelf-skills/powerelf-data-governance/scripts/classify_offline_by_duration.py --db "$DB_URL"

# 2. 查看错误日志
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
sqlite3 ~/.hermes/state.db "SELECT content FROM messages WHERE session_id = '$SESSION_ID' AND role = 'tool' AND content LIKE '%Traceback%';"
```

---

### ❌ 性能未达预期

**排查步骤**：
```bash
# 1. 查看上下文大小（是否加载了完整 SKILL.md）
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
sqlite3 ~/.hermes/state.db "SELECT input_tokens FROM sessions WHERE id = '$SESSION_ID';"

# 如果 input_tokens > 50,000，说明加载了完整 SKILL.md（需要优化路由）

# 2. 查看消息时间线（是否有长时间停顿）
sqlite3 ~/.hermes/state.db "
SELECT timestamp,
       role,
       substr(content, 1, 50) as preview
FROM messages
WHERE session_id = '$SESSION_ID'
ORDER BY timestamp
LIMIT 20;
"
```

---

## 文档索引

| 文档 | 用途 |
|------|------|
| **快速开始（本文件）** | 快速验证方案 |
| [完整测试指南](./HERMES_TESTING_GUIDE.md) | 3 种详细测试方案 + 问题排查 |
| [优化分析报告](../../_shared/optimization_analysis_20260728.md) | 技术分析和优化建议 |
| [验证报告](../../_shared/verification_report_20260728.md) | 单元验证结果 |
| [批量分级规则](../rules/offline-detection.md) | 批量脚本使用文档 |

---

## 🎯 立即开始

**推荐从一键测试开始**：

```bash
bash /home/scada/powerelf-skills/powerelf-data-governance/tests/run_hermes_test.sh
```

只需 5 分钟即可验证批量脚本在 Hermes 环境下的实际表现！

---

**创建时间**: 2026-07-28
**更新**: 2026-07-28 15:00
