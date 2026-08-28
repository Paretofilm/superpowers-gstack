# Placeholder resolution for shared emitted blocks

The block files in this directory are the single source for the sections both
generators (`setup-routing`, `adapt`) emit into a project's CLAUDE.md. Emit each
block **verbatim** — except for `{{...}}` placeholders, which the generator MUST
resolve to concrete values before writing the file. Never let a raw `{{...}}`
token reach a generated CLAUDE.md.

## `{{DOMAIN_SENSITIVITY}}` (model-routing-section.md)

The project's domain-sensitivity level: `very high` | `high` | `medium` | `low`.
Inferred during the skill's analysis step from project type and security signals
(see `model-routing.md` for the domain table). If the user adjusted it during the
confirmation step, use their answer.

## `{{DEVELOPMENT_TEAM}}` (xcode-tools.md — native tracks only)

The project's 10-character Apple Team ID. Resolve in this order:

1. **Existing project setting** — grep the project for `DEVELOPMENT_TEAM` in
   `project.yml`, `*.xcconfig`, or `*.pbxproj` and reuse that value.
2. **Local signing identity** — run
   `security find-identity -v -p codesigning` and extract the Team ID from the
   parentheses of a `Developer ID Application: <Name> (<TEAMID>)` identity
   (fall back to an `Apple Development` identity if no Developer ID cert exists).
3. **Ask the user** — one line: "What is your Apple Team ID? (Apple Developer
   Portal → Membership. Leave blank if you have no paid developer account.)"
   If the user has none, omit the `DEVELOPMENT_TEAM`/`CODE_SIGN_IDENTITY` lines
   from the emitted example and note that stable signing requires a team ID.

Never emit another project's or another user's team ID as a default.

## `{{IOS_SIMULATOR}}` (xcode-tools.md — native tracks only)

A simulator model that exists on this machine right now. Resolve with:

    xcrun simctl list devices available | sed -nE 's/^ *(iPhone [0-9]+) \(.*/\1/p' | sort -uV | tail -1

That returns the highest plain numbered model — `iPhone 17`, not `iPhone 17 Pro`. The
plain model is the one most likely to exist on a collaborator's machine too, and the
pattern earns that claim rather than asserting it: requiring ` (` immediately after the
digits excludes every `Pro`, `Pro Max` and `e` variant, so the answer does not depend on
the order `simctl` happens to list devices in. Do not simplify it back to a `grep -m1`
over the raw list — that returns whichever variant is listed first, which on a normal
machine is the Pro.

If it returns nothing, this machine has no plain numbered iPhone. Fall back to whatever
iPhone it does have:

    xcrun simctl list devices available | sed -nE 's/^ *(iPhone [^(]*[^ (]) \(.*/\1/p' | head -1

If that is empty too, no simulator runtimes are installed: emit `iPhone 17`, and say in
the report that no simulator was found locally so the destination is a guess until a
runtime is installed.

Never hardcode a constant here. Xcode ships a rolling set of simulators and drops
old ones: on the machine that motivated this placeholder (2026-08-27) no iPhone 16
remained, and the emitted command failed as `xcodebuild: error: Unable to find a
device matching the provided destination specifier` — which reads as a project
misconfiguration rather than a stale device name.
