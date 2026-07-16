"""Tests for missing.py — missing data detection module."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import missing


def test_detect_missing_normal():
    r = missing.detect_missing(100, 95, 60)
    assert r["missing_periods"] == 5
    assert r["missing_rate"] == 0.05


def test_detect_missing_all_present():
    r = missing.detect_missing(100, 100, 60)
    assert r["missing_periods"] == 0


def test_detect_missing_zero_expected():
    r = missing.detect_missing(0, 0, 60)
    assert r["missing_rate"] == 0.0


def test_detect_missing_more_than_expected():
    """实际超过期望 → 0 missing"""
    r = missing.detect_missing(100, 120, 60)
    assert r["missing_periods"] == 0


def test_classify_consecutive_info():
    assert missing.classify_consecutive_missing(0) == "INFO"
    assert missing.classify_consecutive_missing(2) == "INFO"


def test_classify_consecutive_warning():
    assert missing.classify_consecutive_missing(3) == "WARNING"
    assert missing.classify_consecutive_missing(5) == "WARNING"


def test_classify_consecutive_error():
    assert missing.classify_consecutive_missing(6) == "ERROR"
    assert missing.classify_consecutive_missing(10) == "ERROR"


def test_classify_consecutive_critical():
    assert missing.classify_consecutive_missing(11) == "CRITICAL"
    assert missing.classify_consecutive_missing(100) == "CRITICAL"


def test_detect_pattern_unknown_few():
    """< 3 timestamps → unknown"""
    assert missing.detect_missing_pattern([1]) == "unknown"
    assert missing.detect_missing_pattern([1, 2]) == "unknown"


def test_detect_pattern_periodic():
    """等间隔 → periodic"""
    assert missing.detect_missing_pattern([1, 2, 3, 4]) == "periodic"


def test_detect_pattern_random():
    """不均匀间隔 → random"""
    assert missing.detect_missing_pattern([1, 2, 100]) == "random"