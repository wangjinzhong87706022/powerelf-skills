# Inspection 高频陷阱（7 类）

> 本文件列出 `powerelf-inspection` 开发/维护中最常见的 7 类错误，每类含❌错误示例与✅正确做法。

---

## 1. 占位符污染

**问题:** SQL 拼接时使用 `{st_id}` 占位符（Python f-string 或 `.format()`），易导致注入或语法错误。

❌ **错误:**
```python
sql = f"SELECT * FROM st_river_r WHERE st_id={st_id}"  # 直接拼接，易注入
sql = "SELECT * FROM st_river_r WHERE st_id={st_id}".format(st_id=st_id)  # 占位符混淆
```

✅ **正确:**
```python
sql = "SELECT * FROM st_river_r WHERE st_id=:st_id"
rows = pd.read_sql(text(sql), engine, params={"st_id": st_id})
```

**参见:** `_shared/references/sql-discipline.md`

---

## 2. 关联键混淆

**问题:** `eq_id`(bigint)/`stcd`(varchar)/`st_id`(int) 三个 ID 体系易混，导致 JOIN 失败或结果错误。

| 字段 | 类型 | 用途 | 表 |
|------|------|------|-----|
| `eq_id` | bigint | 设备ID | `eq_equip_base`, `eq_equip_defect` |
| `stcd` | varchar(32) | 测站编码 | `st_*` 系列表 |
| `st_id` | int | 测站内键 | `st_*` 系列表 |

❌ **错误:**
```python
# 用 st_id 匹配 stcd（类型不匹配）
sql = "SELECT * FROM st_river_r WHERE stcd=:st_id"  # stcd 是 varchar，st_id 是 int
```

✅ **正确:**
```python
# 按需选择正确的键
sql = "SELECT * FROM st_river_r WHERE st_id=:st_id"  # 用 st_id 匹配测站
# 或
sql = "SELECT * FROM st_river_r WHERE stcd=:stcd"  # 用 stcd 匹配测站编码
```

**参见:** `_shared/references/schema.md`

---

## 3. GNSS 表名

**问题:** GNSS 变形数据表名 `dsm_dfr_srvrds_srhrds` 超长且易拼写错误。

❌ **错误:**
```python
sql = "SELECT * FROM dsm_dfr_srv_rd_srhrds"  # 拼写错误
```

✅ **正确:**
```python
# 从 _shared/references/schema.md 核对表名
sql = "SELECT * FROM dsm_dfr_srvrds_srhrds"  # 正确：dsm_dfr_srvrds_srhrds
# 或在 sys_data_source_registry 中定义别名
```

**参见:** `_shared/references/schema.md`

---

## 4. extend JSON 格式

**问题:** `ew_info_rules.extend` 字段存储 JSON，格式坏（`content[0]=null` 或无效 JSON）导致 `json.loads()` 抛异常。

❌ **错误:**
```python
extend = json.loads(rule['extend'])
value = extend['content'][0]  # KeyError: 'content' 或 IndexError
```

✅ **正确:**
```python
try:
    extend = json.loads(rule['extend']) if isinstance(rule.get('extend'), str) else rule.get('extend')
    content = extend.get('content') or []
    value = content[0] if len(content) > 0 else None
except (json.JSONDecodeError, KeyError, TypeError):
    continue  # 跳过坏规则
```

**参见:** `lib/anomaly.py::layer1_threshold`

---

## 5. 泵站 varchar 字段

**问题:** 泵站表 `rei_pump_r` 的电压/电流/功率字段为 `varchar`，存储格式如 `"380V"` 或 `"10.5A"`，不能直接数值比较。

❌ **错误:**
```python
sql = "SELECT * FROM rei_pump_r WHERE uab > 400"  # uab 是 varchar，比较失效
```

✅ **正确:**
```python
# 先 CAST 或清洗
sql = "SELECT CAST(REPLACE(uab, 'V', '') AS DECIMAL(10,2)) AS uab_val FROM rei_pump_r"
# 或在 pandas 清洗
df['uab_val'] = pd.to_numeric(df['uab'].str.replace('V', ''), errors='coerce')
```

**参见:** `powerelf-monitor/rules/gate-pump-status.md`

---

## 6. 传感器故障 vs 真极端

**问题:** 传感器故障（离线/卡滞/漂移）产生的极端值会被误判为真异常，需结合 data-quality tier 区分。

❌ **错误:**
```python
# 只检测异常，不检查数据质量
if value > threshold:
    findings.append({"level": "WARNING", "message": f"...异常..."})
```

✅ **正确:**
```python
# 先检查 data-quality tier
quality_tier = get_data_quality_tier(sensor_id)
if quality_tier == "sensor_fault":
    findings.append({"level": "INFO", "message": f"...传感器故障，忽略..."})
elif value > threshold:
    findings.append({"level": "WARNING", "message": f"...真异常..."})
```

**参见:** `powerelf-data-governance`（data-quality tier 接口）

---

## 7. 双数据库 session 混乱

**问题:** inspection 与 governance 两套库同时使用时，SQLAlchemy session 混用导致事务错乱或连接泄漏。

❌ **错误:**
```python
from powerelf_data_governance.lib.db import get_connection as gov_get_conn
from powerelf_inspection.lib.db import get_connection as insp_get_conn

engine_gov = gov_get_conn()
engine_insp = insp_get_conn()
# 混用 session
with Session(engine_gov) as s1:
    with Session(engine_insp) as s2:
        s1.add(obj_from_insp)  # session 错配
```

✅ **正确:**
```python
# 各用各的 session，不混用
with Session(engine_gov) as s_gov:
    gov_obj = s_gov.query(...).one()

with Session(engine_insp) as s_insp:
    insp_obj = s_insp.query(...).one()
```

**参见:** `_shared/lib/db.py`（单一连接源）
