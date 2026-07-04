#!/usr/bin/env python3
"""Flag when Anthropic ships a Claude model newer than the router points to.

The weekly update pipeline checks GStack / Superpowers / Claude Code versions, but
never the Anthropic model list — so `skills/setup-routing/model-routing.md` silently
went stale when Sonnet 5 shipped (2026-06-30) and sat unwired for days. This closes
that gap: query `/v1/models`, compare per tier against what the router references,
and open a `model-review` GitHub issue when a newer model exists.

DESIGN — flag for review, NEVER auto-change:
  This script only OPENS AN ISSUE. It never edits model-routing.md and is wired as a
  job SEPARATE from the auto-update PR flow, so a model ID is never rewritten
  unattended. A human decides whether a "drop-in replacement" really is one and wires
  it in by hand (model IDs are pinned snapshots with behaviour differences; auto-merge
  is the wrong default here).

Detection is stateless — no baseline file. Per tier keyword (opus/sonnet/haiku/fable):
  router version  = version parsed from the ID model-routing.md references
  api  version    = max parseable version among that tier's IDs in /v1/models
  flag when api_version > router_version.
Version tuples compare correctly across the current dateless format: (5,) > (4, 6),
(4, 8) > (4, 6). Unparseable IDs (previews, dated legacy snapshots) are skipped, not
crashed on. When a human wires the new ID in, router_version catches up and the flag
clears on the next run — no state to reset.

Usage:
  python3 scripts/check-new-models.py            # live: fetch + detect + open issue
  python3 scripts/check-new-models.py --dry-run  # fetch + detect + print, no issue
  python3 scripts/check-new-models.py --self-test # detection logic vs synthetic data

Env (live mode): ANTHROPIC_API_KEY (required), GH_TOKEN (for `gh issue create`).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODEL_ROUTING = REPO / "skills" / "setup-routing" / "model-routing.md"
TIERS = ("fable", "opus", "sonnet", "haiku")
ISSUE_LABEL = "model-review"
API_URL = "https://api.anthropic.com/v1/models"


def parse_version(model_id: str, tier: str) -> tuple[int, ...] | None:
    """Version tuple from a `claude-<tier>-<version>` id, or None if unparseable.

    `claude-sonnet-5` -> (5,); `claude-opus-4-8` -> (4, 8). A preview/dated suffix
    (`claude-fable-5-preview`, legacy `claude-3-5-sonnet-20241022`) yields a
    non-integer token -> None (skip, don't guess an ordering)."""
    m = re.fullmatch(rf"claude-{tier}-(.+)", model_id)
    if not m:
        return None
    parts = m.group(1).split("-")
    # Drop a trailing dated-snapshot segment: `claude-sonnet-5-20260630` is the same
    # tier version as the `claude-sonnet-5` alias, NOT a newer one. Without this, the
    # date parses as a version component and (5, 20260630) > (5,) false-flags the
    # already-wired model, re-opening the issue every week (codex P2).
    if parts and re.fullmatch(r"\d{8}", parts[-1]):
        parts = parts[:-1]
    if not parts:
        return None
    try:
        nums = tuple(int(p) for p in parts)
    except ValueError:
        return None
    # A 5+-digit component is a date/opaque suffix, not a real version number —
    # reject so no other date-like form slips through as a huge int and false-flags.
    if any(n >= 10000 for n in nums):
        return None
    return nums


def router_versions(text: str) -> dict[str, tuple[int, ...]]:
    """{tier: version_tuple} for the IDs model-routing.md currently references."""
    out: dict[str, tuple[int, ...]] = {}
    for tier in TIERS:
        # Match the first `claude-<tier>-<version>` token mentioned for this tier.
        m = re.search(rf"claude-{tier}-[0-9][0-9-]*", text)
        if not m:
            continue
        v = parse_version(m.group(0), tier)
        if v is not None:
            out[tier] = v
    return out


def newest_api_versions(model_ids: list[str]) -> dict[str, tuple[tuple[int, ...], str]]:
    """{tier: (max_version_tuple, that_id)} across the API's model list."""
    best: dict[str, tuple[tuple[int, ...], str]] = {}
    for mid in model_ids:
        for tier in TIERS:
            v = parse_version(mid, tier)
            if v is None:
                continue
            if tier not in best or v > best[tier][0]:
                best[tier] = (v, mid)
    return best


def find_new_models(
    router: dict[str, tuple[int, ...]],
    api_best: dict[str, tuple[tuple[int, ...], str]],
) -> list[dict[str, str]]:
    """Tiers where the API offers a newer model than the router references."""
    flags: list[dict[str, str]] = []
    for tier, (api_v, api_id) in sorted(api_best.items()):
        router_v = router.get(tier)
        if router_v is None:
            # Router doesn't reference this tier at all — not our concern to flag
            # (e.g. a tier the plugin deliberately doesn't route to).
            continue
        if api_v > router_v:
            flags.append(
                {
                    "tier": tier,
                    "router_version": ".".join(map(str, router_v)),
                    "new_id": api_id,
                    "new_version": ".".join(map(str, api_v)),
                }
            )
    return flags


def fetch_models(api_key: str) -> list[str]:
    """All model IDs from /v1/models, following pagination. Raises on any error."""
    ids: list[str] = []
    after: str | None = None
    seen_cursors: set[str] = set()
    for _ in range(20):  # hard page cap — the catalogue is nowhere near 20*1000
        url = f"{API_URL}?limit=1000" + (f"&after_id={after}" if after else "")
        req = urllib.request.Request(
            url,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
        ids.extend(m["id"] for m in payload.get("data", []))
        if not payload.get("has_more"):
            return ids
        # Fail CLOSED on a broken pagination contract: returning a partial list as
        # success would report "router up to date" while newer models sit on pages
        # we never fetched (a silent miss — codex P2). Any of these is an error.
        after = payload.get("last_id")
        if not after:
            raise RuntimeError("pagination: has_more=true but no last_id cursor")
        if after in seen_cursors:
            raise RuntimeError(f"pagination: cursor {after!r} repeated (server loop)")
        seen_cursors.add(after)
    raise RuntimeError("pagination: exceeded 20-page cap with has_more still true")


def issue_already_open(new_id: str) -> bool:
    """True if an open `model-review` issue already names this model id.

    Idempotency: without this the weekly cron opens a fresh issue every Monday until
    a human wires the model in. `gh` unavailable/erroring -> return False (fail toward
    surfacing the model rather than silently swallowing it)."""
    try:
        out = subprocess.run(
            ["gh", "issue", "list", "--label", ISSUE_LABEL, "--state", "open",
             "--search", new_id, "--json", "title,body"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout
        return any(new_id in (i.get("title", "") + i.get("body", "")) for i in json.loads(out))
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
        print(f"::warning::could not check existing issues ({e}); proceeding to create", file=sys.stderr)
        return False


def ensure_label() -> None:
    """Create the model-review label if missing (gh issue create fails without it)."""
    subprocess.run(
        ["gh", "label", "create", ISSUE_LABEL, "--color", "1D76DB",
         "--description", "A newer Claude model is available than the router uses"],
        capture_output=True, text=True,
    )  # non-fatal: already-exists returns non-zero, which is fine


def create_issue(flags: list[dict[str, str]]) -> None:
    ensure_label()
    tiers = ", ".join(f["tier"] for f in flags)
    rows = "\n".join(
        f"| `{f['tier']}` | `{f['new_id']}` (v{f['new_version']}) | v{f['router_version']} |"
        for f in flags
    )
    body = f"""A newer Claude model is available than `skills/setup-routing/model-routing.md` references.

| Tier | Newest on `/v1/models` | Router currently uses |
|------|------------------------|-----------------------|
{rows}

## Action (manual — this is a flag, not an auto-change)
1. Verify on https://platform.claude.com/docs/en/about-claude/models/overview that the new model is a real tier head (not a preview / limited-availability id) and check its capability + pricing notes.
2. If adopting, update the ID in `model-routing.md` **and** the emitted `## Model Routing` block in BOTH generators (lint **E8** enforces the two stay byte-identical).
3. Reconsider the domain-sensitivity floor if the capability/cost calculus shifted (a near-Opus Sonnet narrows the sonnet→opus gap).
4. Bump `plugin.json` + add a CHANGELOG entry (release gate), then merge.

Model IDs are pinned snapshots with behaviour differences, so this is deliberately review-gated — the pipeline never rewrites a model ID unattended.

---
*Opened automatically by the check-models job. Close after wiring in (or deciding to skip) the {tiers} update.*"""
    subprocess.run(
        ["gh", "issue", "create",
         "--title", f"New Claude model available — wire in {tiers}",
         "--body", body, "--label", ISSUE_LABEL],
        check=True,
    )


def run_self_test() -> int:
    """Detection logic against synthetic data — no network, no gh."""
    # Router on sonnet-4-6; API has sonnet-5 + opus-4-8 (matches router) + a preview.
    api_ids = [
        "claude-fable-5", "claude-opus-4-8", "claude-sonnet-5", "claude-sonnet-4-6",
        "claude-haiku-4-5", "claude-fable-5-preview", "claude-mythos-5",
        "claude-3-5-sonnet-20241022",
    ]
    router = {"fable": (5,), "opus": (4, 8), "sonnet": (4, 6), "haiku": (4, 5)}
    flags = find_new_models(router, newest_api_versions(api_ids))
    assert len(flags) == 1, f"expected 1 flag, got {flags}"
    assert flags[0]["tier"] == "sonnet" and flags[0]["new_id"] == "claude-sonnet-5", flags
    # Parser edge cases
    assert parse_version("claude-sonnet-5", "sonnet") == (5,)
    assert parse_version("claude-opus-4-8", "opus") == (4, 8)
    assert parse_version("claude-fable-5-preview", "fable") is None
    assert parse_version("claude-3-5-sonnet-20241022", "sonnet") is None
    assert (5,) > (4, 6) and (4, 8) > (4, 6)
    # Dated snapshot of an already-wired alias must NOT flag (codex P2): the date
    # is dropped, so it parses equal to the alias, not newer.
    assert parse_version("claude-sonnet-5-20260630", "sonnet") == (5,), "date suffix must be dropped"
    router_dated = {"fable": (5,), "opus": (4, 8), "sonnet": (5,), "haiku": (4, 5)}
    assert find_new_models(router_dated, newest_api_versions(
        ["claude-sonnet-5", "claude-sonnet-5-20260630"])) == [], "dated snapshot must not re-flag"
    # After wiring sonnet-5 in, no flag
    router2 = {**router, "sonnet": (5,)}
    assert find_new_models(router2, newest_api_versions(api_ids)) == [], "should clear once wired"
    # Router-references-a-tier-the-api-lacks must not crash
    assert find_new_models({"opus": (9, 9)}, newest_api_versions(api_ids)) == []
    # Pagination fails CLOSED (codex P2): mock urlopen and assert raises on a broken
    # cursor contract, and a clean two-page walk concatenates correctly.
    class _FakeResp:
        def __init__(self, payload): self._p = json.dumps(payload).encode()
        def read(self): return self._p
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _mk(payloads):
        it = iter(payloads)
        return lambda req, timeout=30: _FakeResp(next(it))

    orig = urllib.request.urlopen
    try:
        urllib.request.urlopen = _mk([{"data": [{"id": "claude-opus-4-8"}], "has_more": True}])
        try:
            fetch_models("k"); assert False, "missing cursor must raise"
        except RuntimeError:
            pass
        urllib.request.urlopen = _mk([
            {"data": [{"id": "a"}], "has_more": True, "last_id": "c1"},
            {"data": [{"id": "b"}], "has_more": True, "last_id": "c1"}])
        try:
            fetch_models("k"); assert False, "repeated cursor must raise"
        except RuntimeError:
            pass
        urllib.request.urlopen = _mk([
            {"data": [{"id": "claude-opus-4-8"}], "has_more": True, "last_id": "c1"},
            {"data": [{"id": "claude-sonnet-5"}], "has_more": False}])
        assert fetch_models("k") == ["claude-opus-4-8", "claude-sonnet-5"], "clean walk"
    finally:
        urllib.request.urlopen = orig
    print("self-test: PASS (11 assertions)")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return run_self_test()
    dry = "--dry-run" in sys.argv

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("::error::ANTHROPIC_API_KEY not set — cannot query /v1/models", file=sys.stderr)
        return 1
    try:
        api_ids = fetch_models(api_key)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, RuntimeError) as e:
        print(f"::error::/v1/models query failed ({e}) — refusing to guess model state", file=sys.stderr)
        return 1
    if not api_ids:
        print("::error::/v1/models returned no models — refusing to run on empty data", file=sys.stderr)
        return 1

    router = router_versions(MODEL_ROUTING.read_text())
    flags = find_new_models(router, newest_api_versions(api_ids))

    if not flags:
        summary = ", ".join(f"{t}=v{'.'.join(map(str, v))}" for t, v in sorted(router.items()))
        print(f"No newer models. Router tiers up to date: {summary}")
        return 0

    print("Newer model(s) available than the router references:")
    for f in flags:
        print(f"  {f['tier']}: router v{f['router_version']} -> {f['new_id']} (v{f['new_version']})")

    if dry:
        print("(--dry-run: not opening an issue)")
        return 0

    fresh = [f for f in flags if not issue_already_open(f["new_id"])]
    if not fresh:
        print("An open model-review issue already covers every flagged model — not duplicating.")
        return 0
    create_issue(fresh)
    print(f"Opened model-review issue for: {', '.join(f['new_id'] for f in fresh)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
