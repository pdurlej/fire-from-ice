# HANDOFF — Fire, current state

Current truth as of 2026-11-09. For agents and for a fresh session after
context loss. **Start with [`AGENTS.md`](AGENTS.md)**: it has the exact
commands, hard rules and gotchas. This file says where the project stands and
where to look. The old May–August ship log, including notes on other projects,
is archived verbatim in
[`docs/history/HANDOFF-2026-05-to-08.md`](docs/history/HANDOFF-2026-05-to-08.md).

## What's live

- **`v0.11.13-fire.10.8` "Safe Core"**, build 1181, notarized. GitHub Latest
  since 2026-08-23 and the newest item on the Sparkle appcast. Release contract:
  issue [#18](https://github.com/pdurlej/fire-from-ice/issues/18).
- 10.8 restored the stable release spine from `v0.11.13-fire.10.7.3`: the core
  menu bar runtime is independent of the AI features, XPC calls have bounded
  deadlines (`XPCSyncDeadline`), and CI, release and appcast checks are hardened.
- The Ignition line (`v1.0.x` tags, July 2026) is reference material only. Its
  GitHub releases look newer than 10.8 by version string; Sparkle is not
  affected because it compares build numbers (1181 is higher than any Ignition
  build).
- `fire/main` has 10.8 plus the #25 discovery hotfix (PR #26: retry empty item
  discovery, trace failures) and the macOS 27 spike brief (PR #27). No release
  has been cut since 10.8.

## What's in progress

**macOS 27 Golden Gate is the primary target.** The owner's daily Mac runs
macOS 27.2, and on it Fire does not work: the menu bar is drawn as a single
`MenuBarAgent` window, so Ice's per-item window enumeration finds nothing.
Hiding does nothing, and the IceBar and the Layout pane show "Loading menu bar
items" forever ([#25](https://github.com/pdurlej/fire-from-ice/issues/25)).
macOS 14–26 keep working as in 10.8.

Workstreams, all tracked in [`ROADMAP.md`](ROADMAP.md):

1. **Hiding spike.** Brief:
   [`docs/spikes/MACOS27-HIDING-SPIKE.md`](docs/spikes/MACOS27-HIDING-SPIKE.md).
   The owner runs it on the 27.2 Mac. It writes
   `docs/spikes/MACOS27-HIDING-REPORT.md`, and the follow-up issue batch is cut
   from that report. The port may reuse Thaw's GPLv3 `macos-27-preview` code
   with attribution; Thaw's later closed `PlatformRuntimeKit` binary must not be
   read, decompiled or used.
2. **Release-polish audit** (PR #30) and the issues made from it: P0 #31–#37,
   P1 #38–#44, P2 #45–#47.
3. **Experimental switch** (PR #28): AI Quotas, MCP and automations behind one
   opt-in, off by default.
4. **Agent quality gates** (PR #29): `docs/agent-gates.md`, an agent-task issue
   form, a PR template and CI checks for scope, evidence and owner QA.

Still open from before: #5 (`sendSync` deadline needs a recorded signed
kill-STOP test before closing), #7 and #11 (main-thread SLS calls, macOS ≤ 26
only), #13 (accessibility labels), #19 and #20 (parked feature releases), #21
(polish umbrella).

## How work happens now

- The owner is a non-developer maintainer. Most changes are written by coding
  agents from GitHub issues, many by smaller models, so each issue carries its
  own allowed paths, acceptance criteria and gates.
- A thread or agent may merge its own PR into `fire/main` once CI is green.
  Releases, tags, promoting GitHub Latest and publishing the appcast stay with
  the owner (ship flow in `AGENTS.md`).
- No new feature waves until Fire works on macOS 27.
- The UI product name (Fire vs Ice, #38) is the owner's call. Docs say "Fire".

## Guardrails that don't change

- Bundle id stays `com.jordanbaird.Ice`, product `Ice.app` (TCC permissions,
  Sentry and appcast matching depend on it). A rebrand to a new bundle id is
  parked.
- Sparkle appcast: `https://pdurlej.github.io/fire-releases/appcast.xml`, served
  from the separate `pdurlej/fire-releases` repo. The EdDSA private key lives
  only in the owner's macOS Keychain; signing is local, never in CI.
- Crashes and App Hangs go to Sentry project `pdurlej/fire`, symbolicated via
  dSYMs uploaded by CI. The App-Hang loop and gotchas are in `AGENTS.md`.
- The owner handles all secrets, tokens and agreements personally.

## Where to find things

| What | Where |
|---|---|
| Commands, ship flow, hard rules, gotchas | [`AGENTS.md`](AGENTS.md) |
| Plan: Now / Next / Parked | [`ROADMAP.md`](ROADMAP.md) |
| macOS 27 hiding spike brief | [`docs/spikes/MACOS27-HIDING-SPIKE.md`](docs/spikes/MACOS27-HIDING-SPIKE.md) |
| #25 discovery notes | [`docs/issue-25-macos-27-discovery.md`](docs/issue-25-macos-27-discovery.md) |
| Status-item visibility notes | [`docs/MENU-BAR-STATUS-ITEM-VISIBILITY.md`](docs/MENU-BAR-STATUS-ITEM-VISIBILITY.md) |
| Release-polish audit | `docs/audits/RELEASE-POLISH-AUDIT-2026-11.md` (PR #30) |
| Agent quality gates | `docs/agent-gates.md` (PR #29) |
| MCP server architecture | [`docs/mcp/ARCHITECTURE.md`](docs/mcp/ARCHITECTURE.md) |
| Signed builds and notarization | [`docs/signed-builds/SETUP.md`](docs/signed-builds/SETUP.md) |
| Fork positioning and history | [`FORK.md`](FORK.md) |
| Old ship log, May–August 2026 | [`docs/history/HANDOFF-2026-05-to-08.md`](docs/history/HANDOFF-2026-05-to-08.md) |
| Old plans (roadmap, rebrand, icon brief, BMAD) | [`docs/history/`](docs/history/) |
