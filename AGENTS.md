# AGENTS.md — Fire (Ice fork) working notes

Entry point for coding agents (Codex, Claude, and whoever else). Fire is a fork
of jordanbaird/Ice, the macOS menu bar manager, with an MCP server and
automations on top. This file is the fast path. **`HANDOFF.md`** has the
current state and pointers; the May–August ship log is archived in
`docs/history/HANDOFF-2026-05-to-08.md`. The plan is **`ROADMAP.md`**.

- **Repo:** `pdurlej/fire-from-ice` (GitHub). Always `-R pdurlej/fire-from-ice`
  for `gh`. Branch: **`fire/main`** (not `main`). Local: `/Users/pd/Developer/fire`.
- **Bundle id stays `com.jordanbaird.Ice`**, product `Ice.app`, on purpose (TCC,
  Sentry, appcast version-matching depend on it).
- **Owner (`pdurlej`) runs the shipped build as his DAILY menu bar manager.** Every
  install step below updates his real machine; every Sentry App-Hang is him
  hitting it in normal use. He can test menu-bar behaviour on request — the only
  way to verify the event-handler paths.

## ✅ LIVE NOW / NEXT

**`v0.11.13-fire.10.8` "Safe Core" (build 1181) is the live, notarized build:
GitHub Latest since 2026-08-23 and the newest item on the Sparkle appcast.**
Its contract was issue #18. The Ignition tags (`v1.0.x`) are reference
material, not a base to fix forward.

**macOS 27 Golden Gate is the primary target.** The owner's daily Mac runs
macOS 27.2, and there Fire does not hide anything: the menu bar is a single
`MenuBarAgent` window, so the per-item window approach finds no items and the
IceBar and Layout pane spin forever (#25). The spike brief is
`docs/spikes/MACOS27-HIDING-SPIKE.md`; its output will be
`docs/spikes/MACOS27-HIDING-REPORT.md`, and follow-up issues are cut from that.
Don't touch hiding internals outside that spike. macOS 14–26 must keep working
as they do in 10.8.

**Merge policy.** A thread or agent may merge its own PR into `fire/main` once
CI is green. Releases, tags, GitHub Latest and appcast publishing still need
the owner. Quality gates for agent PRs: `docs/agent-gates.md` (PR #29).

## Commands (exact)

```bash
# Build-gate the app (all targets: Ice + MCPBackend.xpc + MenuBarItemService.xpc)
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
  -project Ice.xcodeproj -scheme Ice -configuration Debug -destination 'platform=macOS' \
  CODE_SIGN_IDENTITY="" CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO build

# The MCP bridge (separate SPM package)
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift build --package-path Bridge

# Tests (needs the Xcode toolchain — plain `swift test` lacks XCTest)
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swift test --package-path FireLogic
```

**Ship flow** (per release): bump BOTH `MARKETING_VERSION` (`0.11.13-fire.X`) +
`CURRENT_PROJECT_VERSION` in `Ice.xcodeproj/project.pbxproj` (2 occurrences each)
→ commit → `git tag -a v0.11.13-fire.X` → `git push origin fire/main` + push tag
→ CI (`gh run list -R pdurlej/fire-from-ice`) builds/signs/notarizes/uploads-dSYMs
and creates or updates a **prerelease** → download DMG, `ditto` it over
`/Applications/Ice.app` (quit Ice first), run signed smoke, inspect Sentry →
explicitly promote GitHub Latest → **`scripts/publish-appcast.sh
v0.11.13-fire.X`** for Sparkle (one Keychain "Allow"; an existing entry is
accepted only when build, URL, length, and signature match).

## Hard rules

- **Do NOT tell the owner to rest / sleep / wrap up** (a documented Opus tic;
  applies to everyone).
- **Owner handles all secrets/tokens/agreements personally.** Never enter API
  tokens. The Sparkle EdDSA key stays in his Keychain — signing is LOCAL, never CI.
- **Oracle** only via the `oracle` MCP wrapper (browser, gpt-5.5-pro); don't rerun
  on timeout (use `oracle-await`).
- Commit trailer for this repo: `Co-Authored-By: <model> <noreply@anthropic.com>`.
- CI GitHub Actions are **SHA-pinned** (tag in a trailing comment). To bump one,
  resolve the SHA via `gh api repos/OWNER/REPO/commits/TAG`.
- **App-Hang model:** Sentry (project `pdurlej/fire`) + dSYM upload in CI means
  each new App Hang symbolicates to a precise stack (FIRE-<letter>). The loop is:
  read the named frame → make a targeted off-main/timeout fix → field-verify by
  the issue going SILENT on the next build. Don't guess; the frame names the organ.

## Gotchas I actually hit (read before repeating)

1. **`log show` is shadowed** by a function in the shell snapshot AND blocked by
   the Bash sandbox. Use the full path `/usr/bin/log show …` and pass
   `dangerouslyDisableSandbox: true` (read-only diagnostics only).
2. **Do NOT cache geometry that changes at guard-evaluation time.** fire.10.7
   cached the menu-bar *item* frames for `isMouseInsideMenuBarItem` (#7); it broke
   show-on-hover/click (lagged / misfired / did nothing) because items move at the
   exact instant the guard runs. Reverted in 10.7.1 — that query stays LIVE. The
   *application-menu* frame cache (#17) is fine because it only changes on app
   switch. `⌘-drag` is the one path that bypasses these guards (useful control).
3. **`SecCodeCopySigningInformation` needs `kSecCSSigningInformation`** or the
   returned dict omits the team id. This silently made `ownTeamIdentifier()`
   return nil for every build since fire.10.2 → `.isFromSameTeam()` was NEVER
   applied (fixed in 10.7.1). If you touch signing/XPC-peer code, verify with a
   standalone `SecCode…` probe against `/Applications/Ice.app`.
4. **`publish-appcast.sh`:** `hdiutil attach -quiet` prints nothing and DMG volume
   names contain spaces — parse the mount point via `-plist` + plistlib (already
   done; don't "simplify" it back to grep).
5. **New source files:** the `Ice`, `MCPBackend`, `MenuBarItemService` targets are
   `PBXFileSystemSynchronizedRootGroup`s — adding/removing a `.swift` file needs
   NO pbxproj edit (`git rm`/create just works). The **Bridge** wire files are
   symlinks to `Shared/Services/…`; edit the Shared source, not the symlink.
6. **Notarization needs the owner's Apple Developer Program License Agreement
   in-effect.** If CI fails with HTTP 403 "agreement missing/expired", the owner
   accepts it at developer.apple.com, then `gh run rerun --failed <run-id>` (no
   code change).

## Open issues (`gh issue list -R pdurlej/fire-from-ice`, 2026-11-09)

| # | P | note |
|---|---|---|
| 25 | P0 | Hiding broken on macOS 27. Owned by the spike (see above). |
| 31–36 | P0 | Docs truth pass: README, AGENTS, HANDOFF, ROADMAP, archive. |
| 32 | P0 | "Not supported on macOS 27 yet" instead of an endless spinner. |
| 37 | P0 | Owner's 10-minute smoke test on macOS 27.2. |
| 38–44 | P1 | Polish for 27: product name (owner decides), own icon clicks, Xcode 27 SDK CI job, onboarding copy, Settings pass, README visuals, Appearance/Spacing. |
| 45–47 | P2 | SwiftLint on all folders, two stale TODOs, Periphery dead-code report. |
| 5 | P2 | `sendSync` deadline is in place (`XPCSyncDeadline`); close only after a recorded signed kill-STOP test against both XPC services. |
| 7, 11 | P2/P3 | Main-thread SLS calls, macOS ≤ 26 only. #7: do NOT cache (gotcha #2). |
| 13 | P3 | a11y labels on fork-added UI. |
| 18 | done | 10.8 Safe Core shipped; can be closed. |
| 19–21 | later | 10.9 glance and 10.10 Fireline are parked; #21 is the polish umbrella. |

Open PRs: #28 Experimental switch for AI/MCP/automations, #29 agent gates,
#30 release-polish audit, #23 and #24 (older Ice Bar / overlay fixes).

The App-Hang franchise (FIRE-F/G/H/K/M/N/P) is field-quiet on ≤ 26; FIRE-Q/J
are false modal ANRs that the client filter catches only best-effort.
