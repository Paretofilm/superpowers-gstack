from __future__ import annotations

import json
import os
import subprocess
import tempfile


class IdbExecutor:
    def __init__(self, udid: str):
        self.udid = udid

    def _run(self, args: list[str]) -> bytes:
        return subprocess.run(args, capture_output=True, check=True).stdout

    def screenshot(self) -> bytes:
        # simctl skriver til fil; les bytes
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            self._run(["xcrun", "simctl", "io", self.udid, "screenshot", path])
            with open(path, "rb") as f:
                return f.read()
        finally:
            os.unlink(path)

    def tap(self, p: "Point") -> None:
        self._run(["idb", "ui", "tap", str(round(p.x)), str(round(p.y)), "--udid", self.udid])

    def swipe(self, start: "Point", end: "Point") -> None:
        # idb ui swipe tar to punkter (start -> end); drag_and_drop/scroll gir begge (SPIKE).
        self._run(["idb", "ui", "swipe",
                   str(round(start.x)), str(round(start.y)),
                   str(round(end.x)), str(round(end.y)), "--udid", self.udid])

    def type_text(self, text: str) -> None:
        self._run(["idb", "ui", "text", text, "--udid", self.udid])

    def coordinate_space(self) -> tuple[float, float]:
        """(point_w, point_h) fra describe-all Application-frame. idb tar punkter, så ingen
        piksel/scale-konvertering (SPIKE-FINDINGS, Task 1)."""
        out = self._run(["idb", "ui", "describe-all", "--udid", self.udid])
        elems = json.loads(out)
        app = next((e for e in elems if e.get("type") == "Application"), None)
        if app is None:
            raise ValueError("No Application element in describe-all output")
        f = app["frame"]
        return (float(f["width"]), float(f["height"]))
