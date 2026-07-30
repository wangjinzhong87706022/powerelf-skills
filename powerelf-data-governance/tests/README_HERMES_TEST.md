# Hermes 测试验证指南 — 批量离线分级脚本

## 🎯 测试目标

验证批量离线分级脚本在 Hermes 环境下的实际表现，确认优化效果：
- ✅ 功能性：脚本能正确执行，分级结果准确
- ✅ 性能：耗时 < 30 秒，调用 ≤ 2 次
- ✅ 路由：Hermes 按需加载，不加载完整 SKILL.md

---

## 📋 测试方案（三选一）

### 方案 1：快速验证（5 分钟） ⭐⭐⭐⭐⭐

**直接运行测试脚本**：

```bash
bash /home/scada/powerelf-skills/powerelf-data-governance/tests/quick_test.sh
```

**流程**：
1. 脚本提示启动 Hermes Chat
2. 在新终端执行：`hermes chat -s powerelf-data-governance`
3. 发送查询："帮我分级所有离线设备"
4. 按 Enter 提取性能指标
5. 自动生成对比报告

**预期结果**：
- 耗时 < 30 秒
- 工具调用 ≤ 2 次
- 输出包含完整的 Markdown 表格

---

### 方案 2：详细对比（15 分钟）⭐⭐⭐⭐

**执行两次测试对比**：

**测试 1：旧方案（逐站检测）**
```bash
hermes chat -s powerelf-data-governance -q "请逐台检测离线设备：对 eq_equip_base 中 status=0 的每台设备执行离线检测"
```
记录指标：耗时、调用次数、tokens

**测试 2：新方案（批量分级）**
```bash
hermes chat -s powerelf-data-governance -q "帮我分级所有离线设备"
```
记录指标：耗时、调用次数、tokens

**对比总结**：

| 指标 | 旧方案（基准） | 新方案 | 提升 |
|------|--------------|--------|------|
| 耗时 | 222 秒 | ? 秒 | ?× |
| 工具调用 | 17 次 | ? 次 | ?%↓ |
| 输出 tokens | 12,811 | ? | ?%↓ |

---

### 方案 3：完整测试流程（30 分钟）⭐⭐⭐

**包含所有验证项**：

```bash
# 1. 单元验证（已通过 ✅）
python3 /home/scada/powerelf-skills/powerelf-data-governance/tests/verify_classify_offline.py --db "$DB_URL"

# 2. Hermes 集成测试
bash /home/scada/powerelf-skills/powerelf-data-governance/tests/test_on_hermes.sh

# 3. 查看详细报告
cat /home/scada/powerelf-skills/_shared/hermes_verification_summary.md
```

---

## 🚀 快速开始

### 前置条件

- ✅ Hermes Agent v0.19.0 已安装
- ✅ powerelf-data-governance skill 已启用
- ✅ 数据库连接正常

### 一键测试

```bash
# 方法 A：非交互模式（推荐，自动执行）
timeout 120 hermes chat -s powerelf-data-governance -q "帮我分级所有离线设备" --quiet --max-turns 3

# 方法 B：交互模式（可观察过程）
hermes chat -s powerelf-data-governance
```

---

## 📊 验证检查清单

### Hermes Chat 执行后检查

```bash
# 1. 获取最新 session
SESSION_ID=$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")

# 2. 查看性能指标
sqlite3 ~/.hermes/state.db -header -column "
SELECT datetime(started_at, 'unixepoch', 'localtime') as start,
       ROUND((ended_at - started_at), 2) as duration_sec,
       tool_call_count,
       message_count,
       output_tokens
FROM sessions WHERE id = '$SESSION_ID';
"

# 3. 查看工具调用详情
sqlite3 ~/.hermes/state.db "
SELECT timestamp,
       tool_name,
       substr(content, 1, 80) as preview
FROM messages
WHERE session_id = '$SESSION_ID' AND role = 'tool'
ORDER BY timestamp;
"
```

### 验收标准

| 指标 | 达标 | 预警 | 失败 |
|------|------|------|------|
| **耗时** | < 30 秒 | 30-60 秒 | > 60 秒 |
| **工具调用** | ≤ 2 次 | 3-5 次 | > 5 次 |
| **输出 tokens** | < 3,000 | 3,000-8,000 | > 8,000 |
| **中途停顿** | 无 | 5-10 秒 | > 10 秒 |

---

## 📚 参考文档

| 文档 | 说明 |
|------|------|
| [优化分析报告](./_shared/optimization_analysis_20260728.md) | 详细的技术分析和优化建议 |
| [验证报告](./_shared/verification_report_20260728.md) | 单元验证结果（数据准确性、性能、完整性） |
| [Hermes 测试指南](./powerelf-data-governance/tests/HERMES_TESTING_GUIDE.md) | 完整的测试方案（含问题排查） |
| [批量分级规则](./powerelf-data-governance/rules/offline-detection.md) | 批量脚本的使用文档（第 159-330 行） |

---

## 🎉 测试完成

**单元验证状态**：✅ **所有测试通过**

| 验证项 | 状态 |
|--------|------|
| 数据准确性 | ✅ 5/5 台设备分级一致 |
| 性能对比 | ✅ 260× 加速（SQL 层） |
| 数据完整性 | ✅ 覆盖率 100% |
| 分级分布合理性 | ✅ 符合预期 |

**Hermes 集成验证**：⏳ **待手动测试**

**推荐下一步**：
```bash
# 运行快速测试
bash /home/scada/powerelf-skills/powerelf-data-governance/tests/quick_test.sh
```

---

**创建时间**: 2026-07-28
**最后更新**: 2026-07-28 15:00
