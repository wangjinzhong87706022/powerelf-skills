# AIOps 开源生态拆解：Keep + SxDevOps + Dify 根因分析实战

> 本文档分析三篇公众号文章（阿铭linux）涉及的两个 GitHub 仓库，并对照本项目
> `early-warning-v3` 告警智能体与 `powerelf-inspection` 智能巡检的可借鉴点。
> 三篇文章分别讲：开源 Keep 告警管理平台、自研 SxDevOps AIOps 平台、基于 Dify 的根因分析实战。

| 文章 | URL | 涉及仓库 |
|------|-----|----------|
| 开源 AIOps 告警解决方案：把满天飞的告警，收进一个"运维驾驶舱" | https://mp.weixin.qq.com/s/HFGwGs1YB5uCwrx6xXU0ZQ | `keephq/keep` |
| AIOps 探索：自研 AIOps 开源平台拆解 | https://mp.weixin.qq.com/s/btpiwYXlAbztgI7NUCKmRg | `aiyiyi121/sxdevops` |
| AIOps 探索：基于 Dify 的根因分析实战案例终于落地了 | https://mp.weixin.qq.com/s/A65Fi10U9a4iag2TxwJirA | Dify Agent（闭源 Prompt） |

两个仓库已在本次分析中克隆到本地：

| 仓库 | 本地路径 | 克隆方式 | 大小 |
|------|----------|----------|------|
| keephq/keep | `/opt/git/keep` | `git clone --depth 1` | 135 MB |
| aiyiyi121/sxdevops | `/opt/git/sxdevops` | `git clone --depth 1` | 24 MB |

---

## 第一章 三篇公众号文章摘要

### 1.1 文章一：开源 Keep 告警管理平台

**核心主张**：Keep 不是"摄像头"，而是"监控室"——不重新造监控系统，而是把现有
Prometheus/Grafana/Datadog/Sentry/CloudWatch/PagerDuty/Slack/Jira 等工具产生的告警
串起来，变成统一入口（single pane of glass）。

**解决的四大问题**：

1. **告警太散**：基础设施、应用、日志、云资源各用一套工具，最后每个系统都在报警，
   但没有一个地方能看全局。Keep 提供统一告警看板（告警表 + 搜索 + 分面分析 + 自定义列）。
2. **重复告警太多**：一个数据库抖动，应用报错、接口超时、队列堆积、日志异常一起出现，
   对人是同一件事，对工具是几十条告警。Keep 的去重（deduplication）把相似告警聚合。
3. **告警来了还要人肉操作**：P1 告警来要发 Slack、建 Jira、拉 PagerDuty、补上下文。
   Keep 的 Workflows（YAML 描述，触发器 + 步骤 + 动作）自动读数据、补上下文、发通知、
   更新工单，甚至执行重启服务这类动作。
4. **AI 落地**：不是简单加一个聊天框，而是把 AI 放进告警处理链路——做告警总结、
   辅助关联、规范化输入、判断严重级别、路由。支持 DeepSeek/OpenAI/Anthropic/Grok/
   Gemini/Ollama/Llama.cpp/vLLM，云上和自托管都能用。

**四个特点**：集成多（provider 覆盖观测/通信/事件/工单/容器/队列/AI 后端）、
工作流灵活（按条件分流，如 payments 服务告警发支付团队，ftp 服务告警自动建 Jira）、
AI 使用务实、对中小团队友好（Docker Compose 一键起，也支持 K8s Helm）。

**适合三类团队**：告警来源很多、on-call 压力大、对数据边界敏感又想用 AIOps 的。

### 1.2 文章二：自研 SxDevOps AIOps 平台

**核心主张**：SxDevOps 是把大模型嵌入运维控制面的 AIOps 平台，不是简单的"运维聊天机器人"。
把监控、告警、事件、任务、工单、容器、主机和权限系统统一成一套可查询、可生成动作、
可人工确认、可审计的 Agent 工作流。目标"看态势、找证据、问系统、确认动作"，
而不是让模型直接获得无限制的服务器操作权限。

**架构**：Vue 3 前端 + Django REST Framework + Channels + Redis + Paramiko +
Kubernetes Python SDK + 阿里云/华为云 SDK，应用最终由 Daphne 启动。
核心后端应用：aiops（Agent/模型/Skill/MCP/知识环境/对话/审计）、ops（主机/任务/部署/
告警/日志/指标/链路/K8s/SSH/容器）、rbac（角色/权限/资源/接口鉴权）、eventwall（事件墙）、
sqlaudit（SQL 查询/审核/工单）、cmdb（资源配置）、multicloud（多云）、iac（基础设施即代码）、
marketplace（功能市场）。

**Agent 核心调用链**（最关键的设计）：

```
用户问题 + 当前页面上下文
    ↓
Action Router：识别动作类型
    ↓
选择执行模式 Direct / ReAct / Plan + ReAct
    ↓
Preflight：参数、权限、资源和风险预检
    ↓
Skill：规定处理 SOP、工具范围和输出格式
    ↓
MCP / 内置 Tool：查询实际运维系统
    ↓
生成事实、证据和候选动作
    ↓
第二阶段 LLM：整理成结构化回答
    ↓
只读结果直接返回 / 高风险动作进入 Pending Action
    ↓
人工确认 → 后端 API 执行 + RBAC + 审计
```

**关键设计**：二阶段 LLM（第一次工具选择 + 信息采集，第二次解释 + 格式整理）、
Action 预检（参数/权限/资源/风险）、Skill 模板（SOP）、待确认动作（Pending Action）、
模型调用审计。内置可观测性（指标/日志/链路/Grafana 链接/告警规则）、
主机和任务中心（SSH WebShell + 任务草案待确认）、容器和 K8s、工单/SQL 审核/审计。

**作者坦诚的问题**：核心编排代码已经出现明显的"大文件、强耦合"问题
（services.py 16403 行、views.py 1934 行），距离高可靠生产级运维中枢仍需工程化改造。

### 1.3 文章三：基于 Dify 的根因分析实战

**核心主张**：先从最简单的架构开始，别一上来就把知识图谱/可观测/RAG/评分体系全加进去——
Token 成本高、分析时间长，小业务系统反而效果更差。

**架构**：Prometheus + Alertmanager 监控告警 → Alertmanager webhook 触发 Dify Agent →
Loki + Alloy 收日志 → 蓝鲸 CMDB 管资源 → Dify Agent 含三个 MCP（Prometheus/Loki/CMDB，
30+ 工具只用 10 个）→ LLM 综合分析三源数据判根因。

**用 Agent 模式不用工作流**：业务逻辑全靠 Prompt 约束（更精准但更像编程，工作流会更可控）。

**七步 Prompt 根因分析流程**：
1. 解析输入（故障时间/告警名/业务/服务/主机/IP/instance/pod/namespace/cluster/module/现象）
2. 查当前告警（Prometheus list_alerts，同对象/同主机/同 namespace 的其他告警）
3. 查 CMDB（list_businesses → list_hosts → 匹配故障 IP/instance → find_sets → find_modules，
   确认业务/主机/集群/模块归属，是否多个异常集中在同一主机/模块/集群）
4. 查 Prometheus 指标（range_query 查 ALERTS/up/CPU/内存/磁盘/网络/容器重启/请求量/错误率/延迟/5xx，
   判断哪个指标最早异常、异常是否集中、异常时间是否与告警一致）
5. 查 Loki 日志（label_names → label_values → loki_query，关注 error/exception/timeout/
   failed/connection refused/OOM/killed/panic/5xx/slow/unavailable）
6. 综合判断根因（最早异常更接近根因、指标和日志互证置信度更高、不把表面现象当根因、
   证据不足明确说明）
7. 输出分析报告（故障摘要/最可能根因 + 置信度 + 判断依据/Prometheus 证据/CMDB 证据/
   Loki 日志证据/故障时间线/影响范围/处置建议/不确定性说明）

**后续改进方向**：作者自述要加评分系统 + 故障库，帮助改进根因分析准确率。

---

## 第二章 keephq/keep 仓库拆解

### 2.1 整体定位

Keep 是一个**告警中枢**而非监控系统——站在现有工具之上，把分散的告警、事件、通知和工单
重新组织起来：先把噪音降下来（去重），再把上下文补齐（enrichment），最后把处理动作
自动化（Workflow）。这正好对应腾讯 TCOP 的"先收敛再定位"思路。

### 2.2 仓库结构（核心目录）

```
keep/
├── keep/                          # 后端核心包
│   ├── api/
│   │   ├── alert_deduplicator/    # 告警去重引擎
│   │   ├── bl/                    # 业务逻辑（含 ai_suggestion_bl.py）
│   │   ├── core/                  # DB/配置/依赖
│   │   ├── models/                # Alert/Incident/Rule 数据模型
│   │   └: bl/ai_suggestion_bl.py # AI 关联与总结
│   ├── rulesengine/              # 规则引擎（CEL 表达式 + incident 生成）
│   ├── workflowmanager/          # Workflow 引擎（YAML → 执行）
│   ├── topologies/               # 拓扑关联（topology_processor.py）
│   ├── providers/                # 集成 provider（131 个目录）
│   │   ├── openai_provider/      # AI 后端（8 个：openai/anthropic/deepseek/
│   │   ├── anthropic_provider/   #       gemini/grok/ollama/llamacpp/vllm）
│   │   ├── deepseek_provider/
│   │   └: llamacpp_provider/
│   ├── actions/                  # Workflow 动作工厂
│   ├── conditions/               # Workflow 条件判断
│   └: step/                      # Workflow 步骤
├── keep-ui/                      # Next.js 前端
┌: docker-compose.yml             # 一键起 FastAPI + Next.js + WebSocket
```

### 2.3 告警去重实现（`alert_deduplicator.py`）

**核心类** `AlertDeduplicator`（610 行），关键方法 `apply_deduplication`：

```python
def apply_deduplication(self, alert, rules=None, last_alert_fingerprint_to_hash=None):
    rules = rules or self.get_deduplication_rules(self.tenant_id, alert.providerId, alert.providerType)
    for rule in rules:
        alert = self._apply_deduplication_rule(alert, rule, last_alert_fingerprint_to_hash)
        if alert.isFullDuplicate or alert.isPartialDuplicate:
            create_deduplication_event(
                tenant_id=self.tenant_id,
                deduplication_rule_id=rule.id,
                deduplication_type="full" if alert.isFullDuplicate else "partial",
                provider_id=alert.providerId,
                provider_type=alert.providerType,
            )
            break  # 命中去重就不再检查其他规则
    return alert
```

**设计要点**：

1. **三分态**：`isFullDuplicate`（完全重复，丢弃）/ `isPartialDuplicate`（部分重复，
   合并）/ 非重复（保留为独立告警）。
2. **规则可配**：每个 provider 可有自己的去重规则（按字段组合算 fingerprint），
   默认规则在 `_get_default_full_deduplication_rule`。
3. **留痕可统计**：每次去重（无论命中与否）都写 `create_deduplication_event`，
   便于后续统计去重命中率。
4. **顺序短路**：命中一条去重规则就 break，不再检查后续规则——保证去重语义清晰。

### 2.4 规则引擎与 incident 生成（`rulesengine.py`，767 行）

**核心类** `RulesEngine`，关键方法 `_run_cel_rules`——把规则引擎跑完，
命中规则的告警聚合成 incident（故障事件）：

```python
def _run_cel_rules(self, events, session=None):
    rules = get_rules_db(tenant_id=self.tenant_id)
    incidents_dto = {}
    for rule in rules:
        for event in events:
            matched_rules = self._check_if_rule_apply(rule, event)  # CEL 表达式匹配
            if matched_rules:
                rule_fingerprints = self._calc_rule_fingerprint(event, rule)
                for rule_fingerprint in rule_fingerprints:
                    incident = self._get_or_create_incident(
                        rule=rule, rule_fingerprint=",".join(rule_fingerprint),
                        session=session, event=event, creation_allowed=creation_allowed
                    )
                    incident = assign_alert_to_incident(
                        fingerprint=event.fingerprint, incident=incident,
                        tenant_id=self.tenant_id, session=session
                    )
                    # threshold 判断 incident 是否可见
                    if alerts_count >= rule.threshold:
                        if rule.create_on == "any" or (rule.create_on == "all" and len(rule_groups) == len(matched_rules)):
                            incident.is_visible = True
                    RulesEngine.send_workflow_event(self.tenant_id, session, incident_dto, "created")
    return list(incidents_dto.values())
```

**设计要点**：

1. **CEL 表达式做规则匹配**：用 celpy（Google Common Expression Language）做条件判断，
   支持 `alert.service == "payments" && alert.severity == "critical"` 这种声明式规则，
   避免硬编码 Python if-else。
2. **threshold + create_on**：incident 不是一命中规则就创建，要满足"告警数 >= threshold"
   且"create_on = any（任一子规则命中）/ all（所有子规则命中）"才可见。
3. **fingerprint 去重**：每条规则算出一个 fingerprint（哪些字段组合算"同一个 incident"），
   同 fingerprint 的告警归到同一 incident。
4. **状态机**：incident 有 `is_visible` 状态——先在后台创建（不可见），满足条件才可见，
   避免规则抖动导致 incident 忽隐忽现。
5. **workflow 联动**：incident 创建/更新时发 `send_workflow_event`，触发下游 Workflow。

### 2.5 拓扑关联（`topology_processor.py`）

**核心类** `TopologyProcessor`——后台常驻进程，按 tenant 周期性扫拓扑，
基于拓扑关联把同 application/同依赖链的告警聚成 topology-based incident：

```python
def _check_topology_for_incidents(self, last_alerts, topology_based_incidents):
    """Check if the topology should create incidents"""
    incidents = []
    # get all alerts within the same application
    # get all alerts within services that have dependencies
    return incidents

def _get_application_based_incident(self, tenant_id, application):
    # 同 application 的多个 service 告警 → 聚成一个 incident
    ...
```

**设计要点**：拓扑关联是规则关联的补充——规则要人写 CEL，拓扑关联靠 CMDB/依赖图自动发现。
同一 application 下的多个 service 告警，或同一依赖链上下游告警，自动聚成 topology-based incident。

### 2.6 AI 关联与建议（`ai_suggestion_bl.py`，507 行）

**核心类** `AISuggestionBl`——用 OpenAI 做 incident 候选聚类（IncidentClustering）和
告警总结。关键设计：

1. **Suggestion 去重缓存**：`get_suggestion_by_input` 按 `suggestion_input_hash`
   （sha256 of JSON）缓存 AI 建议——相同输入不重复调 LLM，省 Token。
2. **AISuggestionType 枚举**：区分 `incident_clustering`（候选聚类）、`incident_summary`
   （故障总结）等，便于按类型查/反馈。
3. **AIFeedback 反馈回路**：用户对 AI 建议的采纳/拒绝记录入库，形成反馈闭环改进后续建议。
4. **依赖 OpenAI 客户端**：`self._client = OpenAI()`——当前强依赖 OpenAI，
   issue #2373/#2365 标注要支持多模型/per-tenant key。

### 2.7 Workflow 引擎（`workflowmanager/workflow.py`）

**核心类** `Workflow`（YAML 描述，GitHub Actions 风格）：

```python
class WorkflowStrategy(enum.Enum):  # 执行策略枚举
    ...

class Workflow:
    def __init__(self, ...): ...
    def run_steps(self): ...      # 按 YAML 跑所有 step
    def run_action(self, action: Step): ...  # 跑单步动作
    def run_actions(self): ...    # 跑所有动作
    def run(self, workflow_execution_id): ...  # 主入口
    def check_run_permissions(self): ...  # 权限校验
```

**设计要点**：YAML 声明式（trigger + steps + actions），支持条件分流
（if service == "payments" then notify payment_team），可调任何 provider
（发 Slack / 建 Jira / 更新 PagerDuty / 调 AI 总结 / 执行 Python 脚本）。
权限校验在 `check_run_permissions`，避免 Workflow 越权。

### 2.8 Keep 给本项目的启发

| Keep 能力 | 本项目 early-warning-v3 现状 | 可借鉴点 |
|-----------|----------------------------|----------|
| 三分态去重（full/partial/keep） | 仅按 st_code+ew_type 分组 + 30 分钟合并 | 引入 full/partial 三分态，partial 合并而非丢弃，保留告警演进痕迹 |
| CEL 表达式规则引擎 | 硬编码 if-else（correlation-analysis.md） | 引入声明式规则引擎（CEL 或类似），规则可配可热更，避免改代码 |
| threshold + create_on 的 incident 可见性 | 团一旦连通就可见 | 引入"告警数 >= threshold 才可见"避免单告警误触 incident |
| topology_processor 后台拓扑关联 | 已有 build_topology.py + topology.py BFS | 拓扑关联已对标，可借鉴"后台常驻周期扫"而非手动 --analyze |
| AI Suggestion 缓存（input_hash） | hermes agent 按 SOP 多轮调用 LLM，每轮入参可不同，难做 input_hash 命中 | 借鉴思路：对"告警聚合 + 根因排序"的**规则层产物**做 fingerprint 缓存（无 LLM 参与），命中则跳过本轮 SOP，省 Token；对"LLM 解释层"产物则用 session 级缓存（同一 session 5 分钟内复用）而非 input_hash |
| AIFeedback 反馈回路 | ew_audit_log 仅记操作审计，未记"用户采纳/拒绝根因候选"的反馈 | 借鉴 Keep 的 AIFeedback：根因排序 TOP3 候选被用户采纳哪一条/拒绝哪一条要入 ew_audit_log，反馈改进五维打分权重 |
| Workflow YAML 自动化 | intelligent-analysis-workflow.md 已是 SOP 级 workflow（hermes agent 按 SOP 多轮驱动），但 SOP 是 Markdown 描述而非 Keep 的声明式 YAML | 借鉴 Keep Workflow YAML：把 SOP 里的"红色告警 → 发通知 + 查历史 + 生成报告"段抽出为声明式 YAML，hermes 可声明式触发而非靠 Markdown 自然语言指引——更可机审、可版本化、可复用 |
| provider 双向集成 | 单向（只查 DB） | 未来若对接 Prometheus/蓝鲸 CMDB，可借鉴 Keep 的双向 provider 模式 |

---

## 第三章 aiyiyi121/sxdevops 仓库拆解

### 3.1 整体定位

SxDevOps 是一个把大模型嵌入运维控制面的 AIOps 平台——不是"运维聊天机器人"，而是
把监控/告警/事件/任务/工单/容器/主机/权限统一成一套可查询、可生成动作、可人工确认、
可审计的 Agent 工作流。核心目标"看态势、找证据、问系统、确认动作"，
强调模型不获得无限制的服务器操作权限。

### 3.2 仓库结构（核心目录）

```
sxdevops/
├── backend/                        # Django 后端
│   ├── aiops/                      # AIOps Agent 核心（最大模块）
│   │   ├── services.py            # 16403 行！编排/预检/二阶段 LLM/审计
│   │   ├── views.py               # 1934 行 DRF viewset
│   │   ├── knowledge_graph.py     # 2965 行 知识图谱构建
│   │   ├── models.py              # 631 行 数据模型
│   │   ├── action_handlers.py     # 342 行 Action 路由
│   │   └: serializers.py          # 699 行
│   ├── ops/                       # 主机/任务/部署/告警/日志/指标/链路/K8s/SSH/容器
│   ├── rbac/                      # 角色/权限/资源/接口鉴权
│   ├── eventwall/                 # 事件墙和事件源
│   ├── sqlaudit/                  # SQL 查询/审核/工单
│   ├── cmdb/                      # 资源配置管理
│   ├── multicloud/                # 多云资源（阿里云/华为云 SDK）
│   ├── iac/                       # 基础设施即代码（Terraform）
│   ┌: marketplace/                 # 功能/模块市场
├── frontend/                      # Vue 3 + Pinia + Element Plus + ECharts + xterm.js
├── docker-compose.yml             # MySQL + Redis + 后端 + 前端
┌: docs/                           # 设计文档（AIOps-MCP-Skill/双阶段应答/Action-Handler）
```

### 3.3 Agent 编排核心（`services.py`，16403 行）

**多智能体编排 profiles**（`AGENT_ORCHESTRATION_PROFILES`）：

```python
AGENT_ORCHESTRATION_PROFILES = [
    {'code': 'diagnostic_agent',  ...},  # 诊断假设生成
    {'code': 'evidence_agent',    ...},  # 只读工具取证
    {'code': 'change_agent',      ...},  # 变更时间线（候选诱因）
    # ... Runbook Agent
]

def _agent_sequence_for_action(action):
    # 按 action.allowed_tools 匹配各 agent 的 preferred_tools，选派出要参战的 agent 序列
    allowed_tools = set(filter_feature_tools((action or {}).get('allowed_tools') or []))
    selected = []
    for profile in AGENT_ORCHESTRATION_PROFILES:
        preferred_tools = filter_feature_tools(profile['preferred_tools'])
        if allowed_tools.intersection(preferred_tools):
            selected.append({**profile, 'preferred_tools': preferred_tools})
    if not selected:
        selected = [profile for profile in AGENT_ORCHESTRATION_PROFILES[:2]]  # 默认诊断+取证
    return selected
```

**编排状态合同**（`_build_orchestration_state`）——把多智能体编排序列化为一个可审计的状态对象：

```python
def _build_orchestration_state(action, payload=None):
    agents = _agent_sequence_for_action(action)
    return {
        'version': '2.1',
        'mode': action.get('agent_mode') or 'direct',
        'agents': [
            {'code': ag['code'], 'name': ag['name'], 'mission': ag['mission'],
             'tools': [t for t in ag['preferred_tools'] if t in allowed_tools or t == 'persist_runbook_draft']}
            for ag in agents
        ],
        'merge_rules': [
            '按证据来源去重，优先保留平台事实工具返回的数据。',
            '诊断结论必须引用至少一条证据；证据不足时输出待确认项。',
            '变更 Agent 的时间线只作为候选诱因，不能单独定性根因。',
            'Runbook Agent 只沉淀草案或复盘知识，不直接执行修复动作。',
        ],
        'interruptible': True,
        'stop_conditions': ['证据链闭环', '达到最大迭代次数', '用户中断', '权限或参数不足'],
        'input_summary': {'environment': ..., 'service': ..., 'incident': ...},
    }
```

**设计要点**（本项目可借鉴）：

1. **Agent 分工明确**：诊断/取证/变更/Runbook 四类 agent 各司其职，
   变更 agent 明确"只作候选诱因不能单独定性根因"——这正是水利场景里
   "气象预警 → 水位告警"不能直接断根因的正确表述。
2. **merge_rules 显式约束**：用规则约束 Agent 间的合并行为（去重/引用证据/降权/边界），
   避免多 agent 输出胡乱拼接。
3. **interruptible + stop_conditions**：编排可中断，停止条件显式声明，
   避免长链推理失控。
4. **Plan-ReAct 五阶段 trace**：plan → execute → observe → revise → terminate，
   每阶段状态可追溯——这对审计至关重要。

### 3.4 Action 预检合同（`build_action_preflight_contract`）

在 Agent 调任何工具前，先做预检（preflight）：

```python
def build_action_preflight_contract(action_code, payload=None, user=None):
    action = _action_registry_item_by_code(action_code, user=user, include_unavailable=True)
    if user and not action.get('available'):
        raise ValueError(action.get('available_reason') or '缺少 Action 权限')
    # 从问题文本或 payload.environment 推断知识环境（K8s 集群/Docker 主机等）
    knowledge_environment = resolve_knowledge_environments_from_text(question)
    analysis_scope = _build_analysis_scope(knowledge_environment)
    missing_fields = _missing_action_context_fields(action, question, knowledge_environment, analysis_scope, page_context)
    return result['metadata']  # 含缺哪些上下文、建议补什么
```

**设计要点**：

1. **权限校验在前**：`action.get('available')` 先过 RBAC，无权限直接 raise。
2. **知识环境推断**：从用户问题文本里推断"在说哪个 K8s 集群 / Docker 主机"，
   避免用户手动选。
3. **missing_fields 反馈**：告诉用户"要跑这个 action 还缺哪些上下文"，
   而非默默跑错。
4. **risk_level 分级**：read_only / draft / write / execute 四档，
   execute 必须过 Pending Action 人工确认。

### 3.5 二阶段 LLM 与 Pending Action

二阶段 LLM 调用链（从 views.py 的 `dispatch_chat` 到 services.py 的 `run_external_task_orchestration`）：

```
用户消息 → dispatch_chat
    ↓
Action Router（normalize_page_context + select_action_by_handler）
    ↓
Preflight（build_action_preflight_contract：权限 + 缺字段检查）
    ↓
第一阶段 LLM：工具选择 + 信息采集
    ↓
内置 Tool / MCP 取事实（只读）
    ↓
第二阶段 LLM：解释 + 格式整理
    ↓
risk_level == read_only → 直接返回
risk_level in {draft, write, execute} → 进入 Pending Action
    ↓
confirm_action（user 二次确认）→ 后端 API 执行 + RBAC + 审计
cancel_action（user 拒绝）→ 终止
```

**Pending Action 模型**（`AIOpsPendingAction`）存 LLM 候选动作 + 风险等级 + 确认状态，
用户 `confirm_action` / `cancel_action` 后留痕到审计。

### 3.6 知识图谱（`knowledge_graph.py`，2965 行）

构建 K8s 集群节点/Pod/Workload/ConfigMap、Docker 容器、CMDB 资源之间的依赖图，
支持 `resolve_knowledge_environments_from_text`（从问题文本匹配知识环境）。
有缓存层（`_cache_get`/`_cache_set`）避免重复调 K8s API。

### 3.7 RBAC 与审计

`rbac/` 模块做后端 API + 前端路由 + 菜单 + 按钮 + WebSocket 的统一鉴权。
`AIOpsModelInvocation` 和 `AIOpsToolInvocation` 两个模型分别记录**每次 LLM 调用**
和**每次工具调用**的入参/出参/耗时/Token，形成完整审计链。

### 3.8 SxDevOps 给本项目的启发

| SxDevOps 能力 | 本项目 early-warning-v3 现状 | 可借鉴点 |
|--------------|----------------------------|----------|
| 多智能体编排（诊断/取证/变更/Runbook） | 单 hermes agent 按 SOP 多轮驱动，根因排序靠规则五维打分；LLM 角色=解释+追问而非"出假设+取证+候选诱因"分段 | 借鉴分工：让 SOP 里显式分"诊断轮（出假设）/取证轮（调只读工具）/变更轮（候选诱因降权）/Runbook 轮（沉淀复盘）"，每轮 LLM mission 明确，避免一轮 LLM 同时出假设又自证又下结论 |
| Plan-ReAct 五阶段可追溯 trace | SOP 已有 Step 1→7 但仅 Markdown 描述，无 LLM 调用 trace（未记每轮入参/出参/Token/耗时） | 借鉴 SxDevOps 的 plan→execute→observe→revise→terminate 五阶段状态对象，每轮 LLM 调用后 append 一段到 ew_audit_log，形成可追溯 trace |
| Action 预检合同（权限 + 缺字段 + 风险分级） | escalation-agent.md 已有 S0~S3 分级 | 可借鉴"missing_fields 反馈"——告警缺哪些上下文不能判根因时，SOP 第 1 步主动告诉用户补什么，而非靠 LLM 临场追问（追问=多轮=多 Token） |
| Pending Action 人工确认 | 已有 HITL 双签闸 | 已对标，可借鉴"AIOpsPendingAction 模型存候选动作"——把根因排序的 TOP3 候选存表待确认 |
| LLM 调用 + 工具调用双审计 | ew_audit_log 仅记操作审计，未记 LLM 轮次/入参/出参/Token | 借鉴 SxDevOps 双审计：本项目 hermes 每轮 LLM 调用要记入 ew_audit_log（轮次/prompt/response/Token/耗时），否则多轮驱动的成本和幻觉源都不可追溯 |
| 知识图谱从 K8s/CMDB 构建 | 已从 att_st_base 等 11 张表建图 | 已对标，可借鉴"从问题文本推断知识环境"——用户说"606K2155"时自动定位到对应工程/大坝 |
| services.py 16403 行强耦合 | SKILL.md 模块化 | 反面教材：本项目要继续保持模块化，避免单文件膨胀 |
| MCP 集成（Prometheus/Loki/CMDB） | 仅直查 MySQL | 未来若对接多源，可借鉴 MCP 标准化工具暴露 |

---

## 第四章 Dify 根因分析实战拆解

> Dify Agent 本身是闭源 Prompt（作者在课程里讲），文章只公开了七步 Prompt 流程。
> 本章拆解这个 Prompt 的设计，对照本项目根因排序的规则层。

### 4.1 七步 Prompt 根因分析流程

| 步骤 | 动作 | 工具 | 对标本项目 |
|------|------|------|-----------|
| 1 解析输入 | 从 Alertmanager payload 或用户问题提取故障时间/告警名/业务/服务/主机/IP/instance/pod/namespace/cluster/module/现象 | 无（LLM 解析） | 本项目 Step 1 数据采集已做（从 ew_info_message 提取 st_code/ew_type/level_r/value） |
| 2 查当前告警 | list_alerts 看当前活跃告警，重点关注同对象/同主机/同 namespace 的其他告警 | Prometheus MCP | 本项目 Step 2 告警聚合已做（aggregate_alarms_to_events 按拓扑社团聚） |
| 3 查 CMDB | list_businesses → list_hosts → 匹配故障 IP/instance → find_sets → find_modules，确认业务/主机/集群/模块归属，是否多个异常集中 | CMDB MCP | 本项目拓扑图已建（att_st_base/eq_equip_base/att_dam_base 聚成 364 节点 + 1196 边），compute_blast_radius 算爆炸半径 |
| 4 查 Prometheus 指标 | range_query 查 ALERTS/up/CPU/内存/磁盘/网络/容器重启/请求量/错误率/延迟/5xx，判断哪个最早异常、异常是否集中、异常时间是否与告警一致 | Prometheus MCP | 本项目指标查询靠 st_rsvr_r/st_pptn_r/st_pressure_r 等表，根因排序的 temporal_priority 维度判最早异常 |
| 5 查 Loki 日志 | label_names → label_values → loki_query，关注 error/exception/timeout/failed/OOM/killed/panic/5xx | Loki MCP | 本项目无日志系统对标（水利场景无应用日志，靠观测数据 + 巡检缺陷） |
| 6 综合判断根因 | 最早异常更接近根因、指标和日志互证置信度更高、不把表面现象当根因、证据不足明确说明 | LLM 推理 | 本项目根因排序五维打分（时序优先 0.25 + 拓扑中心性 0.20 + 因果链证据 0.25 + 告警严重度 0.15 + 历史复发率 0.15）已对标"最早异常更接近根因" |
| 7 输出分析报告 | 故障摘要/最可能根因 + 罊信度 + 判断依据/Prometheus 证据/CMDB 证据/Loki 日志证据/故障时间线/影响范围/处置建议/不确定性说明 | LLM 格式化 | 本项目根因排序输出 ranked_causes（含 score_breakdown + evidence + confidence + display_action）已对标 |

### 4.2 Dify 方案 vs 本项目方案的关键差异

| 维度 | Dify 方案 | 本项目方案 | 谁更合适 |
|------|----------|-----------|----------|
| 架构复杂度 | 简单（3 MCP + 1 LLM Agent） | 中等（11 表建图 + BFS + 五维打分 + 三道闸 + hermes SOP 多轮） | 小业务用 Dify，水利专业场景用本项目 |
| Token 成本 | 高（每告警都让 LLM 推理根因，七步全靠 LLM） | 也高，但性质不同：本项目 hermes 按 SOP 多轮驱动 LLM（每轮 SQL+解释+追问），告警聚合/根因排序/置信度闸走规则层不耗 Token，但 SOP 的"解释 + 追问 + 报告"段仍要 LLM | Dify 七步全 LLM，本项目把"聚合+排序+闸"下沉规则层省了一部分 Token，但 SOP 多轮驱动可能更耗 Token（取决于轮次） |
| 准确率 | 依赖 Prompt 质量，作者自述需加评分系统 + 故障库 | 规则层五维打分已含历史复发率维度（historical_recurrence）；但 LLM 解释层可能因轮次多而漂移 | 本项目规则层更稳，LLM 层需 SOP 约束；Dify 全靠 Prompt |
| 可解释性 | LLM 黑盒，靠 Prompt 约束输出格式 | 规则层五维每维可拆，evidence 引用 ew_info_message.id + 拓扑路径；LLM 层仍是黑盒 | 本项目规则层更可解释，LLM 层与 Dify 同黑盒 |
| 适应性 | LLM 能处理没见过的故障类型 | 规则层抓不到拓扑图没覆盖的新故障（causes 边没建到）；LLM 层可临场补，但受 SOP 约束 | Dify 更自由，本项目更可控 |
| 速度 | 慢（LLM 推理 + 多 MCP 调用，单轮即可） | 也慢，且可能更慢：规则层秒级，但 hermes 按 SOP 多轮驱动 LLM（每轮含 SQL 执行 + LLM 推理 + 追问），多轮累加耗时 | 单轮比 Dify 慢的轮次少，但多轮累加可能更久 |

### 4.3 Dify 方案给本项目的启发

1. **作者自述要加评分系统 + 故障库**——本项目根因排序的五维打分就是评分系统，
   historical_recurrence 维度就是故障库的轻量版。**本项目已走在前面**。
2. **七步 Prompt 的"证据不足明确说明"**——本项目的置信度降级闸
   （< 0.5 suppress / < 0.7 show_with_warning）已对标，且更严格（有结构化动作）。
3. **"不把表面现象当根因"**——本项目根因排序的 causal_evidence 维度
   （有 causes 边指向团内其他节点）正是这个原则的量化实现。
4. **未来若加 LLM 补充**：可借鉴 Dify 的 Agent 模式（Prompt 约束）而非工作流模式——
   先用规则跑出 TOP3 �候选根因 + 置信度，再让 LLM 做自然语言解释 + 不确定性说明，
   规则和 LLM 各司其职。

---

## 第五章 三方案对比与本项目可借鉴点汇总

### 5.1 三方案核心对比

| 维度 | Keep | SxDevOps | Dify 根因分析 | 本项目 early-warning-v3 |
|------|------|----------|--------------|------------------------|
| 定位 | 告警中枢（串现有工具） | AIOps 控制面（嵌入运维） | 根因分析 Agent | 水利预警告警智能体 |
| AI 角色 | 告警总结 + 辅助关联 | 工具选择 + 解释格式化 | 七步根因推理 | hermes agent 按 SOP 多轮驱动：聚合/排序/闸走规则层，解释/追讨/报告走 LLM 多轮 |
| 去重 | 三分态 + provider 级规则 | 无（告警靠事件墙聚合） | 无 | 拓扑社团聚类（aggregate_alarms_to_events） |
| 关联 | CEL 规则 + 拓扑关联 | 知识图谱 + 多智能体编排 | CMDB 资源关联 | 知识图谱 + BFS 爆炸半径 + causes 因果边 |
| 根因定位 | 无（聚合到 incident 为止） | 多智能体推理 | 七步 Prompt | 五维打分 + 置信度闸 |
| 人工审批 | 无（Workflow 自动） | Pending Action + RBAC | 无（只给建议） | HITL 双签 + S0~S3 分级 |
| 审计 | deduplication_event | LLM + 工具双审计 | 无 | ew_audit_log |
| 部署 | Docker/K8s/Helm | Docker Compose | Dify SaaS | MySQL 边表 + Python |
| 适合规模 | 中大型团队 | 中大型企业 | 小业务 | 水利国企单工程 |

### 5.2 本项目可借鉴点优先级

| 优先级 | 借鉴点 | 来源 | 落地方式 |
|--------|--------|------|----------|
| **P0 已完成** | 告警聚合 + 拓扑关联 + 根因排序 + 罚信度闸 | 腾讯 TCOP + Keep + SxDevOps | aggregate_alarms_to_events + compute_blast_radius + rank_root_causes + apply_confidence_gate |
| **P0 已完成** | 知识图谱建图 | SxDevOps knowledge_graph | build_topology.py（364 节点 + 1196 边） |
| **P0 已完成** | 不可逆操作白名单 + HITL | SxDevOps Pending Action | escalation-agent.md S0~S3 分级 + 双签闸 |
| **P1 可借鉴** | 三分态去重（full/partial/keep） | Keep alert_deduplicator | aggregate_alarms_to_events 内引入 partial 合并而非丢弃 |
| **P1 可借鉴** | threshold + create_on 的 incident 可见性 | Keep rulesengine | 团内告警数 < threshold 时 incident 不可见，避免单告警误触 |
| **P1 可借鉴** | 后台常驻拓扑关联扫描 | Keep topology_processor | topology.py 做成 systemd timer 周期扫，而非手动 --analyze |
| **P1 可借鉴** | 从问题文本推断知识环境 | SxDevOps resolve_knowledge_environments_from_text | 用户输入 st_code 时自动定位到对应工程/大坝/设备 |
| **P1 可借鉴** | missing_fields 反馈 | SxDevOps build_action_preflight_contract | 告警缺上下文时主动告诉用户补什么 |
| **P2 未来** | AI Suggestion 缓存（input_hash） | Keep ai_suggestion_bl | 未来加 LLM 总结时，按输入 hash 缓存省 Token |
| **P2 未来** | AIFeedback 反馈回路 | Keep AIFeedback | 未来加 LLM 后，用户采纳/拒绝记入 ew_audit_log 改进建议 |
| **P2 未来** | Workflow YAML 自动化 | Keep workflowmanager | 把"红色告警 → 发通知 + 查历史 + 生成报告"写成声明式 Workflow |
| **P2 未来** | 多智能体编排 | SxDevOps AGENT_ORCHESTRATION_PROFILES | 未来加 LLM 时，分诊断/取证/变更/Runbook 四类 agent |
| **P2 未来** | Plan-ReAct 五阶段 trace | SxDevOps _build_plan_react_trace | 未来加 LLM 时，每次调用记五阶段状态可追溯 |
| **P2 未来** | LLM + 工具双审计 | SxDevOps AIOpsModelInvocation/AIOpsToolInvocation | 未来加 LLM 时，记每次 LLM 入参/出参/Token |
| **P2 未来** | LLM 补充规则短板 | Dify 七步 Prompt | 规则跑 TOP3 候选 + 置信度，LLM 做自然语言解释 + 不确定性说明 |
| **P3 反面教材** | 避免 services.py 16403 行强耦合 | SxDevOps | 本项目继续保持 SKILL.md 模块化，单文件不过千行 |

### 5.3 关键结论

1. **本项目已走在 Dify 方案前面**：五维打分 = 评分系统，historical_recurrence = 故障库轻量版，
   罚信度闸 = "证据不足明确说明"的严格版。作者自述要加的两个模块本项目都有了。
2. **本项目对标 Keep 的核心能力已有**：告警聚合（aggregate_alarms_to_events）、
   拓扑关联（compute_blast_radius + causes 边）、根因排序（rank_root_causes）、
   人工审批（HITL 双签）。Keep 的 Workflow 和 AI 缓存是未来增量。
3. **本项目对标 SxDevOps 的核心能力已有**：知识图谱、RBAC、操作分级、HITL。
   SxDevOps 的多智能体编排和二阶段 LLM 是未来加 LLM 时的参考。
4. **本项目相对三方案的优势**：水利行业因果规则库（25 条 causes 规则）下沉规则层、
   五维可解释打分（每维可拆引用 ew_info_message.id + 拓扑路径）、严格三道安全闸
   （置信度阈值 + HITL 双签 + 结构化输出）。规则层产物可缓存可机审，幻觉源比纯 LLM 方案少。
5. **本项目相对三方案的短板**：hermes 按 SOP 多轮驱动 LLM，**Token 成本可能更高**而非更低——
   每轮含 SQL 执行 + LLM 推理 + 追问，多轮累加耗时也可能比 Dify 单轮七步更久；
   SOP 是 Markdown 描述而非 Keep 的声明式 YAML，可机审性/版本化/复用性弱；
   LLM 轮次未审计（ew_audit_log 只记操作不记 LLM 调用），多轮驱动的成本和幻觉源都不可追溯；
   causes 边没覆盖到的新故障类型，规则层抓不到，全靠 LLM 临场补，但 LLM 受 SOP 约束不如 Dify 自由。

---

## 附录 A：两个仓库的本地克隆信息

```
/opt/git/keep        # keephq/keep, 135 MB, git clone --depth 1
  ∟: keep/api/alert_deduplicator/alert_deduplicator.py  # 去重引擎
  ∟: keep/rulesengine/rulesengine.py                  # 规则引擎 + incident 生成
  ∟: keep/topologies/topology_processor.py            # 拓扑关联后台
  ∟: keep/api/bl/ai_suggestion_bl.py                  # AI 关联与总结
  ∟: keep/workflowmanager/workflow.py                 # Workflow 引擎

/opt/git/sxdevops    # aiyiyi121/sxdevops, 24 MB, git clone --depth 1
  ∟: backend/aiops/services.py      # 16403 行 Agent 编排核心
  ∟: backend/aiops/knowledge_graph.py  # 2965 行知识图谱
  ∟: backend/aiops/action_handlers.py  # 342 行 Action 路由
  ∟: backend/rbac/                  # RBAC 权限模块
```

## 附录 B：腾讯 TCOP 三条经验的对标完成度

| 腾讯 TCOP 经验 | 本项目对标 | Keep 对标 | SxDevOps 对标 | Dify 对标 |
|---------------|-----------|----------|--------------|----------|
| 先收敛再定位 | ✅ aggregate_alarms_to_events | ✅ alert_deduplicator + rulesengine | 🔴 靠事件墙聚合 | 🟡 查当前告警但不去重 |
| 知识图谱当翻译器 | ✅ 364 节点 + 1196 边 | ✅ topology_processor | ✅ knowledge_graph.py | ✅ CMDB MCP |
| 给 AI 装刹车 | ✅ 三道闸（置信度 + HITL + 结构化输出） | 🟡 无 HITL（Workflow 自动） | ✅ Pending Action + RBAC | 🔴 无（只给建议不执行） |

**结论**：本项目在"给 AI 装刹车"上对标最完整（三道闸），Keep 和 SxDevOps 各有部分，
Dify 完全没有（设计上就不执行操作，所以不需要刹车）。

---

## 附录 C：本项目真实架构校正（重要）

> 本附录是对全文一处实质错误的订正。原文第五章节曾把本项目描述为
> "零 Token 成本（纯规则）/ 秒级响应 / 无 Workflow 自动化"，这是错的。
> 本项目是 **hermes agent + skill SOP 驱动的智能体**，不是纯规则脚本。
> 现据 `early-warning-v3/SKILL.md` 的 `hermes:` metadata、
> `intelligent-analysis-workflow.md` 的 workflow 缓存 key、
> `powerelf-inspection` 的 envelope `agent` 字段校正如下。

### C.1 真实架构

```
用户问题（"最近告警情况"/"这个根因是什么"…）
    ↓
hermes agent 加载 SKILL.md → 识别意图 → 按 SOP 驱动
    ↓
SOP = intelligent-analysis-workflow.md（Markdown 描述的 7 步 workflow）
    ↓
Step 1 数据采集 → SQL（不耗 Token）
Step 2 告警聚合 → 调 lib/topology.py aggregate_alarms_to_events（规则层，不耗 Token）
Step 3 跨域关联 → 调 compute_blast_radius（规则层，不耗 Token）
Step 4 根因排序 → 调 rank_root_causes + apply_confidence_gate（规则层，不耗 Token）
    ↓
hermes 把规则层产物喂给 LLM 做解释/追讨/报告
    ↓
LLM 第 1 轮：读规则层产物 + 用户问题 → 生成自然语言摘要 + 候选追问
LLM 第 2 轮：读用户补的上下文 → 深化解释
LLM 第 N 轮：…（hermes 自主决定轮次，直到 SOP 终止条件）
    ↓
输出报告（含规则层 ranked_causes + LLM 自然语言解释）
```

### C.2 与三方案的真实成本对比

| 维度 | 本项目真实情况 | 对比 Keep | 对比 SxDevOps | 对比 Dify |
|------|--------------|----------|--------------|----------|
| LLM 轮次 | hermes 按 SOP 自主多轮，轮次不固定 | Keep AI 仅做总结/关联，单轮 | SxDevOps 二阶段 LLM，固定 2 轮 | Dify 七步全单轮 LLM |
| Token 成本 | **可能最高**——多轮累加，每轮含 SQL 结果 + LLM 推理 + 追问上下文 | 低（单轮总结） | 中（固定 2 轮） | 中（单轮但 prompt 长） |
| 耗时 | **可能最久**——每轮含 SQL 执行 + LLM 推理 + 用户追问等待 | 秒级 | 秒级 | 秒级 |
| 规则层占比 | 告警聚合/根因排序/置信度闸走规则层，占 SOP 4/7 步 | 全走规则（CEL）+ AI 单轮总结 | 规则层薄，全靠 LLM | 全靠 LLM |
| Workflow | intelligent-analysis-workflow.md 已是 SOP 级 workflow（Markdown 描述），且有 `workflow:{user_id}:{minute_bucket}` 缓存 | YAML 声明式 workflow | Django + DRF 编排 | Dify Agent 模式 Prompt 约束 |

### C.3 缓存策略校正

原文说"无 AI 缓存"是错的。本项目现状：

1. **SOP 级缓存已有**：`intelligent-analysis-workflow.md` 第 928 行
   `workflow:{user_id}:{minute_bucket}`——同一用户 5 分钟内重复触发同一 workflow 返回上次结果。
   这是 **session 级缓存**，命中可跳过整轮 SOP（含规则层 + LLM 层），省 Token。
2. **规则层产物可缓存但未做**：`aggregate_alarms_to_events` + `rank_root_causes` 的产物
   可按"告警 fingerprint + 时间窗口"做 fingerprint 缓存——命中则跳过本轮 SOP 的规则层 4 步，
   只让 LLM 做解释层。**这是可落地的 P1 增量**，对标 Keep 的 input_hash 思路。
3. **LLM 解释层难缓存**：hermes 每轮 LLM 入参含用户追问上下文，难做 input_hash 命中。
   只能靠 session 级缓存（第 1 条）整轮跳过。

### C.4 落地优先级更新（替换原第五章 P1/P2 表的错误行）

| 优先级 | 借鉴点 | 来源 | 落地方式（校正版） |
|--------|--------|------|----------|
| **P0 已有** | SOP 级 workflow 缓存 | 本项目 intelligent-analysis-workflow.md 第 928 行 | `workflow:{user_id}:{minute_bucket}` 5 分钟内复用，已实现 |
| **❌ 已撤回** | 规则层产物 fingerprint 缓存 | Keep input_hash 思路（曾列为 P1 增量） | **撤回理由**：平台已有两层缓存覆盖大部分场景——① hermes `prompt_caching.py`（Anthropic cache_control，同会话多轮输入 token 省 ~75%）② SOP 级 workflow 缓存（同用户 5 分钟整轮跳过）。指纹缓存唯一剩余场景（跨用户/跨会话同批告警）在水利值班场景命中率低，且告警增量导致 alarm_ids 键频繁失效；缓存表 + 失效管理 + 清理监控对 skill 层是 2-3 天 + 持续维护的重负担，与省下的 Token 不成比例。**结论：不做，真需要跨会话产物缓存时提给 hermes 平台做** |
| **P0 平台已有** | LLM 调用审计 | hermes-agent（`agent/usage_pricing.py` CanonicalUsage + `conversation_loop.py` update_token_counts + `/usage` 命令） | **skill 层不要重复建表**——token/耗时/费用/用量条平台已实现并落 `_session_db`。skill 层只需在业务表（如 `topo_alarm_event`）加 `session_id` 字段，把"根因分析结果 ← 哪个 hermes 会话"关联起来，配合平台 `/usage` 做成本归因 |
| **P1 增量** | SOP 分轮 mission 约束 | SxDevOps AGENT_ORCHESTRATION_PROFILES | SOP 显式分"诊断轮/取证轮/变更轮/Runbook 轮"，每轮 LLM mission 明确，避免一轮 LLM 同时出假设又自证又下结论 |
| **P2 增量** | 声明式 YAML workflow | Keep workflowmanager | 把 SOP 的 Markdown 描述段抽为声明式 YAML，可机审/版本化/复用 |

### C.5 教训

写这份分析时我犯的错：把"规则层产物不耗 Token"误推为"整个项目不耗 Token"，
把"intelligent-analysis-workflow.md 的 Markdown SOP"漏看为"无 Workflow"。
根因是只读了 lib/topology.py 的规则层代码就下结论，没读 SKILL.md 的 hermes metadata
和 intelligent-analysis-workflow.md 的 workflow 缓存段。

**给后续工作的铁律**：判断本项目任何能力时，先分清是
①规则层产物（lib/topology.py，不耗 Token，可缓存）
还是 ②hermes SOP 驱动的 LLM 层（多轮，耗 Token，难缓存），
两者性质完全不同，不可混为一谈。
