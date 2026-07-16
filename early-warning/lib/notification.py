"""Notification strategy module.

Handles silence period checking, rule shielding, strategy matching,
and notification message formatting for the early warning system.
"""

from datetime import datetime


def check_silence(last_notify_time, silence_minutes, now=None):
    """Check whether a notification strategy is within its silence period.

    Args:
        last_notify_time: datetime of the last notification sent, or None.
        silence_minutes: Silence duration in minutes.
        now: Current datetime (defaults to datetime.now()).

    Returns:
        bool: True if still in silence period (should NOT notify).
              False if silence has expired (may notify).
    """
    if last_notify_time is None:
        return False

    if now is None:
        now = datetime.now()

    silence_seconds = silence_minutes * 60
    elapsed = (now - last_notify_time).total_seconds()
    return elapsed < silence_seconds


def check_shield(rule_id, shield_end_time, now=None):
    """Check whether a rule is currently shielded (suppressed).

    Args:
        rule_id: The rule identifier.
        shield_end_time: datetime when the shield expires, or None
            if no shield is active.
        now: Current datetime (defaults to datetime.now()).

    Returns:
        bool: True if the rule is shielded (should skip processing).
              False if not shielded.
    """
    if shield_end_time is None:
        return False

    if now is None:
        now = datetime.now()

    return now < shield_end_time


def match_notification_strategy(warning_level, warning_type, strategies):
    """Find the first matching notification strategy for a warning.

    Matches strategies where both the warning level and warning type
    are included in the strategy's configured lists.

    Args:
        warning_level: Integer warning level (1-4).
        warning_type: Integer warning type code.
        strategies: List of strategy dicts, each with keys:
            - enabled (bool): Whether the strategy is active.
            - ew_level (str): Comma-separated level values, e.g. "1,2,3".
            - ew_rules_type (str): Comma-separated type values.

    Returns:
        dict or None: The first matching strategy, or None if no match.
    """
    for strategy in strategies:
        if not strategy.get("enabled", False):
            continue

        levels = [int(x.strip()) for x in strategy.get("ew_level", "").split(",") if x.strip()]
        types = [int(x.strip()) for x in strategy.get("ew_rules_type", "").split(",") if x.strip()]

        if warning_level in levels and warning_type in types:
            return strategy

    return None


def build_notification_message(warning_info):
    """Build a formatted notification message from warning information.

    Args:
        warning_info: Dict with keys:
            - rule_name (str): Name of the triggered rule.
            - warning_level (int): Warning level (1-4).
            - level_name (str): Human-readable level name.
            - value (str|number): The triggering value.
            - description (str): Warning description text.
            - trigger_time (str|datetime): When the warning was triggered.
            - location (str, optional): Location or equipment name.

    Returns:
        str: Formatted notification message.
    """
    level = warning_info.get("warning_level", "")
    level_name = warning_info.get("level_name", "")
    rule_name = warning_info.get("rule_name", "未知规则")
    value = warning_info.get("value", "")
    description = warning_info.get("description", "")
    trigger_time = warning_info.get("trigger_time", "")
    location = warning_info.get("location", "")

    # Format trigger_time if it's a datetime object
    if isinstance(trigger_time, datetime):
        trigger_time = trigger_time.strftime("%Y-%m-%d %H:%M:%S")

    parts = [f"【预警通知】{level_name}"]
    parts.append(f"规则: {rule_name}")
    if location:
        parts.append(f"位置: {location}")
    parts.append(f"当前值: {value}")
    if description:
        parts.append(f"详情: {description}")
    parts.append(f"时间: {trigger_time}")

    return "\n".join(parts)
