# 设计：chatbi 去 Vanna 化 + agent 自主 NL2SQL 直连库（B 簇）

- **日期**：2026-07-14
- **目标仓库**：`powerelf-skills` monorepo（权威源 `/home/scada/powerelf-skills`）
- **主受影响 skill**：`powerelf-chatbi`
- **次受影响**：`_shared`（`lib/db.py` 加只读 URL、`references/sql-discipline.md` 新增）
- **来源**：复用 `knowledge-work-plugins/data` 中 `write-query` / `sql-queries`（SQL 写作纪律）；并落实"chatbi 弃后端 Vanna、改 agent 自主 NL2SQL 直连库"的架构决策
- **路线图位置**：外部通用数据技能 → powerelf 复用路线图 **B 簇（chatbi 增强）**，A→B→C 三簇之二；承接 `2026-07-13-governance-profiling-qa-gate-design.md` §9 的 B 簇后续建议

## 1. 背景与动机

`powerelf-chatbi` 原设计依赖后端 Vanna API 做 NL2SQL（`sql-generation.md:8` 的"用户问题 → Vanna API → SQL → 执行"，
即**路径 A**：转发后端执行）。经确认：

1. 后端 `/chatbi/aiReporter/message` 端点**并非 Vanna 封装**，且**当前版本不使用该端点**。
2. 团队决定**不引入 Vanna 等外部 NL2SQL 框架**（增加复杂性）。
3. 改走**路径 B**：hermes agent 用 LLM + `schema.md` + `few_shots.md` 自主生成只读 SQL，
   经本地安全执行工具通过 `_shared/lib/db.py` 只读直连水利库执行。

由此 B 簇性质从原路线图的"方法论嫁接"升级为**架构转型 + 方法论嫁接**：

- **架构转型**：chatbi 从仓库"最轻 skill"（7 个纯 `.md`，无 `impl/lib/algorithms`）变为**执行型 skill**，
  首次引入可执行代码（`impl/query_exec.py`）。这是仓库**第一个执行动态 SQL 的工具**——既有 `impl` 工具
  （governance 的 `profiler.py`/`anomaly_detector.py`）执行的都是固定 SQL，chatbi 要执行 agent 现场生成的
  任意 SQL，安全护栏成为设计核心。
- **方法论嫁接**：把外部 `write-query`/`sql-queries` 的 SQL 写作纪律搬入，作为 agent 自主写 SQL 的护栏。

同时修两个既有事实源对齐问题（chatbi 探索 agent 发现）：chatbi 未引用 `_shared/references/schema.md`
（自维护冗余表映射）；`few_shots.md` 用 `st_id`/`powerelf_data.` 前缀，与 schema.md 关联键铁律（`stcd`/`eq_id`）
及 `_shared/lib/db.py` 默认库名（`powerelf_srm_yml`）冲突——这是 agent 写出 `Unknown column` 错误的根因。

形态沿用 A 簇约定：**方法论文档进 `_shared/`、可运行代码进 skill、判断类护栏为被动文档**；安全护栏为代码层强制。

## 2. 范围

### 做
- 新增 `powerelf-chatbi/impl/query_exec.py`（接收 SQL，7 层安全护栏，只读执行，输出 JSON）。
- 新增 `powerelf-chatbi/impl/test_query_exec.py`（护栏单测，对齐 `test_profiling.py` 风格）。
- 新增 `_shared/references/sql-discipline.md`（通用 SQL 写作纪律，跨域；来源 write-query/sql-queries）。
- 改造 `powerelf-chatbi/rules/sql-generation.md`：删 Vanna 流程→agent 自主；接入 schema.md 关联键铁律；
  表映射段瘦身指向 schema.md 薄指针；保留水利特化（单位陷阱、软删除纪律）。
- 改造 `powerelf-chatbi/rules/intent-classification.md`：后端虚构类名（NL2SQLAgent/ChartDecisionAgent/
  ChartCodeAgent/InterpretationAgent）→ hermes agent 编排描述。
- 改造 `powerelf-chatbi/SKILL.md`：删 `/chatbi/aiReporter/*` 三端点；加 query_exec 使用说明；
  `prerequisites.env_vars` 加只读账号变量。
- 改造 `powerelf-chatbi/references/few_shots.md`：修正 `st_id`→`stcd`/`eq_id`、`powerelf_data.`→统一库名。
- 改造 `_shared/lib/db.py`：加 `get_readonly_sqlalchemy_url()`（单一事实源导出只读 URL）。
- 最小改 `powerelf-chatbi/rules/chart-selection.md`：去掉 Builder 类名列的后端耦合（类型扩充留 B' 簇）。
- 配置只读账号 `chatbi_ro`（`GRANT SELECT ON powerelf_srm_yml.*`），凭证走 `~/.hermes/.env`。

### 不做（YAGNI）
- ❌ **图表选择方法论扩充**（数据关系→图表映射表、黑名单、设计原则、色盲色板）→ 拆到 **B' 簇**后置。
- ❌ **dashboard 多图组合意图**（intent 表 ANALYSIS 未实现项）→ B' 簇。
- ❌ **工具内部封装 NL2SQL**（`impl/ask.py --question` 内部调 LLM）→ NL2SQL 由 hermes agent 负责，工具不重复造。
- ❌ **表白名单**→ 用只读账号纵深防御替代（DB 层兜底，免维护表清单）。
- ❌ **改写后端 powerelf 平台**→ 后端不在本仓库；本仓库零后端代码改动。
- ❌ **删除 chatbi skill**→ 保留职责定位（纯查询入口，monitor/data-governance 转交依赖），仅改实现路径。
- ❌ **纯正则做 SQL 校验**→ 用 sqlparse（准确识别语句类型，只读账号已兜底，sqlparse 作补充）。

## 3. 文件变更清单

### 新建
| 路径 | 内容 |
|------|------|
| `powerelf-chatbi/impl/query_exec.py` | CLI：`--sql --db "$RO_DB_URL" [--limit 2000] [--display 20] [--format json\|table]`；7 层护栏；输出 JSON profile |
| `powerelf-chatbi/impl/test_query_exec.py` | 合成各类 SQL → 断言 7 层护栏（拒绝写语句/多语句/系统库、注入 LIMIT、超时、空/大结果） |
| `_shared/references/sql-discipline.md` | 6 维需求解析 / 7 条性能纪律 / 窗口函数清单 / CTE 规范 / NULLIF 除零 / 6 条错误排查；声明方言中立（MySQL） |

### 修改
| 路径 | 改动 |
|------|------|
| `powerelf-chatbi/rules/sql-generation.md` | `:8` Vanna 流程→agent 自主；顶部加 schema.md 关联键铁律引用+摘要；表映射段(`:16-62`)瘦身指向 schema.md；注意事项段加 sql-discipline.md 引用 |
| `powerelf-chatbi/rules/intent-classification.md` | `:38-44` 后端 Agent 流水线→hermes agent 编排（意图→生成SQL→query_exec→解读） |
| `powerelf-chatbi/SKILL.md` | 删 `:47-49` aiReporter 三端点；加 query_exec 使用段；`prerequisites.env_vars` 加 `POWERELF_DB_READONLY_USER/PASSWORD` |
| `powerelf-chatbi/references/few_shots.md` | 全量修正 `st_id`→`stcd`/`eq_id`（按 schema.md 铁律表）、`powerelf_data.`→裸表名（库名由 db.py 统一） |
| `powerelf-chatbi/rules/chart-selection.md` | `:5-13` Builder 类名列→图表语义描述（去后端耦合）；类型不扩充 |
| `_shared/lib/db.py` | 加 `get_readonly_sqlalchemy_url()`（读 `POWERELF_DB_READONLY_*`，后备 `SRM_DB_*`，再后备主账号） |
| `_shared/bootstrap.sh` | 扩展导出 `RO_DB_URL`（调 `get_readonly_sqlalchemy_url`），供 chatbi query_exec 使用 |

### 配置（DBA 操作，非仓库文件）
```sql
CREATE USER 'chatbi_ro'@'%' IDENTIFIED BY '<from ~/.hermes/.env>';
GRANT SELECT ON powerelf_srm_yml.* TO 'chatbi_ro'@'%';
-- ~\.hermes\.env 追加：POWERELF_DB_READONLY_USER=chatbi_ro / POWERELF_DB_READONLY_PASSWORD=...
```

## 4. 组件设计

### 4.1 `impl/query_exec.py`——7 层安全护栏（核心）

```bash
source ../_shared/bootstrap.sh   # 导出 DB_URL + RO_DB_URL（后者调 get_readonly_sqlalchemy_url）
python3 impl/query_exec.py --sql "SELECT tm,rz FROM st_rsvr_r WHERE stcd='606K215001' AND tm>DATE_SUB(NOW(),INTERVAL 7 DAY)" \
    --db "$RO_DB_URL" [--limit 2000] [--display 20] [--format json|table]
```

```python
import sqlparse
from sqlalchemy import create_engine, text

FORBIDDEN_KEYWORDS = frozenset({
    "insert","update","delete","drop","alter","create","truncate",
    "grant","revoke","replace","merge","call","load","handler","rename",
})
SYSTEM_SCHEMAS = frozenset({"mysql","information_schema","performance_schema","sys"})
MAX_LIMIT = 2000          # 强制 LIMIT 上限（呼应 sql-generation.md max-num）
QUERY_TIMEOUT_SEC = 120   # 语句级超时（水利跨表JOIN/长时段聚合留足余量）

def validate_readonly(sql: str) -> str:
    """7 层护栏：返回消毒后 SQL，或抛 ValueError。"""
    # 层3：单语句
    stmts = sqlparse.split(sql)
    if len(stmts) != 1:
        raise ValueError("仅允许单条语句（拒绝 ; 堆叠）")
    parsed = sqlparse.parse(stmts[0])[0]
    # 层2：语句类型必须是 SELECT（含 WITH ... SELECT 即 CTE）
    if parsed.get_type() != "SELECT":
        raise ValueError(f"仅允许只读 SELECT，检测到: {parsed.get_type() or '未知/写语句'}")
    # 层2双保险：关键字黑名单
    lowered = sql.lower()
    if any(kw in lowered for kw in FORBIDDEN_KEYWORDS):
        raise ValueError("检测到写操作关键字，已拒绝")
    # 层4：系统库黑名单
    for sch in SYSTEM_SCHEMAS:
        if f"{sch}." in lowered:
            raise ValueError(f"禁止访问系统库: {sch}")
    # 层5：强制 LIMIT（无则子查询包裹注入，安全处理 CTE/UNION）
    sql = ensure_limit(sql, MAX_LIMIT)
    return sql

def execute(sql, db_url, display=20):
    sql = validate_readonly(sql)
    engine = create_engine(db_url, connect_args={"connect_timeout": 10})
    with engine.connect() as conn:
        # 层7：只读事务（双保险，主防线是只读账号）
        conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        # 层6：语句级超时（MySQL 5.7.4+ MAX_EXECUTION_TIME，毫秒）
        conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME={QUERY_TIMEOUT_SEC*1000}"))
        result = conn.execute(text(sql))
        cols = list(result.keys())
        rows = result.fetchmany(display)
    return {"sql_sanitized": sql, "columns": cols, "rows": rows,
            "row_count": len(rows), "truncated": len(rows) == display,
            "execution_timeout_sec": QUERY_TIMEOUT_SEC}
```

**7 层护栏汇总**：

| 层 | 机制 | 实现 | 作用 |
|----|------|------|------|
| 1 | 只读账号 | `chatbi_ro` 仅 `GRANT SELECT` | DB 层兜底，代码全失守也写不了库 |
| 2 | 语句类型 | sqlparse `get_type()=="SELECT"` + 关键字黑名单 | 拒绝写语句 |
| 3 | 单语句 | `sqlparse.split()` 长度==1 | 拒绝 `;` 堆叠注入 |
| 4 | 系统库黑名单 | 拒绝 `mysql./information_schema./...` | 防探权限/schema |
| 5 | 强制 LIMIT | 无 LIMIT 则子查询包裹注入，上限 2000 | 防全表扫描 |
| 6 | 超时 | `MAX_EXECUTION_TIME=120000ms` | 防慢查询拖垮 |
| 7 | 只读事务 | `SET SESSION TRANSACTION READ ONLY` | 双保险 |

**输出 JSON**（对齐 profiler.py 风格）：`{sql_sanitized, columns, rows, row_count, truncated, execution_timeout_sec}`。

**依赖**：`sqlparse`（纯 Python 轻量；governance 已用 sqlalchemy/pandas/numpy/pymysql，pip 可装）。

### 4.2 `_shared/references/sql-discipline.md`（通用 SQL 纪律，跨域）

来源 `knowledge-work-plugins/data/skills/{write-query,sql-queries}/SKILL.md`（已分析精确行号）：

| 来源:行号 | 内容 |
|-----------|------|
| write-query L23-31 | NL2SQL 6 维需求解析框架（输出列/过滤/聚合/JOIN/排序/LIMIT） |
| write-query L66-74 | 7 条性能纪律（禁 SELECT *、EXISTS>IN、早过滤、JOIN 类型、避免相关子查询、JOIN 爆炸） |
| write-query L62-80 | CTE 结构 + 可读性规范（语义命名、表别名、注释"为什么"） |
| sql-queries L283-304 | 窗口函数清单（ROW_NUMBER/RANK、运行总数、LAG/LEAD、FIRST/LAST_VALUE、占比） |
| sql-queries L405-417 | ROW_NUMBER 去重范式（`PARTITION BY ... ORDER BY ... DESC` 取 rn=1） |
| sql-queries L419-428 | 6 条错误排查铁律（NULLIF 除零、列名限定、GROUP BY 含非聚合列、CAST、方言语法） |

**丢弃**：PG/Snowflake/BQ/Redshift/Databricks 五大方言速查段（sql-queries L11-277）。**保留方言中立条目**，
并在水利化补注里点名 MySQL（如 MySQL 8+ 支持窗口函数/CTE；`DATE_FORMAT`/`DATE_ADD`/`JSON_EXTRACT`/`REGEXP`）。

结构：① 何时用（agent 生成 SQL 前）② 6 维需求解析 ③ 7 条性能纪律 ④ 窗口函数/CTE 规范 ⑤ 6 条错误排查
⑥ 声明与 `_shared/references/{schema,data-profiling,analysis-qa-checklist,statistical-caution}.md` 的姊妹关系。

### 4.3 `sql-generation.md` 改造（水利特化 + 接入铁律）

- **删**：`:8` Vanna 流程 → agent 自主流程图（问题→LLM+schema+few_shots+sql-discipline→SQL→query_exec→数据）。
- **顶部加**：schema.md 关联键铁律摘要（`st_rsvr_r/st_pptn_r/st_percolation_r`→`stcd` varchar；
  `st_pressure_r`→`eq_id` bigint；铁律：`eq_equip_base.code` 是字符串不能塞 `eq_id='...'`）+ 指向 schema.md 的薄指针。
- **表映射段(`:16-62`)瘦身**：保留水利语义提示（rz=库水位、dr 单位陷阱、电气 varchar），但关联键/完整字段指向 schema.md，不复制。
- **注意事项段**：保留（deleted=0、tenant_id、tm、max-num/display-num、单位陷阱），加 sql-discipline.md 引用（纪律清单在那）。
- **重试机制**：从"后端 Vanna 4 次"改为"hermes agent 见 SQL 错误自修正重试"（query_exec 透传 MySQL 错误信息）。

### 4.4 `_shared/lib/db.py` 只读 URL

```python
def get_readonly_sqlalchemy_url(...) -> str:
    """chatbi 专用只读连接串：优先 POWERELF_DB_READONLY_*，后备 SRM_DB_*，再后备主账号。
    只读账号 chatbi_ro 仅 GRANT SELECT，作 query_exec.py 的 DB 层兜底。"""
    ro_user = os.getenv("POWERELF_DB_READONLY_USER") or DB_USER
    ro_pwd  = os.getenv("POWERELF_DB_READONLY_PASSWORD") or DB_PASSWORD
    return f"mysql+pymysql://{ro_user}:{ro_pwd}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
```

### 4.5 其余改造（简述）
- **intent-classification.md**：`:38-44` 流水线从"NL2SQLAgent→ChartDecisionAgent→..."改为"hermes agent：
  意图分类→生成SQL(用sql-discipline/schema/few_shots)→query_exec执行→选图(chart-selection)→解读"。
- **SKILL.md**：删 aiReporter 三端点（`:47-49`，已废弃）；保留其余 4 端点（knowledge/graph/llm/menu，与 NL2SQL 无关）；
  加 query_exec 使用段；env_vars 加只读账号。
- **few_shots.md**：全量按 schema.md 铁律修正关联键 + 统一库名（去 `powerelf_data.` 前缀）。
- **chart-selection.md**：Builder 类名列→图表语义（去后端耦合），类型不扩充（B' 簇）。

## 5. 数据流

```
用户自然语言问题
      │
      ▼  hermes agent（LLM + schema.md + few_shots.md + sql-discipline.md）
生成只读 SELECT（已遵循纪律：deleted=0、关联键 stcd/eq_id、禁 SELECT *）
      │
      ▼
chatbi/impl/query_exec.py --sql "..." --db "$RO_DB_URL"
      │  7 层护栏（只读账号 → sqlparse类型 → 单语句 → 系统库黑名单 → LIMIT → 超时120s → 只读事务）
      ▼
执行 → 结构化数据（JSON）
      │
      ▼  hermes agent
解读 / 选图(chart-selection.md) / 回复
      │
      ▼  若 SQL 错误：透传 MySQL 错误 → agent 自修正重试
```

**只读全程；无写库路径；无后端依赖（路径 A 废弃）。**

## 6. 错误处理

- **非只读/多语句/系统库/写关键字** → `ValueError`，非零退出 + 清晰提示（"chatbi 仅支持只读 SELECT 查询"）。
- **超时（>120s）** → MySQL `MAX_EXECUTION_TIME` 中断，非零退出 + "查询超时，请加时间过滤或 LIMIT"。
- **空结果** → 正常返回 `row_count=0`（不报错）。
- **大结果** → 截断至 `--display`，`truncated=true` 标志。
- **SQL 语法错误** → 透传 MySQL 错误信息（`BadSqlGrammar`/`Unknown column` 等）→ 喂给 agent 自修正重试。
- **只读账号未配置** → `get_readonly_sqlalchemy_url` 后备 `SRM_DB_*`/主账号 + 告警（**层1 DB 兜底降级**，但层2-7 代码护栏仍生效；开发期不阻断，**生产部署须配 chatbi_ro 只读账号**以恢复层1）。
- **sqlparse 缺失** → import 期 `sys.exit(1)` + 提示 `pip install sqlparse`（对齐 profiler.py 的 HAS_DEPS 模式）。

## 7. 测试

- **单测** `impl/test_query_exec.py`（对齐 `test_profiling.py`）：合成各类 SQL → 断言：
  - 拒绝 `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE`（层2）
  - 拒绝 `;` 堆叠多语句（层3）
  - 拒绝 `mysql.user`/`information_schema.*`（层4）
  - 无 LIMIT 的 SQL 被注入 LIMIT（层5），已有 LIMIT 保留
  - WITH ... SELECT（CTE）被识别为合法只读
  - 空/大结果分别返回 `row_count=0` / `truncated=true`
  - 纯函数 `validate_readonly` 无 DB 依赖，可入 CI
- **文档验证**：(a) sql-discipline.md 无 PG/Snowflake/BQ 方言泄漏；(b) sql-generation.md 链接完整；
  (c) few_shots.md 全量 grep `st_id`/`powerelf_data.` 零残留（与 schema.md 铁律一致）。
- **链接完整性**：sql-discipline.md 被 sql-generation.md + query_exec.py docstring 引用；
  schema.md 关联键铁律被 sql-generation.md + few_shots.md 引用。
- **冒烟**（手动 runbook）：配 chatbi_ro 账号 → `source 引导 && python3 impl/query_exec.py --sql "SELECT ... FROM st_pressure_r WHERE eq_id=..." --db "$RO_DB_URL"` 真实库产出合理 JSON，人工核对。

## 8. 关键决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| NL2SQL 引擎 | agent 自主（弃 Vanna） | 不引入外部框架；hermes agent 即 LLM，NL2SQL 是其强项 |
| 执行模型 | agent 生成 SQL + 工具安全执行 | 职责分离；工具不调 LLM，不重复造 agent 能力 |
| 安全护栏 | 只读账号纵深防御（7 层） | DB 层兜底最硬；免维护表白名单 |
| SQL 校验 | sqlparse（非正则） | 准确识别语句类型；只读账号已兜底，sqlparse 作补充层 |
| 超时 | **120s**（非 10s） | 水利跨表 JOIN（监测+设备+测站）、长时段聚合（"过去一年月均"）、GNSS 高频大表；10s 易误杀；配合 LIMIT 2000 仍防全表扫描 |
| LIMIT 上限 | 2000 | 呼应既有 sql-generation.md max-num=2000 |
| SQL 纪律落点 | `_shared/references/sql-discipline.md`（跨域） | 符合 A 簇"方法论文档进 _shared"约定（与 data-profiling.md 同级）；inspection 未来开放 agent 写 SQL 可复用 |
| 图表扩充 | 后置 B' 簇 | 独立增量，不阻塞路径 B 跑通 |
| chatbi 去留 | 保留（改实现） | 职责定位有价值（monitor/data-governance 纯查询转交依赖）；rules/few_shots 资产可复用 |
| aiReporter 端点 | 删除 | 后端不用该端点，非 Vanna 封装 |
| schema.md 铁律接入 | sql-generation.md 顶部 + few_shots 修正 | 消除 `Unknown column` 根因（st_id vs stcd/eq_id） |

## 9. 后续（不在本 spec 内）

- **B' 簇（图表选择方法论）**：`data-visualization`/`build-dashboard`/`create-viz` → 扩 chart-selection.md
  （数据关系→图表映射表、黑名单、设计原则、色盲色板、水利时序特化、数据量分层门槛、KPI 卡/dashboard 组合）。
- **C 簇（元工具）**：`data-context-extractor` → schema 文档模板 / 打包脚本。
- **跨簇**：sql-discipline.md 若被 inspection 开放 agent 写 SQL 时复用，无需移动（已在 _shared）。
- **只读账号自动化**：若实战中反复漏配，评估加 `_shared/bootstrap.sh` 的只读账号存在性自检。
