import base64
import importlib.util
import json
import os
import pathlib
import subprocess


def _load(n):
    s = importlib.util.spec_from_file_location(n, pathlib.Path(__file__).resolve().parent / f"{n}.py")
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


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
        ["security", "find-generic-password", "-a", os.environ["USER"],
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
            return Turn(action=fc, done=done)
        return Turn(action=None, done=True)

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
