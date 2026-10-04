import numpy as np
from RSMA.Types.Vector3 import Vector3

def py_to_unity_v3(py_vec: np.ndarray) -> Vector3:
    """Конвертирует [x, y, z] из Python в Vector3 Unity (с заменой Y и Z мест)"""
    return Vector3(x=float(py_vec[0]), y=float(py_vec[2]), z=float(py_vec[1]))

def unity_to_py_v3(unity_v3) -> np.ndarray:
    """Конвертирует Vector3 из Unity в [x, y, z] NumPy массив"""
    if unity_v3 is None:
        return np.array([0.0, 0.0, 0.0])
    return np.array([float(unity_v3.x), float(unity_v3.z), float(unity_v3.y)])