"""
Офлайн-модель сцены доставки для Python-скриптов (scene.Simulation.offline()).

Та же модель, что для контура управления роем (sim/swarm_sim.py): дроны
Quadrocopter.cs, тросы RSMACable.cs и груз, расставленные как в
RSMASwarmEnvironment.BuildSwarmScene(). Публикует те же топики, что Unity:
DronePose_i, PayloadPose, CableForce_i, и читает DroneTargetPose_i.
"""

import numpy as np

from control.formation import FormationManager
from RSMA.Broker import InMemoryBroker
from sim.swarm_sim import SwarmPhysicsSim


class OfflineScene:
    def __init__(self, broker: InMemoryBroker, num_drones: int = 6, radius: float = 1.414,
                 payload_position=(0.0, 0.25, 0.0), dt: float = 0.01, **sim_kwargs):
        """payload_position — начальная позиция груза в координатах Unity (Y — вверх)."""
        self.broker = broker
        self.dt = dt
        x, y, z = payload_position
        offsets = FormationManager(num_drones, radius=radius).get_formation_offsets()
        # SwarmPhysicsSim работает в системе Python (Z — вверх)
        self.physics = SwarmPhysicsSim.around_payload(broker, np.array([x, z, y]), offsets, **sim_kwargs)

    @property
    def time(self) -> float:
        return self.physics.time

    def step(self) -> None:
        self.physics.step(self.dt)

    def advance(self, seconds: float) -> None:
        for _ in range(max(1, round(seconds / self.dt))):
            self.step()
