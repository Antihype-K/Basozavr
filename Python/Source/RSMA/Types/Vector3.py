from dataclasses import dataclass
import math

@dataclass(slots=True)
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # --- Математические операции ---

    def magnitude(self) -> float:
        """Returns vector magnitude"""
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def distance_to(self, other: 'Vector3') -> float:
        """Distance from this vector to other"""
        return (self - other).magnitude()

    def normalized(self) -> 'Vector3':
        """Retunrs normalized vector"""
        mag = self.magnitude()
        if mag == 0:
            return Vector3(0.0, 0.0, 0.0)
        return Vector3(self.x / mag, self.y / mag, self.z / mag)

    def __add__(self, other: 'Vector3') -> 'Vector3':
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: 'Vector3') -> 'Vector3':
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> 'Vector3':
        """Returns dot product"""
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    # --- Сериализация ---

    @classmethod
    def from_dict(cls, data: dict) -> 'Vector3':
        return cls(
            x=float(data.get('x', 0.0)), 
            y=float(data.get('y', 0.0)), 
            z=float(data.get('z', 0.0))
        )