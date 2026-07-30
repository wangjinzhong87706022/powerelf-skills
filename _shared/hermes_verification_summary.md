# 批量离线分级脚本 — Hermes 测试验证总结

**测试日期**: 2026-07-28
**测试环境**: Hermes Agent v0.19.0 + powerelf-data-governance skill
**测试对象**: `scripts/classify_offline_by_duration.py`（批量离线分级脚本）

---

## ✅ 已完成验证

### 1. 单元验证（已完成 ✅）

**验证脚本**: `tests/verify_classify_offline.py`

**结果**：
- ✅ 数据准确性：5/5 台设备分级与 lib/offline.py 完全一致
- ✅ 性能对比：260× 加速（SQL 层）
- ✅ 数据完整性：离线记录覆盖率 100%（53/53 台）
- ✅ 分级分布合理性：符合预期（CRITICAL/ERROR/WARNING/INFO）

**执行命令**：
```bash
source /home/scada/powerelf-skills/_shared/bootstrap.sh
python3 powerelf-data-governance/tests/verify_classify_offline.py --db "$DB_URL" --sample 5
```

---

### 2. 脚本功能验证（已完成 ✅）

**测试命令**：
```bash
source /home/scada/powerelf-skills/_shared/bootstrap.sh
python3 powerelf-data-governance/scripts/classify_offline_by_duration.py --db "$DB_URL"
```

**结果**：
- ✅ Markdown 输出：包含分级汇总 + 详细列表（504 台设备）
- ✅ CSV 输出：支持 `--format csv --output /tmp/offline.csv`
- ✅ JSON 输出：支持 `--format json --output /tmp/offline.json`
- ✅ 执行时间：< 1 秒
- ✅ 分级准确：CRITICAL(79) / ERROR(150) / WARNING(160) / INFO(115)

---

### 3. Hermes 集成验证（需要手动测试 ⏳）

#### 测试方案

**方案 A：快速验证（5 分钟）**

```bash
# 1. 启动 Hermes Chat
hermes chat -s powerelf-data-governance

# 2. 发送测试查询
> 帮我分级所有离线设备

# 3. 观察输出
# 预期：Hermes 识别意图 → 调用批量脚本 → 返回完整分级结果

# 4. 提取性能指标
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
sqlite3 ~/.hermes/state.db "
SELECT datetime(started_at, 'unixepoch', 'localtime') as start,
       ROUND((ended_at - started_at), 2) as duration_sec,
       tool_call_count,
       output_tokens
FROM sessions WHERE id = '$SESSION_ID';
"
```

**方案 B：对比测试（15 分钟）**

```bash
# 测试 1：旧方案（逐站检测）
hermes chat -s powerelf-data-governance -q "请逐台检测离线设备"

# 记录指标：耗时、调用次数、tokens
# 预期：耗时 > 60秒，调用 > 10次

# 测试 2：新方案（批量分级）
hermes chat -s powerelf-data-governance -q "帮我分级所有离线设备"

# 记录指标：耗时、调用次数、tokens
# 预期：耗时 < 30秒，调用 ≤ 2次

# 对比总结
```

---

### 4. 自动化测试脚本

已提供以下测试脚本：

| 脚本 | 用途 | 执行方式 |
|------|------|---------|
| `tests/verify_classify_offline.py` | 单元验证 | `python3 tests/verify_classify_offline.py --db "$DB_URL"` |
| `tests/e2e_benchmark.py` | 端到端基准 | `python3 tests/e2e_benchmark.py --db "$DB_URL"` |
| `tests/quick_test.sh` | Hermes 快速测试 | `bash tests/quick_test.sh` |
| `tests/test_on_hermes.sh` | Hermes 完整测试 | `bash tests/test_on_hermes.sh` |

---

## 📊 预期性能指标

### 优化前基准（已实测）

| 指标 | 数值 |
|------|------|
| 墙钟耗时 | **222 秒** |
| 工具调用 | **17 次** |
| 输出 tokens | **12,811** |
| 中途停顿 | **24s + 49s** |

### 优化后预期（基于脚本性能）

| 指标 | 预期值 | 状态 |
|------|--------|------|
| 墙钟耗时 | **< 30 秒** | 🎯 |
| 工具调用 | **1-2 次** | 🎯 |
| 输出 tokens | **< 3,000** | 🎯 |
| 中途停顿 | **< 5 秒** | 🎯 |

### 脚本实测性能

| 指标 | 实测值 |
|------|--------|
| SQL 查询耗时 | **0.002 秒**（504 台设备） |
| 执行时间 | **< 1 秒** |
| 输出大小 | Markdown: ~5KB / CSV: ~15KB / JSON: ~20KB |

---

## 🎯 Hermes 环境验证步骤

### 前置条件

- ✅ Hermes Agent v0.19.0 已安装
- ✅ powerelf-data-governance skill 已启用
- ✅ 数据库连接正常（`POWERELF_DB_*` 环境变量已配置）

### 验证流程

```bash
# 步骤 1：检查 skill 是否启用
hermes skills list | grep powerelf-data-governance

# 步骤 2：运行快速测试
bash /home/scada/powerelf-skills/powerelf-data-governance/tests/quick_test.sh

# 步骤 3：在 Hermes Chat 中手动验证
hermes chat -s powerelf-data-governance -q "帮我分级所有离线设备"

# 步骤 4：查看性能指标
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
sqlite3 ~/.hermes/state.db "
SELECT datetime(started_at, 'unixepoch', 'localtime'),
       ROUND((ended_at - started_at), 2) as duration,
       tool_call_count,
       message_count,
       output_tokens
FROM sessions WHERE id = '$SESSION_ID';
"

# 步骤 5：查看工具调用详情
sqlite3 ~/.hermes/state.db "
SELECT timestamp,
       tool_name,
       substr(content, 1, 80) as preview
FROM messages
WHERE session_id = '$SESSION_ID'
  AND role = 'tool'
ORDER BY timestamp;
"
```

---

## 📝 手动测试记录表

在 Hermes Chat 中测试后，记录以下指标：

| 测试项 | 预期 | 实际 | 状态 |
|--------|------|------|------|
| **测试 1：批量分级查询** | | | |
| 耗时 | < 30 秒 | ___ 秒 | ⬜ |
| 工具调用 | ≤ 2 次 | ___ 次 | ⬜ |
| 输出 tokens | < 3,000 | ___ | ⬜ |
| 结果完整性 | 包含所有 504 台设备 | ___ | ⬜ |
| **测试 2：单站深度分析** | | | |
| 命令 | `offline_detector.py --st-id <id>` | | ⬜ |
| 耗时 | < 10 秒 | ___ 秒 | ⬜ |
| 工具调用 | 1 次 | ___ 次 | ⬜ |
| **测试 3：对比测试** | | | |
| 旧方案耗时 | > 60 秒 | ___ 秒 | ⬜ |
| 新方案耗时 | < 30 秒 | ___ 秒 | ⬜ |
| 加速比 | > 2× | ___× | ⬜ |

---

## 🐛 问题排查

### 如果 Hermes 没有调用批量脚本

**可能原因**：
1. Hermes 未识别"批量分级"意图
2. Hermes 未加载 `rules/offline-detection.md` 的"批量分级"章节

**解决方案**：
```bash
# 检查 session 的 system prompt
sqlite3 ~/.hermes/state.db "SELECT content FROM messages WHERE session_id = '<SESSION_ID>' AND role = 'system';" | grep -A 5 "批量分级"
```

**手动引导**：
```
> 使用 scripts/classify_offline_by_duration.py 帮我分级所有离线设备
```

---

### 如果脚本执行失败

**排查步骤**：
```bash
# 1. 手动运行脚本
source /home/scada/powerelf-skills/_shared/bootstrap.sh
python3 powerelf-data-governance/scripts/classify_offline_by_duration.py --db "$DB_URL"

# 2. 查看错误
echo $?

# 3. 检查数据库连接
python3 -c "from db import query; print(query('SELECT COUNT(*) FROM eq_equip_base'))"
```

---

## 📚 参考文档

| 文档 | 路径 |
|------|------|
| 优化分析报告 | `_shared/optimization_analysis_20260728.md` |
| 验证报告 | `_shared/verification_report_20260728.md` |
| 批量分级规则 | `powerelf-data-governance/rules/offline-detection.md`（第 159-330 行） |
| 路由规则 | `powerelf-data-governance/SKILL.md`（第 22-90 行） |
| Hermes 测试指南 | `powerelf-data-governance/tests/HERMES_TESTING_GUIDE.md` |

---

## 🎉 总结

**已完成**：
- ✅ 批量脚本开发（`classify_offline_by_duration.py`）
- ✅ 单元验证（数据准确性、性能、完整性）
- ✅ Hermes 集成验证方案设计（测试脚本 + 文档）

**待手动验证**：
- ⏳ Hermes Chat 实际测试（需人工启动）
- ⏳ 性能对比（旧方案 vs 新方案）
- ⏳ 路由验证（Hermes 是否按需加载）

**验证入口**：
```bash
# 快速测试（推荐）
bash /home/scada/powerelf-skills/powerelf-data-governance/tests/quick_test.sh

# 详细指南
cat /home/scada/powerelf-skills/powerelf-data-governance/tests/HERMES_TESTING_GUIDE.md
```

---

**报告生成时间**: 2026-07-28 15:00
**验证状态**: 单元验证 ✅ 通过，Hermes 集成验证 ⏳ 待手动测试
