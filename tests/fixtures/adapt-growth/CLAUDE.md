<!-- superpowers-gstack: 2.9.0 -->

# Fixture Project

A native iOS app. This file stands in for a project adapted long ago and never
re-adapted since.

## Native Apple development tools (Xcode workflow) <!-- gstack-xcode-tools-v3 -->

Xcode-related operations MUST be performed by the agent — never delegated to the user.

### Provisioning and signing, the hard way

We burned most of a day on provisioning before anyone thought to check the
build log for the actual flag `xcodebuild` wanted. The Apple Developer Portal
step everyone assumed was mandatory — manually creating an App ID, enabling
the CloudKit container, downloading a profile — turns out to be optional if
you let `xcodebuild` register the container itself.

SENTINEL-LINE-001: `-allowProvisioningUpdates` removed the manual Apple Developer
Portal registration step; without it every fresh clone stalls on provisioning.

Once we found it, the fix was one build-setting change, but the symptom before
that was brutal to diagnose: the build would fail with "no profiles for
'com.fixture.app' were found," which reads exactly like a missing entitlement,
not a missing flag. Three separate people independently concluded the fix was
to hand-edit the provisioning profile UUID into the project file, which
"worked" for about a day until the profile expired and the UUID had to be
hunted down again. Do not do that. The flag is the fix; nothing else is.

A related trap: this only works when the Apple ID behind the build has Account
Holder or Admin role on the team. An Xcode Cloud service account with a
restricted role fails the same registration silently and falls back to the old
broken behavior with no additional log output — if the flag is present and it
still fails, check the account role before re-suspecting the flag.

### Simulator vs. physical device behavior

Simulator runs and device runs are not the same test, and treating them as
interchangeable cost us a shipped regression once (SwiftData migration crash
that never reproduced in CI because CI is simulator-only).

SENTINEL-LINE-002: running on a physical iPhone requires the device unlocked AND
trusted, and the first run after a reboot always fails once before succeeding.

The failure mode on that first post-reboot run is a generic "Could not launch
— Unable to launch com.fixture.app because it has an invalid code signature,"
which has nothing to do with signing — it is `lockdownd` not having finished
re-establishing trust with the host yet. Waiting ~15 seconds and re-running
the same command succeeds without touching anything. Do not chase code-signing
theories the first time you see this error on device; only chase them if it
persists past a second attempt.

Other simulator/device divergences we've now hit more than once:
- Push notification entitlements silently no-op in the simulator (as expected,
  but it is easy to forget mid-session and burn twenty minutes on a "why isn't
  this firing" loop before remembering).
- `BGTaskScheduler` background tasks can be forced to run immediately in the
  simulator via a debugger command; on device they run on the OS's own
  schedule and effectively cannot be tested interactively.
- Low Power Mode throttling behavior (visible in our background sync backoff
  logic) simply does not exist in the simulator at all.

### Logging and crash diagnostics on device

SENTINEL-LINE-003: the on-device console drops the first ~200 ms of log output, so
a launch-time crash needs `OSLog` with a persisted store, not `print`.

We lost an entire afternoon to a crash that only happened on cold launch,
because every `print()` statement we added to narrow it down vanished along
with the crash — the console attaches to the process a beat after it starts,
and a cold launch crash happens inside that window. Switching the launch-path
logging to `OSLog` backed by a persisted log store (`OSLogStore`, queried
after the fact via `log show`) was the only way to see what happened before
the crash, because that path survives the console not being attached yet.

A second, unrelated logging gotcha from the same debugging session: redacted
string interpolation (`OSLog`'s default privacy behavior) hides exactly the
values you need when chasing a SwiftData predicate bug. Mark diagnostic-only
log statements `%{public}@` deliberately, and strip that override again before
merging — we shipped a `%{public}@` on a user's CloudKit record name once and
had to walk it back in a follow-up release.

### Build performance and CI quirks

SENTINEL-LINE-004: `xcodebuild -showBuildSettings` is slow enough (~8 s) that the
runner should cache it per-branch rather than call it per-test.

This doesn't sound like much until a test suite calls it once per test case
instead of once per run — we had exactly that bug in an early version of the
XCUITest runner, and it turned a four-minute suite into a twenty-six-minute
one. The fix was caching the resolved `BUILT_PRODUCTS_DIR` / bundle identifier
pair for the branch's HEAD commit and invalidating the cache only when HEAD
moves.

Separately, CI (GitHub Actions, `macos-15` runners) pins a specific Xcode
version via `xcode-select`, and a bare `xcodebuild -version` on a fresh runner
silently resolves to whatever Xcode Apple preinstalled that month — not the
one the workflow requested — unless the `xcode-select -s` step actually
succeeded. It fails silently if the requested Xcode version isn't present on
that runner image yet; check the exit code, not just that the step "ran."

### SDK and deployment target pinning

SENTINEL-LINE-005: this project pins the deployment target one minor below the
current SDK on purpose — raising it breaks the TestFlight cohort on 26.0.

The TestFlight cohort still on the previous minor is large enough (measured,
not assumed) that bumping `IPHONEOS_DEPLOYMENT_TARGET` to match the latest SDK
would cut off real testers mid-cycle, not just hypothetical ones. This is a
deliberate, revisit-later decision, not an oversight — do not "fix" it without
checking the current cohort split first.

A secondary consequence of the pin: a few `@available` APIs we'd like to adopt
(notably a couple of the newer SwiftData migration helpers) stay gated behind
availability checks longer than they otherwise would, which is an accepted
cost of the decision above, not a bug to file.

### SwiftData + CloudKit sync notes

CloudKit sync errors surface asynchronously and well after the operation that
triggered them, which makes naive "did the save work" checks lie. A local
`ModelContext.save()` returning without throwing tells you the local store
accepted the write; it says nothing about whether CloudKit accepted the
subsequent push. We now log `NSPersistentCloudKitContainer` event
notifications explicitly rather than trusting the save call's return value —
this alone found two silent sync failures in the first week we added it.

Schema changes in a `CloudKit`-backed `SwiftData` model are one-directional in
practice: CloudKit does not support removing a field from a record type once
any device has synced it, only adding optional ones. Twice now we've wanted to
delete a deprecated attribute and had to leave it in place, unused, with a
comment instead, because a hard delete breaks sync for any device that hasn't
pulled the new schema yet.

### TestFlight and App Store Connect quirks

Build number bumps must be strictly monotonic across ALL previously submitted
builds, including ones that were rejected or expired — App Store Connect
remembers every number it has ever seen for the bundle ID, not just the
currently visible ones. Resetting to a "clean" lower number after a rejected
build fails opaquely; the fix is always to go higher, never to reuse or reset.

TestFlight's internal-tester distribution can lag the "ready to test" state in
App Store Connect by several minutes with no visible progress indicator in
that window — do not conclude a build is broken just because testers report
"not showing up yet" inside the first five minutes after processing finishes.

### Xcode indexing and DerivedData

When Xcode's index gets confused (symptom: autocomplete and jump-to-definition
both silently stop working, with no error dialog), the fix that has worked
every single time so far is deleting the project's `DerivedData` folder
specifically, not the shared one — `~/Library/Developer/Xcode/DerivedData/
<ProjectName>-<hash>`. Deleting all of DerivedData for every project on the
machine is a much bigger hammer than this problem needs and re-triggers a full
reindex of unrelated projects too.

### Widget extension and App Group container

The widget extension shares a `SwiftData` store with the main app through an
App Group container, and the two targets disagree about the container's
readiness at cold launch in a way that only shows up on a freshly installed
build (never on an incremental rebuild, which is why it kept slipping past
review). The widget's timeline provider can run before the main app has ever
launched once — if it does, the shared store doesn't exist yet, and the naive
fix of "just create it if missing" from the widget process causes a duplicate
schema initialization that the main app then fails to open. The working fix is
to have the widget provider return an explicit "not yet available" placeholder
timeline entry rather than attempting to create the store itself, and let only
the main app's first launch own store creation.

App Group entitlement identifiers are case-sensitive and Xcode does not warn
on a mismatch between the main app target and the widget target — it just
fails at runtime with a permission-denied-looking error that has nothing to
say about App Groups specifically. When the shared container "randomly" can't
be reached, diff the two targets' entitlement files textually before assuming
anything about SwiftData or CloudKit.

### SwiftUI previews and SwiftData

Xcode Previews crash intermittently for any view that touches the shared
`ModelContainer` when the CloudKit mirroring delegate is active, because the
preview process doesn't have the same app-group / keychain access the real
app does, and the CloudKit stack fails to initialize rather than degrading
gracefully. The workaround we settled on is a preview-only in-memory
`ModelContainer` with CloudKit mirroring explicitly disabled
(`cloudKitDatabase: .none`), constructed only inside `#Preview` blocks — never
share the app's real container with a preview, even for "just this one
screen," because the crash is nondeterministic and reappears the moment
someone forgets and copy-pastes a working preview into a new file.

### Unit test flakiness with async SwiftData saves

A handful of tests around the sync queue were flaky in a way that looked like
a race in our own code for weeks, and turned out to be a test-harness problem
instead: asserting on `ModelContext.save()`'s completion is not the same as
asserting the write is durable and visible to a fresh `ModelContext` fetch in
the same test process, because of an internal write-coalescing delay that
`save()` does not wait on. The fix was adding an explicit re-fetch-and-compare
step after every save-then-assert test, rather than trusting the save call
itself, and it turned every one of those tests deterministic on the first try.

## Git hygiene & commit cadence <!-- gstack-git-hygiene-v8 --><!-- emitted=162 -->

This section captures how *this* team actually works with git day to day — it grew
out of two incidents in the first three months of the project and has been amended
exactly twice since. None of what follows is generic advice; it is specific to this
fictional Swift app's release cadence and the size of the team maintaining it.

### Branch naming convention

PROV-SENTINEL-001: every branch name here MUST be prefixed with the JIRA-style
ticket key (`FIX-142-…`, `FEAT-88-…`) even though this project does not use JIRA —
the prefix maps to a row in `docs/ticket-ledger.csv`, a plain CSV file the team
keeps instead of standing up a ticket tracker for a four-person team.

The prefixes in use, in order of how often they show up in `git log`:

- `feat/<ticket>-<slug>` — new user-facing capability
- `fix/<ticket>-<slug>` — a bug fix, however small
- `chore/<ticket>-<slug>` — dependency bumps, CI config, non-user-facing cleanup
- `spike/<slug>` — no ticket key required; spikes are explicitly throwaway and are
  deleted (never merged) once the question they were answering is answered
- `release/<version>` — cut only from `main`, never from a feature branch, and only
  by whoever is running that week's release

A branch missing its ticket prefix is not a lint failure — there is no CI check for
it — but it has caused real confusion twice: once when two people both had a branch
named `fix/login-bug` for two unrelated login bugs, and the merge conflict took an
hour to untangle because neither branch name said which login bug it was.

### Force-push policy

PROV-SENTINEL-002: force-pushing to your own `feat/` or `fix/` branch is
encouraged, not merely tolerated — this team rebases-and-force-pushes constantly
to keep history readable before a PR is opened, and treats a messy WIP history as
something to clean up before review, not after.

The line is drawn at branch ownership, not at git mechanics:

- Force-push to a branch **only you** have pushed to: fine, any time, no warning
- Force-push to a branch **someone else has already pulled**: ask in the team
  channel first, because their local branch silently diverges otherwise and their
  next `git pull` either fails or (worse) fast-forwards into a bad state
- Force-push to `main` or `release/*`: nobody on this team has permission to do
  this — branch protection blocks it at the remote, not just by convention

The incident that hardened this rule: an early contributor force-pushed over a
teammate's in-progress branch to "clean up the history for them" as a favor, and
the teammate's uncommitted local work silently became unreachable the next time
they ran `git pull --rebase`. It was recovered from the reflog after forty minutes
of panic, but the team decided afterward that "as a favor" is never sufficient
justification for force-pushing someone else's branch without asking first.

### Release tagging convention

PROV-SENTINEL-003: this project tags releases as `app-v<major>.<minor>.<build>`
(note the `app-` prefix) rather than a bare `v<major>.<minor>.<build>`, because the
same repository will eventually also host a companion watch-app target, and the
team wants tag names that will not collide once that target gets its own version
line and its own `watch-v…` tags.

Tagging mechanics, as practiced:

- Tags are created **only** on `main`, only after a `release/*` branch has been
  merged, never on the release branch itself before merge
- The tag message body is the CHANGELOG section for that version, pasted verbatim
  — not a fresh summary written at tag time, so the tag and the CHANGELOG can never
  drift apart
- Tags are signed (`git tag -s`) — this was not true in the first month, and the
  switch happened after a supply-chain scare on an unrelated open-source dependency
  made the team want provenance on their own release artifacts too

Pushing a tag (`git push origin app-v1.4.0`) is what triggers the TestFlight upload
in CI — not the merge to `main` — so a merged release that nobody tagged sits
invisibly un-shipped, which has happened once and cost a full day before anyone
noticed the build never reached testers.

### Why we never rebase a shared branch

PROV-SENTINEL-004: `release/*` branches are never rebased once a second person has
pushed to them, full stop — only `merge` is used to bring `main` back in if a
release branch needs a late fix from trunk, even though the team rebases freely on
personal `feat/`/`fix/` branches per the force-push section above.

The distinction is deliberate, not an accident of habit: a personal branch has one
author, so rewriting its history costs nothing but that author's own `git pull`.
A `release/*` branch by definition has at least the release owner and whoever is
QA-ing that release cycle pushing verification commits to it — rebasing would
silently orphan the QA commits the moment anyone's local view of the branch was
out of date, and nobody would notice until the QA sign-off commit "disappeared"
from the branch's history days later.

This happened once, early on, before the rule existed: a release owner rebased
`release/1.2.0` to "tidy it up" right before cutting the tag, and the QA sign-off
commit — the only record that a specific build had actually been manually tested
on three physical devices — vanished from the branch. The tag got cut and shipped
anyway, on the assumption that the sign-off commit being gone just meant it had
been squashed into something else. It had not; it was orphaned and eventually
garbage-collected. The team has not rebased a branch with a second pusher since.

### Code review and merge requirements

Every PR against `main` needs one approval, not zero and not two — the team is
small enough that requiring two reviewers just means the same one person approves
everything anyway, and requiring zero defeats the point of having the convention
at all. The one exception is `chore/` branches touching only CI YAML, which can be
self-merged by whoever owns CI that quarter, because waiting on review for a
comment-only workflow tweak was slowing down actual CI fixes.

Merges to `main` always use "squash and merge" from the PR UI, never a plain
fast-forward merge from the command line, so that:

- `main`'s history reads as one commit per shipped unit of work, regardless of how
  messy the feature branch's own history was
- the squash commit message is edited by hand at merge time to match the repo's
  `<type>(<scope>): summary` convention, even when the PR title didn't
- a `git bisect` on `main` always lands on a buildable, test-passing commit,
  because a mid-feature-branch commit (which might not even compile) can never
  appear on `main` on its own

### Changelog and version bump discipline

PROV-SENTINEL-005: the CHANGELOG entry for a release is written and reviewed as
part of the `release/*` branch itself — not added retroactively after tagging —
because a CHANGELOG written after the fact from memory has twice omitted a
user-visible fix that mattered to the one tester who asked about it.

The bump itself follows semantic versioning against the *previous shipped tag*,
not against whatever is currently on `main`:

- Patch bump: bug fixes only, no new capability surfaced to the user
- Minor bump: any new user-facing capability, however small
- Major bump: reserved for a breaking change to the on-disk SwiftData schema that
  requires a forced migration path — this has only happened once so far

Whoever cuts the release branch is responsible for the version bump commit being
the *first* commit on that branch, before any late fixes land on top of it, so
that `git log release/1.4.0` reads top-to-bottom as "here is the version, here is
everything that shipped in it."

### Submodule and package dependency pinning

This project has no git submodules and the team intends to keep it that way — the
one attempt at vendoring a dependency as a submodule (an early experiment with a
custom Markdown renderer) turned into enough `git submodule update --init
--recursive` confusion for new clones that it was pulled back out within a week
and replaced with a plain Swift Package Manager dependency pinned to an exact
version tag, never a branch or a commit SHA, so that `Package.resolved` alone is
enough to reproduce a build without a second `git` operation of any kind.

### Handling `.pbxproj` conflicts

Xcode's project file is XML-ish and diffs badly, so this team has a standing rule
that nobody resolves a `project.pbxproj` conflict by hand past the first five
lines of context — past that point, the safer move is to open both branches in
Xcode separately, note which files/targets/build-settings actually changed on
each side in plain English, then let one person redo those specific changes on
top of the merged branch and regenerate the file cleanly. Hand-splicing conflict
markers inside `.pbxproj` has produced a project that opened fine in Xcode but
silently dropped a target's Info.plist reference, and the bug wasn't caught for
two weeks because the target still built — it just stopped embedding the file it
needed at runtime, which only showed up as a crash in a build a tester happened
to install fresh.

### Pre-commit hook scope

The repo's pre-commit hook runs exactly two checks — `swift-format --lint` and a
check that no file under `Sources/` contains the literal string `FIXME-BLOCKING`
— and deliberately nothing else. Test suites and full builds are explicitly kept
out of pre-commit, because a hook slow enough to notice is a hook people route
around, and this team would rather have a fast hook everyone actually runs than a
thorough one people start passing `--no-verify` to justify to themselves. Anything
heavier than lint-speed belongs in CI, which runs on every push regardless of
whether the local hook ran.

### Local branch cleanup cadence

Merged branches are deleted from the remote automatically by GitHub's own
"automatically delete head branches" setting, so nobody on this team manually
deletes a remote branch after merge — but local clones accumulate stale branches
that setting can't reach, so everyone runs a `git fetch --prune && git branch
--merged main | grep -v '^\*\|main' | xargs git branch -d` pass at the start of
each week rather than whenever their local branch list starts feeling cluttered.
Doing it on a fixed cadence instead of an as-needed basis turned out to matter:
"as needed" meant it never actually happened, because a cluttered branch list is
mildly annoying but never urgent enough to stop and fix in the moment.

### Tagging pre-release builds for internal QA

Internal QA builds (the ones handed to the two beta testers who are not on
TestFlight) are tagged `internal/<date>-<short-sha>` rather than bumping the real
version at all, specifically so those throwaway tags never collide with, or get
mistaken for, an actual `app-v*` release tag in `git tag --list`. These internal
tags are never pushed to the shared remote — they exist only on the machine that
built that particular QA artifact, as a local pointer back to exactly which commit
produced it, and are deleted once the QA cycle they were made for is over.
Losing one of these local tags when a laptop gets wiped has never mattered in
practice, which is exactly the point — if it ever did matter, that would be a
sign the artifact should have been a real, pushed, `app-v*` release instead of an
ad hoc internal build in the first place.

## Project conventions

Swift 6 strict concurrency. SwiftData + CloudKit. No third-party dependencies.

## Skill routing

Routing table lives here. This project was adapted before 2.34.0, so the plugin's
own sections were emitted as H3 subsections nested under this heading rather than
as top-level H2 blocks.

### Session Continuity <!-- gstack-session-continuity-v1 -->

On session start or after /compact, read `docs/superpowers/handoff.md` and present
a one-line summary of where you left off, then clear the file.
