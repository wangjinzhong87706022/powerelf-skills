# 预警规则引擎 — 算法详解

## 1. 阈值预警条件判断

10种条件枚举的完整伪代码：

```python
def check_threshold(value, rule):
    """
    value: Decimal 采集值
    rule.extend: {"content": [min, max], "condition": "枚举值"}
    返回: bool 是否触发
    """
    extend = json.loads(rule.extend)
    content = extend["content"]
    condition = extend["condition"]
    min_val = Decimal(str(content[0])) if content[0] is not None else None
    max_val = Decimal(str(content[1])) if len(content) > 1 and content[1] is not None else None
    v = Decimal(str(value))

    if condition == "ZERO":      # = 等于
        return v == min_val
    elif condition == "ONE":     # != 不等于
        return v != min_val
    elif condition == "TOW":     # >= 大于等于
        return v >= min_val
    elif condition == "THREE":   # <= 小于等于
        return v <= max_val
    elif condition == "FOUR":    # {} 闭区间 [min, max]
        return v >= min_val and v <= max_val
    elif condition == "FIVE":    # > 大于
        return v > min_val
    elif condition == "SIX":     # < 小于
        return v < max_val
    elif condition == "SEVEN":   # () 开区间 (min, max)
        return v > min_val and v < max_val
    elif condition == "EIGHT":   # {) 左闭右开 [min, max)
        return v >= min_val and v < max_val
    elif condition == "NINE":    # (} 左开右闭 (min, max]
        return v > min_val and v <= max_val
    else:
        raise ValueError(f"未知条件枚举: {condition}")
```

## 2. 动态等级调整

```python
def compute_dynamic_level(value, threshold, configured_level):
    """
    根据超标幅度自动计算预警等级，与配置等级取更严重的。

    value: Decimal 实际采集值
    threshold: Decimal 阈值边界值（触发条件对应的 min 或 max）
    configured_level: int 规则中配置的等级 (1-4)
    返回: int 最终等级 (1-4, 1最严重)
    """
    if threshold == 0:
        return configured_level

    exceed_ratio = abs(value - threshold) / abs(threshold)

    if exceed_ratio <= Decimal("0.10"):
        dynamic_level = 4  # IV级(一般)
    elif exceed_ratio <= Decimal("0.30"):
        dynamic_level = 3  # III级(较重)
    elif exceed_ratio <= Decimal("0.60"):
        dynamic_level = 2  # II级(严重)
    else:
        dynamic_level = 1  # I级(特别严重)

    return min(configured_level, dynamic_level)  # 取更严重的（数值越小越严重）


LEVEL_NAMES = {
    1: "I级(特别严重)",
    2: "II级(严重)",
    3: "III级(较重)",
    4: "IV级(一般)",
}
```

**示例**：
- 规则: 水位 > 150m (配置等级 III), 实际 155m -> 超标 3.3% -> 动态 IV -> 最终 III
- 规则: 水位 > 150m (配置等级 IV), 实际 170m -> 超标 13.3% -> 动态 III -> 最终 III

## 3. 预警描述语句生成

```python
def generate_statement(condition, value, min_val, max_val):
    v = float(value)
    statements = {
        "ZERO":   f"值等于{min_val}，触发预警",
        "ONE":    f"值不等于{min_val}，触发预警",
        "TOW":    f"值{v}超过阈值{min_val}，超出{abs(v - float(min_val)):.2f}",
        "THREE":  f"值{v}低于阈值{max_val}，低出{abs(float(max_val) - v):.2f}",
        "FOUR":   f"值{v}在区间[{min_val},{max_val}]内，触发预警",
        "FIVE":   f"值{v}大于{min_val}，超出{abs(v - float(min_val)):.2f}",
        "SIX":    f"值{v}小于{max_val}，低出{abs(float(max_val) - v):.2f}",
        "SEVEN":  f"值{v}在开区间({min_val},{max_val})内，触发预警",
        "EIGHT":  f"值{v}在区间[{min_val},{max_val})内，触发预警",
        "NINE":   f"值{v}在区间({min_val},{max_val}]内，触发预警",
    }
    return statements.get(condition, f"值{v}触发预警")
```

## 4. 开关量预警判断

```python
def check_switch(value, rule):
    """
    BigDecimal 精确比较，匹配开/关状态。
    """
    extend = json.loads(rule.extend)
    content = extend["content"]
    open_val = Decimal(str(content[0])) if content[0] is not None else None
    down_val = Decimal(str(content[1])) if len(content) > 1 and content[1] is not None else None
    v = Decimal(str(value))

    if open_val is not None and v.compareTo(open_val) == 0:
        return True, "已触发【开关量预警】: 设备处于开启状态"
    elif down_val is not None and v.compareTo(down_val) == 0:
        return True, "已触发【开关量预警】: 设备处于关闭状态"
    return False, None
```

## 5. 状态变化预警判断

```python
state_store = {}  # key: "{eqCode}:{dotAddress}:{ruleId}" -> last_value

def check_state_change(value, eq_code, dot_address, rule_id):
    """
    当前值与上次值不同时触发。无论是否触发都更新 stateStore。
    """
    key = f"{eq_code}:{dot_address}:{rule_id}"
    last_value = state_store.get(key)
    state_store[key] = value  # 始终更新

    if last_value is not None and value != last_value:
        return True, f"已触发【状态变化预警】: 指标值从{last_value}改变为{value}"
    return False, None
```

## 6. 大坝安全预警判定算法

### 6.1 多测点多指标判定

```python
def check_dam(dam_values_list, rule):
    """
    dam_values_list: List[dict] 断面下所有测点的监测数据
    rule.extend: List[DamExtendVo] 多条子规则
    rule.triggerNumber: int 触发数量阈值

    返回: (triggered: bool, trigger_points: list, direction_analysis: dict)
    """
    extend_list = json.loads(rule.extend)  # List of {field, content, condition}
    trigger_number = rule.triggerNumber

    trigger_points = []
    direction_results = []

    for point in dam_values_list:
        is_warning = False
        trigger_fields = []

        for sub_rule in extend_list:
            field = sub_rule["field"]
            raw_value = point.get(field)
            if raw_value is None:
                continue

            # 位移值取绝对值用于阈值比较
            abs_value = abs(Decimal(str(raw_value)))
            content = sub_rule["content"]
            condition = sub_rule["condition"]

            if check_threshold(abs_value, SimpleRule(content, condition)):
                is_warning = True
                trigger_fields.append(field)

        if is_warning:
            trigger_points.append({
                "pointId": point.get("pointId"),
                "triggerFields": trigger_fields,
            })

        # 方向性分析（使用带符号的原始值）
        direction_results.append(analyze_direction(point))

    trigger_count = len(trigger_points)
    triggered = trigger_count >= trigger_number

    # 一致性检查
    consistency = check_direction_consistency(direction_results)

    return triggered, trigger_points, direction_results, consistency
```

### 6.2 方向性分析

```python
def analyze_direction(point):
    """
    使用带符号的原始值分析位移方向。
    """
    delta_x = Decimal(str(point.get("wgs84DeltaX", 0)))
    delta_y = Decimal(str(point.get("wgs84DeltaY", 0)))
    delta_h = Decimal(str(point.get("wgs84DeltaH", 0)))

    direction = {
        "pointId": point.get("pointId"),
        "x_direction": "downstream" if delta_x > 0 else "upstream" if delta_x < 0 else "stable",
        "y_direction": "left" if delta_y > 0 else "right" if delta_y < 0 else "stable",
        "h_direction": "subsidence" if delta_h > 0 else "uplift" if delta_h < 0 else "stable",
        "delta_x": float(delta_x),
        "delta_y": float(delta_y),
        "delta_h": float(delta_h),
    }
    return direction


def check_direction_consistency(direction_results):
    """
    同一断面多个测点偏移方向一致 -> 可能是整体滑动，升级告警。
    相邻测点偏移方向相反 -> 可能是局部变形，关注。
    """
    x_dirs = [d["x_direction"] for d in direction_results if d["x_direction"] != "stable"]
    h_dirs = [d["h_direction"] for d in direction_results if d["h_direction"] != "stable"]

    result = {"overall_sliding": False, "local_deformation": False}

    # 一致性检查: 所有非稳定测点方向相同
    if len(x_dirs) >= 2 and len(set(x_dirs)) == 1:
        result["overall_sliding"] = True
        result["warning"] = f"X方向整体偏移: {x_dirs[0]}"

    if len(h_dirs) >= 2 and len(set(h_dirs)) == 1:
        result["overall_sliding"] = True
        result["warning_h"] = f"H方向整体: {h_dirs[0]}"

    return result
```

### 6.3 大坝监测字段

| 字段名 | 显示名 | 说明 |
|--------|--------|------|
| wgs84DeltaH | 三角形H | 垂直位移变化量 |
| wgs84DeltaX | 三角形X | 水平X位移变化量 |
| wgs84DeltaY | 三角形Y | 水平Y位移变化量 |
| wgs84TotalX | X累计变化量 | X方向累计位移 |
| wgs84TotalY | Y累计变化量 | Y方向累计位移 |
| wgs84TotalH | H累计变化量 | H方向累计位移 |

## 7. 趋势预警检测算法

```python
def check_trend(values, indicator_type):
    """
    检测连续单调变化趋势。

    values: List[Decimal] 最近N个采集值（按时间正序）
    indicator_type: str 指标类型 (rz/seepage/gnss/flow)

    返回: (triggered: bool, direction: str, count: int, rate: Decimal)
    """
    params = {
        "rz":       {"min_count": 3, "rate_threshold": Decimal("0.01")},   # 水位 1%
        "seepage":  {"min_count": 4, "rate_threshold": Decimal("0.02")},   # 渗压 2%
        "gnss":     {"min_count": 5, "rate_threshold": Decimal("0.005")},  # GNSS 0.5%
        "flow":     {"min_count": 3, "rate_threshold": Decimal("0.15")},   # 流量 15%
    }

    p = params.get(indicator_type, {"min_count": 3, "rate_threshold": Decimal("0.01")})

    if len(values) < p["min_count"]:
        return False, None, 0, Decimal("0")

    # 检测连续单调上升
    rising = all(values[i] > values[i - 1] for i in range(1, len(values)))
    # 检测连续单调下降
    falling = all(values[i] < values[i - 1] for i in range(1, len(values)))

    if not rising and not falling:
        return False, None, 0, Decimal("0")

    direction = "rising" if rising else "falling"
    count = len(values)
    change = abs(values[-1] - values[0])
    rate = change / abs(values[0]) if values[0] != 0 else Decimal("0")

    triggered = count >= p["min_count"] and rate >= p["rate_threshold"]
    return triggered, direction, count, rate
```

**趋势预警描述生成**：

```python
def generate_trend_statement(indicator_name, unit, direction, count, change, rate, current_value):
    dir_cn = "上升" if direction == "rising" else "下降"
    verb = "上涨" if direction == "rising" else "下降"
    return (
        f"{indicator_name}连续{count}次{dir_cn}，"
        f"累计{verb}{change:.2f}{unit}（{float(rate) * 100:.2f}%），"
        f"当前值{current_value}{unit}"
    )
```

## 8. 沉默期检查逻辑

```python
def check_silence(tactics_id, silence_time_min):
    """
    检查通知策略是否在沉默期内。

    tactics_id: int 通知策略ID
    silence_time_min: int 沉默时间(分钟)

    返回: bool True=在沉默期内(应跳过) / False=不在(可发送)
    """
    key = f"EW_NOTICE_TACTICS_KEYS_SILENT:{tactics_id}"
    return redis.exists(key)


def set_silence(tactics_id, silence_time_min):
    """
    通知发送完成后设置沉默期。
    """
    key = f"EW_NOTICE_TACTICS_KEYS_SILENT:{tactics_id}"
    redis.setex(key, silence_time_min * 60, "1")
```

## 9. 屏蔽检查逻辑

```python
def check_shield(rule):
    """
    检查规则是否被屏蔽。

    返回: bool True=应屏蔽(跳过) / False=正常处理
    """
    if rule.isIgnore != "1":
        return False  # 未启用屏蔽

    key = f"CLEAN_EW_RULES_KEYS_CONFIRM:{rule.id}"
    return redis.exists(key)


def set_shield(rule_id, ignore_time):
    """
    设置屏蔽。

    ignore_time: datetime 屏蔽截止时间
    """
    remaining = (ignore_time - datetime.now()).total_seconds()
    if remaining <= 0:
        raise ValueError("屏蔽截止时间不能早于当前时间")

    key = f"CLEAN_EW_RULES_KEYS_CONFIRM:{rule_id}"
    redis.setex(key, int(remaining), "1")


def cancel_shield(rule_id):
    """
    取消屏蔽。
    """
    key = f"CLEAN_EW_RULES_KEYS_CONFIRM:{rule_id}"
    redis.delete(key)
```

## 10. 通知策略匹配

```python
def find_matching_tactics(level, ew_rules_type):
    """
    按预警等级和预警类别匹配通知策略。

    SQL:
    SELECT * FROM ew_notice_tactics
    WHERE enable = 1
      AND find_in_set(#{level}, ewLevel)
      AND find_in_set(#{ewRulesType}, ewRulesType)
    """
    tactics_list = db.query("""
        SELECT * FROM ew_notice_tactics
        WHERE enable = 1
          AND FIND_IN_SET(%s, ew_level)
          AND FIND_IN_SET(%s, ew_rules_type)
    """, [level, ew_rules_type])

    return tactics_list


def dispatch_notification(ew_message, tactics):
    """
    完整通知分发流程:
    1. 检查沉默期
    2. 获取策略关联用户
    3. 按 notice_manner 分发到各通道
    4. 设置沉默期
    5. 记录通知结果
    """
    if check_silence(tactics.id, tactics.silenceTime):
        return  # 沉默期内，跳过

    users = db.query("""
        SELECT user_id FROM ew_notice_tactics_user WHERE tactcs_id = %s
    """, [tactics.id])

    params = build_notification_params(ew_message)

    for notice_type in tactics.noticeManner.split(","):
        notice_type = int(notice_type.strip())
        for user in users:
            send_notification(notice_type, user.user_id, params)
            save_notice_record(ew_message.id, notice_type, user.user_id)

    set_silence(tactics.id, tactics.silenceTime)
```

## 11. 完整预警处理流程

```python
def process_warning(value, rule, dam_values=None):
    """
    主入口: 从规则读取到通知分发的完整流程。

    value: Decimal 采集值（非大坝预警时使用）
    rule: 规则对象
    dam_values: List[dict] 大坝测点数据（仅大坝预警时使用）
    """
    # Step 1: 检查屏蔽
    if check_shield(rule):
        return  # 规则被屏蔽

    # Step 2: 按预警类型执行判断
    triggered = False
    statement = None
    final_level = rule.levelR

    if rule.ewType in (0, 1, 2, 6):  # 水位/水质/雨量/洪水 -> 阈值预警
        extend = json.loads(rule.extend)
        triggered = check_threshold(value, rule)
        if triggered:
            threshold = extract_threshold(extend)
            final_level = compute_dynamic_level(value, threshold, rule.levelR)
            statement = generate_statement(extend["condition"], value,
                                           extend["content"][0],
                                           extend["content"][1] if len(extend["content"]) > 1 else None)

    elif rule.ewType == 4:  # 开关量预警
        triggered, statement = check_switch(value, rule)

    elif rule.ewType == 3:  # 状态变化预警
        triggered, statement = check_state_change(value, rule.eqId, rule.dotId, rule.id)

    elif rule.ewType == 5:  # 大坝安全预警
        triggered, points, directions, consistency = check_dam(dam_values, rule)
        if triggered and consistency.get("overall_sliding"):
            final_level = min(final_level, 2)  # 整体滑动升级到 II级
            statement = build_dam_statement(points, directions, consistency)

    if not triggered:
        return

    # Step 3: 生成预警记录
    ew_message = save_ew_message(rule, value, final_level, statement)

    # Step 4: 触发通知分发
    tactics_list = find_matching_tactics(final_level, rule.ewType)
    for tactics in tactics_list:
        dispatch_notification(ew_message, tactics)

    return ew_message
```
