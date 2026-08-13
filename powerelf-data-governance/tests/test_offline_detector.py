"""Tests for offline_detector.resolve_threshold — 站类型阈值解析（T3）。

复现评审 §6.1 的键不匹配 bug：旧代码 DEFAULT_THRESHOLDS.get(table, 60)
键是站类型码却传表名 → 永不命中 → 全量 fallback 60。
T3 改为 st_id → eq_business_equip_relation.st_type → dg_equip_offline.tm。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "impl"))
import pandas as pd
import offline_detector as od


class _FakeEngine:
    """按 SQL 子串路由返回预设 DataFrame 的假 engine（不连库）。"""
    def __init__(self, st_type_rows=None, dg_rows=None):
        self.st_type_rows = st_type_rows or []
        self.dg_rows = dg_rows or []

    def _df(self, rows, cols):
        return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _mk_engine(st_type=None, dg_tm=None, latest=None):
    """构造假 engine：st_type 查询返回 st_type；dg_equip_offline 返回 tm；MAX(tm) 返回 latest。"""
    eng = _FakeEngine()
    from datetime import datetime

    def fake_read_sql(sql, engine, params=None, **kw):
        s = str(sql)
        if "MAX(" in s:  # load_latest_time 的 SELECT MAX(tm) …
            rows = [{"latest": latest}] if latest is not None else []
            return eng._df(rows, ["latest"])
        if "eq_business_equip_relation" in s:
            rows = [{"st_type": st_type}] if st_type else []
            return eng._df(rows, ["st_type"])
        if "dg_equip_offline" in s:
            rows = [{"tm": dg_tm}] if dg_tm is not None else []
            return eng._df(rows, ["tm"])
        return pd.DataFrame()

    pd.read_sql = fake_read_sql
    return eng


def test_resolve_threshold_uses_dg_config():
    """SP 站：dg_equip_offline.tm=360 → resolve_threshold 返回 360（非 60）。"""
    eng = _mk_engine(st_type="SP", dg_tm="360")
    assert od.resolve_threshold(eng, "st_rsvr_r", 87) == 360


def test_resolve_threshold_pp_120():
    """PP 站：dg_equip_offline.tm=120 → 返回 120。"""
    eng = _mk_engine(st_type="PP", dg_tm="120")
    assert od.resolve_threshold(eng, "st_pptn_r", 85) == 120


def test_resolve_threshold_yz_zero_not_monitored():
    """YZ 站：dg_equip_offline.tm=0（不检测）→ 返回 0，run_detection 短路 NOT_MONITORED。"""
    from datetime import datetime, timedelta
    eng = _mk_engine(st_type="YZ", dg_tm="0", latest=datetime.now() - timedelta(hours=1))
    assert od.resolve_threshold(eng, "st_pressure_r", 93) == 0
    # 短路路径：latest 存在也返回 NOT_MONITORED，不判离线
    result = od.run_detection(eng, "st_pressure_r", 93)
    assert result["status"] == "NOT_MONITORED"


def test_resolve_threshold_fallback_default_thresholds():
    """st_type 有值但 dg_equip_offline 无配置 → 回退 DEFAULT_THRESHOLDS[st_type]。"""
    eng = _mk_engine(st_type="GN", dg_tm=None)
    assert od.resolve_threshold(eng, "dsm_dfr_srvrds_srhrds", 97) == 60


def test_resolve_threshold_fallback_table_map():
    """st_id 查不到 st_type → 表名→站类型兜底映射（st_rsvr_r→RR→DEFAULT 60）。"""
    eng = _mk_engine(st_type=None, dg_tm=None)
    assert od.resolve_threshold(eng, "st_rsvr_r", None) == 60


def test_resolve_threshold_fallback_default():
    """全链缺失 → 返回 default（60）。"""
    eng = _mk_engine(st_type=None, dg_tm=None)
    assert od.resolve_threshold(eng, "unknown_table", None, default=60) == 60
