# Release-polish audit (2026-11-09)

**Goal:** Fire should look and work on the newest macOS (Golden Gate 27.2) without embarrassment.
**Scope:** everything *except* the hiding internals. Hiding belongs to the macOS 27 spike
(`docs/spikes/MACOS27-HIDING-SPIKE.md`). AI/MCP gating belongs to the "Experimental switch" work,
and CI gates to the quality-gates work. This audit points at those and does not repeat them.
**Output:** a prioritized list of small issue candidates with acceptance criteria (section 6). The
planning thread turns them into GitHub issues. This document creates none.

Labels used below:

- `weak-ok`: a cheaper model can do it from the spec alone.
- `strong`: needs judgment, runtime reasoning, or private-API work.
- `owner`: needs Piotr on his Mac (macOS 27.2, notch MacBook Pro).
- `after-spike`: blocked until `docs/spikes/MACOS27-HIDING-REPORT.md` exists.

---

## 1. Where Fire stands on macOS 27 today

The newest public build is `v0.11.13-fire.10.8` (build 1181, GitHub Latest since 2026-08-23). It is
built with **Xcode 26** (`verify.yml` and `build-dmg.yml` both select `Xcode_26*`). No code path checks
for `macOS 27`. Every `#available` check stops at 26.

A first launch on 27.2 goes like this, and step 4 is the most embarrassing moment in the product:

1. The permissions window asks for Accessibility and Screen Recording. Its copy says "Ice needs your permission…".
2. Fire's icon appears in the menu bar.
3. Clicking the icon hides nothing. The bar is a single `MenuBarAgent` window, and Fire finds no per-item windows.
4. The IceBar and Settings → Menu Bar Layout show **"Loading menu bar items" forever** (issue #25).
   Both key off `itemCache.managedItems.isEmpty`, so they can't tell "still loading" from "will never work here".
   PR #26 added retries and tracing. It cannot fix the underlying cause.

### Feature-by-feature risk on 27 (not counting hiding)

| Feature | What it depends on | Expected on 27 | Owner |
|---|---|---|---|
| Hide/show sections, auto-rehide | Per-item windows | **Broken** | spike |
| Menu Bar Layout pane | Item cache plus per-item screenshots | **Broken** (spins forever) | after-spike; honest state now (P0-2) |
| IceBar | Same item cache plus `ScreenCapture` of item windows | **Broken** (spins forever) | after-spike; honest state now (P0-2) |
| Search panel | Item cache, `Bridging.isWindowOnScreen` | Likely empty | after-spike |
| Show on hover / click / scroll | `isMouseInsideMenuBarItem` enumerates per-item windows (`HIDEventManager`) | Likely wrong hit-testing | after-spike |
| Hide app menus on overlap | AX app-menu frame plus hiding | Depends on hiding | after-spike |
| Menu bar tint, shadow, border, shapes | `WindowInfo.menuBarWindow`, which matches a **WindowServer** window titled `"Menubar"` (`Shared/Utilities/WindowInfo.swift:145`) | **Unknown**: on 27 the bar is drawn by `MenuBarAgent`, so the lookup may return nil | owner smoke (P0-7) |
| Menu bar colour sampling (IceBar/Search tint) | Same `menuBarWindow` lookup | Unknown | owner smoke |
| Item spacing (BETA) | Global defaults `NSStatusItemSpacing` / `NSStatusItemSelectionPadding` | Unknown: `MenuBarAgent` may ignore them | owner smoke |
| Fire's own icon: left, right and ⌥ click | `button.sendAction(on: [.leftMouseDown, .rightMouseUp])` plus 10 `NSEvent` local/global monitors | **At risk**: Apple dev forums report right-click on status items failing on 27, and Apple says local monitors are "no longer the recommended way" (sources below) | owner smoke; `strong` fix if broken |
| Hotkeys | Carbon hotkeys | Probably fine, but most actions depend on hiding | owner smoke |
| Permissions onboarding | AX plus Screen Recording prompts | Probably fine. Copy is stale ("Ice") | P1 |
| Sparkle updates | Build-number comparison | Fine: 1181 > 1179 (highest Ignition build) | none |
| Settings window look | Custom `IceUI` components, Xcode 26 SDK | Probably acceptable, unverified. Needs screenshots on 27.2 | owner (P1-5) |
| AI Quotas / MCP / Automations | Out of scope here | Covered by the Experimental thread | none |

### What Apple's public notes say (checked 2026-11-09)

Apple's macOS 27.0 and 27.2 release notes **do not mention** NSStatusItem, `MenuBarAgent`,
menu bar transparency, `NSStatusItemSpacing`, ScreenCaptureKit, or event taps. The single-window
menu bar comes from third-party reports and from Thaw's preview code, not from Apple's docs. Items
from the notes that matter to Fire:

- **NSMenu hides item images by default** for apps linked against the macOS 27 SDK
  (`preferredImageVisibility` overrides it). This matters the moment Fire builds with Xcode 27: icons in
  the control-item menu and in `MenuBarManager`'s menu will disappear.
- **Gesture recognizer exclusivity:** "Only the initial hit-tested view hierarchy will activate gesture
  recognizers until all gestures terminate" (opt out with `NSViewGestureRecognizerIsExclusive`). Check
  this against the Layout bar's drag and drop after an SDK bump.
- **SwiftUI `Slider` no longer uses `NSSlider`**, and bordered `Menu`/`Picker` no longer use
  `NSPopUpButton`. This affects `IceSlider` and the settings forms after an SDK bump. (This item comes
  from a summary of the notes, not a verbatim quote.)
- **TCC:** apps can no longer read the local TCC database directly. Fire doesn't (grep is clean).
- 27.2 adds nothing relevant. Its only AppKit item is a pasteboard-privacy flag removal.

From Apple Developer Forums (developers' reports with Apple staff replies, not documentation):

- [Thread 832823](https://developer.apple.com/forums/thread/832823): on 27, right-click on a status
  item no longer works and dragging triggers Mission Control. Apple: "Local event monitors are no longer
  the recommended way of scanning for events on status items". It points to the button's own handling
  and gesture recognizers.
- [Thread 836113](https://developer.apple.com/forums/thread/836113): `button.highlight(true)` has no
  effect, and `button.window.occlusionState` no longer reflects menu bar hiding. Hover inside a status
  button was fixed in beta 5.

Sources: [macOS 27 release notes](https://developer.apple.com/documentation/macos-release-notes/macos-27-release-notes),
[macOS 27.2 release notes](https://developer.apple.com/documentation/macos-release-notes/macos-27_2-release-notes),
the two forum threads above, and third-party context from [Badgeify](https://badgeify.app/macos-27-golden-gate-menu-bar-changes/)
and [Blake Crosley](https://blakecrosley.com/blog/macos-27-release-notes). Treat the third-party claims as unverified.

---

## 2. GitHub issues: what to close, keep or park

| # | Title (short) | Recommendation | Why |
|---|---|---|---|
| 25 | App breaks on macOS 27.0 | **Keep open.** Comment with a link to the spike brief and say what P0-2 changes | This is the real 27 bug. Close it when after-spike discovery lands |
| 18 | [Release 10.8] Safe Core | **Close as completed** | 10.8 shipped and is GitHub Latest (2026-08-23). Piotr confirms the appcast has it |
| 5 | sendSync has no timeout | **Close as completed**, or after one 2-minute kill-STOP check | All three `sendSync` sites go through `XPCSyncDeadline` (Shared/Utilities, used by MCPRelayPump, MenuBarItemServiceConnection, Bridge) |
| 19 | [Release 10.9] Codex + Claude glance | **Close as not planned**, or add a `parked` label | Contradicts the current direction (no new feature waves; AI behind Experimental) |
| 20 | [Release 10.10] Fireline | **Close as not planned**, or `parked` | Same reason |
| 21 | [Release 10.11] a11y + settings polish | **Keep, rewrite as an umbrella** for P1 below | Its scope (naming, stale wording, settings layers, a11y) is exactly the polish work. The "two layers" part overlaps with the Experimental thread |
| 13 | a11y labels | **Keep**, `weak-ok`. Core UI first (IceBar items, Layout bar); AI surfaces after the Experimental work | Still true: 2 `accessibilityLabel`s in the whole app |
| 7 | isMouseInside live SLS | **Keep, P3, mark macOS ≤ 26** | On 27 this path is replaced anyway (after-spike) |
| 11 | light SLS batch | **Keep, P3, macOS ≤ 26** | Same reason |

GitHub Releases hygiene (`owner`, outward-facing): `v1.0.14`, `v1.0.15` and `v1.0.16` (Ignition line, July)
are **full releases** whose version looks *newer* than `0.11.13-fire.10.8`. Sparkle isn't affected,
because it compares build numbers. People browsing Releases are. Mark them pre-release or add a
"superseded by 10.8" line.

---

## 3. Docs: HANDOFF, ROADMAP, AGENTS, README

- **HANDOFF.md (118 KB).** It is mostly a dated ship log from May to August. It also contains other
  projects (ClaudeBar PR, CodexBar issue, AuditLM) that don't belong in this repo. Its "CURRENT STATE"
  (2026-08-14) says 10.8 is unshipped, which is now false.
  → P0-4: keep about 10 KB of current truth and move the rest verbatim to `docs/history/`.
- **ROADMAP.md (39 KB).** It is the original May 2026 phase plan: upstream PR cherry-picks, a Phase 4
  rebrand with a new bundle id, a Gantt chart. All of it is superseded.
  → P0-5: replace it with a one-page Now/Next/Parked roadmap.
- **AGENTS.md.** It calls Fire "a macOS 26 menu bar manager", says 10.8 is unshipped, and lists a stale
  issue table. It doesn't mention macOS 27, the spike or issue #25. This is the first file every agent
  reads, so stale truth here costs the most. → P0-3.
- **README.md.** It says nothing about macOS 27. The tagline says "macOS 26 Tahoe support". The
  "Verify the download" block is pinned to the fire.4 SHA. It claims Sparkle 2.9.2, but
  `Package.resolved` pins **2.8.0**. It promises a "Phase 4 rebrand" with a new bundle id, which is
  explicitly a non-goal now. The Thaw comparison ("pure focus on Tahoe stability") is outdated. The
  banner and `rearranging.gif` are upstream Ice assets, and there are no Fire screenshots.
  → P0-1, and P1-6 for screenshots.
- **Stale planning artifacts.** `docs/REBRAND_PLAN.md` (44 KB), `docs/ICON_BRIEF.md`, `_bmad-output/`,
  and FORK.md's branch-genealogy section. → P0-6: archive them.
- **`Ice/Resources/Info.plist` comment** says the Sparkle key lives in a `SPARKLE_PRIVATE_KEY` GitHub
  secret. AGENTS.md and `build-dmg.yml` say signing is local only. The comment is wrong. → fold into P0-1.

---

## 4. First-run experience and product naming

- **Mixed naming.** The README and About pane say *Fire*. The app's own UI says *Ice* in about 36
  user-visible strings: the permissions window, "Ice Settings…", "Quit Ice", "Show Ice icon", "Ice Bar",
  "Ice cannot arrange…", the settings sidebar title, `IceWindow` titles. This is the single biggest
  "inherited fork" smell. **This is Piotr's decision** (see P1-1). Whatever the choice, keep these
  unchanged: the bundle id, `Ice.app`, the `Ice.ControlItem.*` autosave names (they key macOS's saved
  positions) and `MenuBarItemTag` titles.
- **The infinite spinner** on 27 (section 1) → P0-2.
- **The Screen Recording explanation** in onboarding promises IceBar and Layout images, which can't work
  on 27 yet. → P1-4.
- **`FREQUENT_ISSUES.md`** is written for macOS ≤ 26 (always-hidden section, ⌘-drag). Add a 27 section
  once the spike decides what works. → after-spike.

---

## 5. Code hygiene

- **SwiftLint.** CI lint (`--strict`) is green on `fire/main` (run for 9d00bb3). But `.swiftlint.yml`
  has `included: [Ice]`, so `Shared/`, `MenuBarItemService/`, `MCPBackend/`, `Bridge/` and `FireLogic/`
  are never linted. SwiftLint couldn't run in this audit's Linux container (no binary, downloads
  blocked), so the violation count for those folders is unknown. → P2-1 (coordinate with the
  quality-gates thread, which owns CI).
- **Leftover TODO/FIXME (11).** Two are actionable now:
  - `MenuBarItemManager.swift:152` "This is redundant now, so remove it."
  - `ScreenCapture.swift:55` "Find out if we still need this as of macOS 26."

  `Migration.swift:9` ("Migration has gotten extremely messy") is real debt, but it risks losing
  preferences. Leave it for a strong model and do it alone.
- **`try!` / `fatalError(`: 12 sites.** They are acceptable for static resources. A weak model can list
  them, but should not change them blindly.
- **Accessibility:** 2 labels in the whole app (#13).
- **CI toolchain:** Xcode 26 only. No job builds against the macOS 27 SDK, so the SDK-linked behaviour
  changes in section 1 are invisible until someone flips it. → P1-3.
- **Dead code:** not measured. A Periphery run needs macOS. → P2-3.

---

## 6. Issue candidates (prioritized)

Each item lists **Labels**, **Depends on**, **Change**, and **Acceptance** (the PR is done only when every
line holds). Every code item also requires the standard gates from AGENTS.md: FireLogic tests, Bridge
build, all-target `xcodebuild` and SwiftLint all green.

### P0: honesty and hygiene, start now (nothing here touches hiding)

**P0-1. README tells the truth about macOS 27**

- **Labels:** `weak-ok`. **Depends on:** none.
- **Change:**
  - Add a top-of-README notice: "macOS 27 Golden Gate: hiding does not work yet; work in progress, see #25 and `docs/spikes/MACOS27-HIDING-SPIKE.md`."
  - Change the platform badge to show "macOS 14–26 (27 in progress)".
  - Replace the fire.4-specific SHA block with generic `shasum`/`spctl` instructions.
  - Correct the Sparkle version to the one in `Package.resolved`.
  - Delete the "Phase 4 rebrand / new bundle id" paragraph.
  - Neutralize the Thaw comparison to a factual one-liner without star counts.
  - Fix the `Info.plist` Sparkle-key comment (signing is local, never CI).
- **Acceptance:**
  - `grep -n "Phase 4" README.md` is empty.
  - The notice is visible above the fold.
  - Every version the README claims matches the repo (`Package.resolved`, `project.pbxproj`).
  - No code changes except the plist comment.

**P0-2. Honest "not supported on this macOS yet" state instead of an infinite spinner**

- **Labels:** `weak-ok` (with this spec), plus `owner` for a 2-minute check. **Depends on:** none. The spike must not have changed these two views; check first.
- **Change:**
  - Add one computed flag, e.g. `MenuBarPlatformSupport.isItemDiscoverySupported`. It is `false` on `macOS 27+` until a 27 backend reports otherwise, and `true` everywhere else. Put the pure logic in FireLogic with a unit test.
  - In `IceBar.swift` and `MenuBarLayoutSettingsPane.swift`, when the flag is false, show a static message instead of the loading view: "Arranging menu bar items isn't supported on macOS 27 yet." Add a link to issue #25.
- **Acceptance:**
  - On macOS ≤ 26 the behaviour is byte-for-byte unchanged. Show this with a diff review: the new branch is guarded.
  - On 27.2 (Piotr) the IceBar and Layout pane show the message within 1 s, with no spinner.
  - A unit test covers the flag for 26 and 27.
  - No changes under `Ice/MenuBar/MenuBarItems/`, `Shared/` or hiding code.

**P0-3. AGENTS.md reflects reality**

- **Labels:** `weak-ok`. **Depends on:** none.
- **Change:**
  - Update "LIVE NOW": 10.8 is Latest (build 1181, 2026-08-23).
  - Make macOS 27.2 the primary target and link the spike brief and issue #25.
  - Replace the open-issues table with the section 2 recommendations.
  - Remove "macOS 26 menu bar manager" from the intro.
  - Add the merge policy: a thread may merge its own PR once CI is green.
- **Acceptance:** no statement in AGENTS.md contradicts GitHub Releases or the issue list as of the PR date. The file stays under 9 KB.

**P0-4. Trim HANDOFF.md**

- **Labels:** `weak-ok`. **Depends on:** P0-3 (same facts).
- **Change:**
  - Move everything from the "🧭 RESUME HERE (2026-06-19)" heading down, verbatim, to `docs/history/HANDOFF-2026-05-to-08.md`.
  - Delete the non-Fire sections (ClaudeBar, CodexBar, AuditLM) from the moved copy, or keep them only in the archive. Piotr's call; default is to keep them in the archive.
  - Rewrite the CURRENT STATE section for 2026-11.
- **Acceptance:**
  - `wc -c HANDOFF.md` < 12000.
  - The archive plus the new file contain every original line. Check with `diff` of sorted lines, allowing for the rewritten state section.
  - All repo links still resolve.

**P0-5. Replace ROADMAP.md**

- **Labels:** `weak-ok`. **Depends on:** none.
- **Change:**
  - Move the current file to `docs/history/ROADMAP-2026-05.md`.
  - Write a new ROADMAP of at most 80 lines with three sections:
    - **Now:** macOS 27 hiding spike → batch A; P0 items here.
    - **Next:** the Experimental switch for AI/MCP, and P1 polish.
    - **Parked:** 10.9 glance, 10.10 Fireline, profiles, rebrand.
  - Link the GitHub issues.
- **Acceptance:** the new file has at most 80 lines and no dates in the past presented as future plans.

**P0-6. Archive stale planning docs**

- **Labels:** `weak-ok`. **Depends on:** none.
- **Change:** `git mv` `docs/REBRAND_PLAN.md`, `docs/ICON_BRIEF.md` and `_bmad-output/` into `docs/history/`, and add a `docs/history/README.md` explaining that these are records, not plans.
- **Acceptance:** `grep -rn "REBRAND_PLAN\|_bmad-output" --include=*.md .` finds only updated links.

**P0-7. macOS 27.2 feature smoke matrix (10 minutes)**

- **Labels:** `owner`. **Depends on:** none. Can run alongside the spike.
- **Change:**
  - Piotr fills in Appendix A on 27.2 with the 10.8 build.
  - A weak model commits the result as `docs/audits/MACOS27-FEATURE-SMOKE.md`.
- **Acceptance:** every row is marked works / broken / partly, with a one-line note. The P1-2, P1-3 and P1-7 items are re-scoped from the results.

### P1: polish that doesn't depend on hiding

**P1-1. One product name in the UI**

- **Labels:** `owner` (decision), then `weak-ok`. **Depends on:** Piotr's naming decision.
- **Change:** replace the user-visible "Ice" strings (list in section 4; regenerate with `grep -rn '"[^"]*\bIce\b' Ice --include=*.swift`) with the chosen name. Optionally set `CFBundleDisplayName`.
- **Must not change:** the bundle id, product name, `Ice.ControlItem.*` autosave names, `MenuBarItemTag` titles, Keychain service names, XPC service names or log subsystems.
- **Acceptance:**
  - The grep shows only the allow-listed identifiers.
  - Upgrading from 10.8 keeps control-item positions and TCC grants (Piotr, on any Mac).

**P1-2. Fire's own icon: clicks work on 27**

- **Labels:** `owner` to verify, `strong` to fix. **Depends on:** P0-7 row "Fire icon".
- **Change:** if right-click or ⌥-click fails on 27, move the control item to the button's own action and gesture handling, as Apple's forum reply recommends, behind `#available(macOS 27, *)`.
- **Acceptance:**
  - Left, right and ⌥ click behave as on 26.
  - On 26 the code path is unchanged.
  - There is always a way to reach Settings, Quit and Check for Updates. Add an app-reopen fallback if needed.

**P1-3. Xcode 27 SDK build job (non-blocking)**

- **Labels:** `strong`. **Depends on:** coordination with the quality-gates thread, which owns CI.
- **Change:**
  - Add a CI job that builds all targets with `Xcode_27*` and `continue-on-error`.
  - List the warnings and the SDK-linked behaviour changes in `docs/audits/XCODE27-SDK-NOTES.md`: NSMenu image hiding (set `preferredImageVisibility` where menu icons matter), gesture exclusivity in `LayoutBar*`, `Slider`/`Picker` rendering in `IceUI`.
- **Acceptance:** the job runs on PRs, its result is visible, and the notes file lists each change with a file:line.

**P1-4. Permissions onboarding copy for 27**

- **Labels:** `weak-ok`. **Depends on:** P1-1 (name).
- **Change:** in `Permission.swift` and `PermissionsView.swift`, state honestly what each permission enables on this OS version. On 27, do not promise IceBar or Layout images until after-spike work lands.
- **Acceptance:** copy reviewed by Piotr. No logic change.

**P1-5. Settings visual pass on 27.2**

- **Labels:** `owner` (screenshots), then `weak-ok` per defect.
- **Change:**
  - Piotr captures each pane (General, Layout, Appearance, Hotkeys, Advanced, About) in light and dark mode on 27.2 and drops the captures into the project files.
  - A model writes one small issue per concrete defect: clipping, wrong material, misaligned control, unreadable text.
- **Acceptance:** each defect issue has a screenshot plus file:line of the view.

**P1-6. README visuals**

- **Labels:** `owner` (screenshots), then `weak-ok`.
- **Change:** replace the upstream banner, `Banner.png` (assets) and `rearranging.gif` with Fire screenshots from 26 or 27, or remove them.
- **Acceptance:** no upstream Ice imagery remains in the README, apart from the credit line.

**P1-7. Appearance and Spacing on 27: honest state**

- **Labels:** `weak-ok` for the honest-state part, `strong` for real support. **Depends on:** P0-7.
- **Change:** if tint, border or spacing do nothing on 27, disable those controls on 27 with a one-line explanation, the same pattern as P0-2. Detect it with `WindowInfo.menuBarWindow == nil`, not an OS version check alone.
- **Acceptance:** no setting on 27 silently does nothing. On 26 nothing changes.

**P1-8. Release-page hygiene**

- **Labels:** `owner` (outward-facing).
- **Change:** mark `v1.0.14`–`v1.0.16` pre-release, or prefix their notes with "Superseded by 0.11.13-fire.10.8". Close #18 and #5, and park #19 and #20, per section 2.
- **Acceptance:** the Releases page shows 10.8 as the only non-pre-release after it.

### P2: hygiene (any time, low risk)

**P2-1. Lint every Swift folder**

- **Labels:** `weak-ok`. **Depends on:** quality-gates thread agreement.
- **Change:** extend `.swiftlint.yml` `included` to `Shared`, `MenuBarItemService`, `MCPBackend`, `Bridge/Sources` and `FireLogic/Sources`. Fix violations mechanically.
- **Acceptance:** `swiftlint --strict` is green. Every changed hunk is whitespace or style only, with no logic edits. If a fix would need a logic change, add a `swiftlint:disable:next` with a reason instead.

**P2-2. Resolve two stale TODOs**

- **Labels:** `weak-ok`.
- **Change:** remove the redundant code at `MenuBarItemManager.swift:152` (prove it is redundant in the PR description). Then decide on the `ScreenCapture.swift:55` TODO: keep it with a dated note if unsure.
- **Acceptance:** gates are green. Piotr's 26/27 smoke shows no behaviour change.

**P2-3. Dead-code report**

- **Labels:** `strong` (needs macOS).
- **Change:** run Periphery on the `Ice` scheme. Commit the report as `docs/audits/DEAD-CODE-2026-11.md` and open no deletions yet.
- **Acceptance:** the report lists each finding with file:line and a keep/delete recommendation.

**P2-4. #13 a11y, core-UI half**

- **Labels:** `weak-ok`.
- **Change:** add accessibility labels to IceBar item views, Layout bar items and section dividers. AI surfaces wait for the Experimental work.
- **Acceptance:** a VoiceOver pass (Piotr, 5 minutes) announces item names.

### P3: after the spike report (hand to the planning thread)

These are listed so nothing is lost. They are `strong` and `after-spike`, and the spike report decides
how to split them:

- Item discovery on 27 via AX, feeding Layout, IceBar and Search. When this lands, P0-2's flag flips and #25 closes.
- Item images on 27, by cropping from a single menu bar capture.
- Show-on-hover/click/scroll hit-testing on 27, replacing the per-window `isMouseInside*`.
- Reordering via `TrailingItemPreferredPositions`.
- App-menu overlap hiding on 27.
- A `FREQUENT_ISSUES.md` section for 27.

---

## Appendix A: macOS 27.2 smoke matrix (Piotr, about 10 minutes, Fire 10.8)

Mark each row **OK / BROKEN / PARTLY** and add a few words.

| # | Check | Result |
|---|---|---|
| 1 | First launch: permission prompts appear and can be granted | |
| 2 | Fire icon visible after granting | |
| 3 | Left-click Fire icon (what happens?) | |
| 4 | Right-click Fire icon → menu with Settings / Quit appears | |
| 5 | ⌥-click Fire icon | |
| 6 | Settings window opens; every pane renders without clipping (light and dark) | |
| 7 | Layout pane: spinner forever? | |
| 8 | IceBar (enable "Use Ice Bar", click icon): spinner forever? | |
| 9 | Search panel hotkey: shows items? | |
| 10 | Appearance → tint on: does the menu bar change colour? | |
| 11 | Appearance → border/shadow/shape: visible? | |
| 12 | Spacing slider (BETA): do icons in the bar move closer or apart after apply? | |
| 13 | A hotkey (e.g. toggle hidden section): anything visible? | |
| 14 | Check for Updates: "You're up to date" (10.8)? | |
| 15 | Quit Fire: all icons still visible, nothing lost? | |
