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


DB_HOST = os.getenv("POWERELF_DB_HOST") or os.getenv("SRM_DB_HOST", "localhost")
DB_PORT = int(os.getenv("POWERELF_DB_PORT") or os.getenv("SRM_DB_PORT", "3306"))
DB_NAME = os.getenv("POWERELF_DB_NAME") or os.getenv("SRM_DB_NAME", "powerelf_srm_yml")
DB_USER = os.getenv("POWERELF_DB_USER") or os.getenv("SRM_DB_USER", "root")
DB_PASSWORD = os.getenv("POWERELF_DB_PASSWORD") or os.getenv("SRM_DB_PASSWORD", "")

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
) -> pymysql.Connection:
    """pymysql 连接（DictCursor，utf8mb4）。供 lib/ 模块使用。"""
    conn = pymysql.connect(
        host=host or DB_HOST,
        port=port or DB_PORT,
        user=user or DB_USER,
        password=password or DB_PASSWORD,
        database=database or DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    return conn


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
