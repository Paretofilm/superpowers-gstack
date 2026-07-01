from test_smoke import load
critic = load("critic")


class FakeVision:
    """Records each analyze() call so tests can assert batching + context forwarding."""
    def __init__(self):
        self.calls = []

    def analyze(self, items, mission=None):
        self.calls.append({"items": items, "mission": mission})
        first = items[0]
        path = first["path"] if isinstance(first, dict) else first
        return [{"severity": "P2", "text": "knapp avkuttet", "screenshot": path}]


def test_criticize_returns_findings():
    fv = FakeVision()
    out = critic.criticize([{"path": "shot_001.png", "caption": "Startskjerm"}], client=fv)
    assert out[0]["severity"] == "P2"
    assert out[0]["screenshot"] == "shot_001.png"


def test_criticize_empty_returns_empty():
    assert critic.criticize([], client=FakeVision()) == []


def test_criticize_batches_large_input():
    fv = FakeVision()
    items = [{"path": f"shot_{i:03d}.png", "caption": f"c{i}"} for i in range(13)]
    out = critic.criticize(items, client=fv, batch_size=6)
    # 13 items / batch_size 6 -> 3 calls (6 + 6 + 1); findings merged across batches
    assert len(fv.calls) == 3
    assert [len(c["items"]) for c in fv.calls] == [6, 6, 1]
    assert len(out) == 3  # one finding echoed per batch


def test_criticize_forwards_mission_context():
    fv = FakeVision()
    critic.criticize([{"path": "s.png", "caption": "cap"}], client=fv, mission="utforsk onboarding")
    assert fv.calls[0]["mission"] == "utforsk onboarding"
    assert fv.calls[0]["items"][0]["caption"] == "cap"
