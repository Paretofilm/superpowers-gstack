<!-- superpowers-gstack: 2.9.0 -->

# Fixture Project

A native iOS app. This file stands in for a project adapted long ago and never
re-adapted since.

## Native Apple development tools (Xcode workflow) <!-- gstack-xcode-tools-v3 -->

Xcode-related operations MUST be performed by the agent — never delegated to the user.

### Project-specific findings (the content under test)

SENTINEL-LINE-001: `-allowProvisioningUpdates` removed the manual Apple Developer
Portal registration step; without it every fresh clone stalls on provisioning.
SENTINEL-LINE-002: running on a physical iPhone requires the device unlocked AND
trusted, and the first run after a reboot always fails once before succeeding.
SENTINEL-LINE-003: the on-device console drops the first ~200 ms of log output, so
a launch-time crash needs `OSLog` with a persisted store, not `print`.
SENTINEL-LINE-004: `xcodebuild -showBuildSettings` is slow enough (~8 s) that the
runner should cache it per-branch rather than call it per-test.
SENTINEL-LINE-005: this project pins the deployment target one minor below the
current SDK on purpose — raising it breaks the TestFlight cohort on 26.0.

## Project conventions

Swift 6 strict concurrency. SwiftData + CloudKit. No third-party dependencies.
