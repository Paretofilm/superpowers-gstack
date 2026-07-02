import base64
import getpass
import importlib.util
import json
import os
import pathlib
import re
import subprocess


def _load(n):
    s = importlib.util.spec_from_file_location(n, pathlib.Path(__file__).resolve().parent / f"{n}.py")
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def _resolve_screenshot(sc, paths):
    """Map a critic finding's screenshot reference to a batch-local path (1-indexed).

    The critic prompt asks it to reference the image number, so `sc` may be an int (3), a string
    index ("3", "Bilde 3", "image 3"), an already-resolved path, or None. A path with its own
    digits (timestamps) must pass through unre-indexed."""
    if isinstance(sc, str) and ("/" in sc or sc.endswith(".png")):
        return sc  # already a path
    idx = None
    if isinstance(sc, bool):
        idx = None
    elif isinstance(sc, int):
        idx = sc
    elif isinstance(sc, str):
        m = re.search(r"\d+", sc)
        if m:
            idx = int(m.group())
    if idx is not None and 1 <= idx <= len(paths):
        return paths[idx - 1]
    return str(sc) if sc is not None else ""


# Turn lastes via samme importlib-mønster som loop bruker for sine sibling-moduler —
# robust både under pakke-import (shim) og test-harness; loop.run leser .action/.done duck-typet.
Turn = _load("loop").Turn

TOOL = [{"type": "computer_use", "environment": "mobile",
         "enable_prompt_injection_detection": True}]


def _api_key() -> str:
    # SPIKE-FINDINGS: SDK plukker arvet GOOGLE_API_KEY/GEMINI_API_KEY — pop begge først.
    for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(k, None)
    return subprocess.run(
        ["security", "find-generic-password", "-a", os.environ.get("USER") or getpass.getuser(),
         "-s", "gemini-api-key-paid", "-w"],
        capture_output=True, text=True, check=True).stdout.strip()


class ComputerUseClient:
    def __init__(self, model: str = "gemini-3.5-flash"):
        import google.genai as g
        self._client = g.Client(api_key=_api_key())
        self.model = model
        self._prev_id = None
        self._call_id = None
        self._name = None

    def _consume(self, interaction) -> Turn:
        d = interaction.model_dump()
        self._prev_id = d.get("id")
        done = d.get("status") != "requires_action"
        steps = d.get("steps") or []
        fc = next((s for s in steps if s.get("type") == "function_call"), None)
        if fc:
            self._call_id = fc.get("id")
            self._name = fc.get("name")
            # Gemini-3 thought signatures (fc["signature"]) need NOT be echoed back: we drive the
            # session with previous_interaction_id (see respond()), so the server holds the thought
            # chain across turns. The signature is still preserved verbatim in the journal via
            # entry["raw"] == fc, for observability. (SPIKE-FINDINGS: echo unnecessary; confirmed
            # across many multi-step live runs.)
            return Turn(action=fc, done=done)
        # F7: respect derived done — requires_action with no function_call → done=False
        return Turn(action=None, done=done)

    def start(self, mission: str, screenshot_png: bytes) -> Turn:
        b64 = base64.b64encode(screenshot_png).decode()
        inter = self._client.interactions.create(
            model=self.model,
            input=[{"type": "text", "text": mission},
                   {"type": "image", "data": b64, "mime_type": "image/png"}],
            tools=TOOL)
        return self._consume(inter)

    def respond(self, result_kind: str, screenshot_png: bytes, reason=None) -> Turn:
        b64 = base64.b64encode(screenshot_png).decode()
        fr = {"type": "function_result", "name": self._name, "call_id": self._call_id,
              "result": [{"type": "text",
                          "text": json.dumps({"status": result_kind, "reason": reason})},
                         {"type": "image", "data": b64, "mime_type": "image/png"}]}
        inter = self._client.interactions.create(
            model=self.model, previous_interaction_id=self._prev_id,
            input=[fr], tools=TOOL)
        return self._consume(inter)


class VisionCritic:
    """Ekte Gemini-vision-kritiker. analyze(paths) -> findings. Degraderer til [] ved enhver feil."""
    def __init__(self, model: str = "gemini-3.5-flash"):
        # F4: lazy client — construction deferred to analyze() so keychain failure degrades to []
        self.model = model
        self._client = None

    def analyze(self, items, mission=None) -> list:
        # items: list of {"path", "caption"} or bare path strings (normalized below).
        try:
            import google.genai as g
            from google.genai import types
            client = g.Client(api_key=_api_key())
            norm = [it if isinstance(it, dict) else {"path": it, "caption": ""} for it in items]
            screenshot_paths = [it["path"] for it in norm]
            parts = [types.Part.from_text(text=_load("critic").CRITIC_PROMPT)]
            if mission:
                parts.append(types.Part.from_text(text=f"Oppdraget som drev utforskingen: {mission}"))
            for i, it in enumerate(norm, 1):
                cap = it.get("caption") or ""
                parts.append(types.Part.from_text(text=f"Bilde {i}: {cap}"))
                with open(it["path"], "rb") as f:
                    parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))
            resp = client.models.generate_content(model=self.model, contents=parts)
            text = (resp.text or "").strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1].removeprefix("json").strip()
            data = json.loads(text)
            if not isinstance(data, list):
                return []

            # Normalize findings: coerce fields to str, map screenshot int → path
            out = []
            for f in data:
                if not isinstance(f, dict):
                    continue
                out.append({
                    "severity": str(f.get("severity", "")),
                    "text": str(f.get("text", "")),
                    "screenshot": _resolve_screenshot(f.get("screenshot"), screenshot_paths)
                })
            return out
        except Exception:
            return []
