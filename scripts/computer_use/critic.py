CRITIC_PROMPT = ("Finn visuelle problemer i disse app-skjermbildene: overlapp, avkutting, "
                 "kontrast, justering, layout-brudd, off-screen-elementer. "
                 "Hvert bilde har en bildetekst som forteller hvilken handling som ga skjermen — "
                 "bruk den til å skille FORVENTET tilstand (tastatur oppe, ark/modal foran, "
                 "lastindikator) fra EKTE feil, og referer hvert funn til bildenummeret. "
                 "Returner JSON-liste med {severity (P1/P2/P3), text, screenshot}.")

CRITIC_BATCH = 6  # cap images per vision call: avoids input-token/attention limits on long runs


def criticize(items, *, client, mission=None, batch_size=CRITIC_BATCH) -> list[dict]:
    """items: list of {"path", "caption"} (or bare path strings). Batched so a long run does not
    dump 25+ images into one vision call (token limit / attention dilution / all-or-nothing failure).
    mission + per-screen captions are forwarded so the critic can judge issues in context."""
    if not items:
        return []
    findings = []
    for i in range(0, len(items), batch_size):
        findings.extend(client.analyze(items[i:i + batch_size], mission=mission))
    return findings
