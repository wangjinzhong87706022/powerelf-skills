"""Reservoir analysis module: water level change rate, storage balance, flow aggregation, data validation."""


def water_level_change_rate(z_new, z_old):
    """Calculate water level change rate as a percentage.

    Returns (rate, level) tuple. Rate is |z_new - z_old| / z_old * 100%.
    Level is one of: 正常, 关注, 预警, 紧急.
    Returns (None, reason_string) when data is missing or invalid.
    """
    if z_old is None or z_old == 0 or z_old == -1:
        return None, "数据缺失"
    if z_new is None or z_new == -1:
        return None, "数据缺失"

    rate = abs(z_new - z_old) / z_old * 100

    if rate > 5:
        level = "紧急"
    elif rate > 3:
        level = "预警"
    elif rate > 1:
        level = "关注"
    else:
        level = "正常"

    return round(rate, 4), level


def storage_balance_check(inq, otq, rz_new, rz_old):
    """Check storage balance: compare expected water-level direction with actual.

    inq: inflow, otq: outflow, rz_new/rz_old: new/old water level.
    Returns a dict with expected_direction, actual_direction, is_consistent, deviation.
    """
    result = {
        "expected_direction": None,
        "actual_direction": None,
        "is_consistent": True,
        "deviation": None,
    }

    if inq is None or otq is None or rz_new is None or rz_old is None:
        result["deviation"] = "数据缺失，无法校验"
        result["is_consistent"] = False
        return result

    if inq > otq:
        result["expected_direction"] = "上升"
    elif inq < otq:
        result["expected_direction"] = "下降"
    else:
        result["expected_direction"] = "持平"

    if rz_new > rz_old:
        result["actual_direction"] = "上升"
    elif rz_new < rz_old:
        result["actual_direction"] = "下降"
    else:
        result["actual_direction"] = "持平"

    result["is_consistent"] = result["expected_direction"] == result["actual_direction"]

    if not result["is_consistent"]:
        if inq > otq and rz_new < rz_old:
            result["deviation"] = "入库大于出库但水位下降，可能存在蒸发/渗漏"
        elif inq < otq and rz_new > rz_old:
            result["deviation"] = "出库大于入库但水位上升，数据可能有误"
        else:
            result["deviation"] = "方向不一致"
    else:
        result["deviation"] = "正常"

    return result


def aggregate_flow_10min(records, field="otq"):
    """Aggregate flow over the last 10 minutes grouped by eq_id.

    For each device, takes the latest record only, then sums the specified field.
    records: list of dicts, each with at least 'eq_id', 'tm', and the flow field.
    Returns a dict mapping eq_id -> summed flow value.
    """
    latest_by_device = {}
    for r in records:
        dev = r.get("eq_id")
        if dev is None:
            continue
        if dev not in latest_by_device or r.get("tm") > latest_by_device[dev].get("tm"):
            latest_by_device[dev] = r

    result = {}
    for dev, r in latest_by_device.items():
        val = r.get(field)
        if val is not None:
            result[dev] = val
    return result


def validate_reservoir_data(rz, inq, otq):
    """Validate reservoir data for nulls, negatives, and out-of-range values.

    Returns a list of issue strings. Empty list means no issues found.
    """
    issues = []

    if rz is None or rz == -1:
        issues.append("水位数据缺失")
    if inq is not None and inq < 0:
        issues.append("入库流量为负")
    if otq is not None and otq < 0:
        issues.append("出库流量为负")

    return issues
