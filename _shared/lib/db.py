"""统一数据库连接层（hermes-skills 各 skill 共享的单一事实源）。

环境变量（优先级从高到低）：
    POWERELF_DB_HOST / SRM_DB_HOST        数据库地址   (默认 localhost)
    POWERELF_DB_PORT / SRM_DB_PORT        数据库端口   (默认 3306)
    POWERELF_DB_NAME / SRM_DB_NAME        数据库名     (默认 powerelf_srm_yml)
    POWERELF_DB_USER / SRM_DB_USER        用户名       (默认 root)
    POWERELF_DB_PASSWORD / SRM_DB_PASSWORD  密码        (默认 "")

约定：POWERELF_DB_* 为标准前缀，SRM_DB_* 为旧名后备（向后兼容）。
未设置密码时仅告警，不阻断，便于本地无密码调试。

历史：本文件合并自 powerelf-data-governance/lib/db.py（含 pymysql.get_connection
+ SRM_DB_* 后备）与 powerelf-inspection/lib/db.py（含 create_engine）。各 skill 的
lib/db.py 现为加载本文件的薄 shim，禁止再各自维护副本。
"""

import os
import warnings
from typing import Optional

import pymysql


# ─── .env 自加载（不依赖进程 env，gateway/CLI/execute_code 任意启动方式都能拿到凭证）──────
# 动机（2026-07-17 日志实证）：hermes gateway 进程启动时不加载 ~/.hermes/.env，
# os.getenv 在 gateway 及其子进程里返回空 → query() 空密码 → agent 被迫猎密码（H3rMES@local
# 等）+ 翻会话历史连错库(powerelf_data)。改为 db.py 自己解析 .env 文件，
# 范式来自 water-resources-skills/_shared/lib/db.py 的 _load_file_env/_cfg。
def _parse_env_file(path):
    """极简 KEY=VALUE 解析器（无 python-dotenv 依赖）。"""
    values = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                val = val.split("#", 1)[0].strip()  # 去行内注释
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                    val = val[1:-1]
                values[key.strip()] = val
    except OSError:
        pass
    return values


# 候选 .env 位置：HERMES_HOME/.env（主），skill 仓库根 .env（后备）
_HERMES_HOME = os.path.expanduser(
    os.environ.get("HERMES_HOME", "~/.hermes"))
_ENV_FILE_CANDIDATES = [
    os.path.join(_HERMES_HOME, ".env"),
    os.path.join(os.environ.get("POWERELF_SKILLS_ROOT", ""), ".env"),
    "/home/scada/powerelf-skills/.env",
]


def _load_file_env():
    merged = {}
    for candidate in _ENV_FILE_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            merged.update(_parse_env_file(candidate))
    return merged


_FILE_ENV = _load_file_env()


def _cfg(key, default=""):
    """解析一个 DB 配置值：进程 env 优先 → .env 文件补齐 → 内置默认兜底。"""
    return os.environ.get(key) or _FILE_ENV.get(key) or default


DB_HOST = _cfg("POWERELF_DB_HOST") or _cfg("SRM_DB_HOST", "localhost")

# 防御：POWERELF_DB_PORT / SRM_DB_PORT 若被误填为非数字（历史曾把密码粘进端口字段），
# 不应让整个 skill 在 import 期崩溃（ValueError）。回退到 3306 并告警，保住 fallback 链。
_raw_port = _cfg("POWERELF_DB_PORT") or _cfg("SRM_DB_PORT", "3306")
try:
    DB_PORT = int(_raw_port)
except ValueError:
    warnings.warn(
        f"POWERELF_DB_PORT/SRM_DB_PORT={_raw_port!r} 不是合法端口数，回退到 3306。"
        "请检查 ~/.hermes/.env 是否把密码误填到了端口字段。",
        RuntimeWarning,
    )
    DB_PORT = 3306
DB_NAME = _cfg("POWERELF_DB_NAME") or _cfg("SRM_DB_NAME", "powerelf_srm_yml")
DB_USER = _cfg("POWERELF_DB_USER") or _cfg("SRM_DB_USER", "root")
DB_PASSWORD = _cfg("POWERELF_DB_PASSWORD") or _cfg("SRM_DB_PASSWORD", "")

if not DB_PASSWORD:
    warnings.warn(
        "POWERELF_DB_PASSWORD 未设置，将使用空密码连接数据库。"
        "生产环境请设置该环境变量。",
        RuntimeWarning,
    )


def get_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    read_timeout: Optional[int] = None,
) -> pymysql.Connection:
    """pymysql 连接（DictCursor，utf8mb4）。供 lib/ 模块使用。

    read_timeout: pymysql 读超时秒数（None=不限）。query() 默认 30s，防慢查询挂死 agent。
    """
    conn = pymysql.connect(
        host=host or DB_HOST,
        port=port or DB_PORT,
        user=user or DB_USER,
        password=password or DB_PASSWORD,
        database=database or DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        **({"read_timeout": read_timeout} if read_timeout is not None else {}),
    )
    return conn


# ─── 防呆查询封装（agent 优先用，勿手写 cursor）──────────────────────────────
# 设计动机：本地 LLM 反复把 pymysql API 写错（conn.execute() / cur.execute().fetchall()），
# 每次烧 2-4 轮 LLM 调用。本封装让 agent 只调 query(sql)→list[dict]，从机制上消灭该类错误。
# 范式来源：water-resources-skills/skills/_shared/lib/db.py 的 query/query_multi。

_READ_ONLY_PREFIXES = ("SELECT", "WITH", "SHOW", "EXPLAIN", "DESCRIBE", "DESC")


def _assert_readonly(sql: str) -> None:
    """只读护栏：拦截 INSERT/UPDATE/DELETE/DROP/ALTER 等写操作。

    写数据请用 lib/writeback.py 的受控接口，不要走 query()。
    """
    stripped = sql.strip()
    # 去掉行注释和块注释前缀，定位真正的首关键字
    while stripped:
        if stripped.startswith("--"):
            stripped = stripped.split("\n", 1)[-1].strip()
        elif stripped.startswith("/*"):
            end = stripped.find("*/")
            stripped = stripped[end + 2:].strip() if end >= 0 else ""
        else:
            break
    first = stripped.split(None, 1)[0].upper() if stripped else ""
    if first not in _READ_ONLY_PREFIXES:
        raise ValueError(
            f"query() 仅允许只读语句（{'/'.join(_READ_ONLY_PREFIXES)}），"
            f"拦截到 '{first}'。写操作请用 lib/writeback.py 的受控接口。"
        )


def query(sql: str, timeout: int = 30) -> list:
    """执行一条 SELECT，返回 list[dict]（DictCursor 行）。

    **agent 优先用这个，不要手写 conn.cursor().execute()**（pymysql API 易错：
    conn 无 execute、execute() 返回 int 不返回 cursor、不能链式 .fetchall()）。

    - 自动开关连接（用完即关，无需手动 close）
    - 只读护栏：仅放行 SELECT/WITH/SHOW/EXPLAIN/DESCRIBE
    - 读超时（默认 30s，timeout=0 表示不限）
    - 空结果返回 []，绝不返回 None

    用法::

        from db import query
        rows = query("SELECT eq_id, rz, tm FROM st_rsvr_r WHERE deleted=0 LIMIT 5")
        for r in rows:
            print(r['tm'], r['rz'])
    """
    _assert_readonly(sql)
    conn = get_connection(read_timeout=(timeout or None))
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return list(cur.fetchall())
    finally:
        conn.close()


def query_multi(sqls, timeout: int = 30) -> list:
    """批量执行多条 SELECT，返回 [每条的结果 list, ...]。每条独立连接，互不污染。"""
    return [query(sql, timeout=timeout) for sql in sqls]


# ─── 列名查询（替代"猜列名"，单一权威来源）──────────────────────────────────
# 设计动机：本地 LLM 反复凭习惯猜列名（data_time/w/head/rp…），每次炸 2 轮重试。
# columns(table) 直接从 DB 取真实列名+类型，叠加中文含义，让"查"比"猜"更省事。
# 中文含义在此维护（COLUMN_MEANINGS）——这是 meanings 的唯一事实源，schema.md 镜像它。
# 缺含义的列返回空串（仍给出真实列名+类型，不会猜错）。

COLUMN_MEANINGS = {
    "st_rsvr_r": {  # 水库水情
        "id": "主键", "st_id": "测站ID", "project_id": "工程ID",
        "tm": "观测时间(★分析窗口用这个)", "blrz": "库下水位(m)",
        "inq": "入库流量(m³/s)", "rwchrcd": "雨水情编码", "rwptn": "雨水势",
        "otq": "出库流量(m³/s)", "msqmt": "测量方式",
        "w": "蓄水量(万m³)", "rz": "库水位(m)★主检测字段",
        "eq_id": "设备ID(→eq_equip_base.id)★关联键", "stcd": "测站编码(本表99.8%空,勿用于JOIN)",
        "msvmt": "监测方式", "eq_code": "设备编码", "inqdr": "入库流量差",
    },
    "st_river_r": {  # 河道水情（本库空表）
        "tm": "观测时间", "z": "河道水位(m)★", "q": "流量(m³/s)★",
        "xsa": "过水断面面积", "xsavv": "断面平均流速", "xsmxv": "断面最大流速",
        "flwchrcd": "流势编码", "wptn": "水势(4涨5落6平)",
        "msqmt": "测量方式", "msamt": "监测方式", "msvmt": "监测手段",
        "eq_id": "设备ID★关联键", "stcd": "测站编码",
    },
    "st_pptn_r": {  # 雨量
        "tm": "观测时间(★分析窗口)", "p": "时段雨量(mm)★主检测字段",
        "dr": "时段长(min)", "pdr": "时段降水强度",
        "dyp": "日雨量(mm)", "cump": "累计雨量(mm)",
        "eq_id": "设备ID★关联键", "stcd": "测站编码(12.6%空)",
    },
    "st_pressure_r": {  # 渗压
        "tm": "观测时间(★分析窗口)", "ext_status": "设备状态",
        "ext_pressure": "外水压力/渗压(kPa)★主检测字段",
        "ext_temperature": "温度(℃)", "water_pressure": "孔隙水压力/测压管水位(m)★",
        "section_id": "断面ID", "stcd": "测站编码", "point_id": "测点ID",
        "address": "地址", "sort": "排序",
    },
    "st_percolation_r": {  # 渗流
        "percolation": "渗流量(L/s)★主检测字段(NOT NULL)",
        "tm": "观测时间(★分析窗口)", "st_id": "测站ID",
        "eq_id": "设备ID★关联键", "stcd": "测站编码(92.2%空,勿用于JOIN)",
    },
    "dsm_dfr_srvrds_srhrds": {  # GNSS位移（无 stcd 列！eq_id 是 int 不是 bigint）
        "tm": "观测时间(★分析窗口)",
        "wgs84_delta_h": "高程位移变化量(mm)★主检测字段",
        "wgs84_delta_x": "X向位移变化量(mm)", "wgs84_delta_y": "Y向位移变化量(mm)",
        "wgs84_total_h": "高程累计位移(mm)", "wgs84_total_x": "X向累计位移(mm)",
        "wgs84_total_y": "Y向累计位移(mm)",
        "speed_gh": "高程位移速率(mm)★", "speed_gx": "X向位移速率(mm)",
        "speed_gy": "Y向位移速率(mm)",
        "data_h": "高程原始观测", "data_x": "X原始观测", "data_y": "Y原始观测",
        "data_z": "Z原始观测", "data_b": "B原始", "data_l": "L原始", "data_p": "P原始",
        "eq_id": "设备ID(int,注意与其他表bigint不同)★关联键",
        "point_id": "测点ID(int)", "point_address": "测点地址",
        "distance": "距离", "hangle": "水平角", "vangle": "垂直角",
    },
    "eq_equip_base": {  # 设备台账（149台）
        "id": "主键★被各监测表eq_id引用", "name": "设备名称★", "code": "设备编码★(字符串)",
        "type_flag": "设备类型标志★", "model": "型号", "level_flag": "等级标志",
        "position": "安装位置", "manage_unit": "管理单位", "status_flag": "状态标志",
        "manufacturer": "厂商", "start_use_date": "启用日期",
        "maintenance_cycle": "维护周期(天)", "service_life": "使用寿命(年)",
        "st_base_id": "测站基础ID", "dept_id": "部门ID",
        "status": "状态(0离线/1在线/2异常)★", "category": "类别",
        "next_maintenance_date": "下次维护日期", "remark": "备注",
    },
    "eq_business_equip_relation": {  # 设备-业务映射（70条）
        "business_table": "业务表名★(如st_rsvr_r)", "eq_id": "设备ID★",
        "st_id": "测站ID★", "st_type": "站类型★",
        "frequency": "采集频率(min)★", "offline_threshold": "离线阈值(min)★",
        "equip_startup_time": "设备启用时间",
    },
    "eq_data_anomaly_record": {  # 数据异常记录
        "equipment_code": "设备编码★", "data_anomaly_datetime": "异常时间★",
        "data_anomaly_date": "异常日期", "table_name": "业务表名★",
        "whether_fix": "是否修复(0/1)", "fix_data_content": "修复内容(JSON)★",
        "time_period_id": "时段ID",
    },
    "eq_data_missing_record": {  # 数据缺失记录
        "equipment_code": "设备编码★", "data_missing_datetime": "缺失时间★",
        "data_missing_date": "缺失日期", "whether_add": "是否已补充(0/1)",
        "table_name": "业务表名★", "filled_data_content": "填充内容(JSON)★",
        "data_missing_count": "缺失数量★", "data_missing_end_time": "缺失结束时间",
    },
    "dg_equip_offline": {  # 离线阈值配置
        "st_type": "站类型★", "tm": "离线阈值(min)★⚠️此表tm是阈值不是时间!",
        "frequency": "采集频率(min)★",
    },
}

# 框架通用列（多租户/审计），每张业务表都有，统一释义，避免重复
_FRAMEWORK_COL_MEANINGS = {
    "id": "主键", "creator": "创建人", "create_time": "记录创建时间(审计,非观测)",
    "updater": "更新人", "update_time": "记录更新时间(审计,非观测)",
    "deleted": "逻辑删除标志(0正常,查询必带deleted=0)",
    "tenant_id": "租户ID",
}


# 监测表白名单（单一事实源）——governance/inspection/chatbi 入口校验均应引用此常量，
# 杜绝幽灵表名（schema.md 不存在的旧名如 st_deformation_r / st_gnss_r 等）。
ALLOWED_TABLES = frozenset({
    "st_rsvr_r", "st_river_r", "st_pptn_r",
    "st_pressure_r", "st_percolation_r",
    "dsm_dfr_srvrds_srhrds",  # GNSS 位移
})


def _sanitize_table_name(table: str) -> str:
    """防注入：表名只允许 [A-Za-z0-9_]。"""
    import re
    if not re.fullmatch(r"[A-Za-z0-9_]+", table or ""):
        raise ValueError(f"非法表名 {table!r}（只允许字母数字下划线）")
    return table


def columns(table: str) -> list:
    """返回某张表的全部列：[{column, type, nullable, key, meaning}, ...]。

    **写 SQL 前先调这个查列名，不要凭记忆/习惯猜**（猜 data_time/w/head/rp 会报错）。
    列名和类型从 DB 实时取（永远准确），中文含义从 COLUMN_MEANINGS 叠加。

    用法::

        from db import columns
        for c in columns("st_rsvr_r"):
            print(c["column"], c["type"], c["meaning"])
    """
    table = _sanitize_table_name(table)
    rows = query(f"SHOW COLUMNS FROM `{table}`")
    meanings = dict(_FRAMEWORK_COL_MEANINGS)
    meanings.update(COLUMN_MEANINGS.get(table, {}))
    return [
        {
            "column": r["Field"],
            "type": r["Type"],
            "nullable": r["Null"] == "YES",
            "key": r["Key"],
            "meaning": meanings.get(r["Field"], ""),
        }
        for r in rows
    ]


def get_sqlalchemy_url(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
) -> str:
    """构造 SQLAlchemy 连接串。供 impl/ CLI 工具的 --db 参数使用。"""
    return (
        f"mysql+pymysql://{user or DB_USER}:{password or DB_PASSWORD}"
        f"@{host or DB_HOST}:{port or DB_PORT}/{database or DB_NAME}"
    )


def create_engine(url: Optional[str] = None):
    """懒加载创建 SQLAlchemy engine（避免无 sqlalchemy 环境下 import 失败）。"""
    from sqlalchemy import create_engine as _create

    return _create(url or get_sqlalchemy_url())


def get_readonly_sqlalchemy_url(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
) -> str:
    """chatbi 专用只读连接串。

    优先级（运行时读 env，便于测试 monkeypatch）：
        POWERELF_DB_READONLY_*  →  POWERELF_DB_*  →  SRM_DB_*  →  默认值
    只读账号 chatbi_ro 仅 GRANT SELECT，作 query_exec.py 层1 DB 兜底。
    未配只读账号时后备主账号（层1 降级，但 query_exec 层2-7 代码护栏仍生效）。
    """
    ro_user = (user or _cfg("POWERELF_DB_READONLY_USER")
               or _cfg("POWERELF_DB_USER") or _cfg("SRM_DB_USER", "root"))
    ro_pwd = (password or _cfg("POWERELF_DB_READONLY_PASSWORD")
              or _cfg("POWERELF_DB_PASSWORD") or _cfg("SRM_DB_PASSWORD", ""))
    ro_host = host or _cfg("POWERELF_DB_HOST") or _cfg("SRM_DB_HOST", "localhost")
    _raw = _cfg("POWERELF_DB_PORT") or _cfg("SRM_DB_PORT", "3306")
    try:
        ro_port = port or int(_raw)
    except ValueError:
        ro_port = 3306
    ro_db = database or _cfg("POWERELF_DB_NAME") or _cfg("SRM_DB_NAME", "powerelf_srm_yml")
    return f"mysql+pymysql://{ro_user}:{ro_pwd}@{ro_host}:{ro_port}/{ro_db}"
