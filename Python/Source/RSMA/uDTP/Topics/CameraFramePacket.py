from dataclasses import dataclass


@dataclass
class CameraFramePacket:
    """Mirror of RSMA.uDTP.Topics.CameraFramePacket."""

    width: int = 0
    height: int = 0
    channels: int = 0  # 3 for RGB24
    timestamp: int = 0
    frameSequence: int = 0
    pixelData: bytes = b""  # Raw RGB24 bytes (base64 in JSON)
