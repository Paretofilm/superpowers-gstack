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


# insets in POINTS as (left, top, right, bottom). HIG defaults; spike-confirmed.
INSET_TABLE = {
    "ipad":          {"portrait": (0, 24, 0, 20),  "landscape": (0, 24, 0, 20)},
    "iphone_island": {"portrait": (0, 59, 0, 34),  "landscape": (59, 0, 59, 21)},
    "iphone_notch":  {"portrait": (0, 47, 0, 34),  "landscape": (47, 0, 47, 21)},
}


def table_insets(device_class, orientation, point_w, point_h):
    left, top, right, bottom = INSET_TABLE[device_class][orientation]
    return SafeArea(left, top, point_w - right, point_h - bottom)
