"""Tests for stagnation.py — stagnation (blocked sensor) detection module."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import stagnation


def test_detect_stagnation_empty():
    assert stagnation.detect_stagnation([]) == []


def test_detect_stagnation_none():
    assert stagnation.detect_stagnation([1, 2, 3, 4, 5]) == []


def test_detect_stagnation_found():
    r = stagnation.detect_stagnation([1, 1, 1, 2, 3])
    assert len(r) == 1
    assert r[0]["value"] == 1
    assert r[0]["count"] == 3


def test_detect_stagnation_repeated():
    r = stagnation.detect_stagnation([1, 1, 1, 2, 2, 2])
    assert len(r) == 2


def test_detect_stagnation_tolerance():
    """容差范围内视为相同"""
    r = stagnation.detect_stagnation([1.0, 1.000001, 1.000002], tolerance=1e-4)
    assert len(r) == 1


def test_detect_near_stagnation_empty():
    assert stagnation.detect_near_stagnation([]) == []


def test_detect_near_stagnation_none():
    assert stagnation.detect_near_stagnation([1, 10, 2, 20]) == []


def test_detect_near_stagnation_found():
    r = stagnation.detect_near_stagnation([5.0, 5.01, 4.99, 5.02, 5.01, 10], max_variation=0.005)
    assert len(r) >= 1


def test_classify_stagnation():
    assert stagnation.classify_stagnation(1) == "INFO"
    assert stagnation.classify_stagnation(4) == "WARNING"
    assert stagnation.classify_stagnation(10) == "ERROR"
    assert stagnation.classify_stagnation(30) == "CRITICAL"