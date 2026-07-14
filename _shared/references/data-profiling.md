# 数据画像方法论（Data Profiling Methodology）

> **跨 skill 单一事实源**。`powerelf-data-governance/lib/profiling.py`、`powerelf-data-governance/impl/profiler.py`
> 以及 `rules/quality-scoring.md` 的完整性 tier 定义均以本文档为准。
> 姊妹文档：[`../algorithms/outlier-methods.md`](../algorithms/outlier-methods.md)（离群检测方法选择）。

---

## 一、何时画像（When to Profile）

数据画像是对表的结构与内容做机械计算的只读操作，产出结构化 profile dict。
以下场景**必须**先做画像，再做质量评估或分析：

| 触发条件 | 说明 | 优先级 |
|----------|------|--------|
| **首次接触某张表** | 建立列分类、统计基线、完整性 baseline，供后续所有分析复用 | P0 |
| **新增测量点 / 设备接入** | 新设备的数据格式、空值率、范围可能与历史设备不同，需独立画像 | P0 |
| **质量评分前** | `completeness_tier`、`accuracy_flags` 是质量评分的直接输入；跳过画像会导致评分基于猜测 | P0 |
| **Schema 变更后** | 新增/删除/重命名字段后，旧 profile 失效，需重跑 | P1 |
| **定期健康巡检** | 每月/每季度对核心监测表做全表画像，追踪分布变化与退化趋势 | P2 |
| **离群检测前** | 了解分布类型（正态/偏态/零膨胀）是选 MAD/IQR/百分位法的前提 | P1 |

**画像原则**：
- 只读：画像不修改数据，不触发告警，不写入治理表。
- 采样先行：全表画像时默认采样 `LIMIT 10000`，仅当采样不足时（行数 < 采样量）才做全表。
- 结果可复用：一张表在同一分析窗口内只需画像一次，profile dict 可被缺失检测、异常检测、质量评分共享。

---

## 二、列分类体系（6 分类 + 水利语义映射）

### 2.1 六分类定义

| 分类 | 含义 | 画像深度 |
|------|------|----------|
| **identifier** | 设备/测站唯一标识，不参与数值计算 | 轻量：null_rate + distinct |
| **temporal** | 时间序列轴，决定数据时序结构与 gap 分析 | 深度：时间范围、gap 统计、未来时间戳检测 |
| **metric** | 物理测量值，核心分析对象 | 深度：统计量、分布检测、零值率、负值率 |
| **dimension** | 空间/分组维度，用于切片与分组（如断面、分区、测点） | 轻量：null_rate + distinct + 枚举值分布 |
| **text** | 自由文本或无法归类的字段 | 轻量：null_rate + 长度统计 |
| **boolean** | 开关状态、标志位 | 轻量：true/false/null 分布 |

> **structural 说明**：主键（`st_id + tm` 复合键）、外键、审计字段（`create_time`/`update_time`/`creator`/`updater`）
> 属于结构性列，按上述分类归位：审计时间字段归 `temporal`，ID 字段归 `identifier` 或 `dimension`，
> 不单独列为第 7 类。

### 2.2 水利语义关键词映射

`classify_column(name, sample_values, dtype)` 按以下优先级匹配：

**identifier 关键词**：`eq_id`、`stcd`、`station_id`、`device_id`、`point_id`、`section_id`、`st_id`、`re_id`、`fca_id`

**temporal 关键词**：`_time`（`data_time`、`create_time`、`update_time`）、`timestamp`、`tm`、`gather_time`

**metric 关键词**：`water_pressure`、`rz`、`rainfall`、`water_level`、`z`、`flow`、`inq`、`otq`、`temperature`、`humidity`、`pressure`、`percolation`、`wgs84_delta_h`、`wgs84_delta_x`、`wgs84_delta_y`、`displacement`、`strain`、`tilt_x`、`tilt_y`、`wind_speed`、`p`（雨量）

**dimension 关键词**：`st_id`（同时是标识符与维度，按出现位置判断）、`re_id`、`fca_id`、`section_id`、`point_id`

**boolean 关键词**：`switch`、`status`、`is_`、`has_`、`flag`、`active`

**dtype 兜底规则**（关键词未匹配时）：
- `datetime` / `timestamp` / `time` → `temporal`
- `int` / `float` / `double` / `decimal` / `numeric` → `metric`
- 其他 → `text`

### 2.3 典型表映射示例

```yaml
# st_rsvr_r（水库水情）
st_id:     identifier  # 同时是 dimension（按站分组）
tm:        temporal
rz:        metric      # 库水位(m)
inq:       metric      # 入库流量
otq:       metric      # 出库流量
w:         metric      # 蓄水量
blrz:      metric      # 下游水位
stcd:      identifier  # 站码

# st_pptn_r（测站雨量）
st_id:     identifier
tm:        temporal
p:         metric      # 时段雨量(mm)
dr:        metric      # 时段长(分钟)
dyp:       metric      # 日雨量(mm)
cump:      metric      # 累计雨量(mm)
stcd:      identifier

# st_pressure_r（渗压）
st_id:     identifier
tm:        temporal
ext_pressure:    metric  # 渗压(kPa)
water_pressure:  metric  # 水位压力(kPa)
ext_temperature: metric  # 温度(℃)
section_id:      dimension  # 断面ID
point_id:        dimension  # 测点ID

# dsm_dfr_srvrds_srhrds（GNSS 位移）
st_id:     identifier
tm:        temporal
wgs84_delta_h:  metric
wgs84_delta_x:  metric
wgs84_delta_y:  metric
wgs84_total_h:  metric
point_id:       dimension

# rei_gate_r（闸门工情）
st_id:     identifier
tm:        temporal
gtq:       metric      # 流量
gtophgt:   metric      # 开启高度
gtopnum:   metric      # 开启孔数
status:    boolean     # 闸门状态(1=开启/2=关闭/3=异常)
stcd:      identifier
slcd:      identifier  # 闸码
```

---

## 三、分类型画像清单（Type-Specific Profiling Checklist）

### 3.1 metric（数值列）— 深度画像

| 指标 | 说明 | 水利示例 |
|------|------|----------|
| `count` | 总行数 | — |
| `null_rate` | 空值率 = null_count / count | 应 < 5%（正常采集） |
| `min` / `max` | 最小值 / 最大值 | 水位: 50~250m；雨量: 0~200mm |
| `mean` / `median` | 均值 / 中位数 | 均值 vs 中位数差异反映偏态 |
| `std` | 标准差 | 缓变指标（GNSS）std 极小；雨量 std 较大 |
| `p1` / `p5` / `p25` / `p50` / `p75` / `p95` / `p99` | 百分位 | 用于 IQR/百分位离群检测 |
| `zero_rate` | 零值占比 | 雨量零值率 > 80% 属正常（无雨时段） |
| `negative_rate` | 负值占比 | 多数水利指标不应为负（渗压例外：可能为真空） |
| `distinct` | 去重计数 | 步进式传感器（雨量 0.5mm 一跳）distinct 较少 |
| `distribution_hint` | 分布提示 | 正态/右偏/左偏/双峰/幂律/均匀 |

**分布与选法关联**：
- 正态/缓变 → MAD（水位、GNSS、渗压）
- 右偏/零膨胀 → IQR（雨量、流量）
- 双峰 → 需分群分析，勿用全局离群检测
- 幂律 → 百分位法或对数变换后检测

### 3.2 temporal（时间列）— 深度画像

| 指标 | 说明 | 阈值/注释 |
|------|------|-----------|
| `min` / `max` | 最早 / 最晚时间 | — |
| `span` | 时间跨度 | max - min |
| `median_gap` | 中位间隔 | 应与采集频率匹配（默认 10 分钟） |
| `max_gap` | 最大间隔 | > 2× 采集频率可能为通信中断 |
| `future_count` | 未来时间戳数量 | > 0 说明时钟同步异常 |
| `null_rate` | 空值率 | 应接近 0 |

### 3.3 identifier / dimension（标识/维度列）— 轻量画像

| 指标 | 说明 |
|------|------|
| `null_rate` | 空值率 |
| `distinct` | 去重计数 | 
| `sample_values` | 样本值格式校验 | 如 stcd 应为字符串而非纯数字 |

### 3.4 text（文本列）— 轻量画像

| 指标 | 说明 |
|------|------|
| `null_rate` | 空值率 |
| `avg_length` | 平均字符串长度 |
| `distinct` | 去重计数 |

### 3.5 boolean（布尔列）— 轻量画像

| 指标 | 说明 |
|------|------|
| `true_rate` | true 占比 |
| `false_rate` | false 占比 |
| `null_rate` | 空值率 |
| `unexpected_values` | 非 true/false 的异常取值 | 如 status 字段出现 99 |

---

## 四、质量评估框架（Quality Assessment Framework）

### 4.1 完整性（Completeness）— 4 级 Tier

**单一事实源**：`completeness_tier(valid_rate)` 定义于 `lib/profiling.py`，
`quality-scoring.md` 维度四（数据完整性 15%）复用此 tier 语义。

| Tier | 有效值率 | 颜色 | 含义 | 质量评分处理 |
|------|----------|------|------|-------------|
| **绿** | > 99% | 🟢 | 数据完整 | 满分 |
| **黄** | 95% ~ 99% | 🟡 | 轻微缺失 | 正常处理 |
| **橙** | 80% ~ 95% | 🟠 | 中度缺失 | 触发缺失检测，考虑插值 |
| **红** | < 80% | 🔴 | 严重缺失 | 需人工确认，评分降级 |

**表级 tier 计算**：取所有列有效值率（`1.0 - null_rate`）的算术平均，不做加权。
若某列全为 null，则该列有效值率 = 0，显著拉低表级 tier。

### 4.2 一致性（Consistency）

一致性关注**同一指标在不同时间/测点间的值是否自洽**，画像阶段检测以下模式：

| 检查项 | 方法 | 红旗 |
|--------|------|------|
| 类型一致性 | dtype 与样本值实际类型是否匹配 | `type_mismatch` |
| 枚举值一致性 | boolean/enum 列是否出现未定义值 | `invalid_enum_value` |
| 数值范围一致性 | min/max 是否超出物理合理范围 | `out_of_range` |
| 采集频率一致性 | temporal 列 median_gap 是否偏离预期频率 | `frequency_drift` |
| 步进值一致性 | 步进式传感器（雨量 0.5mm）是否出现非法步长 | `invalid_step` |

> 一致性深度检测通常在离群检测/卡滞检测阶段完成，画像阶段只做基础范围告警。

### 4.3 准确性红旗（Accuracy Flags）

`detect_accuracy_flags(col_profile)` 在画像阶段自动检测以下红旗：

| 红旗标签 | 触发条件 | 严重级别 | 处理建议 |
|----------|----------|----------|----------|
| `placeholder_999999` | max == 999999 且 mean > 999000 | 🔴 高 | 传感器通信故障，数据全为占位符 |
| `placeholder_neg_one` | min == -1 | 🔴 高 | -1 为非法占位符，需排查采集端 |
| `bimodal_distribution` | 分布提示为"双峰" | 🟠 中 | 可能混入不同工况数据，建议分群分析 |
| `stale_temporal` | 时间列 max 距今 > 365 天 | 🟠 中 | 数据过旧，可能设备已停用或迁移 |
| `impossible_value` | min/max 超出水利合理范围 | 🔴 高 | 如水位 > 1000m（除非特殊高坝） |
| `future_timestamp` | 时间列含未来时间戳 | 🟠 中 | 时钟不同步，需校准 |

### 4.4 及时性（Timeliness）

及时性衡量数据的**新鲜度**与**时效性**：

| 指标 | 计算方法 | 阈值 |
|------|----------|------|
| 最新数据距今天数 | `now() - max(temporal.max)` | > 7 天为橙色，> 30 天为红色 |
| 数据覆盖时长 | `temporal.span` | 用于判断数据连续性 |
| 最大 gap | `temporal.max_gap` | > 2× 采集频率为橙色，> 10× 为红色 |

---

## 五、分布类型与 SCADA 特例（Distribution Types + SCADA Exceptions）

### 5.1 六种分布类型

`_detect_distribution()` 在 `lib/profiling.py` 中实现，输出以下分布提示：

| 分布类型 | 检测逻辑 | 典型指标 | 推荐离群检测法 |
|----------|----------|----------|---------------|
| **正态** | Pearson 偏态系数 \|3×(mean-median)/std\| < 0.5 | 水位、GNSS 位移、渗压 | MAD |
| **右偏** | 偏态系数 > 0.5（长尾向右） | 流量、蓄水量 | IQR |
| **左偏** | 偏态系数 < -0.5（长尾向左） | 少数指标，通常为异常信号 | IQR |
| **双峰** | 直方图局部最大值 ≥ 2 | 多工况混合数据 | 分群后分别检测 |
| **幂律** | max / mean > 10 | 降雨量（零膨胀）、极端事件 | IQR 或百分位 |
| **均匀** | distinct ≤ 1 | 常量列、故障列 | 无需离群检测 |

### 5.2 SCADA 特例（必须阅读 [`outlier-methods.md`](../algorithms/outlier-methods.md)）

#### 特例 1：雨量步进式读数 ≠ 卡滞

雨量传感器为**步进式读数**（通常 0.5mm 一跳），在无降雨时段连续输出 0.0 是**正常工况**，
不是传感器卡滞。

- **错误做法**：用卡滞检测（`stagnation.py`）标记雨量连续 0 值 → 大量误报。
- **正确做法**：雨量站的卡滞检测需调参：`tolerance=0.5`（步进值）、`min_consecutive=24`（至少连续 24 条相同值才视为卡滞）。
- **离群检测同理**：雨量零值率高（>80%）是正常现象，IQR 检测时大量 0 值会把非零降雨推到上尾——
  需结合字段语义判断是否合理，不要盲目标记所有上尾为异常。

#### 特例 2：零膨胀分布 → 优先 IQR，非 MAD

雨量、流量等指标存在大量零值（零膨胀分布，Zero-Inflated）：

- **MAD 失效原因**：MAD 基于中位数与绝对偏差，零膨胀数据的中位数 = 0，MAD 也接近 0，
  导致几乎所有非零值都被判为异常。
- **IQR 更稳健**：IQR 基于 p25/p75 分位数，不受极端零值集中影响。
- **选法口诀**（出自 `outlier-methods.md`）：**正态缓变用 MAD，偏态长尾用 IQR，海量筛查用百分位。**

#### 特例 3：泵站电气参数为 varchar

`rei_pump_r` 的电气参数（`uab`/`ubc`/`uca`/`ia`/`ib`/`ic`/`p`/`freq`/`speed`）
在数据库中为 **varchar** 类型，数值比较前需 CAST 或应用层转换。
画像时 `classify_column` 可能将其归为 `text`，需人工确认后手动修正为 `metric`。

---

## 六、可执行伴侣：`powerelf-data-governance/impl/profiler.py`

### 6.1 概述

`impl/profiler.py` 是数据画像的 CLI 入口，直接调用 `lib/profiling.py` 的纯函数。
只读操作，输出 JSON（默认）或可读 text 到 stdout。

### 6.2 前置条件

```bash
# 加载数据库凭证（从 ~/.hermes/.env 读取 POWERELF_DB_*）
source ../_shared/bootstrap.sh   # 导出 DB_URL
```

### 6.3 用法

```bash
# 画像全表（默认采样 10000 行）
python3 impl/profiler.py --db "$DB_URL" --table st_pressure_r

# 指定字段 + 自定义采样量
python3 impl/profiler.py --db "$DB_URL" --table st_pressure_r \
  --field water_pressure --sample 5000

# text 格式输出（可读性更好）
python3 impl/profiler.py --db "$DB_URL" --table st_pptn_r --format text
```

### 6.4 输出结构（JSON）

```json
{
  "row_count": 10000,
  "sample_size": 10000,
  "table": "st_pressure_r",
  "field": null,
  "status": "OK",
  "completeness_tier": "绿",
  "flags": [],
  "columns": [
    {
      "name": "water_pressure",
      "type": "metric",
      "null_rate": 0.001,
      "numeric_stats": {
        "count": 9990,
        "null_rate": 0.001,
        "min": 101.3,
        "max": 245.6,
        "mean": 156.2,
        "median": 154.8,
        "std": 23.1,
        "p1": 105.2, "p5": 112.0, "p25": 141.0, "p50": 154.8,
        "p75": 171.5, "p95": 198.3, "p99": 220.1,
        "zero_rate": 0.0,
        "negative_rate": 0.0,
        "distinct": 4500,
        "distribution_hint": "正态"
      },
      "accuracy_flags": []
    },
    {
      "name": "tm",
      "type": "temporal",
      "null_rate": 0.0,
      "temporal_stats": {
        "min": "2026-01-01 00:00:00",
        "max": "2026-07-13 08:00:00",
        "span": "193 days 08:00:00",
        "median_gap": "0 days 00:10:00",
        "max_gap": "0 days 02:30:00",
        "future_count": 0,
        "null_rate": 0.0
      },
      "accuracy_flags": []
    }
  ]
}
```

### 6.5 输出结构（text）

```
表画像: 10000 行 (sample=10000)
完整性等级: 绿
红旗: 无

列: water_pressure  分类: metric  空值率: 0.1%
  min=101.3  max=245.6  mean=156.2  median=154.8
  std=23.1  分布: 正态
  p1=105.2  p5=112.0  p25=141.0  p50=154.8  p75=171.5  p95=198.3  p99=220.1
  zero_rate=0.0  negative_rate=0.0  distinct=4500

列: tm  分类: temporal  空值率: 0.0%
  min=2026-01-01 00:00:00  max=2026-07-13 08:00:00  span=193 days 08:00:00
  median_gap=0 days 00:10:00  max_gap=0 days 02:30:00  future_count=0
```

### 6.6 编程调用

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from lib.profiling import profile_table

rows = [
    {"st_id": 1, "tm": "2026-07-13 00:00:00", "water_pressure": 150.0, "rz": 105.2},
    # ... 采样行
]
result = profile_table(rows)
print(result["completeness_tier"])   # 绿/黄/橙/红
print(result["flags"])               # 准确性红旗列表
```

### 6.7 允许表与字段白名单

`profiler.py` 内置白名单，防止误操作生产库：

- **允许表**：`st_rsvr_r`、`st_river_r`、`st_pptn_r`、`st_pressure_r`、`st_percolation_r`、
  `st_deformation_r`、`st_gnss_r`、`st_seepage_r`、`st_rain_r`、`st_wind_r`、`st_temp_r`、
  `st_strlevel_r`、`st_strain_r`、`st_tilt_r`、`st_environment_r`
- **允许字段**：`rz`、`z`、`p`、`water_pressure`、`ext_pressure`、`percolation`、
  `wgs84_delta_h`、`inq`、`otq`、`temperature`、`humidity`、`wind_speed`、`wind_direction`、
  `strain`、`tilt_x`、`tilt_y`、`displacement`

> 白名单不在本文档维护，随 `impl/profiler.py` 代码演进。方法论层面的列分类不受白名单限制。

---

## 七、与上下游工具的衔接

### 7.1 上游输入

画像通常由以下动作触发：
- `powerelf-data-governance` 的 `anomaly_detector.py`、`missing_detector.py`、`quality_scorer.py`
- `powerelf-early-warning` 在建立预警基线前
- `powerelf-inspection` 在巡检前了解表结构

### 7.2 下游消费

| 消费者 | 消费内容 | 用途 |
|--------|----------|------|
| `quality-scoring.md` | `completeness_tier`、`null_rate` 分布 | 维度四（数据完整性）评分 |
| `anomaly_detector.py` | `distribution_hint` | 自动选 MAD/IQR/百分位 |
| `missing_detector.py` | `temporal.median_gap` | 判断期望采集周期 |
| `stagnation.py` | `metric.zero_rate`、`distinct` | 雨量站调参（tolerance/min_consecutive） |
| `rules/quality-scoring.md` | `accuracy_flags` | 标记需人工确认的数据问题 |

### 7.3 离群检测方法选择决策树

```
profile_table 返回 distribution_hint
        |
        +-- 正态 / 缓变 → MAD (--method mad, --threshold 按指标)
        |
        +-- 右偏 / 左偏 / 幂律 → IQR (--method iqr, --threshold 1.5)
        |
        +-- 双峰 → 先分群（按 dimension 字段），再分别画像后选法
        |
        +-- 均匀 / 常量 → 跳过离群检测
        |
        +-- 雨量/流量 + 零膨胀 → 强制 IQR（MAD 会失效）
```

详见 [`../algorithms/outlier-methods.md`](../algorithms/outlier-methods.md)。

---

## 附录 A：profile dict 完整字段参考

### A.1 表级字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `row_count` | int | 实际采样/总行数 |
| `sample_size` | int | 采样大小（等于 row_count 除非被 LIMIT 截断） |
| `table` | str | 表名（CLI 模式附加） |
| `field` | str \| null | 指定字段名（CLI 模式附加） |
| `status` | str | `OK` / `NO_DATA` / `EMPTY_TABLE` |
| `completeness_tier` | str | 绿/黄/橙/红 |
| `flags` | list[str] | 表级红旗（如 `empty_table`） |
| `columns` | list[col_profile] | 列画像列表 |

### A.2 列级字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 列名 |
| `type` | str | 分类：identifier/temporal/metric/dimension/text/boolean |
| `null_rate` | float | 空值率（0.0 ~ 1.0） |
| `numeric_stats` | dict \| null | metric 列的深度统计 |
| `temporal_stats` | dict \| null | temporal 列的时间统计 |
| `accuracy_flags` | list[str] | 准确性红旗标签 |

### A.3 numeric_stats 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `count` | int | 有效值数量 |
| `null_rate` | float | 空值率 |
| `min` / `max` | float \| null | 最小/最大值 |
| `mean` / `median` | float \| null | 均值/中位数 |
| `std` | float \| null | 标准差 |
| `p1`~`p99` | float \| null | 百分位 |
| `zero_rate` | float | 零值占比 |
| `negative_rate` | float | 负值占比 |
| `distinct` | int | 去重计数 |
| `distribution_hint` | str | 分布提示 |

### A.4 temporal_stats 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `min` / `max` | pd.Timestamp \| null | 最早/最晚时间 |
| `span` | pd.Timedelta \| null | 时间跨度 |
| `median_gap` | pd.Timedelta \| null | 中位间隔 |
| `max_gap` | pd.Timedelta \| null | 最大间隔 |
| `future_count` | int | 未来时间戳数 |
| `null_rate` | float | 空值率 |

---

## 附录 B：术语表

| 术语 | 定义 |
|------|------|
| **画像（Profiling）** | 对表的结构与内容做机械计算，产出结构化统计描述 |
| **列分类（Classification）** | 根据列名、样本值、dtype 将列归入预定义类别 |
| ** completeness tier** | 基于有效值率的四级完整性评级（绿/黄/橙/红） |
| **准确性红旗（Accuracy Flag）** | 数据值本身可疑但非缺失的异常模式标签 |
| **分布提示（Distribution Hint）** | 基于统计量推断的数值分布类型 |
| **SCADA 特例** | 水利监控系统中因传感器特性导致的非典型数据模式 |
| **零膨胀（Zero-Inflated）** | 大量零值与少量非零值共存的分布（如雨量） |
| **步进式读数** | 传感器按固定步长输出（如雨量 0.5mm/跳），非连续值 |
