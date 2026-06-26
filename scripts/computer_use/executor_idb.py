import json
import subprocess


class IdbExecutor:
    def __init__(self, udid: str):
        self.udid = udid

    def _run(self, args: list[str]) -> bytes:
        return subprocess.run(args, capture_output=True, check=True).stdout

    def screenshot(self) -> bytes:
        # simctl skriver til fil; les bytes
        import tempfile, os
        path = tempfile.mktemp(suffix=".png")
        self._run(["xcrun", "simctl", "io", self.udid, "screenshot", path])
        data = open(path, "rb").read()
        os.unlink(path)
        return data

    def tap(self, p) -> None:
        self._run(["idb", "ui", "tap", str(round(p.x)), str(round(p.y)), "--udid", self.udid])

    def swipe(self, start, end) -> None:
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
        app = next(e for e in elems if e.get("type") == "Application")
        f = app["frame"]
        return (float(f["width"]), float(f["height"]))
