# Powerelf Hermes Agent Skills v2

规则内嵌、按需加载、自我进化的水利工程 AI Skill 集合。

## v2 架构特点

- **规则内嵌**: 核心算法直接写入 Skill，Agent 可独立判断，不依赖平台 API
- **按需加载**: 轻量入口 + 模块化规则文件，按用户意图加载，减少 token 消耗
- **自我进化**: 每个 Skill 包含可调参数表和反馈日志，支持参数持续优化
- **高可扩展**: 新增规则只需添加 .md 文件，无需修改已有结构

## Skills

| Skill | 规则文件数 | 说明 |
|-------|-----------|------|
| [powerelf-data-governance](powerelf-data-governance/SKILL.md) | 5规则+3算法 | 缺失检测、MAD异常检测、智能插值、离线监测、统计评分 |
| [powerelf-early-warning](powerelf-early-warning/SKILL.md) | 5规则+3策略 | 阈值/开关量/状态变化/大坝/趋势预警，视频AI报警，通知分发 |
| [powerelf-monitor](powerelf-monitor/SKILL.md) | 5规则+3算法 | 12类监测：水库/河道/闸站/潮汐/雨情/闸门/泵站/GNSS/渗流/渗压/墒情/白蚁 |
| [powerelf-inspection](powerelf-inspection/SKILL.md) | 10规则+2模式 | 智能巡检、数据采集、异常判定、复杂工况、规则进化、质量评估、代码检测、缺陷预测、路线优化、任务生命周期、缺陷分类、排班 |
| [powerelf-chatbi](powerelf-chatbi/SKILL.md) | 3规则 | 意图分类、图表选择、SQL生成（覆盖20+业务表） |

## 目录结构

```
powerelf-skills/
├── README.md                         # 本文件
├── .gitignore
├── .github/workflows/auto-merge.yml  # 全仓库唯一 PR 自动合并工作流
├── _shared/                          # ★ 跨 skill 共享层（单一事实源）
│   ├── lib/db.py                     #   统一数据库连接（POWERELF_DB_* + SRM_DB_* 后备）
│   ├── bootstrap.sh                  #   导出 DB_URL，统一 CLI 连接风格
│   ├── references/schema.md          #   唯一 st_* 表结构源
│   ├── algorithms/                   #   共享算法（MAD / 水位变化率 / 位移速率）
│   ├── rules/                        #   共享规则（水库 / 雨情分析）
│   ├── api-auth.md                   #   统一 REST 鉴权约定
│   └── evolution/                    #   进化机制模板
├── powerelf-data-governance/
│   ├── SKILL.md                      # 轻量入口 (~300 tokens)
│   ├── rules/                        # 5个规则模块
│   ├── algorithms/                   # 3个算法详解
│   └── evolution/                    # 参数表 + 反馈日志
├── powerelf-early-warning/
│   ├── SKILL.md
│   ├── rules/                        # 5个规则模块
│   ├── strategies/                   # 3个策略模块
│   └── evolution/
├── powerelf-monitor/
│   ├── SKILL.md
│   ├── rules/                        # 5个规则模块
│   ├── algorithms/                   # 3个算法详解
│   └── evolution/
├── powerelf-inspection/
│   ├── SKILL.md
│   ├── rules/                        # 10个规则模块
│   ├── impl/                         # 2个实现模式 (API + Python)
│   └── evolution/
└── powerelf-chatbi/
    ├── SKILL.md
    ├── rules/                        # 3个规则模块
    └── evolution/
```

> ℹ️ 本仓库为 **monorepo**，整合 5 个 powerelf 领域 skill + `_shared` 共享层。
> `darwin-skill`（通用 skill 优化器，独立上游 github.com/alchaincyf/darwin-skill）不纳入本仓库，单独管理。

## 加载层级

| 层级 | Token 消耗 | 内容 |
|------|-----------|------|
| Level 0 | ~300 | 入口索引，仅列出 skill 名称 |
| Level 1 | ~500 | Skill 入口，能力概览 + 加载指令 |
| Level 2 | ~1000-2000 | 规则模块，具体判断逻辑 |
| Level 3 | ~1500-3000 | 算法详解 / API 参考 |

## 自我进化机制

每个 Skill 的 `evolution/` 目录包含:

- **parameters.md** — 可调参数注册表（当前值、合理范围、调整依据）
- **feedback-log.md** — 执行反馈日志（事件、原因、改进措施）

进化流程:
1. Agent 执行规则 → 记录判断结果
2. 用户反馈不准确 → 记录到 feedback-log
3. 分析反馈模式 → 建议参数调整
4. 更新 parameters.md → 下次执行使用新参数

## 安装

```yaml
# ~/.hermes/config.yaml
skills:
  external_dirs:
    - /path/to/powerelf-skills             # clone 后的目录；Linux/macOS；Windows 示例 D:/code/powerelf-skills
```

> ⚠️ 各 skill 必须位于 `hermes-skills/<skill>/` 目录结构内运行，因为它们通过相对路径
> 引用 `_shared/` 共享层（数据库连接、表结构、算法等）。不要单独移动某个 skill 目录。

### 环境变量

不同 skill 按访问方式需要不同的环境变量:

```bash
# REST API 访问类（powerelf-monitor / powerelf-early-warning / powerelf-chatbi / inspection 实时监测模式）
export POWERELF_API_BASE="http://localhost:48080/admin-api"
export POWERELF_API_TOKEN="your-bearer-token"

# 数据库直连类（powerelf-data-governance / inspection 深度巡检模式）
export POWERELF_DB_HOST="localhost"
export POWERELF_DB_PORT="3306"
export POWERELF_DB_NAME="powerelf_srm_yml"
export POWERELF_DB_USER="root"
export POWERELF_DB_PASSWORD="your-password"   # 禁止在文档/代码中落盘明文，统一走环境变量
# 也可用旧的 SRM_DB_* 变量名（_shared/lib/db.py 向后兼容）
```

### 统一 DB_URL（数据库直连类 CLI）

所有 `impl/*.py` 的 `--db` 参数统一用 `$DB_URL`（由 `_shared/lib/db.py` 单一来源生成，
会正确尊重 `POWERELF_DB_PORT`）。执行工具前先 source 引导脚本：

```bash
source /path/to/powerelf-skills/_shared/bootstrap.sh
# 之后任意 skill 工具统一：python3 <skill>/impl/<tool>.py --db "$DB_URL" ...
```

## `_shared/` 共享层

跨 skill 复用的单一事实源集中在此，各 skill 仅引用、不复制：

| 路径 | 作用 |
|------|------|
| `_shared/lib/db.py` | 统一数据库连接层（`POWERELF_DB_*` + `SRM_DB_*` 后备，`get_connection` / `get_sqlalchemy_url` / `create_engine`） |
| `_shared/bootstrap.sh` | 导出 `DB_URL`，统一 CLI 连接风格 |
| `_shared/references/schema.md` | 唯一 `st_*` 表结构事实源 |
| `_shared/algorithms/` | 跨 skill 重复算法（MAD、位移/水位变化率等） |
| `_shared/api-auth.md` | 统一 `Authorization: Bearer` + `tenant-id` 头 |
