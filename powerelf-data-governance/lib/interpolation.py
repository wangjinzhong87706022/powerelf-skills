"""
Smart Interpolation Module
============================

Implements four interpolation strategies for filling missing data points
in water conservancy time-series data:

  1. Linear interpolation - for short gaps and linear trends
  2. Quadratic interpolation - for mild non-linearity
  3. Cubic natural spline - for periodic data (uses Thomas algorithm)
  4. Moving average - for noisy data without clear trends

The module includes an automatic strategy selector that analyzes data
characteristics (R-squared, periodicity) to choose the best approach.

All implementations are pure Python with no scipy dependency.
"""

import math


def _round3(value):
    """Round to 3 decimal places, half-up."""
    return math.floor(value * 1000 + 0.5) / 1000.0


def _get_valid_points(values, indices_to_fill):
    """Extract valid (non-missing) data points as (index, value) pairs."""
    fill_set = set(indices_to_fill)
    return [(i, values[i]) for i in range(len(values)) if i not in fill_set]


def _find_bracketing(valid_points, idx):
    """Find the two valid points that bracket the given index.

    Returns:
        Tuple of ((left_idx, left_val), (right_idx, right_val)) or None
        if bracketing points cannot be found.
    """
    left = None
    right = None
    for pi, pv in valid_points:
        if pi <= idx:
            left = (pi, pv)
        if pi >= idx and right is None:
            right = (pi, pv)
    return (left, right)


# ---------------------------------------------------------------------------
# Linear interpolation
# ---------------------------------------------------------------------------

def interpolate_linear(values, indices_to_fill):
    """Fill missing values using linear interpolation.

    For missing points:
      - Before the first valid point: use the first valid value (forward fill).
      - After the last valid point: use the last valid value (backward fill).
      - Between two valid points: linear interpolation.

    Formula:
        value = val0 + (val1 - val0) * (idx - idx0) / (idx1 - idx0)

    Args:
        values: List of numeric values (with gaps).
        indices_to_fill: List of integer indices of missing values.

    Returns:
        List of filled values (copy of input with missing points replaced).
    """
    result = list(values)
    valid = _get_valid_points(values, indices_to_fill)

    if not valid:
        return result

    for idx in indices_to_fill:
        bracket = _find_bracketing(valid, idx)
        left, right = bracket

        if left is None:
            # Before all valid points
            result[idx] = _round3(right[1])
        elif right is None:
            # After all valid points
            result[idx] = _round3(left[1])
        elif left[0] == right[0]:
            result[idx] = _round3(left[1])
        else:
            # Linear interpolation
            idx0, val0 = left
            idx1, val1 = right
            filled = val0 + (val1 - val0) * (idx - idx0) / (idx1 - idx0)
            result[idx] = _round3(filled)

    return result


# ---------------------------------------------------------------------------
# Quadratic interpolation
# ---------------------------------------------------------------------------

def _solve_3x3(A, b):
    """Solve a 3x3 linear system Ax = b using Gaussian elimination.

    Returns the solution vector [x0, x1, x2] or None if the matrix is singular.
    """
    # Copy to avoid mutation
    M = [row[:] for row in A]
    rhs = list(b)

    n = 3
    for col in range(n):
        # Partial pivoting
        max_row = col
        for row in range(col + 1, n):
            if abs(M[row][col]) > abs(M[max_row][col]):
                max_row = row
        M[col], M[max_row] = M[max_row], M[col]
        rhs[col], rhs[max_row] = rhs[max_row], rhs[col]

        if abs(M[col][col]) < 1e-12:
            return None  # Singular

        for row in range(col + 1, n):
            factor = M[row][col] / M[col][col]
            for k in range(col, n):
                M[row][k] -= factor * M[col][k]
            rhs[row] -= factor * rhs[col]

    # Back substitution
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = rhs[i]
        for j in range(i + 1, n):
            x[i] -= M[i][j] * x[j]
        x[i] /= M[i][i]

    return x


def _find_nearest_3_valid(valid_points, idx):
    """Find the 3 nearest valid points to the given index.

    Returns list of (index, value) tuples sorted by distance, or fewer
    if not enough valid points exist.
    """
    sorted_by_dist = sorted(valid_points, key=lambda p: abs(p[0] - idx))
    return sorted_by_dist[:3]


def interpolate_quadratic(values, indices_to_fill):
    """Fill missing values using quadratic (second-order polynomial) interpolation.

    Uses the 3 nearest valid points to fit a quadratic polynomial:
        y = a*x^2 + b*x + c

    Falls back to linear interpolation if:
      - Fewer than 3 valid points are available
      - The 3x3 system is singular (degenerate points)
      - The predicted value exceeds 3x the standard deviation of valid data

    Args:
        values: List of numeric values (with gaps).
        indices_to_fill: List of integer indices of missing values.

    Returns:
        List of filled values (copy of input with missing points replaced).
    """
    result = list(values)
    valid = _get_valid_points(values, indices_to_fill)

    if len(valid) < 3:
        # Fallback to linear
        return interpolate_linear(values, indices_to_fill)

    # Compute std of valid values for range checking
    valid_vals = [v for _, v in valid]
    mean_v = sum(valid_vals) / len(valid_vals)
    var_v = sum((v - mean_v) ** 2 for v in valid_vals) / len(valid_vals)
    std_v = math.sqrt(var_v) if var_v > 0 else 0.0

    for idx in indices_to_fill:
        nearest3 = _find_nearest_3_valid(valid, idx)

        if len(nearest3) < 3:
            # Fallback for this point
            bracket = _find_bracketing(valid, idx)
            left, right = bracket
            if left is None:
                result[idx] = _round3(right[1])
            elif right is None:
                result[idx] = _round3(left[1])
            else:
                idx0, val0 = left
                idx1, val1 = right
                filled = val0 + (val1 - val0) * (idx - idx0) / (idx1 - idx0)
                result[idx] = _round3(filled)
            continue

        # Sort by index for consistent matrix construction
        pts = sorted(nearest3, key=lambda p: p[0])
        x0, y0 = pts[0]
        x1, y1 = pts[1]
        x2, y2 = pts[2]

        A = [
            [x0 * x0, x0, 1],
            [x1 * x1, x1, 1],
            [x2 * x2, x2, 1],
        ]
        b = [y0, y1, y2]

        coeffs = _solve_3x3(A, b)

        if coeffs is None:
            # Singular matrix - fallback to linear
            bracket = _find_bracketing(valid, idx)
            left, right = bracket
            if left is None:
                result[idx] = _round3(right[1])
            elif right is None:
                result[idx] = _round3(left[1])
            else:
                idx0, val0 = left
                idx1, val1 = right
                filled = val0 + (val1 - val0) * (idx - idx0) / (idx1 - idx0)
                result[idx] = _round3(filled)
            continue

        a, b_c, c_c = coeffs
        predicted = a * idx * idx + b_c * idx + c_c

        # Range check: if predicted value is more than 3 std devs away, fallback
        if std_v > 0 and abs(predicted - mean_v) > 3 * std_v:
            bracket = _find_bracketing(valid, idx)
            left, right = bracket
            if left is None:
                result[idx] = _round3(right[1])
            elif right is None:
                result[idx] = _round3(left[1])
            else:
                idx0, val0 = left
                idx1, val1 = right
                filled = val0 + (val1 - val0) * (idx - idx0) / (idx1 - idx0)
                result[idx] = _round3(filled)
        else:
            result[idx] = _round3(predicted)

    return result


# ---------------------------------------------------------------------------
# Cubic natural spline interpolation (Thomas algorithm)
# ---------------------------------------------------------------------------

def _thomas_solve(a, b, c, d):
    """Solve a tridiagonal system using the Thomas algorithm.

    Solves: a[i]*x[i-1] + b[i]*x[i] + c[i]*x[i+1] = d[i]

    This is an O(n) forward-elimination / back-substitution algorithm.

    Args:
        a: Sub-diagonal (a[0] is ignored).
        b: Main diagonal.
        c: Super-diagonal (c[n-1] is ignored).
        d: Right-hand side.

    Returns:
        Solution vector x.
    """
    n = len(b)
    if n == 0:
        return []
    if n == 1:
        return [d[0] / b[0]] if abs(b[0]) > 1e-15 else [0.0]

    # Forward sweep
    cp = [0.0] * n
    dp = [0.0] * n

    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]

    for i in range(1, n):
        denom = b[i] - a[i] * cp[i - 1]
        if abs(denom) < 1e-15:
            denom = 1e-15  # Prevent division by zero
        if i < n - 1:
            cp[i] = c[i] / denom
        dp[i] = (d[i] - a[i] * dp[i - 1]) / denom

    # Back substitution
    x = [0.0] * n
    x[n - 1] = dp[n - 1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]

    return x


def interpolate_spline(values, indices_to_fill):
    """Fill missing values using cubic natural spline interpolation.

    Constructs a natural cubic spline through all valid data points and
    evaluates it at missing indices. Uses the Thomas algorithm (O(n))
    for the tridiagonal system that arises from the spline constraints.

    Constraints:
        1. S(xi) = yi (interpolant passes through data points)
        2. Continuity of S, S', S'' at interior knots
        3. S''(x0) = 0, S''(xn) = 0 (natural boundary conditions)

    Falls back to linear interpolation if fewer than 3 valid points exist.

    Args:
        values: List of numeric values (with gaps).
        indices_to_fill: List of integer indices of missing values.

    Returns:
        List of filled values (copy of input with missing points replaced).
    """
    result = list(values)
    valid = _get_valid_points(values, indices_to_fill)

    if len(valid) < 3:
        return interpolate_linear(values, indices_to_fill)

    n = len(valid)
    xs = [p[0] for p in valid]
    ys = [p[1] for p in valid]

    # Compute step sizes h[i] = x[i+1] - x[i]
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]

    # Build tridiagonal system for second derivatives (M values).
    # Natural spline: M[0] = M[n-1] = 0
    # For interior points (i = 1..n-2):
    #   h[i-1]*M[i-1] + 2*(h[i-1]+h[i])*M[i] + h[i]*M[i+1]
    #       = 6 * ((y[i+1]-y[i])/h[i] - (y[i]-y[i-1])/h[i-1])

    if n == 3:
        # Single interior equation
        a_d = [0.0]
        b_d = [2.0 * (h[0] + h[1])]
        c_d = [0.0]
        rhs_d = [
            6.0 * ((ys[2] - ys[1]) / h[1] - (ys[1] - ys[0]) / h[0])
        ]
    else:
        m = n - 2  # number of interior unknowns
        a_d = [0.0] * m
        b_d = [0.0] * m
        c_d = [0.0] * m
        rhs_d = [0.0] * m

        for i in range(m):
            gi = i + 1  # global index
            a_d[i] = h[gi - 1] if i > 0 else 0.0
            b_d[i] = 2.0 * (h[gi - 1] + h[gi])
            c_d[i] = h[gi] if i < m - 1 else 0.0
            rhs_d[i] = 6.0 * (
                (ys[gi + 1] - ys[gi]) / h[gi]
                - (ys[gi] - ys[gi - 1]) / h[gi - 1]
            )

    interior_M = _thomas_solve(a_d, b_d, c_d, rhs_d)

    # Full M vector (including natural boundary conditions M[0]=M[n-1]=0)
    M = [0.0] + interior_M + [0.0]

    def _eval_spline(eval_idx):
        """Evaluate the spline at a given index."""
        # Find the correct segment
        seg = 0
        for k in range(n - 1):
            if eval_idx <= xs[k + 1]:
                seg = k
                break
        else:
            seg = n - 2

        dx = eval_idx - xs[seg]
        h_seg = h[seg]

        # S(x) = A*(x1-x)^3/(6*h) + B*(x-x0)^3/(6*h) + C*(x1-x) + D*(x-x0)
        # where A=M[k], B=M[k+1], C=y[k]/h - M[k]*h/6, D=y[k+1]/h - M[k+1]*h/6
        A = M[seg]
        B = M[seg + 1]
        C = ys[seg] / h_seg - M[seg] * h_seg / 6.0
        D = ys[seg + 1] / h_seg - M[seg + 1] * h_seg / 6.0

        val = (
            A * (h_seg - dx) ** 3 / (6.0 * h_seg)
            + B * dx ** 3 / (6.0 * h_seg)
            + C * (h_seg - dx)
            + D * dx
        )
        return val

    for idx in indices_to_fill:
        result[idx] = _round3(_eval_spline(idx))

    return result


# ---------------------------------------------------------------------------
# Moving average interpolation
# ---------------------------------------------------------------------------

def interpolate_moving_avg(values, indices_to_fill, window=5):
    """Fill missing values using a moving average of nearby valid points.

    For each missing point, collects the nearest valid values (up to `window`
    on each side) and computes their mean.

    Degradation rules when fewer than `window` valid points are available:
      - 3-4 valid points: use all available
      - 1-2 valid points: use the nearest (degrades to forward/backward fill)

    Args:
        values: List of numeric values (with gaps).
        indices_to_fill: List of integer indices of missing values.
        window: Number of valid points to consider on each side (default 5).

    Returns:
        List of filled values (copy of input with missing points replaced).
    """
    result = list(values)
    valid = _get_valid_points(values, indices_to_fill)

    if not valid:
        return result

    for idx in indices_to_fill:
        # Sort valid points by distance to idx
        by_dist = sorted(valid, key=lambda p: abs(p[0] - idx))
        nearest = by_dist[:window]
        filled = sum(v for _, v in nearest) / len(nearest)
        result[idx] = _round3(filled)

    return result


# ---------------------------------------------------------------------------
# R-squared computation
# ---------------------------------------------------------------------------

def compute_confidence(actual, predicted):
    """Compute R-squared (coefficient of determination) as a confidence score.

    Formula:
        R^2 = 1 - SS_res / SS_tot
        SS_res = sum((actual_i - predicted_i)^2)
        SS_tot = sum((actual_i - mean(actual))^2)

    Returns 1.0 if SS_tot is 0 (constant actual values).

    Args:
        actual: List of actual observed values.
        predicted: List of predicted/interpolated values.

    Returns:
        R-squared value (float). Can be negative if the model is worse
        than a horizontal line.
    """
    n = len(actual)
    if n == 0:
        return 0.0

    mean_a = sum(actual) / n
    ss_tot = sum((a - mean_a) ** 2 for a in actual)
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))

    if ss_tot == 0:
        return 1.0

    return 1.0 - ss_res / ss_tot


# ---------------------------------------------------------------------------
# Strategy selection
# ---------------------------------------------------------------------------

def _compute_r2_linear(values, indices_to_fill):
    """Compute R-squared of a linear fit on valid data points."""
    valid = _get_valid_points(values, indices_to_fill)
    if len(valid) < 2:
        return 0.0

    xs = [p[0] for p in valid]
    ys = [p[1] for p in valid]
    n = len(xs)

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)

    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-15:
        return 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    predicted = [slope * x + intercept for x in xs]
    return compute_confidence(ys, predicted)


def _compute_r2_quadratic(values, indices_to_fill):
    """Compute R-squared of a quadratic fit on valid data points."""
    valid = _get_valid_points(values, indices_to_fill)
    if len(valid) < 3:
        return 0.0

    pts = sorted(valid, key=lambda p: p[0])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    # Use first, middle, last points
    n = len(xs)
    idxs = [0, n // 2, n - 1]
    A = [
        [xs[idxs[0]] ** 2, xs[idxs[0]], 1],
        [xs[idxs[1]] ** 2, xs[idxs[1]], 1],
        [xs[idxs[2]] ** 2, xs[idxs[2]], 1],
    ]
    b = [ys[idxs[0]], ys[idxs[1]], ys[idxs[2]]]

    coeffs = _solve_3x3(A, b)
    if coeffs is None:
        return 0.0

    a_c, b_c, c_c = coeffs
    predicted = [a_c * x * x + b_c * x + c_c for x in xs]
    return compute_confidence(ys, predicted)


def _detect_periodicity(values, indices_to_fill):
    """Detect periodic patterns in the data using autocorrelation.

    Returns True if a strong periodic signal is detected (autocorrelation
    peak > 0.6 at any lag >= 2).
    """
    valid = _get_valid_points(values, indices_to_fill)
    if len(valid) < 6:
        return False

    ys = [p[1] for p in valid]
    n = len(ys)
    mean_y = sum(ys) / n
    centered = [y - mean_y for y in ys]
    var = sum(c * c for c in centered) / n

    if var == 0:
        return False

    max_lag = min(n // 2, 20)
    for lag in range(2, max_lag + 1):
        ac = sum(centered[i] * centered[i + lag] for i in range(n - lag))
        ac /= n * var
        if ac > 0.6:
            return True

    return False


def select_strategy(values, indices_to_fill):
    """Select the best interpolation strategy based on data characteristics.

    Decision tree:
        1. If fewer than 3 missing points -> 'linear'
        2. If linear R-squared > 0.9 and slope is small -> 'linear'
        3. If quadratic R-squared > 0.7 and curvature is small -> 'quadratic'
        4. If periodicity detected -> 'spline'
        5. Otherwise -> 'moving_avg'

    Args:
        values: List of numeric values (with gaps).
        indices_to_fill: List of integer indices of missing values.

    Returns:
        Strategy name: 'linear', 'quadratic', 'spline', or 'moving_avg'.
    """
    if len(indices_to_fill) < 3:
        return "linear"

    r2_lin = _compute_r2_linear(values, indices_to_fill)
    if r2_lin > 0.9:
        return "linear"

    r2_quad = _compute_r2_quadratic(values, indices_to_fill)
    if r2_quad > 0.7:
        return "quadratic"

    if _detect_periodicity(values, indices_to_fill):
        return "spline"

    return "moving_avg"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_STRATEGIES = {
    "linear": interpolate_linear,
    "quadratic": interpolate_quadratic,
    "spline": interpolate_spline,
    "moving_avg": interpolate_moving_avg,
}


def interpolate(values, indices_to_fill, strategy="auto"):
    """Main entry point for interpolation.

    Args:
        values: List of numeric values (with gaps).
        indices_to_fill: List of integer indices of missing values.
        strategy: One of 'auto', 'linear', 'quadratic', 'spline', 'moving_avg'.
            If 'auto', the best strategy is selected automatically.

    Returns:
        List of filled values (copy of input with missing points replaced).
    """
    if not indices_to_fill:
        return list(values)

    if strategy == "auto":
        strategy = select_strategy(values, indices_to_fill)

    func = _STRATEGIES.get(strategy)
    if func is None:
        raise ValueError(
            f"Unknown strategy '{strategy}'. "
            f"Choose from: {', '.join(sorted(_STRATEGIES.keys()))}"
        )

    return func(values, indices_to_fill)
