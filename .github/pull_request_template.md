<!--
Agent PRs: fill in every section. CI ("Agent gates") checks it; see docs/agent-gates.md.
Owner PRs without an agent-task issue: delete what doesn't apply.
-->

Closes #

## What changed

<!-- Two to five bullets. Say explicitly if any code that runs on macOS 26 or earlier changed. -->

## Not done / follow-ups

<!-- Anything from the issue you didn't do, and anything you noticed but left alone. -->

## Gate evidence

<!-- Paste the last ~15 lines of each command from AGENTS.md, or, if you couldn't run it
(e.g. no Mac), write "not run locally" plus the link to the green CI run. -->

### G1 Build all app targets

```text
<paste the tail>
```

### G2 Build the MCP bridge

```text
<paste the tail>
```

### G3 FireLogic tests

```text
<paste the tail>
```

### G4 Release script tests

```text
<paste the tail>
```

### G5 SwiftLint

```text
<paste the tail>
```

## Manual QA

<!-- The OWNER fills in this section after testing on his Mac. Agents: copy the table,
add the issue's Q rows, and leave every Result as "pending". -->

Tested on: macOS
Tested commit:

| # | Step | Result |
|---|------|--------|
| S1 | Build and launch the PR build | pending |
| S2 | Open Settings, visit every pane | pending |
| S3 | Hide and show with the Fire icon | pending |
| S4 | Quit Fire | pending |
| S5 | 15 minutes of normal use | pending |
| S6 | No new crash or App Hang from this build | pending |
| S7 | Back on the installed build | pending |
