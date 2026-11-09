# Agent gates: the contract for agent-written PRs

Fire is maintained by one owner who doesn't review Swift line by line. Most
changes are written by coding agents from GitHub issues, often by smaller
models. This file is the contract every such change has to meet. CI enforces
the mechanical parts; the owner does the manual QA on his Mac.

A PR that meets every gate below, with all checks green, may be merged by the
agent or thread that opened it. A PR that doesn't is not done, however good the
code looks.

Read this together with `AGENTS.md` (exact commands, gotchas) and the issue you
are working on. If the issue and this file disagree, the stricter rule wins.
Task-specific briefs such as `docs/spikes/MACOS27-HIDING-SPIKE.md` add their own
rules on top of these; they don't replace them.

## The workflow in one paragraph

Each task is one issue made from the **Agent task** template (label
`agent-task`). The agent works on its own branch, opens one PR against
`fire/main` using the PR template, and writes `Closes #<issue>` in the body.
CI runs the build, tests and lint (`verify.yml`, `lint.yml`) and the agent gates
(`agent-gates.yml`). The agent pastes evidence into the PR body and leaves the
Manual QA table as `pending`. If the issue asks for manual QA, the owner tests
the PR build on his Mac and fills in the table. When every check is green, the
PR is merged.

## Gates

| Gate | What | Enforced by |
|------|------|-------------|
| G1 | Build all app targets (Ice, MCPBackend.xpc, MenuBarItemService.xpc), signing disabled, zero errors | CI `Verify macOS`, evidence in PR body |
| G2 | `swift build --package-path Bridge` passes | CI `Verify macOS`, evidence |
| G3 | `xcrun swift test --package-path FireLogic` passes, with new tests for new logic | CI `Verify macOS`, evidence |
| G4 | `python3 -m unittest discover -s scripts/tests` passes | CI `Verify macOS`, evidence |
| G5 | SwiftLint clean with the repo config (`--strict`) | CI `Lint Swift Files`, evidence |
| G6 | Every changed file is inside the issue's **Allowed paths** | CI `Gates: scope and protected paths` |
| G7 | No protected file or setting touched (list below) | CI `Gates: scope and protected paths` |
| G8 | No gate weakened: no new `swiftlint:disable`, no skipped or disabled tests | CI `Gates: scope and protected paths` |
| G9 | The PR body has evidence for G1–G5 | CI `Gates: evidence in PR body` |
| G10 | Manual QA passed on the owner's Mac, for the exact head commit | CI `Gates: owner QA` |

The exact commands for G1–G3 are in `AGENTS.md` under "Commands (exact)". Run
them as written there. SwiftLint locally: `swiftlint lint --strict` from the
repo root.

The `Agent gates` workflow runs on `pull_request_target`: the workflow and
`scripts/agent_gates.py` always come from `fire/main`, never from the PR, and
the PR's code is never checked out or run by it. Changing the gates therefore
only takes effect after the change is merged, and a PR can't relax the checks
that judge it.

### G6: scope

The issue lists **Allowed paths**, one glob per line: `**` crosses directories,
`*` and `?` don't, and a trailing `/` means the whole directory. Every file the
PR adds, changes, deletes or renames must match one of them. If the task really
needs a file outside the list, stop and say so in the PR under "Not done /
follow-ups" instead of touching it. Don't "tidy up" unrelated code, don't
reformat files, don't rename things you weren't asked to rename.

### G7: protected files and settings

Agents never change these. CI fails on any of them:

- Code signing and release: `ExportOptions.plist`, any `*.entitlements`, any file
  with `appcast` in its name (including `scripts/publish-appcast.sh` and
  `scripts/verify_appcast_entry.py`).
- In `Ice.xcodeproj/project.pbxproj`: `MARKETING_VERSION`,
  `CURRENT_PROJECT_VERSION`, `DEVELOPMENT_TEAM`, any `CODE_SIGN*`,
  `PROVISIONING_PROFILE*`, `ENABLE_HARDENED_RUNTIME`,
  `PRODUCT_BUNDLE_IDENTIFIER`, `OTHER_CODE_SIGN_FLAGS`, `INFOPLIST_FILE`,
  `GENERATE_INFOPLIST_FILE`, any `INFOPLIST_KEY_*`.
- In any `Info.plist`: `SUFeedURL`, `SUPublicEDKey`, `CFBundleIdentifier`.
- CI and the gates themselves: everything in `.github/workflows/`,
  `.swiftlint.yml`, `scripts/agent_gates.py` and its test, this file, the PR
  template and the agent-task issue template.

Agents also never tag, publish a release, or edit the appcast, whatever the
diff says. Releases follow the ship flow in `AGENTS.md` and are the owner's.

Only the owner may accept a protected change, by adding the label
`gates-override` to the PR. Agents must never add that label, and must not ask
for it as a way around a failing gate.

### G8: don't weaken a gate to pass it

No new `// swiftlint:disable`, no `XCTSkip`, no `.disabled(...)` tests, no
deleted or commented-out assertions. (`.disabled(...)` is only flagged in test
files, since it's also a normal SwiftUI modifier.) A failing test means the code is wrong or
the test is out of date, and the PR must say which and why.

### G9: evidence

The PR body has one `### G1 …` to `### G5 …` section each (the PR template
has them). Each contains the last ~15 lines of the command's output, which must
include its success line:

| Gate | Success line |
|------|--------------|
| G1 | `** BUILD SUCCEEDED **` |
| G2 | `Build complete!` |
| G3 | `Executed N tests, with 0 failures` |
| G4 | `Ran N tests` … `OK` |
| G5 | `Found 0 violations` |

If you can't run a command (for example, you run on Linux without Xcode), write
"not run locally" and link the green CI run of this PR
(`https://github.com/pdurlej/fire-from-ice/actions/runs/…`). CI checks the
link: it must be a successful run of the right workflow (`Verify macOS` for
G1–G4, `Lint Swift Files` for G5) on the PR's current head commit. If the PR
changes no Swift files, `lint.yml` doesn't run; write "N/A: no Swift files
changed" under G5 and CI verifies that. Never paste output you didn't get, and
never claim a gate passed when you didn't see it pass.

## Manual QA (G10)

The issue picks one of three levels:

- **none**: no runtime change (docs, tests, pure FireLogic, CI). G10 passes on its own.
- **smoke**: the owner runs the smoke checklist below.
- **smoke + issue rows**: the smoke checklist plus the rows `Q1`, `Q2`, … from the
  issue's "Issue QA rows". Every Q row listed in the issue must be in the PR
  table. A task brief can supply its own table, such as the 12 rows in
  `docs/spikes/MACOS27-HIDING-SPIKE.md`; they go in as `Q` rows.

The agent copies the table into the PR and leaves every result as `pending`.
Only the owner writes results. CI stays red until every row is `PASS` (or `N/A`
with a reason), the `Tested on: macOS …` line is filled in, and
`Tested commit:` matches the PR's head commit. A new push therefore needs a new
QA run.

### Smoke checklist (owner's Mac, macOS 27.2)

Fire may not work fully on macOS 27 yet. The bar for the smoke test is "no
worse than the build currently installed", not "everything works".

| # | Step | Expected |
|---|------|----------|
| S1 | Build and launch the PR build (below) | It launches, no crash dialog, the Fire icon is in the menu bar |
| S2 | Open Settings and visit every pane | No beachball, nothing blank or broken that works in the installed build |
| S3 | Hide and show with the Fire icon | Same behaviour as the installed build, or better |
| S4 | Quit Fire | Every menu bar icon is visible again |
| S5 | 15 minutes of normal use | No flashing of the menu bar, no beachball, Ice under ~5% CPU when idle (Activity Monitor) |
| S6 | Check Sentry (project `pdurlej/fire`) and Console | No new crash or App Hang from this build |
| S7 | Quit the PR build and reopen `/Applications/Ice.app` | The installed build starts and works as before |

### Building the PR for QA

```bash
cd ~/Developer/fire
gh pr checkout <PR number> -R pdurlej/fire-from-ice
git rev-parse --short HEAD     # this goes into "Tested commit:"
xcodebuild -project Ice.xcodeproj -scheme Ice -configuration Debug \
  -destination 'platform=macOS' -derivedDataPath build/qa build
osascript -e 'quit app "Ice"'  # quit the installed build first
open build/qa/Build/Products/Debug/Ice.app
```

The PR build has the same bundle id as the installed one, so macOS may ask for
Accessibility or Screen Recording again for each build, and again for
`/Applications/Ice.app` afterwards. That's expected.

## PR checklist for agents

1. Read the issue, `AGENTS.md`, and the files the issue names, before writing code.
2. One issue, one branch, one PR against `fire/main`. Body from the template,
   `Closes #<issue>` on its own line.
3. Change only Allowed paths. Add the tests the issue asks for.
4. Run G1–G5, paste the tails. Fix failures; don't weaken the gate.
5. Under "What changed", say explicitly whether code that runs on macOS 26 or
   earlier changed.
6. Copy the Manual QA table with every result `pending`.
7. Don't merge while any check is red. A red `Gates: owner QA` means waiting for
   the owner, not something to work around.

## Branch protection (owner, one-time)

To make the gates binding, mark these as required checks for `fire/main` in
the repository settings: `verify`, `Gates: scope and protected paths`,
`Gates: evidence in PR body`, `Gates: owner QA`. Don't make `swiftlint`
required: `lint.yml` only runs when Swift files change, so a docs-only PR would
wait forever. G9 still requires the lint output in the PR body.
