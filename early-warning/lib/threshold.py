"""Threshold evaluation module for early warning system.

Implements 10 condition types, dynamic level adjustment,
description generation, and switch-type rule checking.
"""

from decimal import Decimal, ROUND_HALF_UP


# Level names for warning severity
LEVEL_NAMES = {
    1: "I级(特别严重)",
    2: "II级(严重)",
    3: "III级(较重)",
    4: "IV级(一般)",
}


def evaluate_condition(value, condition, content):
    """Evaluate a threshold condition against a value.

    Args:
        value: Numeric value to check (will be converted to Decimal).
        condition: One of 'ZERO','ONE','TOW','THREE','FOUR','FIVE',
                   'SIX','SEVEN','EIGHT','NINE'.
        content: List with threshold values [min, max]. Either may be None.

    Returns:
        bool: True if the condition is met (value triggers the rule).

    Raises:
        ValueError: If condition is not a recognized enum.
    """
    v = Decimal(str(value))
    min_val = Decimal(str(content[0])) if content[0] is not None else None
    max_val = (
        Decimal(str(content[1]))
        if len(content) > 1 and content[1] is not None
        else None
    )

    if condition == "ZERO":      # = equal
        return v == min_val
    elif condition == "ONE":     # != not equal
        return v != min_val
    elif condition == "TOW":     # >= greater or equal
        return v >= min_val
    elif condition == "THREE":   # <= less or equal
        return v <= max_val
    elif condition == "FOUR":    # {} closed interval [min, max]
        return v >= min_val and v <= max_val
    elif condition == "FIVE":    # > greater than
        return v > min_val
    elif condition == "SIX":     # < less than
        return v < max_val
    elif condition == "SEVEN":   # () open interval (min, max)
        return v > min_val and v < max_val
    elif condition == "EIGHT":   # {) half-open [min, max)
        return v >= min_val and v < max_val
    elif condition == "NINE":    # (} half-open (min, max]
        return v > min_val and v <= max_val
    else:
        raise ValueError(f"Unknown condition enum: {condition}")


def compute_dynamic_level(value, threshold, configured_level):
    """Compute dynamic warning level based on exceedance ratio.

    The final level is the more severe (smaller number) of the configured
    level and the dynamically computed level.

    Args:
        value: Actual collected value.
        threshold: Threshold boundary value that triggered the rule.
        configured_level: Level configured in the rule (1-4).

    Returns:
        int: Final warning level (1-4, 1 is most severe).
    """
    value = Decimal(str(value))
    threshold = Decimal(str(threshold))
    configured_level = int(configured_level)

    if threshold == 0:
        return configured_level

    exceed_ratio = abs(value - threshold) / abs(threshold)

    if exceed_ratio <= Decimal("0.10"):
        dynamic_level = 4   # IV (general)
    elif exceed_ratio <= Decimal("0.30"):
        dynamic_level = 3   # III (moderate)
    elif exceed_ratio <= Decimal("0.60"):
        dynamic_level = 2   # II (severe)
    else:
        dynamic_level = 1   # I (critical)

    return min(configured_level, dynamic_level)


def generate_description(value, condition, content, min_val=None, max_val=None):
    """Generate a Chinese warning description string.

    Args:
        value: The actual collected value.
        condition: Condition enum string.
        content: Raw content list [min, max].
        min_val: Override for min threshold (extracted from content if None).
        max_val: Override for max threshold (extracted from content if None).

    Returns:
        str: Formatted Chinese description of the warning.
    """
    v = float(value)
    if min_val is None:
        min_val = content[0] if content[0] is not None else None
    if max_val is None:
        max_val = content[1] if len(content) > 1 and content[1] is not None else None

    if condition == "ZERO":
        return f"值等于{min_val}，触发预警"
    elif condition == "ONE":
        return f"值不等于{min_val}，触发预警"
    elif condition == "TOW":
        return f"值{v}超过阈值{min_val}，超出{abs(v - float(min_val)):.2f}"
    elif condition == "THREE":
        return f"值{v}低于阈值{max_val}，低出{abs(float(max_val) - v):.2f}"
    elif condition == "FOUR":
        return f"值{v}在区间[{min_val},{max_val}]内，触发预警"
    elif condition == "FIVE":
        return f"值{v}大于{min_val}，超出{abs(v - float(min_val)):.2f}"
    elif condition == "SIX":
        return f"值{v}小于{max_val}，低出{abs(float(max_val) - v):.2f}"
    elif condition == "SEVEN":
        return f"值{v}在开区间({min_val},{max_val})内，触发预警"
    elif condition == "EIGHT":
        return f"值{v}在区间[{min_val},{max_val})内，触发预警"
    elif condition == "NINE":
        return f"值{v}在区间({min_val},{max_val}]内，触发预警"
    else:
        return f"值{v}触发预警"


def check_switch(value, expected_state):
    """Check a switch-type rule using precise Decimal comparison.

    Args:
        value: Current device value.
        expected_state: Decimal value representing the expected on/off state
                        (typically content[0] for open, content[1] for closed).

    Returns:
        bool: True if value matches expected_state exactly.
    """
    v = Decimal(str(value))
    target = Decimal(str(expected_state))
    return v == target
