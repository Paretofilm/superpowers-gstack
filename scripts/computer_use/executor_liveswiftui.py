from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import threading
import queue


class LiveSwiftUIError(RuntimeError):
    """En FORVENTET MCP-tool-feil (kode + melding). Loopen fanger den som et 'failed'-steg."""


class ViewCrashedError(LiveSwiftUIError):
    """Terminal: user-viewet krasjet (W døde). Ikke retry-bar — økten er over."""


class LiveSwiftUIExecutor:
    """macOS computer-use-executor: driver live-swiftui-MCP-serveren som det rene alternativet
    til `cliclick`. Duck-typed mot samme grensesnitt som `IdbExecutor` (screenshot/tap/swipe/
    type_text/long_press/go_back/press_key/coordinate_space), pluss macOS-spesifikk `scroll`.

    Kontrakt: docs/superpowers/specs/2026-07-04-interaction-tools-contract.md (i live-swiftui-repoet).
    ALLE koordinater er i view-POINTS, bilderom (origo øverst-venstre, y ned) — samme rom som
    `coords.denormalize` produserer. Ingen piksel/scale-konvertering (scale er kun metadata).

    live-swiftui eier sin egen server-instans (egen P+W, eget vindu) — spawnes i __init__ og
    aktiverer pakka via `render`. Prosessen dør når vi lukker stdin (P sin parent-watch tar W).
    """

    def __init__(self, binary_path: str, package_path: str, preview_id: str | None = None):
        self.binary_path = binary_path
        self.package_path = package_path
        self.preview_id = preview_id
        self._id = 0
        self._respq: "queue.Queue[dict]" = queue.Queue()
        # tmp-KATALOG (ikke pre-opprettet fil): F-7-guarden i live-swiftui nekter å overskrive en
        # eksisterende ikke-PNG, og mkstemp ville lagd en tom fil. La serveren skape PNG-en selv;
        # gjenbruk av samme sti er OK etterpå (PNG-over-PNG tillatt).
        self._shot_dir = tempfile.mkdtemp(prefix="liveswiftui-shots-")
        self._shot_path = os.path.join(self._shot_dir, "shot.png")

        self._proc = subprocess.Popen(
            [binary_path, "--mcp-stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        )
        threading.Thread(target=self._reader, daemon=True).start()

        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "gstack-macos-executor", "version": "1"}})
        # Aktiver pakka (bygger wrapper + rendrer). Feiler fail-fast med build-diagnostikk.
        self._tool("render", {"packagePath": package_path,
                              **({"previewIdentifier": preview_id} if preview_id else {})})

    # ---- MCP-transport ------------------------------------------------------

    def _reader(self):
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._respq.put(json.loads(line))
            except json.JSONDecodeError:
                pass  # ikke-JSON-støy på stdout ignoreres (protokoll-kanalen er linje-JSON)

    def _rpc(self, method: str, params: dict | None = None, timeout: float = 120.0) -> dict:
        self._id += 1
        mid = self._id
        req = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            req["params"] = params
        self._proc.stdin.write((json.dumps(req) + "\n").encode())
        self._proc.stdin.flush()
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = self._respq.get(timeout=deadline - time.time())
            except queue.Empty:
                break
            if r.get("id") == mid:
                return r
        raise LiveSwiftUIError(f"timeout waiting for '{method}'")

    def _tool(self, name: str, args: dict) -> dict:
        """Kall et MCP-tool, pakk ut ResultWrapper {"value": ..., "ok": bool}. Reiser på feil."""
        r = self._rpc("tools/call", {"name": name, "arguments": args})
        if "error" in r and r["error"] is not None:
            raise LiveSwiftUIError(f"{name}: {r['error']}")
        try:
            wrapper = json.loads(r["result"]["content"][0]["text"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            raise LiveSwiftUIError(f"{name}: malformed result ({e})")
        if wrapper.get("ok"):
            return wrapper.get("value", {})
        # Feil-sti: rekonstruer kode/melding og oversett til gstack-vennlige exceptions.
        err = wrapper.get("error", {})
        code, msg = self._error_code_message(err)
        if code == "view_crashed":
            raise ViewCrashedError(f"{name}: view_crashed ({msg})")
        raise LiveSwiftUIError(f"{name}: {code} {msg}".strip())

    @staticmethod
    def _error_code_message(err) -> tuple[str, str]:
        # ToolServiceError encodes som {"<case>": {...}} eller "<case>". Hent en lesbar kode+melding.
        if isinstance(err, str):
            return err, ""
        if isinstance(err, dict) and err:
            case = next(iter(err.keys()))
            payload = err[case]
            # camelCase case-navn → snake_case kode (samme som ToolServiceError.code på wire).
            code = "".join(("_" + c.lower()) if c.isupper() else c for c in case).lstrip("_")
            return code, (json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload))
        return "error", json.dumps(err)

    # ---- Executor-grensesnitt (matcher IdbExecutor) -------------------------

    def coordinate_space(self) -> tuple[float, float]:
        v = self._tool("coordinate_space", {"packagePath": self.package_path})
        return (float(v["pointWidth"]), float(v["pointHeight"]))

    def screenshot(self) -> bytes:
        v = self._tool("screenshot", {"packagePath": self.package_path, "outputPath": self._shot_path})
        # Med outputPath skriver serveren PNG-en til disk og dropper base64 → les fila.
        if v.get("path"):
            with open(v["path"], "rb") as f:
                return f.read()
        # Fallback: base64 inline (hvis en eldre server ikke støtter outputPath).
        return base64.b64decode(v["pngBase64"])

    def tap(self, p: "Point") -> None:
        self._tool("tap", {"packagePath": self.package_path, "x": float(p.x), "y": float(p.y)})

    def swipe(self, start: "Point", end: "Point") -> None:
        self._tool("swipe", {"packagePath": self.package_path,
                             "startX": float(start.x), "startY": float(start.y),
                             "endX": float(end.x), "endY": float(end.y)})

    def scroll(self, p: "Point", delta_x: float, delta_y: float) -> None:
        """macOS-spesifikk (loopen ruter hit via hasattr): scrollWheel-primitiv i points."""
        self._tool("scroll", {"packagePath": self.package_path,
                              "x": float(p.x), "y": float(p.y),
                              "deltaX": float(delta_x), "deltaY": float(delta_y)})

    def type_text(self, text: str) -> None:
        self._tool("type_text", {"packagePath": self.package_path, "text": text[:1000]})

    def long_press(self, p: "Point", duration: float = 1.0) -> None:
        # v0.5-A: ekte long-press er en live-swiftui-ekstensjon; degradér ærlig til tap.
        self.tap(p)

    def go_back(self, point_w: float, point_h: float) -> None:
        # macOS-preview har ingen navigasjons-stack/edge-swipe → Escape er idiomet (kontrakt §2.8).
        self._tool("press_key", {"packagePath": self.package_path, "key": "escape"})

    def press_key(self, key) -> None:
        # Serveren godtar både navn og HID-int; send uoversatt (bool avvises).
        if isinstance(key, bool):
            raise LiveSwiftUIError(f"invalid key: {key!r}")
        self._tool("press_key", {"packagePath": self.package_path, "key": key})

    # ---- Livssyklus ---------------------------------------------------------

    def close(self) -> None:
        try:
            if self._proc.stdin:
                self._proc.stdin.close()   # EOF → P avslutter, W følger
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()
