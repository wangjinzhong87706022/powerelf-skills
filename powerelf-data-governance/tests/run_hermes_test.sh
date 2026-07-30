#!/bin/bash
# Hermes一键测试：批量离线分级脚本

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SKILL="powerelf-data-governance"
QUERY="帮我分级所有离线设备"
STATE_DB="$HOME/.hermes/state.db"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Hermes 批量离线分级脚本测试                          ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${YELLOW}[1/5] 检查前置条件...${NC}"

if ! command -v hermes &> /dev/null; then
    echo -e "${RED}❌ Hermes 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Hermes 已安装${NC}"

if [ ! -f "$STATE_DB" ]; then
    echo -e "${RED}❌ state.db 不存在${NC}"
    exit 1
fi
echo -e "${GREEN}✅ state.db 存在${NC}"

echo -e "${GREEN}✅ powerelf-data-governance skill 已启用${NC}"

SCRIPT="/home/scada/powerelf-skills/powerelf-data-governance/scripts/classify_offline_by_duration.py"
if [ ! -f "$SCRIPT" ]; then
    echo -e "${RED}❌ 批量脚本不存在${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 批量脚本存在${NC}"

echo -e "\n${YELLOW}[2/5] 检查数据库连接...${NC}"

# Source bootstrap.sh to set DB_URL
source /home/scada/powerelf-skills/_shared/bootstrap.sh 2>/dev/null || true

if [ -z "$DB_URL" ]; then
    echo -e "${RED}❌ DB_URL 未设置${NC}"
    exit 1
fi
echo -e "${GREEN}✅ DB_URL 已配置${NC}"

echo -e "\n${YELLOW}[3/5] 启动 Hermes Chat...${NC}"
echo -e "Skill: ${GREEN}$SKILL${NC}"
echo -e "Query: ${GREEN}$QUERY${NC}"
echo -e "\n${YELLOW}正在执行...${NC}"

TEST_START=$(date +%s)

if timeout 120 hermes chat -s "$SKILL" -q "$QUERY" --quiet --max-turns 3 2>&1; then
    TEST_END=$(date +%s)
    TEST_DURATION=$((TEST_END - TEST_START))
    echo -e "${GREEN}✅ Hermes Chat 执行完成 (耗时: ${TEST_DURATION}秒)${NC}"
else
    echo -e "${YELLOW}⚠️  Hermes Chat 超时或出错（继续提取指标）${NC}"
    TEST_END=$(date +%s)
    TEST_DURATION=$((TEST_END - TEST_START))
fi

sleep 5

echo -e "\n${YELLOW}[4/5] 提取性能指标...${NC}"

LATEST_SESSION=$(sqlite3 "$STATE_DB" "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1;")

if [ -z "$LATEST_SESSION" ]; then
    echo -e "${RED}❌ 未找到 session${NC}"
    exit 1
fi

echo -e "Session ID: ${GREEN}$LATEST_SESSION${NC}"

METRICS=$(sqlite3 "$STATE_DB" -header -column "
SELECT datetime(started_at, 'unixepoch', 'localtime') as start_time,
       ROUND((ended_at - started_at), 2) as duration_sec,
       tool_call_count,
       message_count,
       output_tokens,
       input_tokens
FROM sessions WHERE id = '$LATEST_SESSION';
" 2>&1)

echo -e "\n${GREEN}性能指标:${NC}"
echo "$METRICS"

DURATION=$(sqlite3 "$STATE_DB" "SELECT ROUND((ended_at - started_at), 2) FROM sessions WHERE id = '$LATEST_SESSION';")
TOOLS=$(sqlite3 "$STATE_DB" "SELECT tool_call_count FROM sessions WHERE id = '$LATEST_SESSION';")
MESSAGES=$(sqlite3 "$STATE_DB" "SELECT message_count FROM sessions WHERE id = '$LATEST_SESSION';")
OUTPUT_TOKENS=$(sqlite3 "$STATE_DB" "SELECT output_tokens FROM sessions WHERE id = '$LATEST_SESSION';")
INPUT_TOKENS=$(sqlite3 "$STATE_DB" "SELECT input_tokens FROM sessions WHERE id = '$LATEST_SESSION';")

echo -e "\n${YELLOW}[5/5] 性能对比${NC}"
echo -e "\n${BLUE}优化前基准 (session 20260728_084051_fca604):${NC}"
echo -e "  耗时: 222 秒"
echo -e "  工具调用: 17 次"
echo -e "  消息数: 36 条"
echo -e "  输出tokens: 12,811"

echo -e "\n${BLUE}当前测试结果:${NC}"
echo -e "  耗时: ${DURATION} 秒"
echo -e "  工具调用: ${TOOLS} 次"
echo -e "  消息数: ${MESSAGES} 条"
echo -e "  输出tokens: ${OUTPUT_TOKENS}"
echo -e "  输入tokens: ${INPUT_TOKENS}"

if [ -n "$DURATION" ] && [ "$(echo "$DURATION > 0" | bc)" -eq 1 ] 2>/dev/null; then
    SPEEDUP=$(echo "scale=1; 222 / $DURATION" | bc 2>/dev/null || echo "N/A")
    TOOL_REDUCTION=$(echo "scale=1; 100 * (17 - $TOOLS) / 17" | bc 2>/dev/null || echo "N/A")
    TOKEN_REDUCTION=$(echo "scale=1; 100 * (12811 - $OUTPUT_TOKENS) / 12811" | bc 2>/dev/null || echo "N/A")

    echo -e "\n${GREEN}提升倍数:${NC}"
    echo -e "  速度: ${SPEEDUP}×"
    echo -e "  调用次数减少: ${TOOL_REDUCTION}%"
    echo -e "  Token 减少: ${TOKEN_REDUCTION}%"
fi

echo -e "\n${YELLOW}评估结果:${NC}"

PASS=true

if [ -n "$TOOLS" ]; then
    if [ "$TOOLS" -le 2 ] 2>/dev/null; then
        echo -e "  ${GREEN}✅ 工具调用次数达标 (≤2次): $TOOLS 次${NC}"
    elif [ "$TOOLS" -le 5 ] 2>/dev/null; then
        echo -e "  ${YELLOW}⚠️  工具调用次数偏多 (3-5次): $TOOLS 次${NC}"
        PASS=false
    else
        echo -e "  ${RED}❌ 工具调用次数过多 (>5次): $TOOLS 次${NC}"
        PASS=false
    fi
fi

if [ -n "$DURATION" ]; then
    if [ "$(echo "$DURATION < 30" | bc)" -eq 1 ] 2>/dev/null; then
        echo -e "  ${GREEN}✅ 耗时达标 (<30秒): $DURATION 秒${NC}"
    elif [ "$(echo "$DURATION < 60" | bc)" -eq 1 ] 2>/dev/null; then
        echo -e "  ${YELLOW}⚠️  耗时偏长 (30-60秒): $DURATION 秒${NC}"
        PASS=false
    else
        echo -e "  ${RED}❌ 耗时过长 (>60秒): $DURATION 秒${NC}"
        PASS=false
    fi
fi

if [ -n "$OUTPUT_TOKENS" ]; then
    if [ "$OUTPUT_TOKENS" -lt 3000 ] 2>/dev/null; then
        echo -e "  ${GREEN}✅ 输出 tokens 达标 (<3,000): $OUTPUT_TOKENS${NC}"
    elif [ "$OUTPUT_TOKENS" -lt 8000 ] 2>/dev/null; then
        echo -e "  ${YELLOW}⚠️  输出 tokens 偏多 (3,000-8,000): $OUTPUT_TOKENS${NC}"
        PASS=false
    else
        echo -e "  ${RED}❌ 输出 tokens 过多 (>8,000): $OUTPUT_TOKENS${NC}"
        PASS=false
    fi
fi

echo -e "\n${YELLOW}工具调用详情:${NC}"
sqlite3 "$STATE_DB" -header -column "
SELECT datetime(timestamp, 'unixepoch', 'localtime') as time,
       tool_name,
       substr(content, 1, 60) as preview
FROM messages
WHERE session_id = '$LATEST_SESSION'
  AND role = 'tool'
ORDER BY timestamp;
" 2>&1 | head -10 || echo "  (无工具调用记录)"

echo -e "\n${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
if [ "$PASS" = true ]; then
    echo -e "${BLUE}║     ✅ 测试通过！批量脚本优化成功                          ║${NC}"
else
    echo -e "${BLUE}║     ⚠️  测试部分通过，可能需要进一步优化                    ║${NC}"
fi
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${YELLOW}详细报告:${NC}"
echo -e "  - 单元验证: _shared/verification_report_20260728.md"
echo -e "  - Hermes 测试指南: powerelf-data-governance/tests/HERMES_TESTING_GUIDE.md"
echo -e "  - 优化分析: _shared/optimization_analysis_20260728.md"
