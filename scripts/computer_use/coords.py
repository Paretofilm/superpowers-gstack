from collections import namedtuple
from dataclasses import dataclass

Point = namedtuple("Point", ["x", "y"])


@dataclass
class SafeArea:
    left: float
    top: float
    right: float
    bottom: float


def denormalize(x: int, y: int, point_w: float, point_h: float) -> Point:
    """0–1000 normalisert → device-points, mot punkt-rommet (describe-all Application-frame).
    Ingen piksel/scale-konvertering: idb ui tap tar punkter (SPIKE-FINDINGS, Task 1)."""
    return Point(x / 1000.0 * point_w, y / 1000.0 * point_h)


def in_safe_area(p: Point, safe: SafeArea) -> bool:
    return safe.left <= p.x <= safe.right and safe.top <= p.y <= safe.bottom
