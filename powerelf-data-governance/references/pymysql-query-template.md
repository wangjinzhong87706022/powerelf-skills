# pymysql 查询模板

```python
import pymysql
conn = pymysql.connect(
    host='${POWERELF_DB_HOST}', port=int('${POWERELF_DB_PORT}'),
    db='${POWERELF_DB_NAME}', user='${POWERELF_DB_USER}',
    password='${POWERELF_DB_PASSWORD}',
    charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute('SELECT ... FROM st_rsvr_r WHERE ...')
for r in cur.fetchall(): ...
conn.close()
```

> 详见 `../../_shared/references/schema.md`（跨 skill 单一事实源）获取真实表名、列名与设备关联键映射。