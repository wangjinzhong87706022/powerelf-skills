#!/bin/bash
# -*- coding: utf-8 -*-
"""
快速验证：一键测试批量脚本在 Hermes 环境下的表现

用法:
  bash quick_test.sh

输出:
  - 自动启动 hermes chat
  - 发送测试查询
  - 提取性能指标
  - 生成对比报告
"""

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SKILL="powerelf-data-governance"
QUERY="帮我分级所有离线设备"
STATE_DB="$HOME/.hermes/state.db"

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Hermes 批量脚本快速测试              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"

# 检查 state.db
if [ ! -f "$STATE_DB" ]; then
    echo -e "${RED}❌ state.db 不存在${NC}"
    exit 1
fi

echo -e "\n${YELLOW}正在启动 Hermes Chat...${NC}"
echo -e "Skill: $SKILL"
echo -e "Query: $QUERY"
echo -e "\n${YELLOW}请在新终端手动执行:${NC}"
echo -e "  ${GREEN}hermes chat -s $SKILL -q \"$QUERY\"${NC}"
echo -e "\n${YELLOW}或使用非交互模式:${NC}"
echo -e "  ${GREEN}hermes chat -s $SKILL -q \"$QUERY\" --quiet --max-turns 3${NC}"

echo -e "\n${YELLOW}测试完成后按 Enter 提取指标...${NC}"
read

# 提取最新 session
LATEST_SESSION=$(sqlite3 "$STATE_DB" "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")

if [ -z "$LATEST_SESSION" ]; then
    echo -e "${RED}❌ 未找到 session${NC}"
    exit 1
fi

echo -e "\n${GREEN}Session ID: $LATEST_SESSION${NC}"

# 提取指标
START_TIME=$(sqlite3 "$STATE_DB" "SELECT datetime(started_at, 'unixepoch', 'localtime') FROM sessions WHERE id = '$LATEST_SESSION';")
DURATION=$(sqlite3 "$STATE_DB" "SELECT ROUND((ended_at - started_at), 2) FROM sessions WHERE id = '$LATEST_SESSION';")
TOOLS=$(sqlite3 "$STATE_DB" "SELECT tool_call_count FROM sessions WHERE id = '$LATEST_SESSION';")
MESSAGES=$(sqlite3 "$STATE_DB" "SELECT message_count FROM sessions WHERE id = '$LATEST_SESSION';")
TOKENS=$(sqlite3 "$STATE_DB" "SELECT output_tokens FROM sessions WHERE id = '$LATEST_SESSION';")

echo -e "\n${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   性能指标                              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"

echo -e "  开始时间: $START_TIME"
echo -e "  耗时: ${DURATION}秒"
echo -e "  工具调用: ${TOOLS}次"
echo -e "  消息数: ${MESSAGES}条"
echo -e "  输出tokens: ${TOKENS}"

# 对比基准
echo -e "\n${YELLOW}对比优化前基准:${NC}"
echo -e "  基准: 222秒 / 17次调用 / 12,811 tokens"

if [ -n "$DURATION" ] && [ "$(echo "$DURATION > 0" | bc)" -eq 1 ]; then
    SPEEDUP=$(echo "scale=1; 222 / $DURATION" | bc)
    TOOL_REDUCTION=$(echo "scale=1; 100 * (17 - $TOOLS) / 17" | bc)

    echo -e "\n${GREEN}提升倍数:${NC}"
    echo -e "  速度: ${SPEEDUP}×"
    echo -e "  调用次数减少: ${TOOL_REDUCTION}%"
fi

# 评估
echo -e "\n${YELLOW}评估:${NC}"

if [ "$TOOLS" -le 2 ] 2>/dev/null; then
    echo -e "  ${GREEN}✅ 工具调用次数达标 (≤2次)${NC}"
elif [ "$TOOLS" -le 5 ] 2>/dev/null; then
    echo -e "  ${YELLOW}⚠️  工具调用次数偏多 (3-5次)${NC}"
else
    echo -e "  ${RED}❌ 工具调用次数过多 (>5次)${NC}"
fi

if [ -n "$DURATION" ] && [ "$(echo "$DURATION < 30" | bc)" -eq 1 ]; then
    echo -e "  ${GREEN}✅ 耗时达标 (<30秒)${NC}"
elif [ -n "$DURATION" ] && [ "$(echo "$DURATION < 60" | bc)" -eq 1 ]; then
    echo -e "  ${YELLOW}⚠️  耗时偏长 (30-60秒)${NC}"
else
    echo -e "  ${RED}❌ 耗时过长 (>60秒)${NC}"
fi

# 查看工具调用详情
echo -e "\n${YELLOW}工具调用详情:${NC}"
sqlite3 "$STATE_DB" -header -column "
SELECT timestamp,
       datetime(timestamp, 'unixepoch', 'localtime') as time,
       tool_name,
       substr(content, 1, 50) as preview
FROM messages
WHERE session_id = '$LATEST_SESSION'
  AND role = 'tool'
ORDER BY timestamp;
" | head -20

echo -e "\n${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   测试完成                              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
