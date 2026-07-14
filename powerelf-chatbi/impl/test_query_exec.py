"""query_exec + db 只读 URL 单元测试（纯函数，无 DB 连接）。"""
import os
import sys

# 加载 _shared/lib 到 path
_HERE = os.path.dirname(os.path.abspath(__file__))
_SHARED_LIB = os.path.abspath(os.path.join(_HERE, "..", "..", "_shared", "lib"))
if _SHARED_LIB not in sys.path:
    sys.path.insert(0, _SHARED_LIB)

from db import get_readonly_sqlalchemy_url  # noqa: E402


def test_readonly_url_uses_readonly_creds(monkeypatch):
    """层1：配了只读账号时，URL 用只读账号。"""
    monkeypatch.setenv("POWERELF_DB_READONLY_USER", "chatbi_ro")
    monkeypatch.setenv("POWERELF_DB_READONLY_PASSWORD", "ropass")
    monkeypatch.setenv("POWERELF_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("POWERELF_DB_PORT", "3306")
    monkeypatch.setenv("POWERELF_DB_NAME", "powerelf_srm_yml")
    url = get_readonly_sqlalchemy_url()
    assert url.startswith("mysql+pymysql://chatbi_ro:ropass@127.0.0.1:3306/powerelf_srm_yml")


def test_readonly_url_falls_back_to_main(monkeypatch):
    """层1 降级：未配只读账号时，后备主账号（告警由调用方/部署保证）。"""
    monkeypatch.delenv("POWERELF_DB_READONLY_USER", raising=False)
    monkeypatch.delenv("POWERELF_DB_READONLY_PASSWORD", raising=False)
    monkeypatch.setenv("POWERELF_DB_USER", "root")
    monkeypatch.setenv("POWERELF_DB_PASSWORD", "mainpass")
    monkeypatch.setenv("POWERELF_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("POWERELF_DB_PORT", "3306")
    monkeypatch.setenv("POWERELF_DB_NAME", "powerelf_srm_yml")
    url = get_readonly_sqlalchemy_url()
    assert "root:mainpass" in url
