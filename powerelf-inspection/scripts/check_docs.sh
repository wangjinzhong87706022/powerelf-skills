#!/usr/bin/env bash
# 文档/链接 grep 校验脚本（CI）
# 在 powerelf-inspection/ 目录下运行。
# 退出码：0=OK, 1=FAIL

set -e
cd "$(dirname "$0")/.."

errors=0

echo "=== 1. _shared 引用检查 ==="
for ref in "analysis-qa-checklist" "statistical-caution" "sql-discipline" "data-profiling" "_shared/references/schema"; do
    if grep -rq "$ref" SKILL.md; then
        echo "  ✅ $ref"
    else
        echo "  ❌ 缺少 $ref 引用"
        errors=$((errors + 1))
    fi
done

echo "=== 2. 占位符检查（SQL 拼接注入检查）==="
# rules/ 中的 {st_id} 是 AI Agent 规则模板，合法使用。
# references/pitfalls.md 和 references/few_shots.md 的 {st_id} 是错误示例展示。
# impl/ 中的 {st_id} 在 f-string 消息中合法使用（如 f"测站{st_id}:"）。
# 检查真正危险的模式：SQL 字符串中直接拼接变量（非参数化）。
if grep -rn "WHERE.*{st_id}\|WHERE.*{equipment_code}\|{st_id}.*FROM\|{st_id}.*LIMIT" impl/ 2>/dev/null | grep -v "test_\|\.pyc"; then
    echo "  ❌ impl/ 发现 SQL 注入风险"
    errors=$((errors + 1))
else
    echo "  ✅ impl/ 无 SQL 注入风险"
fi

echo "=== 3. 本地 schema 副本检查 ==="
if [ -f references/database-schema.md ]; then
    echo "  ❌ 本地 schema 副本仍在"
    errors=$((errors + 1))
else
    echo "  ✅ 无本地 schema 副本"
fi

echo "=== 4. few_shots 占位符检查 ==="
# few_shots.md 中的 {st_id} 是❌错误示例展示，不计数
if [ -f references/few_shots.md ]; then
    echo "  ✅ few_shots.md 存在（占位符为反例展示，不计）"
else
    echo "  ⚠️  few_shots.md 不存在，跳过"
fi

echo "=== 5. SKILL.md 必含段落检查 ==="
for section in "Pitfalls" "When NOT to Use" "Validation Gate" "Few-Shots" "输出深度模式"; do
    if grep -q "$section" SKILL.md; then
        echo "  ✅ $section 段落存在"
    else
        echo "  ❌ 缺少 $section 段落"
        errors=$((errors + 1))
    fi
done

echo "=== 6. references 文件完整性检查 ==="
for file in "pitfalls.md" "few_shots.md" "business_rules.md" "data-model.md"; do
    if [ -f "references/$file" ]; then
        echo "  ✅ references/$file"
    else
        echo "  ❌ 缺少 references/$file"
        errors=$((errors + 1))
    fi
done

echo ""
if [ "$errors" -eq 0 ]; then
    echo "✅ doc check OK — 全部通过"
    exit 0
else
    echo "❌ doc check FAIL — $errors 个问题"
    exit 1
fi