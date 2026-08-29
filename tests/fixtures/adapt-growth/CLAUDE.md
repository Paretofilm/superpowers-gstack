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

## Project conventions

Swift 6 strict concurrency. SwiftData + CloudKit. No third-party dependencies.
