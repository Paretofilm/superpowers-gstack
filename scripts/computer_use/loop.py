import time
from dataclasses import dataclass


@dataclass
class Turn:
    action: dict | None   # computer_use step (nested) or None when done
    done: bool            # derived from interaction.status by the client


def run(mission, executor, client, *, max_steps=25, safe_area, settle=0.3,
        screenshot_dir=None, foreground_check=None):
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
    turn = client.start(mission, shot)
    step = 0
    while turn.action and not turn.done and step < max_steps:
        step += 1
        entry = {"step": step, "state": "planned", "raw": turn.action}
        journal.append(entry)
        ea = actions.adapt(turn.action)
        kind, reason = "success", None
        try:
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
            entry["state"] = "result_sent"; entry["result"] = "error"
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
            turn = client.respond(kind, shot, reason)
        except Exception:
            entry["state"] = "result_sent"; entry["result"] = kind
            status = "error"; break
        entry["state"] = "result_sent"; entry["result"] = kind
    if status is None:
        status = "completed" if (turn and turn.done) else "step_limit"
    return {"journal": journal, "status": status, "baseline_screenshot": baseline}
