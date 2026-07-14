# SQL 写作纪律（跨域通用，单一事实源）

> 通用 SQL 写作方法论，所有手写或 agent 生成 SQL 的 skill 共用。
> 来源：复用 `knowledge-work-plugins/data` 的 `write-query`/`sql-queries`（方言中立条目），
> 丢弃 PostgreSQL/Snowflake/BigQuery/Redshift/Databricks 方言段，保留 MySQL 适用部分。
> 水利特化（表映射/单位陷阱/软删除）在各 skill 的 `sql-generation.md`，不在本文件。
> 姊妹文档：[`schema.md`](schema.md)（关联键铁律）、[`data-profiling.md`](data-profiling.md)（画像）、
> [`analysis-qa-checklist.md`](analysis-qa-checklist.md)（交付前 QA）、[`statistical-caution.md`](statistical-caution.md)（措辞）。

## 1. 何时用

agent 生成 SQL **之前**（NL2SQL 前置 checklist）+ 人工写 SQL **之时**。

## 2. 6 维需求解析（NL2SQL 前置）

生成 SQL 前先把自然语言拆成 6 维：
- **输出列**：要哪些字段（避免 `SELECT *`）
- **过滤**：时间范围 / 状态 / 分段
- **聚合**：GROUP BY / 计数 / 求和 / 平均
- **JOIN**：是否多表，关联键是否正确（查 `schema.md`）
- **排序**：如何排序
- **LIMIT**：top-N 或采样

## 3. 7 条性能纪律

1. **禁止 `SELECT *`**：只指定需要的列。
2. **早过滤**：WHERE 尽量贴近基表，先筛再 JOIN/聚合。
3. **时间过滤必带**：时序查询必须带时间条件（水利表数据量大，全表扫描代价高）。
4. **`EXISTS` 优于 `IN`**：子查询结果集大时用 EXISTS。
5. **JOIN 类型正确**：该 INNER 别用 LEFT。
6. **避免相关子查询**：JOIN 或窗口函数能做就别用相关子查询。
7. **警惕 JOIN 爆炸**：多对多 JOIN 前先聚合到相同粒度。

## 4. 窗口函数 / CTE 规范

**窗口函数**（MySQL 8+ 支持）：
- 排名：`ROW_NUMBER()/RANK()/DENSE_RANK() OVER (PARTITION BY ... ORDER BY ...)`
- 偏移：`LAG(col,n)/LEAD(col,n) OVER (...)`（同比/环比、前后值）
- 运行总数/移动平均：`SUM() OVER (ORDER BY ... ROWS BETWEEN N PRECEDING AND CURRENT ROW)`
- 占比：`SUM() OVER ()`（分组总计做分母）
- `FIRST_VALUE/LAST_VALUE`：注意必须写 `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`，否则取错。

**去重范式**（取每组最新一条）：
```sql
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY stcd ORDER BY tm DESC) AS rn
  FROM st_rsvr_r WHERE tm > DATE_SUB(NOW(), INTERVAL 7 DAY)
)
SELECT * FROM ranked WHERE rn = 1;
```

**CTE 可读性**：每 CTE 表达一个逻辑变换，语义命名（`daily_rainfall`/`latest_reading`），不要 `a/b/c`。

## 5. 6 条错误排查铁律

1. **除零**：用 `NULLIF(denominator, 0)`（返回 NULL 而非报错）。
2. **列名限定**：JOIN 中列名必须加表别名（`r.rz` 不是 `rz`），防歧义。
3. **GROUP BY**：必须包含所有非聚合列（或用 ANY_VALUE）。
4. **类型不匹配**：比较前显式 CAST（水利电气参数是 varchar，数值比较前 `CAST(p AS DECIMAL)`）。
5. **MySQL 方言**：`DATE_FORMAT(tm,'%Y-%m')`、`DATE_ADD(tm,INTERVAL 7 DAY)`、`JSON_EXTRACT`、`REGEXP`、`DAYOFWEEK()`。
6. **关联键**：查 `schema.md` 铁律，`stcd`(varchar) vs `eq_id`(bigint) 不能混用。
