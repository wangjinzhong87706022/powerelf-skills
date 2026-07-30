# 快速参考

> 本文件包含 powerelf-data-governance 常用的速查信息。

---

## 数据库连接

### Python（推荐）

```python
import sys, os
sys.path.insert(0, os.path.join(
    os.environ.get("POWERELF_SKILLS_ROOT", "/home/scada/powerelf-skills"), "_shared", "lib"))
from db import query, columns

# 查询
rows = query("SELECT * FROM st_rsvr_r WHERE deleted=0 LIMIT 5")

# 查看列名
for c in columns("st_rsvr_r"):
    print(f"{c['column']}: {c['type']} - {c['meaning']}")
```

### CLI（DB_URL）

```bash
source ../_shared/bootstrap.sh  # 导出 DB_URL
python3 script.py --db "$DB_URL"
```

---

## 核心数据表速查

### 设备表

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| eq_equip_base | 设备主数据 | id, name, code, type_flag, status(0=离线/1=在线/2=异常) |
| eq_business_equip_relation | 设备-业务映射 | business_table, eq_id, st_id, offline_threshold |
| eq_equip_offline_record | 离线记录 | equipment_code, total_offline_duration(秒), offline_start_date/time |

### 监测表（原始数据）

| 表名 | 说明 | 主键 | 时间列 | 关联键 |
|------|------|------|--------|--------|
| st_rsvr_r | 水库水情 | id | tm | eq_id |
| st_pptn_r | 雨量 | id | tm | eq_id |
| st_pressure_r | 渗压 | id | tm | eq_id |
| st_percolation_r | 渗流 | id | tm | eq_id |
| dsm_dfr_srvrds_srhrds | GNSS 位移 | id | tm | eq_id (int) |

### 治理表

| 表名 | 说明 |
|------|------|
| eq_data_missing_record | 数据缺失记录 |
| eq_data_anomaly_record | 数据异常记录 |
| stats_data_collection_daily | 每日采集统计 |
| stats_data_missing_daily | 每日缺失统计 |
| stats_data_anomaly_daily | 每日异常统计 |

---

## 常用 SQL 模式

### 查询设备最新记录时间

```sql
SELECT MAX(tm) as latest FROM st_rsvr_r WHERE st_id = :st_id AND deleted = 0
```

### 查询离线设备

```sql
SELECT * FROM eq_equip_base WHERE status = 0 AND deleted = 0
```

### 关联查询（标准模式）

```sql
SELECT e.name, r.rz, r.tm
FROM st_rsvr_r r
JOIN eq_equip_base e ON r.eq_id = e.id
WHERE r.deleted = 0
  AND r.tm BETWEEN '2026-07-01' AND '2026-07-28'
```

---

## 离线阈值（dg_equip_offline）

| st_type | 站类型 | 阈值(min) |
|---------|--------|----------|
| SP | 水位站 | 360 |
| GN | GNSS站 | 60 |
| ZS | 雨量站 | 60 |
| PP | 渗压站 | 60 |
| DP | 渗流站 | 60 |
| DD | 位移站 | 60 |

---

## 分级阈值（lib/offline.py）

### 离线时长分级

| 时长 | 级别 |
|------|------|
| 0-1 小时 | INFO |
| 1-4 小时 | WARNING |
| 4-24 小时 | ERROR |
| > 24 小时 | CRITICAL |

---

## 常见错误（速查）

| 错误 | 正确做法 |
|------|---------|
| 用 `stcd` JOIN | 用 `eq_id` 或 `code` |
| 漏写 `deleted = 0` | 每条 SQL 必须带 `deleted = 0` |
| 用 `data_time` | 用 `tm`（监测表） |
| 手写 pymysql | 用 `query()` |

---

**完整文档**: 见 SKILL.md 和相关 references/
