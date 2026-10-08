import time


def get_unix_time_milliseconds() -> int:
    """Unix time in milliseconds, same as DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()."""
    return time.time_ns() // 1_000_000
