# 算法参考手册

本文档包含所有分析算法的完整公式、阈值和伪代码。Agent 执行分析时按此文档计算。

---

## 1. 水位变化率算法

### 计算公式

```
输入: 最近两次采集 z_new (新), z_old (旧)
变化量 = z_new - z_old
变化率 = |z_new - z_old| / z_old * 100%
```

### 预警阈值

| |变化率| | 级别 | 动作 |
|---------|------|------|
| > 1% | 关注 | 水位变化较快，持续监测 |
| > 3% | 预警 | 水位变化异常，需人工确认 |
| > 5% | 紧急 | 水位急剧变化，立即上报 |

### 伪代码

```python
def water_level_change_rate(z_new, z_old):
    """计算水位变化率"""
    if z_old is None or z_old == 0 or z_old == -1:
        return None, "数据缺失"
    if z_new is None or z_new == -1:
        return None, "数据缺失"

    change = z_new - z_old
    rate = abs(change) / z_old * 100  # 百分比

    if rate > 5:
        level = "紧急"
    elif rate > 3:
        level = "预警"
    elif rate > 1:
        level = "关注"
    else:
        level = "正常"

    return round(rate, 4), level
```

### 10分钟流量汇总

```python
def flow_summary_10min(records):
    """
    查询最近10分钟内所有设备数据
    按设备ID分组取最新一条，分别求和
    """
    latest_by_device = {}
    for r in records:
        dev = r['eq_id']
        if dev not in latest_by_device or r['tm'] > latest_by_device[dev]['tm']:
            latest_by_device[dev] = r

    sum_inq = sum(r['inq'] for r in latest_by_device.values() if r['inq'] is not None)
    sum_otq = sum(r['otq'] for r in latest_by_device.values() if r['otq'] is not None)
    return sum_inq, sum_otq
```

### 库容平衡校验

```python
def reservoir_balance_check(inq, otq, rz_new, rz_old, time_interval_hours):
    """
    理论水位变化 ≈ (inq - otq) * 时间间隔 / 库容曲线系数
    实际水位变化 = rz_new - rz_old
    偏差 = |实际变化 - 理论变化|
    """
    actual_change = rz_new - rz_old
    # 简化: 定性判断方向一致性
    if inq > otq:
        expected_direction = "上升"
        if rz_new < rz_old:
            return "异常", "入库大于出库但水位下降，可能存在蒸发/渗漏"
    elif inq < otq:
        expected_direction = "下降"
        if rz_new > rz_old:
            return "异常", "出库大于入库但水位上升，数据可能有误"
    else:
        expected_direction = "持平"

    return "正常", f"预期方向: {expected_direction}"
```

### 异常值识别

```python
def check_water_level_anomaly(rz, inq, otq, hist_min, hist_max):
    """识别水位/流量异常值"""
    anomalies = []
    if rz is None or rz == -1:
        anomalies.append("水位数据缺失")
    elif rz < hist_min or rz > hist_max:
        anomalies.append(f"水位超出历史极值[{hist_min}, {hist_max}]")

    if inq is not None and inq < 0:
        anomalies.append("入库流量为负")
    if otq is not None and otq < 0:
        anomalies.append("出库流量为负")

    return anomalies
```

---

## 2. GNSS 位移速率算法

### 计算公式

```
查询近两年数据，按测点地址分组
速率 = (最大值 - 最小值) / 月份数 * 100  (单位: cm/月)

分别计算三个方向:
  speedX = X方向速率
  speedY = Y方向速率
  speedH = H方向(高程)速率

变化率差 = 当年速率 - 去年速率  (判断是否加速)
```

### 速率等级

| 速率 (cm/月) | 等级 | 含义 | 建议动作 |
|--------------|------|------|----------|
| < 0.5 | 稳定 | 正常范围 | 常规监测 |
| 0.5 - 2.0 | 缓慢 | 缓慢变形 | 持续监测，关注趋势 |
| 2.0 - 5.0 | 中速 | 需关注 | 加密监测频率，现场核查 |
| > 5.0 | 快速 | 高风险 | 立即上报，启动应急预案 |

### 方向判断

```python
def displacement_direction(total_x, total_y, total_h):
    """判断位移方向"""
    directions = []

    # 水平X方向 (上下游)
    if total_x > 0:
        directions.append("向下游偏移")
    elif total_x < 0:
        directions.append("向上游偏移")

    # 垂直H方向 (沉降/隆起)
    if total_h > 0:
        directions.append("下沉")
    elif total_h < 0:
        directions.append("上升(隆起)")

    # 水平Y方向 (左右岸)
    if total_y > 0:
        directions.append("向右岸偏移")
    elif total_y < 0:
        directions.append("向左岸偏移")

    return directions
```

### 速率计算伪代码

```python
def calc_displacement_rate(data_points, months):
    """
    data_points: list of dict with keys delta_h, delta_x, delta_y
    months: 数据跨越的月份数
    """
    if months == 0 or not data_points:
        return None

    max_h = max(p['wgs84_delta_h'] for p in data_points if p['wgs84_delta_h'] is not None)
    min_h = min(p['wgs84_delta_h'] for p in data_points if p['wgs84_delta_h'] is not None)
    speed_h = (max_h - min_h) / months * 100  # cm/月

    max_x = max(p['wgs84_delta_x'] for p in data_points if p['wgs84_delta_x'] is not None)
    min_x = min(p['wgs84_delta_x'] for p in data_points if p['wgs84_delta_x'] is not None)
    speed_x = (max_x - min_x) / months * 100

    max_y = max(p['wgs84_delta_y'] for p in data_points if p['wgs84_delta_y'] is not None)
    min_y = min(p['wgs84_delta_y'] for p in data_points if p['wgs84_delta_y'] is not None)
    speed_y = (max_y - min_y) / months * 100

    def rate_level(speed):
        s = abs(speed)
        if s > 5: return "快速"
        if s > 2: return "中速"
        if s > 0.5: return "缓慢"
        return "稳定"

    return {
        'speed_h': round(speed_h, 2), 'level_h': rate_level(speed_h),
        'speed_x': round(speed_x, 2), 'level_x': rate_level(speed_x),
        'speed_y': round(speed_y, 2), 'level_y': rate_level(speed_y),
    }
```

### 一致性检查 (同一断面多测点)

```python
def consistency_check(section_points):
    """
    同一断面多个测点方向一致性检查
    section_points: list of dict with total_x, total_h
    """
    x_directions = [p['total_x'] > 0 for p in section_points]
    h_directions = [p['total_h'] > 0 for p in section_points]

    if len(set(x_directions)) == 1:
        return "整体滑动", "同断面测点偏移方向一致，可能是整体滑动，升级告警"
    elif len(set(x_directions)) > 1:
        return "局部变形", "相邻测点偏移方向相反，可能是局部变形，需关注"

    return "不确定", "数据不足以判断"
```

### 年度位移统计

```python
def annual_stats(gnss_daily_records):
    """
    从 srm_gnss_stat_day 表计算年度统计
    字段: maxh/minh/avgh, maxx/minx/avgx, maxy/miny/avgy
    """
    result = {}
    for dim in ['h', 'x', 'y']:
        max_val = max(r[f'max{dim}'] for r in gnss_daily_records if r[f'max{dim}'] is not None)
        min_val = min(r[f'min{dim}'] for r in gnss_daily_records if r[f'min{dim}'] is not None)
        result[f'annual_range_{dim}'] = round(abs(max_val - min_val), 2)
    return result
```

---

## 3. 闸泵电气参数校验算法

### 电压校验

```python
def check_voltage(uab, ubc, uca):
    """
    标准电压: 380V ±10% → 正常范围 [342, 418]
    放宽范围: [340, 420]
    电气参数为varchar类型，需parseFloat
    """
    voltages = []
    for v_str in [uab, ubc, uca]:
        try:
            v = float(v_str)
            voltages.append(v)
        except (TypeError, ValueError):
            return None, "电压数据无法解析"

    anomalies = []
    for v in voltages:
        if v < 340 or v > 420:
            anomalies.append(f"电压 {v}V 超出正常范围 [340, 420]")

    if anomalies:
        return "异常", "; ".join(anomalies)
    return "正常", "电压正常"
```

### 频率校验

```python
def check_frequency(freq_str):
    """标准频率: 50Hz ±2% → 正常范围 [49, 51], 放宽 [48, 52]"""
    try:
        freq = float(freq_str)
    except (TypeError, ValueError):
        return None, "频率数据无法解析"

    if freq < 48 or freq > 52:
        return "异常", f"频率 {freq}Hz 超出正常范围 [48, 52]"
    return "正常", f"频率 {freq}Hz 正常"
```

### 三相不平衡度

```python
def check_phase_imbalance(ia_str, ib_str, ic_str):
    """
    不平衡度 = max(|ia-ib|, |ib-ic|, |ia-ic|) / mean(ia, ib, ic)
    阈值: > 10% 预警
    """
    try:
        ia, ib, ic = float(ia_str), float(ib_str), float(ic_str)
    except (TypeError, ValueError):
        return None, "电流数据无法解析"

    mean_i = (ia + ib + ic) / 3
    if mean_i == 0:
        return "正常", "三相电流均为0"

    imbalance = max(abs(ia-ib), abs(ib-ic), abs(ia-ic)) / mean_i * 100

    if imbalance > 10:
        return "预警", f"三相不平衡度 {imbalance:.1f}% 超过10%阈值"
    return "正常", f"三相不平衡度 {imbalance:.1f}%"
```

### 闸门流量合理性

```python
def check_gate_flow(gtophgt, gtq, status, total_holes):
    """闸门流量合理性检查"""
    issues = []

    if gtophgt == 0 and gtq > 0:
        issues.append("闸门关闭但有流量，可能存在漏水")

    if gtophgt > 0 and gtq == 0:
        issues.append("闸门开启但无流量，可能存在堵塞")

    if gtopnum is not None and total_holes is not None and gtopnum > total_holes:
        issues.append(f"开启孔数 {gtopnum} 超过总孔数 {total_holes}")

    # 状态一致性
    if status == 0 and gtophgt > 0:
        issues.append("状态为关但有开度，数据不一致")

    if status == 1 and gtophgt == 0:
        issues.append("状态为开但开度为0，数据不一致")

    return issues
```

### 负载率分析

```python
def check_load_rate(actual_power_str, rated_power, is_running):
    """
    负载率 = 实际功率 / 额定功率
    额定功率从 eq_equip_base 获取
    """
    try:
        actual = float(actual_power_str)
    except (TypeError, ValueError):
        return None, "功率数据无法解析"

    if not is_running:
        return "停机", "设备未运行"

    if rated_power is None or rated_power == 0:
        return None, "缺少额定功率数据"

    load_rate = actual / rated_power

    if load_rate > 0.95:
        return "过载", f"负载率 {load_rate*100:.1f}% > 95%，过载预警"
    elif load_rate < 0.1:
        return "空载", f"负载率 {load_rate*100:.1f}% < 10%，空载运行需检查"
    return "正常", f"负载率 {load_rate*100:.1f}%"
```

### 冷却系统检查

```python
def check_cooling(fan_fault, fan_run, is_running, ot_str, it_str):
    """冷却系统检查"""
    issues = []

    if fan_fault == 1:
        issues.append("风机故障")

    if fan_run == 0 and is_running == 1:
        issues.append("泵运行但风机未开")

    if ot_str is not None and it_str is not None:
        try:
            ot, it = float(ot_str), float(it_str)
            temp_rise = it - ot
            if temp_rise > 10:
                issues.append(f"温升 {temp_rise:.1f}度 > 10度，冷却不足")
        except (TypeError, ValueError):
            pass

    return issues
```

### 励磁系统检查

```python
def check_excitation(ul_str, al_str, is_running):
    """励磁系统检查"""
    if not is_running:
        return "正常", "设备未运行，无需检查励磁"
    try:
        ul = float(ul_str)
    except (TypeError, ValueError):
        return None, "励磁电压数据无法解析"

    if ul == 0:
        return "异常", "运行中励磁电压为0，励磁系统异常"
    return "正常", "励磁系统正常"
```

---

## 4. 降雨强度计算与等级划分

### 降雨强度计算

```python
def rainfall_intensity(p, dr, table='st_pptn_r'):
    """
    计算降雨强度 (mm/h)

    st_pptn_r: dr 单位是分钟，需转换: 强度 = p / (dr/60)
    st_pptn_region_r: intv 单位已经是小时: 强度 = drp / intv
    """
    if table == 'st_pptn_r':
        if dr is None or dr == 0:
            return None
        return p / (dr / 60)  # mm/h
    elif table == 'st_pptn_region_r':
        if dr is None or dr == 0:
            return None
        return p / dr  # dr 实际是 intv, 单位小时
    return None
```

### 降雨等级划分 (24小时累计)

| 等级 | 24h雨量 (mm) | 颜色代码 | 颜色 |
|------|-------------|----------|------|
| 小雨 | 0.1 - 9.9 | green | 绿色 |
| 中雨 | 10.0 - 24.9 | blue | 蓝色 |
| 大雨 | 25.0 - 49.9 | yellow | 黄色 |
| 暴雨 | 50.0 - 99.9 | orange | 橙色 |
| 大暴雨 | 100.0 - 249.9 | red | 红色 |
| 特大暴雨 | >= 250.0 | purple | 紫色 |

### 强度等级判定

```python
def rainfall_intensity_level(intensity_mm_h):
    """按小时强度判定"""
    if intensity_mm_h > 30:
        return "极端降雨"
    elif intensity_mm_h > 16:
        return "暴雨级别"
    elif intensity_mm_h > 8:
        return "大雨级别"
    elif intensity_mm_h > 2.5:
        return "中雨级别"
    else:
        return "小雨级别"

def rainfall_24h_level(dyp_24h):
    """按24小时累计判定等级"""
    if dyp_24h >= 250:
        return "特大暴雨"
    elif dyp_24h >= 100:
        return "大暴雨"
    elif dyp_24h >= 50:
        return "暴雨"
    elif dyp_24h >= 25:
        return "大雨"
    elif dyp_24h >= 10:
        return "中雨"
    elif dyp_24h >= 0.1:
        return "小雨"
    return "无降雨"
```

### 累计降雨趋势预警

```python
def check_cumulative_rainfall(daily_records, days=3, threshold_3d=100, threshold_7d=200):
    """
    查询最近N天的dyp(日雨量)求和
    3天>100mm → 持续降雨预警
    7天>200mm → 严重持续降雨
    """
    total = sum(r['dyp'] for r in daily_records[:days] if r['dyp'] is not None)

    if days >= 7 and total > threshold_7d:
        return "严重持续降雨", f"{days}天累计 {total:.1f}mm > {threshold_7d}mm"
    elif days >= 3 and total > threshold_3d:
        return "持续降雨预警", f"{days}天累计 {total:.1f}mm > {threshold_3d}mm"
    return "正常", f"{days}天累计 {total:.1f}mm"
```

### 雨量数据校验

```python
def check_rainfall_anomaly(p, dr, dyp):
    """雨量数据校验"""
    issues = []
    if p is not None and p < 0:
        issues.append("时段雨量为负")
    if p is not None and dr is not None and dr >= 50 and p > 200:
        issues.append(f"单小时雨量 {p}mm > 200mm，数据异常或极端天气")
    if dr is not None and dr == 0 and p is not None and p > 0:
        issues.append("时段为0但有雨量，数据异常")
    if dyp is not None and dyp < 0:
        issues.append("日雨量为负")
    return issues
```

---

## 5. Mann-Kendall 趋势检验 (简化版)

### 完整伪代码

```python
def mann_kendall_test(values):
    """
    Mann-Kendall 趋势检验简化版
    输入: 时间序列 values[]
    输出: 趋势方向, S统计量, 是否显著
    """
    n = len(values)
    if n < 4:
        return "数据不足", 0, False

    # 计算S统计量
    S = 0
    for i in range(n):
        for j in range(i + 1, n):
            if values[j] > values[i]:
                S += 1
            elif values[j] < values[i]:
                S -= 1

    # 判断趋势方向
    if S > 0:
        trend = "上升趋势"
    elif S < 0:
        trend = "下降趋势"
    else:
        trend = "无明显趋势"

    # 显著性判断 (简化版临界值)
    # n=10: |S|>16 显著; n=20: |S|>52 显著; n=50: |S|>264 显著
    # 简化公式: 临界值 ≈ 1.96 * sqrt(n*(n-1)*(2*n+5)/18)
    import math
    variance = n * (n - 1) * (2 * n + 5) / 18
    critical = 1.96 * math.sqrt(variance)  # 95%置信度

    significant = abs(S) > critical

    return trend, S, significant
```

### 使用场景

- 水位长期趋势: 连续30天以上数据判断涨落趋势
- 位移趋势: 连续6个月以上数据判断是否持续变形
- 渗压趋势: 判断渗压是否持续升高

---

## 6. 变化点检测算法

### 完整伪代码

```python
def change_point_detection(values, threshold_ratio=0.3):
    """
    变化点检测: 寻找数据统计特性突变的位置
    输入: 时间序列 values[], 阈值比例(相对于序列标准差)
    输出: 变化点位置列表
    """
    import statistics

    n = len(values)
    if n < 10:
        return []

    std = statistics.stdev(values)
    threshold = std * threshold_ratio
    change_points = []

    for i in range(1, n - 1):
        left_mean = statistics.mean(values[:i])
        right_mean = statistics.mean(values[i:])
        diff = abs(right_mean - left_mean)

        if diff > threshold:
            change_points.append({
                'position': i,
                'left_mean': round(left_mean, 4),
                'right_mean': round(right_mean, 4),
                'diff': round(diff, 4),
                'direction': '上升' if right_mean > left_mean else '下降'
            })

    # 去重: 合并相邻变化点
    filtered = []
    for cp in change_points:
        if not filtered or cp['position'] - filtered[-1]['position'] > 5:
            filtered.append(cp)

    return filtered
```

### 变化点含义

- 数据均值在该位置发生突变
- 可能原因: 设备校准、环境变化、工程干预
- 水位变化点: 可能对应闸门操作、降雨事件
- 位移变化点: 可能对应地震、库水位剧变

---

## 7. 周期性检测 (自相关函数)

### 完整伪代码

```python
def detect_periodicity(values, max_lag=None):
    """
    通过自相关函数(ACF)检测周期性
    输入: 时间序列 values[]
    输出: 主周期长度, ACF峰值
    """
    import math

    n = len(values)
    if max_lag is None:
        max_lag = n // 3  # 最大滞后不超过序列长度的1/3

    mean_val = sum(values) / n
    variance = sum((v - mean_val) ** 2 for v in values) / n

    if variance == 0:
        return None, 0  # 常数序列无周期

    acf_values = []
    for lag in range(1, max_lag + 1):
        cov = sum((values[i] - mean_val) * (values[i - lag] - mean_val)
                  for i in range(lag, n)) / n
        acf = cov / variance
        acf_values.append((lag, acf))

    # 找ACF峰值 (排除lag=0)
    peaks = []
    for i in range(1, len(acf_values) - 1):
        if acf_values[i][1] > acf_values[i-1][1] and acf_values[i][1] > acf_values[i+1][1]:
            if acf_values[i][1] > 0.3:  # ACF > 0.3 视为显著
                peaks.append(acf_values[i])

    if not peaks:
        return None, 0

    # 取最显著的峰值
    best_peak = max(peaks, key=lambda x: x[1])
    return best_peak[0], round(best_peak[1], 4)
```

### 典型周期

| 监测指标 | 典型周期 | 说明 |
|----------|----------|------|
| 水位 | 24小时 | 日变化(日夜间来水差异) |
| 温度 | 24小时 | 日变化 |
| 雨量 | 季节性 | 汛期/非汛期 |
| 渗压 | 24小时或无明显周期 | 受水位影响 |
| GNSS位移 | 无明显短周期 | 长期趋势为主 |

---

## 8. 指数平滑预测 (Holt-Winters)

### 公式

```
水平:   Lt = alpha * (Xt - St-m) + (1-alpha) * (Lt-1 + Tt-1)
趋势:   Tt = beta * (Lt - Lt-1) + (1-beta) * Tt-1
季节:   St = gamma * (Xt - Lt) + (1-gamma) * St-m
预测:   Ft+h = Lt + h*Tt + St-m+h
```

### 水利场景参数建议

| 指标 | alpha | beta | gamma | 季节周期m | 预测步长 |
|------|-------|------|-------|----------|---------|
| 水位 | 0.2 | 0.05 | 0.2 | 24(小时) | 1-6小时 |
| 渗压 | 0.15 | 0.03 | 0.15 | 24(小时) | 1-24小时 |
| GNSS位移 | 0.1 | 0.02 | 0.1 | 168(周) | 1-7天 |
| 流量 | 0.3 | 0.1 | 0.2 | 24(小时) | 1-6小时 |

### 伪代码

```python
def holt_winters_forecast(data, alpha, beta, gamma, m, h):
    """
    三次指数平滑预测
    data: 历史数据序列
    alpha, beta, gamma: 平滑参数
    m: 季节周期
    h: 预测步长
    """
    n = len(data)
    if n < 2 * m:
        return None, "数据不足，需要至少2个完整季节周期"

    # 初始化
    L = [sum(data[:m]) / m]
    T = [(sum(data[m:2*m]) - sum(data[:m])) / m / m]
    S = [data[i] - L[0] for i in range(m)]

    # 递推
    for t in range(m, n):
        Lt = alpha * (data[t] - S[t - m]) + (1 - alpha) * (L[-1] + T[-1])
        Tt = beta * (Lt - L[-1]) + (1 - beta) * T[-1]
        St = gamma * (data[t] - Lt) + (1 - gamma) * S[t - m]
        L.append(Lt)
        T.append(Tt)
        S.append(St)

    # 预测未来h步
    forecast = []
    for i in range(1, h + 1):
        f = L[-1] + i * T[-1] + S[-m + (i - 1) % m]
        forecast.append(round(f, 4))

    return forecast, "成功"
```

---

## 9. ARIMA 预测

### 模型表示

```
ARIMA(p, d, q)
  AR(p):  自回归 — Xt = c + phi1*Xt-1 + ... + phi_p*Xt-p + eps_t
  I(d):   差分阶数 — 使序列平稳的差分次数
  MA(q):  移动平均 — Xt = c + eps_t + theta1*eps_t-1 + ... + theta_q*eps_t-q
```

### 水利场景参数建议

| 指标 | p | d | q | 说明 |
|------|---|---|---|------|
| 水位 | 2-4 | 1 | 1-2 | 日变化有周期性 |
| 渗压 | 3-5 | 1 | 1-2 | 缓慢变化 |
| GNSS | 2-3 | 1-2 | 1 | 需要差分消除趋势 |
| 流量 | 3-6 | 1 | 2-3 | 波动较大 |

### 模型选择流程

```
1. 平稳性检验 (ADF检验)
   if p-value > 0.05:
     需要差分 d += 1
     重复检验

2. 确定p和q:
   - 查看ACF(自相关)图 → 确定q
   - 查看PACF(偏自相关)图 → 确定p

3. 模型拟合:
   最小化 AIC = 2k - 2ln(L)
   k=参数个数, L=似然函数

4. 残差检验:
   残差应为白噪声 (Ljung-Box检验 p > 0.05)
```

### 伪代码

```python
def arima_predict(data, p, d, q, steps):
    """ARIMA预测框架"""
    # 差分
    diff_data = list(data)
    for _ in range(d):
        diff_data = [diff_data[i] - diff_data[i-1] for i in range(1, len(diff_data))]

    # 拟合AR系数 (Yule-Walker方程)
    ar_coeffs = fit_ar(diff_data, p)

    # 拟合MA系数 (最大似然估计)
    ma_coeffs = fit_ma(diff_data, q)

    # 预测
    forecast_diff = []
    for h in range(steps):
        pred = ar_predict(diff_data, ar_coeffs) + ma_predict(ma_coeffs)
        forecast_diff.append(pred)
        diff_data.append(pred)

    # 反差分
    forecast = inverse_diff(forecast_diff, data, d)
    return forecast
```

---

## 10. LSTM 预测

### 网络结构

```
输入层: [batch_size, seq_length, features]
  features = 监测指标数 (水位+流量+雨量 = 3)

LSTM层:
  hidden_size = 64
  num_layers = 2
  dropout = 0.2

全连接层:
  output_size = 预测步长
```

### 水利场景训练参数

```python
config = {
    'seq_length': 96,       # 输入序列长度 (24小时 * 4次/小时)
    'pred_length': 24,      # 预测长度 (6小时 * 4次/小时)
    'hidden_size': 64,
    'num_layers': 2,
    'dropout': 0.2,
    'learning_rate': 0.001,
    'batch_size': 32,
    'epochs': 100,
}
```

### 特征工程

```
原始特征:
  - 监测值 (水位/渗压/位移)
  - 时间特征: hour_sin, hour_cos, day_sin, day_cos
  - 滞后特征: lag_1h, lag_6h, lag_24h
  - 滚动统计: rolling_mean_6h, rolling_std_6h

衍生特征:
  - 变化率: (xt - xt-1) / xt-1
  - 季节分量: 通过FFT提取主频
  - 外部变量: 雨量(对水位), 温度(对渗压)
```

### 伪代码

```python
class WaterLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, pred_length):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                           dropout=0.2, batch_first=True)
        self.fc = nn.Linear(hidden_size, pred_length)

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        out = self.fc(lstm_out[:, -1, :])  # 取最后时间步
        return out
```

---

## 算法选择指南

| 场景 | 推荐算法 | 理由 |
|------|----------|------|
| 实时预测(秒级) | 指数平滑 | 计算快，无需训练 |
| 短期预测(小时级) | ARIMA | 捕捉趋势和周期 |
| 中期预测(天级) | LSTM | 长期依赖 |
| 缺乏历史数据 | 指数平滑 | 不需要训练数据 |
| 多变量预测 | LSTM | 可处理多输入特征 |
| 需要置信区间 | ARIMA | 自带置信区间 |

### 预测与预警联动

```
预测值 → 与阈值比较 → 提前预警

示例:
  当前水位: 149.5m
  预测6小时后: 151.2m
  预警阈值: 150m
  → 提前6小时发出"预计水位将超限"预警
```
