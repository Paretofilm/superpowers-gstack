from test_smoke import load
critic = load("critic")


class FakeVision:
    def analyze(self, paths):
        return [{"severity": "P2", "text": "knapp avkuttet", "screenshot": paths[0]}]


def test_criticize_returns_findings():
    out = critic.criticize(["shot_001.png"], client=FakeVision())
    assert out[0]["severity"] == "P2"
    assert out[0]["screenshot"] == "shot_001.png"
