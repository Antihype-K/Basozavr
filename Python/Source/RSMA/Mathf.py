def delta_angle(current: float, target: float) -> float:
    """Works like Unity Mathf.DeltaAngle: returns normal two angles difference in [-180, 180]."""
    diff = (target - current + 180) % 360 - 180
    return diff if diff >= -180 else diff + 360