# SOP 分轮 Mission 约束分析——智能告警 Agent 的多轮 LLM 幻觉治理

> 本文档分析"SOP 分轮 mission 约束"改造方案：把 hermes 驱动的智能告警 Agent
> 中**隐式、职责混杂的多轮 LLM 调用**，改为**显式、单职责的分轮 mission 约束**。
> 借鉴来源：`aiyiyi121/sxdevops` 的 `AGENT_ORCHESTRATION_PROFILES`（多智能体编排
> 中的 mission 分工设计），对齐腾讯 TCOP"结构化输出 + 引用上下文 + 绝不胡编"经验。
> 配套文档：`docs/aiops-keep-sxdevops-analysis.md`（三个开源方案整体拆解）、
> `early-warning-v3/analysis/intelligent-analysis-workflow.md`（被改造的 SOP）。

---

## 第一章 问题背景：现状的 LLM 调用是隐式的

### 1.1 本项目真实架构

`early-warning-v3` 是 **hermes agent + skill SOP 驱动的智能体**（SKILL.md 有
`hermes:` metadata），不是纯规则脚本。执行链路：

```
用户问题（"最近告警情况"/"这个根因是什么"…）
    ↓
hermes agent 加载 SKILL.md → 识别意图 → 按 SOP 驱动
    ↓
SOP = analysis/intelligent-analysis-workflow.md（Markdown 描述的 7 步 workflow）
    ↓
Step 1 数据采集        → SQL（规则层，不耗 Token）
Step 2 告警聚合        → lib/topology.py aggregate_alarms_to_events（规则层）
Step 3 跨域关联        → lib/topology.py compute_blast_radius（规则层）
Step 4 根因排序        → lib/topology.py rank_root_causes + apply_confidence_gate（规则层）
Step 5 趋势预测        → 线性外推 Python（规则层）
Step 6 响应建议        → 规则表 + infer_plan_params（规则层）
    ↓
HITL 检查点（人工确认）
    ↓
多轮对话处理（"Agent 行为指引" + "多轮对话处理"章节）
    ↓
LLM 多轮：hermes 自主决定轮次，解释规则层产物 + 回答用户 + 生成报告
```

### 1.2 核心问题：文档里没有任何显式 LLM 调用定义

探查 `intelligent-analysis-workflow.md` 全文后发现：

| 探查项 | 结果 |
|--------|------|
| Step 1-6 的 LLM 调用定义 | **无**——全部是规则层（SQL / Python 伪代码） |
| 显式的"第 N 轮 LLM 做什么" | **无**——没有轮次、没有 mission、没有输入输出契约 |
| LLM 职责描述散落在 | `## Agent 行为指引`（5 条）+ `## 多轮对话处理`（指代词解析/典型对话流程） |
| 每轮 LLM 的工具范围 | **无限制**——hermes 全工具可用 |

**后果**：hermes 执行 SOP 时隐式调 LLM，**一轮 LLM 同时干多件事**：

```
用户："最近告警情况怎样？"（触发完整工作流）

hermes 跑完 Step 1-6 规则层后，隐式调 LLM：
┌─ LLM 一次调用里同时做 ─────────────────────────┐
│ 1. 解释规则层产物（200 条告警 → 2 事件 → TOP3 根因）│
│ 2. 判断要不要追问（用户可能问什么）              │
│ 3. 生成自然语言报告                              │
│ 4. 隐含地"证明"根因排序对不对（可能引入幻觉）     │
└────────────────────────────────────────────────┘
```

**风险示例**：LLM 在解释"station:46 是根因"时，可能自作主张补一句
"因为 46 号站离水库最近"——这句没有规则层依据，是幻觉；但因为同一轮里它既要
解释又要下结论，没人拦得住。这正对应 SxDevOps 想避免的
**"一轮 LLM 同时出假设又自证又下结论"**。

### 1.3 为什么要治理：对齐腾讯"绝不胡编"

腾讯 TCOP 经验的第三道闸是"结构化输出 + 引用上下文，低置信度降级，绝不胡编"。
本项目的规则层已经做到了（`apply_confidence_gate` 三档降级），但 **LLM 解释层
仍是黑盒**——规则层算出来的置信度，到了 LLM 嘴里可能被"自由发挥"改写。
分轮 mission 约束就是给 LLM 解释层装上同样的闸。

---

## 第二章 借鉴来源：sxdevops 的 AGENT_ORCHESTRATION_PROFILES

> 源码位置：`/opt/git/sxdevops/backend/aiops/services.py`（已 clone 到本地分析）。

### 2.1 真实现（4 个 agent profile）

```python
AGENT_ORCHESTRATION_PROFILES = [
    {
        'code': 'diagnostic_agent',
        'name': '诊断 Agent',
        'mission': '识别故障现象、影响对象和初始假设。',
        'preferred_tools': ['query_alerts', 'query_alert_root_cause',
                            'query_alert_metrics', 'query_k8s_cluster_summary'],
    },
    {
        'code': 'evidence_agent',
        'name': '证据 Agent',
        'mission': '收集告警、日志、链路、K8s 和知识图谱证据。',
        'preferred_tools': ['query_logs', 'query_traces',
                            'query_knowledge_graph', 'query_task_resources'],
    },
    {
        'code': 'change_agent',
        'name': '变更 Agent',
        'mission': '关联发布、工单、事件墙和变更窗口。',
        'preferred_tools': ['query_recent_changes', 'query_event_wall',
                            'query_workorders'],
    },
    {
        'code': 'runbook_agent',
        'name': 'Runbook Agent',
        'mission': '把结论、证据和处置步骤沉淀成 Runbook 或复盘知识。',
        'preferred_tools': ['persist_runbook_draft', 'query_task_resources',
                            'query_knowledge_graph'],
    },
]
```

### 2.2 可借鉴的 4 个设计要点

| 设计点 | 实现 | 作用 |
|--------|------|------|
| **一句 mission** | 每个 agent 的 mission 一句话，如"收集…证据" | 职责边界清晰，避免越权 |
| **preferred_tools 限定工具** | 每个 agent 只声明自己偏好的工具子集 | 工具范围受限 = 行为范围受限 |
| **按工具交集选参战** | `_agent_sequence_for_action` 按 `allowed_tools ∩ preferred_tools` 选 agent | 没工具的 agent 不参战，避免空转 |
| **merge_rules 显式约束** | "变更时间线只作候选诱因，不能单独定性根因"、"Runbook 只沉淀草案，不直接执行修复" | 跨 agent 产物合并时有硬性规则，防胡编 |

### 2.3 编排状态合同（`_build_orchestration_state`）

sxdevops 把多智能体编排序列化为一个可审计的状态对象：

```python
{
    'version': '2.1',
    'mode': action.get('agent_mode') or 'direct',
    'agents': [{'code': ..., 'name': ..., 'mission': ..., 'tools': [...]}],
    'merge_rules': [
        '按证据来源去重，优先保留平台事实工具返回的数据。',
        '诊断结论必须引用至少一条证据；证据不足时输出待确认项。',
        '变更 Agent 的时间线只作为候选诱因，不能单独定性根因。',
        'Runbook Agent 只沉淀草案或复盘知识，不直接执行修复动作。',
    ],
    'interruptible': True,
    'stop_conditions': ['证据链闭环', '达到最大迭代次数', '用户中断', '权限或参数不足'],
}
```

**本项目可借鉴的核心**：不是照搬"多智能体"（本项目是单 hermes agent），而是
借鉴 **"每轮一个 mission + 工具受限 + merge_rule 禁止项"** 这套约束机制——
把它用在 SOP 的 LLM 轮次划分上。

---

## 第三章 改造示例：把隐式 LLM 调用改成显式分轮（前后对比）

> 用本项目真实场景（一次完整的水利告警根因分析会话）演示。

### 3.1 改造前（现状）：LLM 调用隐式，一轮干多件事

```
用户："最近告警情况怎样？"（触发完整工作流）

hermes 跑完 Step 1-6 规则层后，隐式调 LLM：
┌─ LLM 一次调用里同时做 ─────────────────────────┐
│ 1. 解释规则层产物（200 条告警 → 2 事件 → TOP3 根因）│
│ 2. 判断要不要追问（用户可能问什么）              │
│ 3. 生成自然语言报告                              │
│ 4. 隐含地"证明"根因排序对不对（可能引入幻觉）     │
└────────────────────────────────────────────────┘
```

**风险**：LLM 在解释"station:46 是根因"时，可能自作主张补一句
"因为 46 号站离水库最近"——这句没有规则层依据，是幻觉；但因为同一轮里它既要
解释又要下结论，没人拦得住。

### 3.2 改造后（SOP 显式分轮）：每轮一个 mission，工具受限

SOP 显式定义 4 个 LLM 轮次（参照 sxdevops 4 agent 的 mission 设计）：

```
用户："最近告警情况怎样？"（触发完整工作流）

── 诊断轮（diagnostic）─────────────────────────
mission: 只描述"发生了什么"，不做根因断言
输入: 规则层 Step 4 产物（ranked_causes + confidence）
输出: {"现象": "近90天2个故障事件，EVT-001 25条告警",
       "最高置信根因": "station:46 (0.53, 低置信度)"}
禁止: 下根因结论、提处置建议、补规则层没有的证据

── 取证轮（evidence）───────────────────────────
mission: 只收集证据，不解释
输入: 诊断轮的根因候选（station:46, device:386）
工具: 查 st_rsvr_r 水位趋势 / st_pptn_r 降雨 / 拓扑爆炸半径
输出: {"证据": [{"类型":"水位", "数据":[...]},
                {"类型":"降雨", "数据":[...]}]}
禁止: 对证据做因果推断

── 变更轮（change）────────────────────────────
mission: 只列候选诱因（气象预警/调度记录），降权不定性
输入: 取证轮的证据 + weather_warn / 调度记录
输出: {"候选诱因": ["6/2 暴雨橙色预警 (降权, 仅候选)"]}
禁止: 单独用变更时间线定性根因（merge_rule 3）

── 报告轮（report）────────────────────────────
mission: 把前三轮结论 + 规则层证据 + 处置步骤整理成报告
输入: 诊断轮 + 取证轮 + 变更轮产物
输出: {"根因": "station:46 水位红色预警 (置信度0.53, 低)",
       "证据链": [...], "处置": [...], "待确认项": [...]}
禁止: 新增前三轮没有的事实
```

### 3.3 关键差异对照

| 维度 | 改造前（现状） | 改造后（分轮 mission） |
|------|--------------|---------------------|
| LLM 调用定义 | 文档无显式定义，hermes 隐式决定 | SOP 显式定义 4 轮，每轮 mission 一句话 |
| 每轮职责 | 一轮同时解释+判断+报告+回应 | 诊断只描述 / 取证只收集 / 变更只列候选 / 报告只整理 |
| 工具范围 | 无限制（hermes 全工具可用） | 每轮 preferred_tools 限定（如变更轮只能用 weather_warn 查询） |
| 幻觉防线 | 无——LLM 可自行补"规则层没有的证据" | merge_rule 禁止：报告轮不得新增前三轮没有的事实 |
| 轮次可审计 | 无（平台审计是 token 级，不是业务语义级） | 每轮 purpose 明确（diagnostic/evidence/change/report），业务语义可关联 |
| 与 HITL 衔接 | HITL 检查点在 Step 4 后固定 | 报告轮产物才进 HITL，且"待确认项"显式列出 |

### 3.4 改造后的完整链路

```
用户问题
    ↓
SOP Step 1-6 规则层（SQL / lib/topology.py，不耗 Token）
    ↓
LLM 轮次 1：诊断轮 —— 只描述现象（mission 约束）
    ↓
LLM 轮次 2：取证轮 —— 只收集证据（工具受限）
    ↓
LLM 轮次 3：变更轮 —— 只列候选诱因（降权不定性）
    ↓
LLM 轮次 4：报告轮 —— 只整理不新增（merge_rule 禁止）
    ↓
HITL 检查点（报告轮产物 + 待确认项 → 人工确认）
    ↓
输出报告
```

---

## 第四章 轻重与 ROI 评估

### 4.1 轻重判断：轻改造

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动范围 | 仅 `intelligent-analysis-workflow.md` 一个文件 | 新增"LLM 轮次定义"章节（~60 行）+ 精简"Agent 行为指引"（~20 行） |
| 代码改动 | **零** | 不动 `lib/topology.py`、不建表、不动 SKILL.md 结构——纯 Markdown 文档 |
| 工作量 | **半天** | 写 4 个轮次的 mission/输入/输出/禁止项表格 |
| 风险 | **低** | 规则层行为完全不变（Step 1-6 照旧），只约束 LLM 解释层的执行方式 |
| 回滚 | 容易 | 删掉新章节即还原 |

**为什么轻**：SOP 本来就是 hermes 按 Markdown 执行的——加"LLM 轮次定义"章节
= 给 hermes 更明确的执行指令，不是新造一套机制。对比指纹缓存（要建表 + 3 函数
+ 失效管理 + 2-3 天），这个只有它的 1/4 成本。

### 4.2 ROI 判断：高，值得做

| 收益 | 说明 |
|------|------|
| 直接压幻觉源 | 现状"一轮 LLM 同时解释+判断+报告"，LLM 可自行补规则层没有的证据。分轮后报告轮**禁止新增前三轮没有的事实**（merge_rule），幻觉被结构性拦截 |
| 成本归因更准 | 平台审计是 token 级（记录花了多少），但不知道花在"诊断"还是"取证"上。分轮后每轮 purpose 明确（diagnostic/evidence/change/report），平台 token 数据 + 业务语义可关联 |
| 对齐腾讯"绝不胡编" | 腾讯经验的第三道闸是"结构化输出 + 引用上下文，低置信度降级"。分轮 = 每轮强制输出结构化产物 + 引用证据，比现在的隐式调用更接近这个要求 |
| 与现有能力兼容 | HITL 检查点保留（报告轮产物才进 HITL）、指代词解析保留、5 分钟 workflow 缓存保留——全部不冲突 |

### 4.3 与其他 P1/P2 增量的对比

| 增量 | 工作量 | ROI | 结论 |
|------|--------|-----|------|
| **SOP 分轮 mission 约束** | 半天（纯文档） | 高（压幻觉源 + 成本归因） | ✅ **值得做** |
| 规则层指纹缓存 | 2-3 天 | 低（平台已有 prompt_caching + workflow 缓存覆盖） | ❌ 已撤回 |
| LLM 轮次审计 | 平台已有（_session_db + /usage） | — | ❌ 不重复建表 |
| AIFeedback 反馈回路 | 1-2 天（建反馈表 + SOP） | 中（需先有稳定分轮产物） | 🟡 可做，但依赖分轮先落地 |
| 声明式 YAML workflow | 2-3 天（抽 SOP 为 YAML） | 中（可机审/版本化） | 🟡 架构演进方向，不急 |

**结论**：在撤回指纹缓存、确认平台已有 LLM 审计之后，**SOP 分轮 mission 约束
是目前唯一"轻 + 高 ROI"的增量**——半天纯文档改造，直接压住多轮驱动最大的幻觉源。

---

## 第五章 落地方式

### 5.1 改动文件与位置

改 `early-warning-v3/analysis/intelligent-analysis-workflow.md` 一个文件：

1. **新增 `## LLM 轮次定义` 章节**（Step 6 之后、`## HITL 检查点` 之前）：
   - 放 4 轮 mission 表格（diagnostic / evidence / change / report）
   - 每轮含：mission（一句话）/ 输入 / 输出 / 禁止项 / preferred_tools
2. **精简 `## Agent 行为指引`**：把散落的 5 条映射到 4 轮——
   - 升级决策 → 报告轮
   - 通知模板 → 报告轮
   - 策略分析 → 诊断轮
   - 升级对象 → 报告轮
   - 不可逆操作拦截 → HITL 前（报告轮产物提交人工确认时）
3. **在每轮 mission 里显式写"禁止"项**（对齐 sxdevops 的 merge_rule 思路）：
   - 诊断轮禁止下根因结论
   - 取证轮禁止因果推断
   - 变更轮禁止单独定性根因
   - 报告轮禁止新增前三轮没有的事实

### 5.2 与规则层/平台层的边界（不要越界）

| 层 | 已有能力 | 本次改造范围 |
|----|---------|-------------|
| 规则层（lib/topology.py） | 告警聚合/根因排序/置信度闸 | **不动**——Step 1-6 照旧 |
| 平台层（hermes） | prompt caching / LLM 审计（_session_db + /usage） | **不动**——不建表不重复实现 |
| SOP 文档层 | intelligent-analysis-workflow.md | **只改这里**——新增 LLM 轮次定义章节 |

### 5.3 验收方式

1. 文档校验：章节齐全（新增"LLM 轮次定义"含 4 轮 mission 表格）、Agent 行为指引已映射
2. 行为验证：触发一次完整 SOP，观察 hermes 是否按 4 轮执行（诊断→取证→变更→报告），
   报告轮的"待确认项"是否显式列出
3. 回归验证：规则层产物（ranked_causes + confidence）与改造前一致（纯文档改动不应影响规则层）
4. 与平台审计关联：`/usage` 数据能按 purpose 归类（多少 token 花在诊断/取证/变更/报告）

---

## 附录：本文档与相关文件的关系

| 文件 | 关系 |
|------|------|
| `docs/sop-mission-constraints-analysis.md` | 本文档——分轮 mission 约束方案分析 |
| `docs/aiops-keep-sxdevops-analysis.md` | 总拆解——三个开源方案整体对比（含本项目可借鉴点优先级表） |
| `early-warning-v3/analysis/intelligent-analysis-workflow.md` | 被改造对象——SOP 主体 |
| `/opt/git/sxdevops/backend/aiops/services.py` | 借鉴来源——AGENT_ORCHESTRATION_PROFILES 真实现 |
| `/opt/git/hermes-agent/agent/prompt_caching.py` | 平台层已有缓存（同会话多轮，省 ~75% 输入 token） |
| `/opt/git/hermes-agent/agent/usage_pricing.py` + `conversation_loop.py` | 平台层 LLM 审计（CanonicalUsage + update_token_counts + /usage） |

