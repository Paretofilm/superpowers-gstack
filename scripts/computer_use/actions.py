from dataclasses import dataclass

SCROLL_DELTA = 250  # normalisert 0–1000 dra-lengde når scroll utledes fra retning


@dataclass
class ExecutorAction:
    kind: str
    params: dict


def _clamp(v: float) -> float:
    return max(0, min(1000, v))


def adapt(step: dict) -> ExecutorAction:
    name = step.get("name", "")
    args = step.get("arguments", {}) or {}
    if name in ("click", "tap"):
        return ExecutorAction("tap", {"x": args.get("x"), "y": args.get("y")})
    if name == "drag_and_drop":
        return ExecutorAction("swipe", {
            "start_x": args.get("start_x"), "start_y": args.get("start_y"),
            "end_x": args.get("end_x"), "end_y": args.get("end_y"),
        })
    if name == "scroll":
        # 'scroll down' = se nedover = finger swiper opp = end_y < start_y
        x = args.get("x", 500); y = args.get("y", 500)
        d = args.get("direction", "down")
        dy = {"down": -SCROLL_DELTA, "up": SCROLL_DELTA}.get(d, 0)
        dx = {"left": SCROLL_DELTA, "right": -SCROLL_DELTA}.get(d, 0)
        return ExecutorAction("swipe", {
            "start_x": _clamp(x), "start_y": _clamp(y),
            "end_x": _clamp(x + dx), "end_y": _clamp(y + dy),
        })
    if name in ("type", "press_key"):
        return ExecutorAction("type", {"text": args.get("text", "")})
    if name == "wait":
        return ExecutorAction("wait", {})
    return ExecutorAction("unsupported", {"original": name})
