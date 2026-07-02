from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

# SPIKE: iPad describe-all degenerates during transitions; retry until a usable tree.
# Applies to ALL describe-all calls — coordinate_space included (mirrors preflight's settle).
_SETTLE_ATTEMPTS = 8
_SETTLE_DELAY = 2.0


class IdbExecutor:
    def __init__(self, udid: str, orientation: str = "portrait"):
        self.udid = udid
        self.orientation = orientation

    def _run(self, args: list[str]) -> bytes:
        # F3: bounded timeout so hung idb/simctl calls propagate as TimeoutExpired.
        # check=False + explicit raise so the model gets stderr ("element not found") for
        # self-correction, not the bare "returned non-zero exit status 1" CalledProcessError hides.
        r = subprocess.run(args, capture_output=True, check=False, timeout=30)
        if r.returncode != 0:
            err = (r.stderr or b"").decode(errors="replace").strip()
            raise RuntimeError(f"{' '.join(args)} failed (exit {r.returncode}): {err or 'no stderr'}")
        return r.stdout

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

    def long_press(self, p: "Point", duration: float = 1.0) -> None:
        # a long press is a zero-length swipe held for `duration` (idb has no press-duration on tap)
        x, y = str(round(p.x)), str(round(p.y))
        self._run(["idb", "ui", "swipe", x, y, x, y, "--duration", str(duration), "--udid", self.udid])

    def go_back(self, point_w: float, point_h: float) -> None:
        # iOS has no Back button; the system "back" is an interactive-pop edge-swipe from the left.
        # Start ~1pt from the edge (x=0 can miss the gesture recognizer) and drag inward, mid-height.
        y = str(round(point_h / 2))
        self._run(["idb", "ui", "swipe", "1", y, str(round(point_w * 0.45)), y,
                   "--duration", "0.2", "--udid", self.udid])

    # HID usage ids for the common keys computer-use emits by name (idb ui key takes a keycode).
    _HID = {"return": 40, "enter": 40, "escape": 41, "esc": 41, "backspace": 42, "delete": 42,
            "tab": 43, "space": 44, "spacebar": 44}

    def press_key(self, key) -> None:
        if isinstance(key, bool):
            raise ValueError(f"invalid key: {key!r}")
        if isinstance(key, int):
            code = key
        else:
            k = str(key).strip().lower()
            if k.isdigit():
                code = int(k)
            elif k in self._HID:
                code = self._HID[k]
            else:
                raise ValueError(f"unknown key name '{key}'; no HID mapping")
        self._run(["idb", "ui", "key", str(code), "--udid", self.udid])

    def coordinate_space(self) -> tuple[float, float]:
        """(point_w, point_h) fra describe-all Application-frame. idb tar punkter, så ingen
        piksel/scale-konvertering (SPIKE-FINDINGS, Task 1).

        Settle-retry: iPad describe-all can hand back a degenerate tree (no Application) right after
        launch/transition. The SPIKE requires retry on ALL describe-all calls — including this one,
        which is hoisted once at loop start, so a single flake would otherwise kill the whole run."""
        last = "no Application element"
        for i in range(_SETTLE_ATTEMPTS):
            try:
                elems = json.loads(self._run(["idb", "ui", "describe-all", "--udid", self.udid]))
                if isinstance(elems, list):
                    app = next((e for e in elems if e.get("type") == "Application"), None)
                    if app is not None and isinstance(app.get("frame"), dict):
                        f = app["frame"]
                        return (float(f["width"]), float(f["height"]))
                    last = "no Application element"
                else:
                    last = "describe-all did not return a list"
            except (json.JSONDecodeError, ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
                # transient idb failure/timeout during a transition → retry within the settle budget
                last = str(e)
            if i < _SETTLE_ATTEMPTS - 1:
                time.sleep(_SETTLE_DELAY)
        raise ValueError(f"describe-all never yielded an Application frame after {_SETTLE_ATTEMPTS} attempts ({last})")
