"""uDTP: topic-based data exchange with the RSMA (Unity) DataBroker."""

from typing import Any


def is_published(message: Any) -> bool:
    """
    True if the message was really published in Unity.

    The NetMQ server answers `get` for an unknown topic with a C# `default(T)`
    struct (all zeros), which is indistinguishable from data except for the
    zero timestamp. All RSMA publishers fill in the timestamp.
    """
    return message is not None and getattr(message, "timestamp", 0) != 0
