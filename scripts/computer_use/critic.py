CRITIC_PROMPT = ("Finn visuelle problemer i disse app-skjermbildene: overlapp, avkutting, "
                 "kontrast, justering, layout-brudd, off-screen-elementer. "
                 "Returner JSON-liste med {severity (P1/P2/P3), text, screenshot}.")


def criticize(screenshot_paths, *, client) -> list[dict]:
    if not screenshot_paths:
        return []
    return client.analyze(screenshot_paths)
