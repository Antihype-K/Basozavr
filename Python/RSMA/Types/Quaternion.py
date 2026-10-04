from dataclasses import dataclass
import math

@dataclass
class Quaternion:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    def to_yaw(self) -> float:
        """
        Returns Yaw rotation.
        Actual Y-axis rotation (Unity Y-up).
        """

        siny_cosp = 2.0 * (self.w * self.y - self.x * self.z)
        cosy_cosp = 1.0 - 2.0 * (self.y * self.y + self.z * self.z) # или (self.x * self.x + self.y * self.y)
        
        return math.degrees(math.atan2(siny_cosp, cosy_cosp))
    
    def normalize(self) -> 'Quaternion':
        """Returns normilized quaternion"""
        mag = math.sqrt(self.x**2 + self.y**2 + self.z**2 + self.w**2)
        if mag == 0:
            return Quaternion(0, 0, 0, 1)
        return Quaternion(self.x/mag, self.y/mag, self.z/mag, self.w/mag)

    def __mul__(self, other: 'Quaternion') -> 'Quaternion':
        """
        Compose of two rotations (Q1 * Q2). 
        Usefull: Q1 * Q2 != Q2 * Q1
        """
        return Quaternion(
            w = self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z,
            x = self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y,
            y = self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x,
            z = self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w
        )

    @classmethod
    def from_dict(cls, data: dict) -> 'Quaternion':
        """Build Quaternion и вытаскивает готовый yaw из eulerAngles"""
        
        return cls(
            x=float(data.get('x', 0.0)), 
            y=float(data.get('y', 0.0)), 
            z=float(data.get('z', 0.0)), 
            w=float(data.get('w', 1.0))
        )