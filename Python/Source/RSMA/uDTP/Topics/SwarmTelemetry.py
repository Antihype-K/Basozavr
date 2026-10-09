from dataclasses import dataclass


@dataclass
class SwarmTelemetry:
    """Mirror of RSMA.uDTP.Topics.SwarmTelemetry: swarm state of the built-in mission (scene 1)."""

    timestamp: int = 0
    missionTime: float = 0.0  # simulation time of the mission, s
    swingAngle: float = 0.0  # cable deviation from vertical (payload swing), deg
    totalTension: float = 0.0  # N
    minTension: float = 0.0  # N, one cable
    maxTension: float = 0.0  # N, one cable
    payloadSpeed: float = 0.0  # m/s
    traveledDistance: float = 0.0  # m
    laps: int = 0
    payloadAttached: bool = False
