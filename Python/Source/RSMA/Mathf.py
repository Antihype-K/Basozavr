def delta_angle(current: float, target: float) -> float:
    """Works like Unity Mathf.DeltaAngle: shortest difference between two angles, in [-180, 180)."""
    return (target - current + 180.0) % 360.0 - 180.0


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Works like Unity Mathf.Clamp."""
    return max(min_value, min(max_value, value))


def lerp(a: float, b: float, t: float) -> float:
    """Works like Unity Mathf.Lerp (t is clamped to [0, 1])."""
    return a + (b - a) * clamp(t, 0.0, 1.0)


def move_towards(current: float, target: float, max_delta: float) -> float:
    """Works like Unity Mathf.MoveTowards."""
    if abs(target - current) <= max_delta:
        return target
    return current + max_delta * (1.0 if target > current else -1.0)
