# eval_cases — 静态评测用例（Phase 5.1）

> 先于 A/B 对照的低成本评测：每个检测维度至少一对 **✅ 应报 / ❌ 不应报** 成对用例，
> ❌ 用例必须写明**边界理由**（差多少不该触发）。用例用占位实体（st-9xxx 虚构测点）
> 先验证流程正确性，再上真实案例（从 `ew_info_message` / `evolution/feedback-log.md` 挑）。

## 文件

- `cases.json` — 机器可读用例集 v2（44 条）：15 检测维度成对 ✅/❌ 用例（含"恰等于阈值"
  严格比较边界、TERM ≥3 含边界的对照）+ 质量闸（红档 inconclusive / 占位值）+ 护栏
  （零值合法 GATE-NEG-2 / 季节降级 SEASON-GUARD-1 / MAD 样本下限 / idle 平线）+ 3 态空数据
  + 诊断链 DIAG-HIT-1/DIAG-MISS-1（WARNING 命中路由即触发，验证 root_cause 回填与
  "已查为空"可区分性）。
- 校验脚本：`../../impl/verify_output.py`（envelope 一致性 + 5 条 red-flag 元检查）

## 用例格式

```json
{
  "id": "WL-NEG-1",
  "dimension": "水库水情",
  "kind": "should_report | should_not_report | empty_data",
  "fixture": {"table": "st_rsvr_r", "rows": [...]},
  "expected": {"min_level": "WARNING", "message_contains": "连续上升"},
  "reason": "❌ 用例必填：边界理由（如 '仅4次连续上升，阈值5次，差1不应触发'）"
}
```

## 运行方式（当前为 fixture 注入前的人工/agent 流程）

1. 将 fixture rows 写入测试库对应表（占位 st_id 9xxx，跑完清理）；
2. `python3 impl/inspection_analyzer.py --db "$TEST_DB_URL" --days 7 --json > /tmp/env.json`；
3. 按 expected 断言 findings；
4. `python3 impl/verify_output.py /tmp/env.json --exit-code $?` 过元检查闸。

空数据 3 态用例**不需要 fixture**（NOT_APPLICABLE 用天然空表 `st_river_r`；
QUERY_FAILED 用改坏表名/权限模拟），断言 envelope 的 status_code 正确且**没有伪造数值**。

## 评测后闭环

误报/漏报案例按七字段格式（现象/根因/触发条件/修复/验证/影响面/复发计数）写入
`../../evolution/feedback-log.md`；**同类问题 ≥2 次才升格为规则/路由表修改**，避免单例过拟合。
