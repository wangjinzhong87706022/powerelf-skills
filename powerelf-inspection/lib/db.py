"""数据库连接 shim —— 委托给 _shared/lib/db.py（单一事实源）。

本文件仅做转发，保留 `from db import get_connection / get_sqlalchemy_url /
create_engine / DB_*` 的既有调用方式不变。真正的实现见
hermes-skills/_shared/lib/db.py，请勿在此维护副本。
"""

import importlib.util
import os

_SHARED_DB = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared", "lib", "db.py")
)

if not os.path.isfile(_SHARED_DB):
    raise ImportError(
        f"找不到共享数据库层：{_SHARED_DB}\n"
        "本 skill 必须位于 hermes-skills/<skill>/ 目录下运行，以确保 _shared/ 可达。"
    )

_spec = importlib.util.spec_from_file_location("_shared_db", _SHARED_DB)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# re-export 全部公开符号，保持 from db import ... 调用不变
get_connection = _mod.get_connection
get_sqlalchemy_url = _mod.get_sqlalchemy_url
create_engine = _mod.create_engine
DB_HOST = _mod.DB_HOST
DB_PORT = _mod.DB_PORT
DB_NAME = _mod.DB_NAME
DB_USER = _mod.DB_USER
DB_PASSWORD = _mod.DB_PASSWORD

__all__ = [
    "get_connection",
    "get_sqlalchemy_url",
    "create_engine",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
]
