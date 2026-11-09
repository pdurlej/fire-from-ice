# Fire roadmap

Updated 2026-11-09. One page, three lists. Anything not here is not planned.

**Live:** `v0.11.13-fire.10.8` "Safe Core" (build 1181), GitHub Latest since 2026-08-23.
**Primary target:** macOS 27 Golden Gate (27.2). macOS 14–26 keep working as they do today.

## Now

Make Fire usable and honest on macOS 27.

1. **Hiding on macOS 27.** On 27 the menu bar is one `MenuBarAgent` window, so the
   per-item window approach finds nothing and hiding does nothing
   ([#25](https://github.com/pdurlej/fire-from-ice/issues/25)). The spike brief is
   [`docs/spikes/MACOS27-HIDING-SPIKE.md`](docs/spikes/MACOS27-HIDING-SPIKE.md); it ends in
   `docs/spikes/MACOS27-HIDING-REPORT.md`, and a batch of follow-up issues is cut from that report.
2. **P0 polish**, from the [release-polish audit](https://github.com/pdurlej/fire-from-ice/pull/30):
   - [#31](https://github.com/pdurlej/fire-from-ice/issues/31) README tells the truth about macOS 27
   - [#32](https://github.com/pdurlej/fire-from-ice/issues/32) "Not supported on macOS 27 yet" instead of an endless spinner
   - [#33](https://github.com/pdurlej/fire-from-ice/issues/33) AGENTS.md up to date
   - [#34](https://github.com/pdurlej/fire-from-ice/issues/34) HANDOFF.md trimmed to current truth
   - [#35](https://github.com/pdurlej/fire-from-ice/issues/35) this roadmap
   - [#36](https://github.com/pdurlej/fire-from-ice/issues/36) stale planning docs archived
   - [#37](https://github.com/pdurlej/fire-from-ice/issues/37) owner smoke test on macOS 27.2
3. **Quality gates for agent PRs**: [`docs/agent-gates.md`](https://github.com/pdurlej/fire-from-ice/pull/29).

## Next

1. **AI, MCP and automations behind one Experimental switch**, off by default
   ([PR #28](https://github.com/pdurlej/fire-from-ice/pull/28)). Builds on `FireFeaturePolicy` from 10.8.
2. **P1 polish:**
   - [#38](https://github.com/pdurlej/fire-from-ice/issues/38) one product name in the UI (owner decides)
   - [#39](https://github.com/pdurlej/fire-from-ice/issues/39) Fire's own menu bar icon: left, right and ⌥ clicks on 27
   - [#40](https://github.com/pdurlej/fire-from-ice/issues/40) non-blocking CI build with the Xcode 27 SDK
   - [#41](https://github.com/pdurlej/fire-from-ice/issues/41) honest permissions onboarding copy on 27
   - [#42](https://github.com/pdurlej/fire-from-ice/issues/42) Settings visual pass on 27.2
   - [#43](https://github.com/pdurlej/fire-from-ice/issues/43) README visuals: Fire screenshots
   - [#44](https://github.com/pdurlej/fire-from-ice/issues/44) Appearance and Spacing on 27: disable controls that do nothing
   - [#21](https://github.com/pdurlej/fire-from-ice/issues/21) accessibility and settings polish (umbrella)
3. **P2 hygiene:** [#45](https://github.com/pdurlej/fire-from-ice/issues/45) SwiftLint everywhere,
   [#46](https://github.com/pdurlej/fire-from-ice/issues/46) stale TODOs,
   [#47](https://github.com/pdurlej/fire-from-ice/issues/47) dead-code report.

## Parked

Not scheduled. Revisit only after Fire works on macOS 27.

- 10.9 "glance" for Codex and Claude Code ([#19](https://github.com/pdurlej/fire-from-ice/issues/19))
- 10.10 Coding Fireline ([#20](https://github.com/pdurlej/fire-from-ice/issues/20))
- Profiles, layout import/export, per-display configuration
- Rebrand to a new bundle id. The app stays `Ice.app` with bundle id `com.jordanbaird.Ice`.

---

The original May 2026 plan and other old planning docs are in [`docs/history/`](docs/history/).
