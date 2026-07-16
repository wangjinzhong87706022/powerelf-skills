"""Tests for offline.py — offline detection module."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime, timedelta
import offline


def test_determine_status_online():
    now = datetime(2026, 7, 16, 12, 0)
    latest = now - timedelta(minutes=30)
    assert offline.determine_status(latest, 60, now) == "ONLINE"


def test_determine_status_offline():
    now = datetime(2026, 7, 16, 12, 0)
    latest = now - timedelta(minutes=120)
    assert offline.determine_status(latest, 60, now) == "OFFLINE"


def test_determine_status_threshold_zero():
    """threshold=0 → 总是 ONLINE"""
    assert offline.determine_status(datetime(2020, 1, 1), 0) == "ONLINE"


def test_aggregate_station_status_all_online():
    assert offline.aggregate_station_status(["ONLINE", "ONLINE"]) == "ONLINE"


def test_aggregate_station_status_mixed():
    assert offline.aggregate_station_status(["ONLINE", "OFFLINE"]) == "ERROR"


def test_aggregate_station_status_has_error():
    assert offline.aggregate_station_status(["ONLINE", "ERROR"]) == "ERROR"


def test_aggregate_station_status_empty():
    assert offline.aggregate_station_status([]) == "OFFLINE"


def test_progressive_alert_ok():
    now = datetime(2026, 7, 16, 12, 0)
    deadline = now + timedelta(minutes=60)
    r = offline.progressive_alert(deadline, 60, now)
    assert r["status"] == "OK"


def test_progressive_alert_offline():
    now = datetime(2026, 7, 16, 12, 0)
    deadline = now - timedelta(minutes=10)
    r = offline.progressive_alert(deadline, 60, now)
    assert r["status"] == "OFFLINE"


def test_progressive_alert_disabled():
    now = datetime(2026, 7, 16, 12, 0)
    r = offline.progressive_alert(now, 0, now)
    assert r["status"] == "OK"


def test_classify_offline_duration():
    assert offline.classify_offline_duration(0) == "INFO"
    assert offline.classify_offline_duration(1) == "INFO"
    assert offline.classify_offline_duration(2) == "WARNING"
    assert offline.classify_offline_duration(5) == "ERROR"
    assert offline.classify_offline_duration(48) == "CRITICAL"


def test_compute_mttr_empty():
    assert offline.compute_mttr([]) == 0.0


def test_compute_mttr_normal():
    assert offline.compute_mttr([1, 2, 3]) == 2.0