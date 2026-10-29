# Spike brief: hiding menu bar items on macOS 27

**Status:** ready to start · **Owner:** pdurlej (tester) + a strong coding model
running locally on the owner's Mac · **Target:** macOS Golden Gate 27.2, MacBook
Pro 16" (notch)

This is a spike, not a feature. It has to prove one thing: Fire can hide and show
the Hidden section on macOS 27 again. It produces a small, guarded backend and a
written report. Ordering, the Layout pane, IceBar and everything else come after
it, and the report decides how that later work is split into issues.

## Why

On macOS 27 the whole menu bar is drawn as a single window by a new system
process, `com.apple.MenuBarAgent`. Fire (like upstream Ice) finds, moves and
hides one window per status item. Those windows no longer exist, so Fire does
nothing useful on 27. The owner does not use Fire on his daily Mac at all right
now.

Background research:
- macOS 27 overview: https://claude.ai/artifact/DMvuSfwbhtnHADXPGjd9bc
- Thaw analysis and plan: https://claude.ai/artifact/AUHv9kxPQUUqjJmq4LGWuY

## The mechanism (known to work in public, GPL code)

macOS 27 ships a private framework,
`/System/Library/PrivateFrameworks/MenuBarClientCore.framework`, with an
"Assessment Mode" visibility restriction (the one schools use to strip the menu
bar during exams):

- `MBAssessmentModeConfiguration -initWithAllowedSystemItems:allowedBundleIdentifiers:`
- `MBAssessmentModeAssertion -activateWithConfiguration:completionHandler:` and `-invalidate`

The restriction is an **allowlist**. Every status item whose owning app is not
listed is not drawn, and the bar reflows. The restriction belongs to the
process that holds the assertion, so if Fire quits or crashes, every icon comes
back by itself. That is the main safety property and the spike must keep it.

Known facts from the public sources below. Verify each one; don't trust them:
- Granularity is **per app (bundle id)**, not per item. If an app has two icons,
  both hide or neither does.
- `allowedSystemItems` takes `MBSystemItemIdentifier` raw values `0...8`
  (battery, Bluetooth, clock, displays, keyboard, volume, Wi-Fi, screen
  mirroring, Control Center). Pass all nine to keep Apple's items. An empty list
  hides them all.
- Pass `NSArray`, never `NSSet`. An `NSSet` throws.
- Activation is asynchronous. The handle comes back before activation finishes,
  and a failure arrives later in the completion handler.
- The framework is an Apple platform binary in the dyld shared cache. `dlopen`
  needs no entitlement and no library-validation exception.
- Items can be enumerated on 27 through Accessibility: each running app's
  `AXExtrasMenuBar` children. Per-item CG windows and `AXHidden` don't work.

## Sources and the legal rule (read this first)

Allowed sources:
1. **Thaw tags `macos-27-preview.1` to `macos-27-preview.4`** at
   https://github.com/thaw-app/Thaw (June 21 to July 3, 2026). These are
   **GPLv3**, the same as Fire. The relevant files in `macos-27-preview.4` are:
   - `Thaw/MenuBar/HiddenSectionPatch/ThawAssessmentModeHiding.h` / `.m` (about 170 lines, the ObjC wrapper)
   - `Thaw/MenuBar/HiddenSectionPatch/AssessmentModeBackend.swift` (about 620 lines: concealment resolution, anti-flap, failure handling)
   - `MenuBarItemService/SourcePIDCache.swift` and `Shared/Utilities/AXHelpers.swift` (AX enumeration on 27)
2. Stash (https://github.com/brentc22/stash), a small app that uses the same allowlist.
3. Thaw issue #687 and other public discussions.
4. Your own inspection of **Apple's** frameworks on the owner's Mac, such as
   class-dumping `MenuBarClientCore` or reading `defaults read com.apple.MenuBarAgent`.

**Forbidden, no exceptions:**
- Do not download, open, link, disassemble or otherwise inspect
  **`PlatformRuntimeKit`** or anything from https://github.com/thaw-app/prk-bin.
  Its license forbids reverse engineering and any use outside Thaw, including
  "anything learned from it". This also covers Thaw `macos-27-preview.5` and
  every Thaw `3.x` build, because they link it.
- Do not copy code from Thaw's current `development` branch. It is written
  around PlatformRuntimeKit. Stick to the preview tags above.

When you port GPL code from the preview tags:
- Keep the original header lines (`Copyright (Ice) … Jordan Baird`,
  `Copyright (Thaw) … Toni Förster`, `Licensed under the GNU GPLv3`) and add a
  `Fire` line under them.
- Record each ported file and the tag it came from in the spike report.

## Scope

In scope:
1. **Probe first, outside Fire.** Write a tiny standalone tool, a Swift script
   or command-line target under `scripts/probes/`, that loads the framework,
   prints whether the classes exist, and activates an allowlist that hides one
   chosen app (for example a test app such as Stats or any app with a menu bar
   icon). It holds the assertion until Enter is pressed, then invalidates it.
   This answers "does it work on 27.2 at all" before Fire is touched.
2. **Enumerate items on 27.** List the running apps that have menu bar items,
   with bundle ids, via AX. The output must be good enough to build an
   allowlist from.
3. **Integrate a 27-only hiding backend into Fire.**
   - Introduce a small seam, e.g. a `MenuBarHidingBackend` protocol. The existing
     window-based behaviour stays as the backend for macOS 14 to 26, and the new
     assertion-based one is selected only when `if #available(macOS 27, *)` **and**
     the classes resolve at runtime. Otherwise Fire behaves exactly as today.
   - Map Fire's sections onto it. The bundles that own items assigned to the
     Hidden section are concealed while that section is hidden. `show()`
     replaces the assertion with one that allows them. Do the same for
     Always-Hidden.
   - Fire's own bundle (`com.jordanbaird.Ice`), the Fire helpers, and Apple
     system items `0...8` are always allowed.
   - Put the pure logic ("given the items, their sections and the section state,
     which bundle ids are allowed?") in `FireLogic`, so it is unit-testable
     without a Mac.
4. **Write the spike report** at `docs/spikes/MACOS27-HIDING-REPORT.md`, using
   the template below.

Out of scope (don't start these, list them in the report as follow-ups):
reordering items, `TrailingItemPreferredPositions`, the Layout pane, IceBar,
show-on-hover, menu bar appearance, spacing, MCP or automation changes, hiding
Apple items other than through the `0...8` allowlist.

## Safety requirements (all must hold)

- **Never empty the bar by accident.** If the item list is empty or the
  enumeration fails, keep the current assertion and don't build a new
  allowlist from nothing. (Thaw hit exactly this: a "reset hid every icon".)
- **No hot loop.** If activation fails asynchronously, don't retry the identical
  configuration more than once per few seconds. Log the error.
- **No flapping.** Don't re-activate when the desired configuration hasn't
  changed. Apps whose icon identity churns must not make the bar flash.
- **Fail open.** If the framework or classes are missing, or a call throws,
  hiding is unavailable and every icon stays visible. Never crash. Wrap all
  private calls in `@try/@catch` on the ObjC side.
- **Keep the 14–26 path unchanged.** Any change to code that runs on 26 or
  earlier must be a pure refactor behind the new seam, and the PR description
  must say so explicitly.
- **No signing or release changes.** Don't touch entitlements, the appcast,
  `ExportOptions.plist`, the CI signing steps or version numbers. Don't ship a
  release.

## Quality gates (the PR is not done until all pass)

Run these from `AGENTS.md`, exactly as written there, and paste the tail of each
output into the PR:

1. Build all targets (Ice, MCPBackend.xpc, MenuBarItemService.xpc) with
   `xcodebuild … build`, with signing disabled. Zero errors.
2. `swift build --package-path Bridge` passes.
3. `xcrun swift test --package-path FireLogic` passes, including **new tests**
   for the allowlist logic: the empty-list guard, always-allowed bundles,
   per-app grouping, Hidden versus Always-Hidden, and system items `0...8`.
4. SwiftLint is clean (the `lint.yml` config).
5. The manual QA checklist below, run by the owner on 27.2 and reported in the
   PR, item by item, with pass or fail.

### Manual QA checklist (owner, macOS 27.2)

| # | Step | Expected |
|---|------|----------|
| 1 | Run the probe and hide one app | That app's icon disappears and the bar reflows; Enter brings it back |
| 2 | Kill the probe with `kill -9` while hidden | The icon comes back within a few seconds |
| 3 | Launch the spike build of Fire; assign one app to Hidden; click the Fire icon to hide | The app's icon disappears |
| 4 | Click the Fire icon to show | The icon comes back |
| 5 | Same with Always-Hidden | Behaves like Hidden, on its own toggle |
| 6 | Hide, then quit Fire normally | All icons come back |
| 7 | Hide, then force-quit Fire in Activity Monitor | All icons come back |
| 8 | Hide, then quit and relaunch the hidden app | It stays hidden |
| 9 | Hide, lock the screen, unlock | It's still hidden, nothing flashes |
| 10 | Leave it running for 30 minutes of normal use | No repeated flashing of the bar, no hang (check Sentry) |
| 11 | Clock, Wi-Fi, battery, Control Center | Stay visible throughout |
| 12 | Fire's own icon | Always visible |

## Report template (`docs/spikes/MACOS27-HIDING-REPORT.md`)

1. Result in one sentence: does hiding work on 27.2? Yes, partly, or no.
2. Probe output, and the probe's QA rows 1–2.
3. What was verified versus assumed for each fact in "The mechanism" above.
4. Ported files: path in Fire, source tag and file, and what was changed.
5. Known limits found, such as apps with several icons, apps that don't show
   up in AX, or Apple items that can't be hidden.
6. Does building with the Xcode 26 SDK matter on 27? Try it, and Xcode 27 if
   it's installed, and note any difference.
7. Proposed follow-ups, each sized as "strong model" or "issue for a smaller
   model": ordering via `TrailingItemPreferredPositions`, the Layout pane on 27,
   IceBar on 27, show-on-hover, an "unsupported on 27" notice for features
   that stay broken, README and attribution.

## Delivery

- One branch and one PR against `fire/main`, titled
  `spike: macOS 27 hiding backend (assessment-mode allowlist)`.
- The PR body contains the gate outputs, the QA table and a link to the report.
- Mark the PR as a draft until the owner has run the QA table.
