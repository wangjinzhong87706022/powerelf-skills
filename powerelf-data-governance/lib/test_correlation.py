"""Tests for correlation.py — cross-indicator correlation detection."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import pytest
import correlation


def test_rules_defined():
    """至少有一条物理规则"""
    assert len(correlation.PHYSICS_RULES) >= 1


def test_pressure_flow_contradiction():
    """渗压上升 + 渗流下降 → 矛盾"""
    changes = {"seepage_pressure": 1.0, "seepage_flow": -1.0}
    for rule in correlation.PHYSICS_RULES:
        if rule["id"] == "pressure_flow_contradiction":
            assert rule["condition"](changes) is True
            break
    else:
        pytest.fail("未找到 pressure_flow_contradiction 规则")


def test_pressure_flow_consistent():
    """渗压上升 + 渗流上升 → 一致"""
    changes = {"seepage_pressure": 1.0, "seepage_flow": 1.0}
    for rule in correlation.PHYSICS_RULES:
        if rule["id"] == "pressure_flow_contradiction":
            assert rule["condition"](changes) is False
            break


def test_rainfall_level_contradiction():
    """大雨 + 水位下降 → 矛盾"""
    changes = {"rainfall": 50, "water_level": -2.0}
    for rule in correlation.PHYSICS_RULES:
        if rule["id"] == "rainfall_level_contradiction":
            assert rule["condition"](changes) is True
            break