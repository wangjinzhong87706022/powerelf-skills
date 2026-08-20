# 20260819 全量评测代码冻结违规——取证结论与处置记录

> 评测运行：`hermes-eval-20260819-183116`（2026-08-19 18:31 启动，2026-08-20 01:54 结束，156 题实测）
> 结果：104/156 题级联判 CODE-MUTATED（score=0），总体 0.245 为假分；有效片段仅 mutation 前的 52 题（DG 集均分 0.735，与基线 0.759/0.774 一致，无回归）。
> 本文档为 state.db（`~/.hermes/state.db`）只读取证 + git 取证的结论存档，处置已于 2026-08-20 执行。

## 一、两处突变的完整证据链

### 突变 1：`powerelf-data-governance/SKILL.md`（首现 routing-evals-v1/4）

- **触发题**：routing-evals-v1[4]「水位数据有缺失，帮我用插值方法补全缺失的部分」（session `20260819_213529_cf02ec`，21:35–21:38）。
- **行为链**（state.db messages 实录）：
  1. agent 跑 `interpolate.py`/`missing_detector.py`，自写 3 个 `/tmp/check_missing_rsvr*.py` 发现**真实缺陷**：两个脚本不检测时间断档（设备停报整段空窗），st_rsvr_r 30 天窗口 eq_id=NULL 存在 244h 断档（08-06→08-16）。
  2. 依 hermes 平台系统提示词「发现 skill 过时/有错就立即 patch，不要等用户开口」，先调 `skill_manage(action='patch', name='powerelf-data-governance')` → **失败**（`Skill 'powerelf-data-governance' not found in active profile 'default'`，skill 以 `powerelf` 顶层软链注册）。
  3. **降级用裸 `patch` 工具直接改文件**：给「插值/缺失补全」行追加「⚠️ 已知限制：…244h 断档…」（patch diff 全文见 state.db 该 session，仅此一行变更）。
- **全历史查证**：state.db 全部 session 中对 SKILL.md 的写类调用（patch/write_file/edit_file/skill_manage）**仅此一次**。
- **重要澄清**：工作区 diff 的另外 3 处 hunk（st_river_r 拉黑对齐 f59130a、eq_id 关联键说明、表名删除线）**不是 agent 改的**，是评测启动前已存在的人工未提交修改（护栏基线内合法起点），处置时**予以保留**。

### 突变 2：`powerelf-inspection/autoresearch/results_cases.json`（首现 inspection-eval-cases/CORR-NEG-1）

- **不是直接写入**：state.db 全历史对该文件的写类调用为 **0**。
- **真实机制**：CORR-NEG-1 的 agent 按 SKILL.md/autoresearch README 文档化用法执行
  `cd powerelf-inspection && python3 impl/eval_runner.py --only CORR-NEG-1,CORR-POS-1,CORR-NEG-2,CORR-POS-2 --verbose`（session `20260820_013125_1cb3de`），
  而 `impl/eval_runner.py` 的 `--out` **默认值就是该文件**且无条件整文件覆写 → 47 条全量验收记录（score 47/47，commit 09a70fc）被 4 条部分运行结果（score 4）冲掉。

## 二、级联机制（为什么 104 题全灭）

冻结护栏（dcdf775）基线只存内容哈希、只检测不恢复（`docs/hermes_eval_runner.py` 快照/检测逻辑）。routing-evals-v1/4 突变后文件持续偏离基线 → 后续每题复检都命中 → 从第 53 题起连续 104 题判 CODE-MUTATED（含整个 routing-evals-v2、inspection-eval-criteria、inspection-eval-cases）。

## 三、处置（2026-08-20 执行）

| 动作 | 方式 | 结果 |
|---|---|---|
| SKILL.md 外科回滚 | Edit 只逆向 agent 追加的那一段（原行原文取自 patch diff 的 `-` 行），**不整文件 checkout** | diff 只剩 3 处人工 hunk（-138/-168/-297） |
| results_cases.json | `git checkout --`（工作区改动为评测覆写副作用，无人工内容） | score=47 恢复 |
| agent 发现内容 | 验证准确后**人工采纳**回 SKILL.md 同位置 + `evolution/feedback-log.md` 首条 | 内容不丢失、出处转人工 |
| 突变前工作区 | 13 个 tracked 人工修改提交为 pre-eval 快照 | 干净树，重跑可复现 |
| 根因修复 | runner 护栏升级（检测→自动恢复→单题重试）+ `eval_runner.py --out` 默认改 /tmp + hermes 写拦截 hook | 见对应提交 |

## 四、遗留的真实缺陷（已转正规渠道，勿再由评测 agent 就地修）

1. `interpolate.py`/`missing_detector.py` 不检测时间断档（30 天窗口 244h 空窗漏检）——已记 feedback-log；修复属人工开发工作。
2. hermes 平台提示词鼓励「发现 skill 有错立即 patch」+ `skill_manage` 对软链注册的 skill 名解析失败 → agent 降级裸写。平台侧问题，本仓库以写拦截 hook 防御。

## 五、事后追记：护栏升级自身引入的 skill 同名冲突（2026-08-20 当日）

**现象**：阶段3 实跑验证 3 题（output/verify-freeze-real-20260820-160809）全部秒败
「FAIL（session 未写入）」，state.db 零新增 session；手工复现
`hermes chat -s powerelf-data-governance` 报 `Unknown skill(s)`。

**根因**：内容快照镜像原设计落盘在仓库内 `{out-dir}/freeze-baseline/`。仓库经
`~/.hermes/skills/powerelf` 软链整体暴露给 hermes 技能扫描器，镜像里的
`powerelf-data-governance/SKILL.md`、`powerelf-inspection/SKILL.md` 副本与真 skill
**同名** → 扫描器报 `Skill name collision`（3 candidates）→ `-s` 裸名解析全部失败。
时间线：15:39 dry-run 引入第一份镜像 → 16:08 实跑 3 题全灭。即**护栏自己毒死了被测对象**。

**修复**：
1. 清除仓库内镜像目录（output/verify-freeze-dry、output/verify-freeze-real-*），裸名解析立即恢复；
2. 快照目录固定为仓库兄弟目录 `powerelf-eval-freeze/<out目录名>-<时间戳>/`（跨重启留存、不进 git、不在技能扫描范围），报告 JSON/MD 留痕 `freeze_baseline_dir`；
3. `snapshot_guarded_state` 加 fail-fast 断言：快照目录位于仓库内直接 raise（不降级为"护栏关闭"，防症状被掩盖）；单测 `test_snapshot_dir_inside_repo_rejected` 回归。

**普适教训**：任何会经 `~/.hermes/skills/` 软链可见的路径下出现 `SKILL.md`（评测产物
镜像、备份、worktree 副本）都会造成同名冲突。另：`early-warning` 裸名存在**存量** 4 路
冲突（本仓库 early-warning/ + early-warning-v3/ 旧目录 + SmartTwinRes-skills 两份副本），
runner SET_TO_SKILL 用的是 `early-warning-v3`（可正常解析），不受影响；人工调用时避免
用 `early-warning` 裸名即可。
