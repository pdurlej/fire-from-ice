# Issue #25: menu bar discovery on macOS 27

## INTENT

- Goal: analyze `pdurlej/fire-from-ice#25`, compare `17ceea1` with current main, and prepare a minimal regression fix or discriminating instrumentation.
- Success: a tested local patch for a proven defect, plus a reproduction that identifies the unproven macOS 27 trigger.
- Non-goals: installation, permission/preferences resets, broad discovery rewrites, public comments/pushes, or release/appcast publication.
- Appetite: one bounded change at the cache retry seam; diagnostic reads preserve existing window filtering, source matching, and section geometry.

## Verified source and report

Checked on 2026-09-29. [Issue #25](https://github.com/pdurlej/fire-from-ice/issues/25) is open, created 2026-09-24, with zero comments. It reports `0.11.13-fire 10.8` on macOS `27.0`; clicking the tray icon displays “loading menu bar items” forever. It contains no trace, permission state, display topology, or concrete missing-control message.

Current `origin/fire/main` is `21308349218bd76f994ec86b5b60896d07c29cc9`, committed 2026-08-14 01:56:55 CEST. The GitHub repository `pushed_at` timestamp is later (2026-08-23), but there is no post-report fix on the default branch.

`17ceea1751ec961302ce0331edb0783851676533` is an ancestor. Its discovery-related source is unchanged at current main:

- `temporarilyShow` still enumerates pre-click and post-click windows through `Task.detached`.
- The fallback UUID dictionary is still protected by `OSAllocatedUnfairLock`.

Those changes do not control the initial item-cache population. `temporarilyShow` needs an already-discovered item. Its detached window calls cannot explain an initially empty cache by themselves. The UUID lock prevents races but cannot turn an unknown source PID into Fire's hidden-control tag.

## Confirmed defect and minimal fix

`cacheItemsRegardless` saves the discovered window IDs before checking whether `ControlItemPair` contains the hidden divider. When that check fails, it leaves an empty item cache. Previously `cacheItemsIfNeeded` compared only window IDs, so identical IDs suppressed another source-PID/tag lookup indefinitely.

The loading UI uses `itemCache.managedItems.isEmpty` in both `IceBar.swift` and `MenuBarLayoutSettingsPane.swift`. It does not distinguish loading from a completed discovery failure.

The patch changes the existing refresh condition to:

```swift
!hasManagedItems || cachedWindowIDs != currentWindowIDs
```

The app calls the small `MenuBarItemCachePolicy` helper directly; FireLogic tests the same source through a symlink. Four regression cases cover empty-cache retry with unchanged IDs, recovery to a populated cache, changed IDs/order, and initially empty discovery. Before the fix, two cases failed; after it, all four passed.

This fixes retry suppression after a transient failure. It does **not** prove or fix the underlying macOS 27 discovery failure. A persistent missing divider will still fail on each attempt. The existing five-second observer cadence and explicit UI requests remain the only retry triggers; no timer or background subsystem was added.

## Most likely remaining trigger

The evidence points to a missing **recognized hidden-control tag**, with two primary paths to test:

1. The private menu-bar window list or its active-Space/window-level filtering no longer returns the divider on macOS 27.
2. The divider window is returned, but source lookup or title identity cannot reconstruct `.hiddenControlItem`. On macOS 26+, source lookup requires a stable window rect and an enabled AX child whose center is within one point of that rect. A nil PID produces a UUID namespace; a missing/different title also prevents the exact control tag from matching.

There is no macOS 27 runtime here: local host is macOS 26.7 (25G229), with Xcode 27.0. Historical local evidence reproduced a similar missing-control failure on both 10.7.3 and 10.8 on macOS 26. Earlier title/AX-identifier/order/preference experiments did not resolve it. Do not reinstate those speculative changes from `codex/fire-rebuild` or older temporary binaries.

## Instrumentation and affected-machine reproduction

All added events have `[FireDiscovery25]`, use debug-level local OSLog, and contain counts, booleans, numeric geometry, and ephemeral window/attempt IDs. They do not emit app names, window titles, AX text, tokens, or a menu inventory. Capture with `--level debug`; these events are not a new telemetry upload. The matching tolerances and APIs are unchanged. Filter counters reuse existing queries in their original short-circuit order.

Use a signed diagnostic candidate built from this branch on the affected macOS 27 machine. The temporary unsigned build in this workspace is compile evidence only; do not distribute or use it as a signed runtime verdict. Keep its existing settings/permissions unchanged for the first reproduction.

1. Start this bounded capture while the diagnostic app is already running:

   ```bash
   python3 scripts/capture_menu_bar_discovery.py --seconds 30
   ```

2. Click Fire's menu bar icon once, then reopen it after 10 seconds. Optionally open Menu Bar Layout within the same capture. Avoid moving icons or changing preferences during capture.
3. The command stops its own log reader after 30 seconds and emits only tagged events. Exit 2 means no diagnostic events were captured, not success. Exit 1 means log access failed. Exit 0 means a trace was obtained, not that Fire works. Redirect output to a local file if desired; inspect it before sharing.

| Trace observation | What it distinguishes |
| --- | --- |
| `window-list-error` | Private API failure, distinct from a legitimately empty list. |
| `window-list raw>0 selected=0` with `otherSpace` or `menuLevel` rejects | Active-Space/window-level assumptions, before source-PID lookup. Counters are sequential, not independent. |
| `materialize ids>0 windows=0` | Window-description materialization failure. |
| `xpc-begin` without an end, or `transport-failure` | XPC activation/transport/deadline path, distinct from a valid nil-PID reply. Correlate by window ID. |
| `ax-match result=untrusted` | Helper process cannot use Accessibility. |
| `ax-match result=unstable-or-missing-bounds` | No stable live window geometry. |
| `matched=false frames>0 nearestDistance>1` | AX/WindowServer geometry mismatch. `deltaX`/`deltaY` describe the nearest candidate only; they do not establish its identity. |
| `matched=false bars=0` or `frames=0` | AX discovery returned no usable extras children/frames; the trace alone does not distinguish unsupported attributes from AX errors. |
| `discovery hiddenTitles>0 hiddenTags=0` | A divider title exists but the namespace/source lookup cannot identify it as Fire's control item. |
| `discovery ownSourceItems>0 hiddenTitles=0 hiddenTags=0` | Fire-source items exist but the expected divider title does not; this alone cannot distinguish changed titles from an absent divider. |
| `cache-rejected reason=missing-hidden-control` | Cache validation failure; no successful cache is being mistaken for loading. |
| `cache-check changed=false managed=0 retry=true` | The regression fix is exercising another discovery pass with unchanged IDs. |

Follow one failed attempt from `cache-begin` to `cache-end`; overlapping attempts have separate IDs, while XPC/AX work correlates through window IDs. If `cache-begin` has no end, use the last recorded stage to locate the blocked operation. A successful runtime reproduction must show a populated cache and working menu-bar hide/reveal, not just a resolved PID or a completed trace.

## Verification and limitations

- Baseline FireLogic: 36 tests passed.
- Regression demonstration with the old IDs-only predicate: 4 tests, 2 expected failures.
- Patched FireLogic: 40 tests passed.
- Python capture/release-script tests: 7 passed.
- The real two-second capture with no instrumented app running correctly returned exit 2 and no trace; its filtering was tested against the actual `log stream` header so the header cannot masquerade as a diagnostic event.
- SwiftLint for the changed Ice files: passed. Repository-wide strict lint reports seven existing `legacy_swiftui_aspect_ratio` violations in unrelated files with the current installed SwiftLint.
- Unmodified baseline app build with Xcode 27 fails in CompactSlider 1.2.1 (`ProminentCompactSliderStyle.swift:37`, ambiguous `View.opacity` vs `ShapeStyle.opacity`). The app-source compile check temporarily wraps the gradient in `AnyView` in the task-owned DerivedData checkout only. That workaround is excluded from this repository patch and must not be treated as a clean stock build or release evidence.
- With that temporary dependency workaround, the full unsigned app/XPC/Bridge build passed. The temporary dependency edit was then reverted. Build log: `/private/tmp/fire-issue-25-patch-build.log`; original baseline failure: `/private/tmp/fire-issue-25-baseline-build.log`.
- macOS 27 signed E2E and root-cause confirmation remain pending; the affected-machine trace is the next discriminating evidence.
- Independent read-only review of the final implementation found no confirmed blocking defect. Residual risk: persistent slow failure can now trigger repeated full discovery through the existing five-second observer; existing cache tasks cancel/replace earlier attempts. Watch `cache-begin`/`cache-end`, `cancelled`, and elapsed time for overlapping attempts or excessive AX/XPC load. This risk was not reproduced on macOS 27 and is not a reason to introduce a new retry subsystem without runtime evidence.
- Captured lines are local diagnostics, not an authenticated provenance format. The message predicate could also match another process deliberately emitting the same marker. Inspect traces before sharing; no trace was uploaded by this task.

## Preservation and rollback

Worktree: `/Users/pd/Developer/fire-issue-25`, branch `codex/issue-25-discovery`, base `2130834`. Preserve it because the patch is unmerged and the diagnostic evidence is needed for continuation. Existing worktrees and installed `/Applications/Ice.app` were left untouched.

Nothing was pushed, posted, installed, tagged, or published. The cache behavior rollback is to restore the IDs-only refresh comparison in `MenuBarItemManager.cacheItemsIfNeeded`; diagnostic cleanup is a search for `[FireDiscovery25]` plus removal of the capture script/tests. Keep the regression test when integrating a confirmed macOS 27 fix so recovery with unchanged IDs remains protected.
