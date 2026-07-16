# Inspection Few-Shots（SQL 最佳实践）

> 本文件收录 `powerelf-inspection` 开发中最常用的 SQL 模式与代码示例，含正确做法与反模式对照。

---

## 1. 参数化查询（禁占位符注入）

### SELECT 带参数

✅ **正确 — SQLAlchemy `text()` + `params`**
```python
from sqlalchemy import text
import pandas as pd

sql = """
    SELECT id, name, ew_type, level_r, st_id, extend
    FROM ew_info_rules
    WHERE deleted = 0 AND status = :status AND st_id = :st_id
"""
df = pd.read_sql(text(sql), engine, params={"status": "1", "st_id": 10035})
```

❌ **错误 — Python f-string 拼接**
```python
# 注入风险：st_id = "1; DROP TABLE ew_info_rules;--"
sql = f"SELECT ... WHERE st_id = {st_id}"
```

❌ **错误 — `.format()` 占位符**
```python
sql = "SELECT ... WHERE st_id = {st_id}".format(st_id=st_id)
```

### INSERT / UPDATE

✅ **正确**
```python
sql = text("""
    INSERT INTO business_check_task (name, status, st_id)
    VALUES (:name, :status, :st_id)
""")
engine.execute(sql, name="巡检任务", status="1", st_id=10035)
```

❌ **错误**
```python
engine.execute(f"INSERT INTO business_check_task VALUES ('{name}', '{status}', {st_id})")
```

---

## 2. JOIN-by-Name（用 pandas merge，少写 SQL JOIN）

### 场景：任务表 + 路线表关联

✅ **正确 — SQL 只做基础过滤，JOIN 在 Python 层**
```python
tasks = pd.read_sql("""
    SELECT t.id, t.name, t.route_id, t.check_percent, t.bad_num
    FROM business_check_task t
    WHERE t.deleted = 0 AND t.status = '3'
""", engine)

routes = pd.read_sql("""
    SELECT id, name AS route_name, max_time
    FROM business_check_route
    WHERE deleted = 0
""", engine)

# JOIN by name（pandas merge）
merged = tasks.merge(routes, left_on="route_id", right_on="id", how="left")
```

❌ **错误 — 多表 SQL JOIN 难以测试/调试**
```python
# 复杂 JOIN 难维护，列名冲突要手动别名
df = pd.read_sql("""
    SELECT t.*, r.name AS route_name
    FROM business_check_task t
    LEFT JOIN business_check_route r ON t.route_id = r.id
    WHERE t.deleted = 0
""", engine)
```

### 场景：巡检结果 + 缺陷记录关联

✅ **正确 — 分批读取后 merge**
```python
results = pd.read_sql("""
    SELECT id, task_id, check_obj_id, result_status
    FROM business_check_result WHERE deleted = 0
""", engine)

defects = pd.read_sql("""
    SELECT id, task_id, check_obj_id, problem, status
    FROM business_check_error WHERE deleted = 0
""", engine)

# 按 task_id + check_obj_id 关联
joined = results.merge(
    defects,
    on=["task_id", "check_obj_id"],
    how="left",
    suffixes=("_result", "_defect")
)
```

---

## 3. 标识符白名单（防注入 II）

当表名/字段名来自用户输入或外部配置时，**不能参数化表名和列名**，需要用白名单校验。

✅ **正确**
```python
_ALLOWED_TABLES = {
    "st_river_r", "st_rsvr_r", "st_pressure_r", "st_percolation_r",
    "rei_gate_r", "rei_pump_r", "eq_equip_base", "business_check_task",
}
_ALLOWED_FIELDS_RE = re.compile(r"^[A-Za-z0-9_]+(,[A-Za-z0-9_]+)*$")

def _validate_identifiers(table, fields, time_field):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table}")
    if not _ALLOWED_FIELDS_RE.match(fields or ""):
        raise ValueError(f"非法字段列表: {fields}")

# 使用（表名和字段已校验，字段列表用字符串拼接安全）
sql = f"SELECT {fields} FROM {table} WHERE tm >= NOW() - INTERVAL :hours HOUR"
df = pd.read_sql(text(sql), engine, params={"hours": 24})
```

❌ **错误 — 无校验直接拼接**
```python
# table = "users; DELETE FROM ew_info_rules;--"
sql = f"SELECT {fields} FROM {table} WHERE ..."
```

---

## 4. 时间窗口查询

### 固定天数

✅ **正确**
```python
sql = """
    SELECT id, ew_name, level_r, value, gather_time
    FROM ew_info_message
    WHERE deleted = 0 AND create_time >= NOW() - INTERVAL :days DAY
    ORDER BY create_time DESC
    LIMIT :limit
"""
df = pd.read_sql(text(sql), engine, params={"days": 30, "limit": 500})
```

### 起止日期范围

✅ **正确**
```python
sql = """
    SELECT id, name, plan_time, begin_time, end_time
    FROM business_check_task
    WHERE deleted = 0 AND create_time BETWEEN :start AND :end
"""
df = pd.read_sql(text(sql), engine, params={
    "start": "2026-01-01 00:00:00",
    "end": "2026-12-31 23:59:59",
})
```

---

## 5. CAST / 类型转换

### 泵站 varchar 字段数值化

```python
# uab, ubc, uca 是 varchar(16)，存储如 "380V"
sql = """
    SELECT st_id,
           CAST(REPLACE(uab, 'V', '') AS DECIMAL(10,2)) AS uab_val,
           CAST(REPLACE(ubc, 'V', '') AS DECIMAL(10,2)) AS ubc_val,
           CAST(REPLACE(uca, 'V', '') AS DECIMAL(10,2)) AS uca_val,
           tm
    FROM rei_pump_r
    WHERE deleted = 0 AND tm >= NOW() - INTERVAL :hours HOUR
"""
df = pd.read_sql(text(sql), engine, params={"hours": 24})
```

### 或 Python 层清洗

```python
df['uab_val'] = pd.to_numeric(df['uab'].str.replace('V', ''), errors='coerce')
```

---

## 6. 聚合统计

### 按测站分组统计

```python
sql = """
    SELECT st_id,
           COUNT(*) AS data_count,
           MAX(rz) AS max_rz,
           MIN(rz) AS min_rz,
           AVG(rz) AS avg_rz
    FROM st_rsvr_r
    WHERE deleted = 0 AND tm >= NOW() - INTERVAL 30 DAY
    GROUP BY st_id
    HAVING COUNT(*) >= :min_samples
"""
stats = pd.read_sql(text(sql), engine, params={"min_samples": 10})
```

---

## 7. 分页查询（大表）

```python
page = 0
batch_size = 5000
all_data = []

while True:
    sql = """
        SELECT id, st_id, value, tm
        FROM st_pressure_r
        WHERE deleted = 0 AND tm >= :since
        ORDER BY id
        LIMIT :limit OFFSET :offset
    """
    batch = pd.read_sql(text(sql), engine, params={
        "since": "2026-06-01",
        "limit": batch_size,
        "offset": page * batch_size,
    })
    if batch.empty:
        break
    all_data.append(batch)
    page += 1

df = pd.concat(all_data, ignore_index=True)
```

---

## 8. 事务控制

```python
from sqlalchemy import create_engine, text

engine = create_engine(db_url)

with engine.begin() as conn:  # begin() 自动提交/回滚
    conn.execute(text("""
        UPDATE business_check_task SET status = :new_status
        WHERE id = :task_id AND deleted = 0
    """), {"new_status": "3", "task_id": task_id})

    conn.execute(text("""
        INSERT INTO business_check_error (task_id, problem, status)
        VALUES (:task_id, :problem, :status)
    """), {"task_id": task_id, "problem": "渗压异常", "status": "0"})
# 两语句在同一事务：任一失败则全部回滚
```

---

## 参考

- `pitfalls.md` — 7 类高频错误清单
- `_shared/references/sql-discipline.md` — SQL 编写规范
- `impl/registry.py` — 标识符白名单 + 参数化采集实现
- `lib/db.py` — 数据库连接管理