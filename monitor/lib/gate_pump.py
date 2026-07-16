"""Gate and pump analysis module: flow checks, voltage, frequency, phase balance, load, cooling, excitation."""


def _to_float(value):
    """Safely convert a value to float. Returns None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_gate_flow(gtophgt, gtq, total_holes, gtopnum):
    """Check gate flow consistency.

    gtophgt: gate opening height (0 = closed).
    gtq: gate flow.
    total_holes: total number of gate holes.
    gtopnum: number of open holes.
    Returns a list of issue strings.
    """
    issues = []

    gtophgt = _to_float(gtophgt)
    gtq = _to_float(gtq)
    total_holes = _to_float(total_holes)
    gtopnum = _to_float(gtopnum)

    if gtophgt is not None and gtq is not None:
        if gtophgt == 0 and gtq > 0:
            issues.append("闸门关闭但有流量，可能存在漏水")
        if gtophgt > 0 and gtq == 0:
            issues.append("闸门开启但无流量，可能存在堵塞")

    if gtopnum is not None and total_holes is not None and gtopnum > total_holes:
        issues.append(f"开启孔数 {int(gtopnum)} 超过总孔数 {int(total_holes)}")

    return issues


def check_pump_voltage(uab, ubc, uca, nominal=380, tolerance=0.10):
    """Check three-phase pump voltages.

    Inputs can be strings or floats. Standard nominal 380V with +/-10% tolerance.
    Returns a dict with is_normal (bool), values (list of floats), issues (list of strings).
    """
    values = []
    issues = []

    for label, v_str in [("Uab", uab), ("Ubc", ubc), ("Uca", uca)]:
        v = _to_float(v_str)
        if v is None:
            issues.append(f"{label} 电压数据无法解析")
        else:
            values.append(v)

    if not values:
        return {"is_normal": False, "values": [], "issues": issues}

    low = nominal * (1 - tolerance)
    high = nominal * (1 + tolerance)

    for i, v in enumerate(values):
        label = ["Uab", "Ubc", "Uca"][i]
        if v < low or v > high:
            issues.append(f"{label} 电压 {v}V 超出正常范围 [{low}, {high}]")

    return {
        "is_normal": len(issues) == 0,
        "values": values,
        "issues": issues,
    }


def check_pump_frequency(freq, nominal=50, tolerance=0.02):
    """Check pump power supply frequency.

    Standard 50Hz with +/-2% tolerance. Input can be string or float.
    Returns a dict with is_normal (bool), value (float or None), issue (str or None).
    """
    f = _to_float(freq)
    if f is None:
        return {"is_normal": False, "value": None, "issue": "频率数据无法解析"}

    low = nominal * (1 - tolerance)
    high = nominal * (1 + tolerance)

    if f < low or f > high:
        return {
            "is_normal": False,
            "value": f,
            "issue": f"频率 {f}Hz 超出正常范围 [{low}, {high}]",
        }

    return {"is_normal": True, "value": f, "issue": None}


def three_phase_imbalance(ia, ib, ic):
    """Calculate three-phase current imbalance.

    imbalance = max(|ia-ib|, |ib-ic|, |ia-ic|) / mean(ia,ib,ic) * 100
    Warning threshold: 10%.
    Inputs can be strings or floats.
    Returns a dict with imbalance_pct, is_warning, threshold.
    """
    ia_f = _to_float(ia)
    ib_f = _to_float(ib)
    ic_f = _to_float(ic)

    threshold = 0.10

    if ia_f is None or ib_f is None or ic_f is None:
        return {"imbalance_pct": None, "is_warning": False, "threshold": threshold}

    mean_i = (ia_f + ib_f + ic_f) / 3
    if mean_i == 0:
        return {"imbalance_pct": 0.0, "is_warning": False, "threshold": threshold}

    imbalance = max(abs(ia_f - ib_f), abs(ib_f - ic_f), abs(ia_f - ic_f)) / mean_i
    imbalance_pct = round(imbalance * 100, 2)

    return {
        "imbalance_pct": imbalance_pct,
        "is_warning": imbalance > threshold,
        "threshold": threshold,
    }


def load_rate(actual_power, rated_power):
    """Calculate pump load rate.

    Returns a dict with rate (float 0-1+), is_overload (bool), is_light_load (bool).
    """
    actual = _to_float(actual_power)
    rated = _to_float(rated_power)

    if actual is None or rated is None or rated == 0:
        return {"rate": None, "is_overload": False, "is_light_load": False}

    rate = actual / rated

    return {
        "rate": round(rate, 4),
        "is_overload": rate > 0.95,
        "is_light_load": rate < 0.10,
    }


def check_cooling(fan_run, fan_fault, ot, it):
    """Check cooling system status.

    fan_run: fan running status (0=stopped, 1=running).
    fan_fault: fan fault flag (0=normal, 1=fault).
    ot: oil/output temperature (string or float).
    it: inner/winding temperature (string or float).
    Returns a list of issue strings.
    """
    issues = []

    fan_run_f = _to_float(fan_run)
    fan_fault_f = _to_float(fan_fault)

    if fan_fault_f is not None and fan_fault_f == 1:
        issues.append("风机故障")

    if fan_run_f is not None and fan_run_f == 0:
        issues.append("风机未运行")

    ot_f = _to_float(ot)
    it_f = _to_float(it)

    if ot_f is not None and it_f is not None:
        temp_rise = it_f - ot_f
        if temp_rise > 10:
            issues.append(f"温升 {temp_rise:.1f}度 > 10度，冷却不足")

    return issues


def check_excitation(ul, al, status):
    """Check excitation system.

    ul: excitation voltage (string or float).
    al: excitation current (string or float).
    status: running status (0=stopped, 1=running).
    Returns a list of issue strings.
    """
    issues = []

    status_f = _to_float(status)
    if status_f is not None and status_f == 0:
        return issues

    ul_f = _to_float(ul)
    if ul_f is not None and ul_f == 0:
        issues.append("运行中励磁电压为0，励磁系统异常")
    elif ul_f is None:
        issues.append("励磁电压数据无法解析")

    al_f = _to_float(al)
    if al_f is not None and al_f == 0:
        issues.append("运行中励磁电流为0，励磁系统异常")

    return issues
