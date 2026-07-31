# 写护栏（Write Gate）— 写操作 preview→confirm→execute

> **本文件职责**：管"**写之前**"——任何会改配置 / 发通知到真人的操作，**必须先 preview + 等用户显式确认**才能执行。
>
> **不在本文件**：阈值/等级/条件枚举的语义（→ `rules/threshold-rules.md`）、通知渠道与沉默期（→ `strategies/notification-strategy.md` + `silence-period.md`）、屏蔽机制本身（→ `strategies/warning-shield.md`）。本文件只给"写操作的门控流程与边界"。

---

## 一、强制原则（优先级高于一切）

1. **默认 dry-run**：任何写操作先出 preview 块，**等用户回复"确认"后才调接口**；不确认 = 不写。
2. **不得自授权跳过**：agent **不得**以"自动化 / 演示 / 模拟 / 用户之前说过"为由跳过 preview（抄阿里云 `cms-alert-rule-create` critical rule #12）。每次写都要当次确认。
3. **只读免确认**：查规则 / 查消息 / 统计 / 列表（GET）**永不**需要确认。
4. **直达真人 = 最高谨慎**：凡会触发短信/微信/钉钉/邮件到真人的动作，preview **必须**显式列出"谁能收到 + 哪个渠道 + 沉默期"。

---

## 二、写操作分级

| 级 | 操作（端点） | 后果 | 门控 |
|---|---|---|---|
| **T1 硬配置变更** | `POST /info-rules/create`、`PUT /info-rules/update`、`DELETE /info-rules/delete`、`POST /notice-tactics/create` | 错配阈值/等级/范围 → **漏报或误报到真人** | 完整 preview→confirm→execute |
| **T2 通知触发** | 判断流程末尾"触发通知分发"（`threshold-rules.md`）；凡 agent 实际发起通知 | **直接 SMS/IM 到真人** | 同 T1，preview 必含通知对象+渠道+沉默期 |
| **T3 状态标记** | `PUT /info-message/confirm`、`PUT /camera-info/confirm` | 改确认标记，blast radius 小 | 轻量确认（一句话："将确认该预警，对吗？"） |
| **T3 → T1 升级** | `POST /info-rules/ignoreConfirm`（屏蔽） | **压掉真实告警**，风险等同改阈值 | **按 T1** 完整 preview |

> 判据：**会不会让该响的告警不响、或不该响的告警响到真人？** 会 → T1/T2。

---

## 三、preview 模板（固定格式，T1/T2 必用）

### 3.1 规则写操作（create/update/delete）

```
⚠️ 即将【创建 | 更新 | 删除】预警规则，请确认：
  动作:    创建
  规则名:  XX水库水位超警
  类型:    ew_type=0（水位预警）
  关联:    st_id=128 → "XX水库"（att_st_base.name 解析；多站/设备同理列出）
  等级:    level_r=3（III级·较重）
  阈值:    condition=FIVE(>)  content=[150.0, null]  →  "rz > 150.0m"
  通知:    策略"水库值班组" / 短信+微信 / 沉默期 60min
  影响:    对 XX水库 实时 rz 越限生成 I~IV 级预警，并通知上述对象
确认执行？回复"确认"后我才调用接口；不确认 = 不写。
```

> 字段解析要求：`st_id`/`eq_id`/`dot_id` **解析成站名/设备名**再展示（别让用户看裸 id）；`extend` 的 `condition`+`content` **翻成中文条件句**（如 `rz > 150.0m`）；`ew_type`/`level_r` 带中文枚举。

### 3.2 通知触发（T2）

```
⚠️ 即将触发通知，请确认（直达真人）：
  触发源:  规则"XX水库水位超警"（ew_info_rules.id=…）
  事件:    rz=155.2m 超阈值 150.0m，超标 3.5% → 动态 IV 级，最终 III 级
  收件人:  水库值班组（张三、李四）+ 防汛主管
  渠道:    短信 + 微信
  沉默期:  60min（期内同规则不重复通知）
确认发送？回复"确认"后才发；不确认 = 不发。
```

### 3.3 状态标记（T3 轻量）

```
将确认预警「XX水库水位超警 · III级 · gather_time=…」，对吗？（确认后 message_confirm 置位）
```

---

## 四、边界规则（A2）

- **DELETE 改软删优先**：删规则前**先建议禁用**（`status=0` 或 `deleted=1`），硬删（`DELETE /info-rules/delete`）需用户**二次确认**并说明为何不能软删。硬删不可逆，软删可恢复。
- **批量写**：一次建/改 N 条 → **汇总 preview**（逐行列 `规则名 + 关联站 + 阈值中文句`）+ **单次确认**；**禁止静默批量**（不 preview 就批量调接口）。N>10 时只列前 10 + "…共 N 条"，但必须明示总数。
- **屏蔽（ignoreConfirm）**：按 T1，且 preview 必须警示"屏蔽期间该规则**不产生任何告警与通知**，确认已知风险？"——防误屏蔽压掉真实险情。
- **通知对象写前 probe**（借鉴 cms）：建/改规则关联通知策略前，若能 probe 收件人是否有效（用户是否在职/有联系方式），异常时在 preview 标注"⚠️ 收件人 X 可能无效"。
- **越权拦截**：只读账号（chatbi/governance 用的 RO 账号）**根本不能写**——若 agent 误用只读凭证调写接口，会被 DB 拒；写操作必须用 early-warning 自己的 `POWERELF_API_TOKEN`（见 `_shared/references/api-auth.md`）。

---

## 五、流程

```
用户请求一个写动作（建/改/删规则、屏蔽、确认、触发通知）
  → 判级（T1 / T2 / T3，§二）
  → 出对应 preview 块（§三），解析 id→名称、条件→中文句
  → 停下，等用户当次显式"确认"
  → 收到确认 → 调写接口
  → 未确认 / 拒绝 → 不写，回报"已取消，未做任何更改"
  → 只读请求（GET 查询）→ 不经此闸，直接查
```

---

## 六、何时不经此闸

- 任何 GET（查规则列表、查预警消息、统计、视频报警列表）
- agent **内部推演**（"若 rz=155 会触发 III 级"的沙盘演算，不调接口、不发通知）——这是读/算，不是写。**但**若要把推演结果真发出去，则落 T2。
- 回答用户"规则长什么样"的解读（只读展示）
