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
