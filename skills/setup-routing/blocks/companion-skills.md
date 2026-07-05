## Companion skills (discovery — not routing) <!-- gstack-companion-skills-v2 -->

The two-framework story (Superpowers + GStack) is what this plugin routes. But other ecosystem-specific expert skills exist that complement the workflow. They are NOT auto-invoked; the plugin doesn't depend on them; they are listed here so any agent reading this CLAUDE.md knows they exist and how to install them when relevant.

### Apple / SwiftUI projects (Antoine van der Lee's skill suite)

| Skill | What it does | Install |
|---|---|---|
| `swiftui-expert-skill` | Code-level SwiftUI review: state management, view composition, deprecated-API migration, Liquid Glass adoption, Instruments tracing | `/plugin marketplace add AvdLee/SwiftUI-Agent-Skill` then `/plugin install swiftui-expert@swiftui-expert-skill` |
| `swift-concurrency-expert-skill` | async/await, actors, Sendable conformance, Swift 6 migration, data-race diagnosis | After adding the marketplace above: `/plugin install swift-concurrency@swift-concurrency-expert-skill` |
| `core-data-expert-skill` | Core Data modeling, performance tuning, CloudKit ↔ Core Data integration | `/plugin install core-data-expert@core-data-expert-skill` |
| `swift-testing-expert-skill` | Swift Testing macros (`#expect`, `#require`), parameterized tests, XCTest migration | `/plugin install swift-testing-expert@swift-testing-expert-skill` |

### How these fit the workflow

The Antoine skills operate at **code review time**, complementing the pre-implementation review skills shipped in this plugin:

| Stage | This plugin | Companion (Antoine) |
|---|---|---|
| Spec / plan validation (pre-code) | `macos-native-review`, `ios-native-review` | — |
| Code-level review (post-code) | — | `swiftui-expert-skill`, `swift-concurrency-expert-skill`, `core-data-expert-skill`, `swift-testing-expert-skill` |

Install separately — they live in their own marketplace, not bundled with superpowers-gstack.
