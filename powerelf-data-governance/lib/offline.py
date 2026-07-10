"""
Offline Detection Module
=========================

Implements device offline detection algorithms for the data-governance
engine. Determines device online/offline status based on the latest
record time and configured thresholds, aggregates station-level status,
and provides progressive alerting with severity classification.

Algorithms:
  - Three-state determination (ONLINE / OFFLINE based on deadline)
  - Station-level status aggregation from device statuses
  - Progressive alerting with remaining-time ratio
  - Offline duration severity classification
  - Mean Time To Recovery (MTTR)
"""

from datetime import datetime, timedelta


def determine_status(latest_time, threshold_min, now=None):
    """Determine device online/offline status based on deadline check.

    Algorithm:
        if threshold == 0: return 'ONLINE' (no offline detection)
        deadline = latest_time + threshold_min minutes
        if deadline < now: return 'OFFLINE'
        else: return 'ONLINE'

    Args:
        latest_time: datetime of the device's latest data record.
        threshold_min: Offline threshold in minutes. A device is considered
            offline if no data has been received for this many minutes.
            A value of 0 disables offline detection (always ONLINE).
        now: Current datetime. Defaults to datetime.now() if not provided.

    Returns:
        Status string: 'ONLINE' or 'OFFLINE'.
    """
    if now is None:
        now = datetime.now()

    if threshold_min <= 0:
        return "ONLINE"

    deadline = latest_time + timedelta(minutes=threshold_min)

    if deadline < now:
        return "OFFLINE"
    else:
        return "ONLINE"


def aggregate_station_status(device_statuses):
    """Aggregate multiple device statuses into a single station status.

    Rules:
        - Any device has status 'ERROR'   -> station is 'ERROR'
        - Mixed 'ONLINE' and 'OFFLINE'    -> station is 'ERROR'
        - All devices 'OFFLINE'           -> station is 'OFFLINE'
        - All devices 'ONLINE'            -> station is 'ONLINE'

    Args:
        device_statuses: List of status strings for devices in the station.
            Expected values: 'ONLINE', 'OFFLINE', 'ERROR'.

    Returns:
        Aggregated station status string: 'ONLINE', 'OFFLINE', or 'ERROR'.
    """
    if not device_statuses:
        return "OFFLINE"

    unique = set(device_statuses)

    if "ERROR" in unique:
        return "ERROR"

    if len(unique) > 1:
        # Mixed statuses (e.g., some ONLINE, some OFFLINE)
        return "ERROR"

    # All the same
    return unique.pop()


def progressive_alert(deadline, threshold_min, now=None):
    """Generate a progressive alert based on remaining time before offline.

    The alert severity increases as the deadline approaches:
        remaining_ratio <= 0   -> OFFLINE
        remaining_ratio <= 0.2 -> WARNING (about to go offline)
        remaining_ratio <= 0.5 -> NOTICE  (data delayed)
        remaining_ratio >  0.5 -> OK      (normal)

    Args:
        deadline: datetime when the device will be declared offline.
        threshold_min: The configured offline threshold in minutes.
        now: Current datetime. Defaults to datetime.now() if not provided.

    Returns:
        Dict containing:
        - status: 'OK', 'NOTICE', 'WARNING', or 'OFFLINE'
        - remaining_ratio: Fraction of threshold time remaining (float).
            Negative values indicate the device is already overdue.
        - message: Human-readable alert message.
    """
    if now is None:
        now = datetime.now()

    remaining = (deadline - now).total_seconds() / 60.0  # in minutes

    if threshold_min <= 0:
        return {
            "status": "OK",
            "remaining_ratio": 1.0,
            "message": "Offline detection disabled.",
        }

    remaining_ratio = remaining / threshold_min

    if remaining_ratio <= 0:
        offline_duration = -remaining  # positive minutes
        return {
            "status": "OFFLINE",
            "remaining_ratio": round(remaining_ratio, 4),
            "message": f"Device is offline. Offline for {offline_duration:.0f} minutes.",
        }
    elif remaining_ratio <= 0.2:
        return {
            "status": "WARNING",
            "remaining_ratio": round(remaining_ratio, 4),
            "message": f"Device will be declared offline in {remaining:.0f} minutes.",
        }
    elif remaining_ratio <= 0.5:
        delay = threshold_min - remaining
        return {
            "status": "NOTICE",
            "remaining_ratio": round(remaining_ratio, 4),
            "message": f"Device data delayed {delay:.0f} minutes.",
        }
    else:
        return {
            "status": "OK",
            "remaining_ratio": round(remaining_ratio, 4),
            "message": "Device is operating normally.",
        }


def classify_offline_duration(hours):
    """Classify the severity of an offline event by its duration.

    Classification:
        0-1 hours   -> 'INFO'
        1-4 hours   -> 'WARNING'
        4-24 hours  -> 'ERROR'
        > 24 hours  -> 'CRITICAL'

    Args:
        hours: Duration of the offline period in hours (float).

    Returns:
        Severity level string: 'INFO', 'WARNING', 'ERROR', or 'CRITICAL'.
    """
    if hours <= 0:
        return "INFO"
    elif hours <= 1:
        return "INFO"
    elif hours <= 4:
        return "WARNING"
    elif hours <= 24:
        return "ERROR"
    else:
        return "CRITICAL"


def compute_mttr(offline_durations):
    """Compute Mean Time To Recovery (MTTR) from historical offline durations.

    MTTR is the average duration of offline events over the observation
    period. Used to assess equipment reliability.

    Formula:
        MTTR = mean(offline_durations)

    Threshold:
        MTTR > 4 hours indicates equipment reliability issues and
        suggests maintenance is needed.

    Args:
        offline_durations: List of offline event durations in hours (floats).

    Returns:
        MTTR in hours (float). Returns 0.0 if the list is empty.
    """
    if not offline_durations:
        return 0.0

    return sum(offline_durations) / len(offline_durations)
