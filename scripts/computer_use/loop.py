import time
from dataclasses import dataclass

_API_RETRIES = 2       # retries beyond the first attempt (3 tries total)
_API_RETRY_BASE = 1.0  # seconds; exponential backoff between attempts


def _call_with_retry(fn):
    """Bounded retry for a computer-use API call: one transient blip (rate limit, 5xx, network)
    should not lose the whole unattended run. Re-raises the last error if all attempts fail."""
    last = None
    for attempt in range(_API_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt < _API_RETRIES:
                time.sleep(_API_RETRY_BASE * (2 ** attempt))
    raise last


@dataclass
class Turn:
    action: dict | None   # computer_use step (nested) or None when done
    done: bool            # derived from interaction.status by the client


def run(mission, executor, client, *, max_steps=25, safe_area, settle=0.5,
        screenshot_dir=None, foreground_check=None):
    # settle=0.5: the post-action screenshot must land AFTER the UI transition, not mid-animation.
    # Standard iOS push/pop is ~0.35s and modal presentation ~0.5s; 0.3s could capture a half-rendered
    # frame that both the driving model and the critic then misread. 0.5s covers the common cases.
    import importlib.util, pathlib
    pkg = pathlib.Path(__file__).resolve().parent
    def _load(n):
        s = importlib.util.spec_from_file_location(n, pkg / f"{n}.py")
        m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
    actions, coords = _load("actions"), _load("coords")

    def _persist(shot_bytes, idx):
        if not screenshot_dir:
            return None
        d = pathlib.Path(screenshot_dir); d.mkdir(parents=True, exist_ok=True)
        p = d / f"shot_{idx:03d}.png"; p.write_bytes(shot_bytes)
        return str(p)

    point_w, point_h = executor.coordinate_space()   # hoisted: static for the run
    journal = []
    baseline = None
    status = None
    shot = executor.screenshot()
    baseline = _persist(shot, 0)
    turn = _call_with_retry(lambda: client.start(mission, shot))
    step = 0

    # F9: foreground check before the first action
    if foreground_check is not None:
        try:
            alive = foreground_check()
        except Exception:
            alive = True
        if not alive:
            return {"journal": [], "status": "app_left_foreground", "baseline_screenshot": baseline}

    while turn.action and not turn.done and step < max_steps:
        step += 1
        entry = {"step": step, "state": "planned", "raw": turn.action}
        journal.append(entry)
        kind, reason = "success", None
        try:
            # F2: adapt inside try so malformed actions are caught as "failed" entries
            ea = actions.adapt(turn.action)
            if ea.kind == "tap":
                p = coords.denormalize(ea.params["x"], ea.params["y"], point_w, point_h)
                if not coords.in_safe_area(p, safe_area):
                    kind, reason = "rejected", "outside safe area"
                else:
                    entry["state"] = "validated"; executor.tap(p); entry["state"] = "executed"
            elif ea.kind == "swipe":
                start = coords.denormalize(ea.params["start_x"], ea.params["start_y"], point_w, point_h)
                end = coords.denormalize(ea.params["end_x"], ea.params["end_y"], point_w, point_h)
                if not (coords.in_safe_area(start, safe_area) and coords.in_safe_area(end, safe_area)):
                    kind, reason = "rejected", "outside safe area"
                else:
                    entry["state"] = "validated"; executor.swipe(start, end); entry["state"] = "executed"
            elif ea.kind == "long_press":
                p = coords.denormalize(ea.params["x"], ea.params["y"], point_w, point_h)
                if not coords.in_safe_area(p, safe_area):
                    kind, reason = "rejected", "outside safe area"
                else:
                    entry["state"] = "validated"; executor.long_press(p); entry["state"] = "executed"
            elif ea.kind == "go_back":
                # system edge-swipe; deliberately not safe-area-checked (it must start at the edge)
                entry["state"] = "validated"; executor.go_back(point_w, point_h); entry["state"] = "executed"
            elif ea.kind == "press_key":
                executor.press_key(ea.params["key"]); entry["state"] = "executed"
            elif ea.kind == "type":
                executor.type_text(ea.params["text"]); entry["state"] = "executed"
            elif ea.kind == "wait":
                entry["state"] = "executed"
            else:
                kind, reason = "unsupported", ea.params.get("original")
        except Exception as exc:
            kind, reason = "failed", str(exc)
        time.sleep(settle)
        try:
            shot = executor.screenshot()
        except Exception as exc:
            # F6: explicit state so journal never falsely claims success
            entry["state"] = "screenshot_failed"; entry["result"] = "error"
            status = "error"; break
        entry["screenshot"] = _persist(shot, step)
        if foreground_check is not None:
            try:
                alive = foreground_check()
            except Exception:
                alive = True   # never let the liveness probe itself abort the run
            if not alive:
                entry["state"] = "result_sent"; entry["result"] = "app_left_foreground"
                status = "app_left_foreground"; break
        try:
            turn = _call_with_retry(lambda: client.respond(kind, shot, reason))
        except Exception:
            # F6: respond failure (after bounded retry) must not report the action kind as result
            entry["state"] = "respond_failed"; entry["result"] = "error"
            status = "error"; break
        entry["state"] = "result_sent"; entry["result"] = kind
    if status is None:
        if turn and turn.done:
            status = "completed"
        elif turn and turn.action is None:
            # loop exited because the model returned no action while not done — an abnormal
            # empty/malformed turn (requires_action without a function_call), not step exhaustion.
            status = "error"
        else:
            status = "step_limit"  # ran out of steps with an action still pending
    return {"journal": journal, "status": status, "baseline_screenshot": baseline}
