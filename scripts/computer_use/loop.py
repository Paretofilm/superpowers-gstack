import time
from dataclasses import dataclass


@dataclass
class Turn:
    action: dict | None   # computer_use-steg (nestet) eller None når ferdig
    done: bool            # avledet av interaction.status av klienten


def run(mission, executor, client, *, max_steps=25, safe_area, settle=0.3):
    import importlib.util, pathlib
    pkg = pathlib.Path(__file__).resolve().parent
    def _load(n):
        s = importlib.util.spec_from_file_location(n, pkg / f"{n}.py")
        m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
    actions, coords = _load("actions"), _load("coords")

    journal = []
    shot = executor.screenshot()
    turn = client.start(mission, shot)
    step = 0
    while turn.action and not turn.done and step < max_steps:
        step += 1
        entry = {"step": step, "state": "planned", "raw": turn.action}
        journal.append(entry)
        ea = actions.adapt(turn.action)
        point_w, point_h = executor.coordinate_space()
        kind, reason = "success", None
        if ea.kind == "tap":
            p = coords.denormalize(ea.params["x"], ea.params["y"], point_w, point_h)
            if not coords.in_safe_area(p, safe_area):
                kind, reason = "rejected", "outside safe area"
            else:
                entry["state"] = "validated"
                executor.tap(p); entry["state"] = "executed"
        elif ea.kind == "swipe":
            start = coords.denormalize(ea.params["start_x"], ea.params["start_y"], point_w, point_h)
            end = coords.denormalize(ea.params["end_x"], ea.params["end_y"], point_w, point_h)
            if not (coords.in_safe_area(start, safe_area) and coords.in_safe_area(end, safe_area)):
                kind, reason = "rejected", "outside safe area"
            else:
                entry["state"] = "validated"
                executor.swipe(start, end); entry["state"] = "executed"
        elif ea.kind == "type":
            executor.type_text(ea.params["text"]); entry["state"] = "executed"
        elif ea.kind == "wait":
            time.sleep(settle); entry["state"] = "executed"
        else:
            kind, reason = "unsupported", ea.params.get("original")
        time.sleep(settle)
        shot = executor.screenshot()
        turn = client.respond(kind, shot, reason)
        entry["state"] = "result_sent"; entry["result"] = kind
    status = "fullført" if (turn and turn.done) else "maks-steg-nådd"
    return {"journal": journal, "status": status}
