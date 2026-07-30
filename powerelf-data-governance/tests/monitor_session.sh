#!/bin/bash
# 监控 Hermes session 性能指标

SESSION_ID="${1:-$(sqlite3 ~/.hermes/state.db "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")}"

if [ -z "$SESSION_ID" ]; then
    echo "❌ 未找到 session"
    exit 1
fi

echo "Session ID: $SESSION_ID"
echo ""

sqlite3 ~/.hermes/state.db -header -column "
SELECT
    datetime(started_at, 'unixepoch', 'localtime') as start_time,
    datetime(ended_at, 'unixepoch', 'localtime') as end_time,
    ROUND((ended_at - started_at), 2) as duration_sec,
    tool_call_count,
    message_count,
    output_tokens,
    input_tokens,
    CAST(output_tokens AS FLOAT) / NULLIF(message_count, 0) as tokens_per_msg
FROM sessions WHERE id = '$SESSION_ID';
"

echo ""
echo "=== 评估 ==="

DURATION=$(sqlite3 ~/.hermes/state.db "SELECT ROUND((ended_at - started_at), 2) FROM sessions WHERE id = '$SESSION_ID';")
TOOLS=$(sqlite3 ~/.hermes/state.db "SELECT tool_call_count FROM sessions WHERE id = '$SESSION_ID';")
OUTPUT_TOKENS=$(sqlite3 ~/.hermes/state.db "SELECT output_tokens FROM sessions WHERE id = '$SESSION_ID';")
INPUT_TOKENS=$(sqlite3 ~/.hermes/state.db "SELECT input_tokens FROM sessions WHERE id = '$SESSION_ID';")

echo "工具调用: $TOOLS 次 $(if [ "$TOOLS" -le 2 ] 2>/dev/null; then echo '✅'; elif [ "$TOOLS" -le 5 ] 2>/dev/null; then echo '⚠️'; else echo '❌'; fi)"
echo "输出 tokens: $OUTPUT_TOKENS $(if [ "$OUTPUT_TOKENS" -lt 3000 ] 2>/dev/null; then echo '✅'; elif [ "$OUTPUT_TOKENS" -lt 8000 ] 2>/dev/null; then echo '⚠️'; else echo '❌'; fi)"
echo "输入 tokens: $INPUT_TOKENS $(if [ "$INPUT_TOKENS" -lt 15000 ] 2>/dev/null; then echo '✅'; elif [ "$INPUT_TOKENS" -lt 30000 ] 2>/dev/null; then echo '⚠️'; else echo '❌'; fi)"
echo "耗时: ${DURATION}秒 $(if [ "$(echo "$DURATION < 30" | bc)" -eq 1 ] 2>/dev/null; then echo '✅'; elif [ "$(echo "$DURATION < 60" | bc)" -eq 1 ] 2>/dev/null; then echo '⚠️'; else echo '❌'; fi)"
