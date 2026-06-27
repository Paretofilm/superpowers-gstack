from __future__ import annotations

import json
import os
import subprocess
import tempfile


class IdbExecutor:
    def __init__(self, udid: str, orientation: str = "portrait"):
        self.udid = udid
        self.orientation = orientation

    def _run(self, args: list[str]) -> bytes:
        # F3: bounded timeout so hung idb/simctl calls propagate as TimeoutExpired
        return subprocess.run(args, capture_output=True, check=True, timeout=30).stdout

    def screenshot(self) -> bytes:
        # simctl skriver til fil; les bytes
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            self._run(["xcrun", "simctl", "io", self.udid, "screenshot", path])
            if self.orientation == "landscape":
                # `simctl io screenshot` captures the native-portrait framebuffer regardless of UI
                # rotation, so a landscape app lands rotated 90° inside a portrait-shaped PNG. The
                # computer-use model would then see content whose orientation does not match the
                # landscape Application frame that `denormalize` maps taps against → transposed taps.
                # Rotate the PNG upright (clockwise, matching a "Rotate Left"/Cmd+Left simulator) so
                # image orientation == frame orientation == idb tap space. iPad safe-area is symmetric,
                # so pinning the contract to left-rotation loses nothing; SKILL.md documents it.
                self._run(["sips", "-r", "90", path])
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
        text = text[:1000]  # F11: cap to prevent pathological argv sizes
        self._run(["idb", "ui", "text", text, "--udid", self.udid])

    def coordinate_space(self) -> tuple[float, float]:
        """(point_w, point_h) fra describe-all Application-frame. idb tar punkter, så ingen
        piksel/scale-konvertering (SPIKE-FINDINGS, Task 1)."""
        out = self._run(["idb", "ui", "describe-all", "--udid", self.udid])
        elems = json.loads(out)
        if not isinstance(elems, list):
            raise ValueError("describe-all did not return a list")
        app = next((e for e in elems if e.get("type") == "Application"), None)
        if app is None:
            raise ValueError("No Application element in describe-all output")
        f = app["frame"]
        return (float(f["width"]), float(f["height"]))
