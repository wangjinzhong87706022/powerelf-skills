#!/bin/bash
# -*- coding: utf-8 -*-
"""
在 Hermes 环境下测试验证批量离线分级脚本

测试步骤:
1. 启动 hermes chat 并指定 data-governance skill
2. 发送测试查询："帮我分级所有离线设备"
3. 记录 session ID
4. 从 state.db 提取性能指标
5. 对比优化前后的差异

用法:
  bash test_on_hermes.sh
"""

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Hermes 环境测试验证${NC}"
echo -e "${GREEN}========================================${NC}"

# 配置
SKILL_NAME="powerelf-data-governance"
TEST_QUERY="帮我分级所有离线设备"
STATE_DB="$HOME/.hermes/state.db"
SESSION_FILE="/tmp/hermes_test_session.txt"

# 检查 state.db 是否存在
if [ ! -f "$STATE_DB" ]; then
    echo -e "${RED}❌ state.db 不存在: $STATE_DB${NC}"
    exit 1
fi

echo -e "\n${YELLOW}准备启动 Hermes Chat...${NC}"
echo -e "Skill: $SKILL_NAME"
echo -e "测试查询: $TEST_QUERY"
echo -e "\n${YELLOW}请在新终端执行以下命令:${NC}"
echo -e "  ${GREEN}hermes chat -s $SKILL_NAME -q \"$TEST_QUERY\"${NC}"
echo -e "\n${YELLOW}测试完成后，将 session ID 保存到: $SESSION_FILE${NC}"
echo -e "可以从 state.db 中提取: sqlite3 $STATE_DB \"SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;\""
echo -e "\n按 Enter 继续..."
read

# 等待用户输入 session ID
echo -e "\n${YELLOW}请输入 Session ID (或留空自动提取最新 session):${NC}"
read -r SESSION_ID

if [ -z "$SESSION_ID" ]; then
    # 自动提取最新 session
    SESSION_ID=$(sqlite3 "$STATE_DB" "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")
    echo -e "自动提取到最新 session: $SESSION_ID"
fi

# 保存 session ID
echo "$SESSION_ID" > "$SESSION_FILE"

# 验证 session 是否存在
SESSION_EXISTS=$(sqlite3 "$STATE_DB" "SELECT COUNT(*) FROM sessions WHERE id = '$SESSION_ID';")

if [ "$SESSION_EXISTS" -eq 0 ]; then
    echo -e "${RED}❌ Session 不存在: $SESSION_ID${NC}"
    exit 1
fi

echo -e "\n${GREEN}✅ Session 已保存: $SESSION_ID${NC}"

# 提取性能指标
echo -e "\n${YELLOW}正在提取性能指标...${NC}"

# 查询 session 信息
SESSION_INFO=$(sqlite3 "$STATE_DB" "SELECT datetime(started_at, 'unixepoch', 'localtime'), datetime(ended_at, 'unixepoch', 'localtime'), (ended_at - started_at) as duration, tool_call_count, message_count, output_tokens FROM sessions WHERE id = '$SESSION_ID';")

echo -e "\n${GREEN}Session 信息:${NC}"
echo "$SESSION_INFO" | while read start end duration tools messages tokens; do
    echo -e "  开始时间: $start"
    echo -e "  结束时间: $end"
    echo -e "  耗时: ${duration}秒"
    echo -e "  工具调用: ${tools}次"
    echo -e "  消息数: ${messages}条"
    echo -e "  输出tokens: ${tokens}"
done

# 计算耗时
DURATION=$(sqlite3 "$STATE_DB" "SELECT ROUND((ended_at - started_at), 2) FROM sessions WHERE id = '$SESSION_ID';")
TOOLS=$(sqlite3 "$STATE_DB" "SELECT tool_call_count FROM sessions WHERE id = '$SESSION_ID';")
MESSAGES=$(sqlite3 "$STATE_DB" "SELECT message_count FROM sessions WHERE id = '$SESSION_ID';")
TOKENS=$(sqlite3 "$STATE_DB" "SELECT output_tokens FROM sessions WHERE id = '$SESSION_ID';")

# 对比基准数据
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}性能对比${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n优化前基准 (20260728_084051_fca604):"
echo -e "  耗时: 222秒"
echo -e "  工具调用: 17次"
echo -e "  消息数: 36条"
echo -e "  输出tokens: 12,811"

echo -e "\n当前测试结果:"
echo -e "  耗时: ${DURATION}秒"
echo -e "  工具调用: ${TOOLS}次"
echo -e "  消息数: ${MESSAGES}条"
echo -e "  输出tokens: ${TOKENS}"

# 计算提升
if [ "$DURATION" != "" ] && [ "$(echo "$DURATION > 0" | bc)" -eq 1 ]; then
    SPEEDUP=$(echo "scale=1; 222 / $DURATION" | bc)
    TOOL_REDUCTION=$(echo "scale=1; 100 * (17 - $TOOLS) / 17" | bc)
    TOKEN_REDUCTION=$(echo "scale=1; 100 * (12811 - $TOKENS) / 12811" | bc)

    echo -e "\n提升倍数:"
    echo -e "  速度: ${SPEEDUP}×"
    echo -e "  调用次数减少: ${TOOL_REDUCTION}%"
    echo -e "  Token 减少: ${TOKEN_REDUCTION}%"
fi

# 保存报告
REPORT_FILE="/tmp/hermes_test_report_$(date +%Y%m%d_%H%M%S).md"
cat > "$REPORT_FILE" <<EOF
# Hermes 环境测试报告

**测试时间**: $(date '+%Y-%m-%d %H:%M:%S')
**Session ID**: $SESSION_ID
**Skill**: $SKILL_NAME
**测试查询**: $TEST_QUERY

## 性能指标

| 指标 | 值 |
|------|----|
| 耗时 | ${DURATION}秒 |
| 工具调用 | ${TOOLS}次 |
| 消息数 | ${MESSAGES}条 |
| 输出tokens | ${TOKENS} |

## 对比基准

| 指标 | 优化前 | 当前 | 提升 |
|------|--------|------|------|
| 耗时 | 222秒 | ${DURATION}秒 | ${SPEEDUP:-N/A}× |
| 工具调用 | 17次 | ${TOOLS}次 | ${TOOL_REDUCTION:-N/A}%↓ |
| 输出tokens | 12,811 | ${TOKENS} | ${TOKEN_REDUCTION:-N/A}%↓ |

## 结论

$(if [ "$TOOLS" -lt 5 ]; then echo "✅ **优化成功**: 工具调用次数大幅减少"; else echo "⚠️ **需要优化**: 工具调用次数仍较多"; fi)

$(if [ "$DURATION" \< "60" ]; then echo "✅ **速度达标**: 耗时 < 60秒"; else echo "⚠️ **速度偏慢**: 耗时 > 60秒"; fi)

---
由 test_on_hermes.sh 自动生成
EOF

echo -e "\n${GREEN}✅ 报告已保存: $REPORT_FILE${NC}"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}测试完成${NC}"
echo -e "${GREEN}========================================${NC}"
