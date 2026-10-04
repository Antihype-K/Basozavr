from dataclasses import dataclass

@dataclass
class MotorInput:
    timestamp: int
    input: float = 0.0