#!/bin/bash
# 真实场景测试：模拟用户日常使用

set -e

SKILL="powerelf-data-governance"
STATE_DB="$HOME/.hermes/state.db"

echo "=== 真实场景测试 ==="
echo ""

# 场景 1：快速查询（用户想知道大概情况）
echo "场景 1：快速查询"
echo "Query: 有多少设备离线？"
timeout 60 hermes chat -s "$SKILL" -q "有多少设备离线？" --quiet --max-turns 2 2>&1 | tail -20
echo ""
sleep 3

# 场景 2：深度分析（用户想知道详细信息）
echo "场景 2：深度分析"
echo "Query: 帮我分析最严重的几个离线设备"
timeout 60 hermes chat -s "$SKILL" -q "帮我分析最严重的几个离线设备" --quiet --max-turns 2 2>&1 | tail -20
echo ""
sleep 3

# 场景 3：导出需求（用户需要数据）
echo "场景 3：导出需求"
echo "Query: 导出所有离线设备到 CSV"
timeout 60 hermes chat -s "$SKILL" -q "导出所有离线设备到 CSV 文件 /tmp/offline_devices.csv" --quiet --max-turns 3 2>&1 | tail -20
echo ""

# 提取性能指标
LATEST_SESSION=$(sqlite3 "$STATE_DB" "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
echo "最新 Session: $LATEST_SESSION"
echo ""

sqlite3 "$STATE_DB" -header -column "
SELECT datetime(started_at, 'unixepoch', 'localtime') as start,
       ROUND((ended_at - started_at), 2) as duration,
       tool_call_count,
       output_tokens,
       input_tokens
FROM sessions WHERE id IN (
    SELECT id FROM sessions ORDER BY started_at DESC LIMIT 3
)
ORDER BY started_at DESC;
"
