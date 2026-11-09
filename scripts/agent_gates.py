#!/usr/bin/env python3
"""Mechanical quality gates for pull requests (see docs/agent-gates.md).

Three subcommands, one per CI job in .github/workflows/agent-gates.yml:

  safety    Every PR: no protected files touched (signing, release, appcast,
            versions, CI and the gates themselves). Agent PRs additionally:
            every changed file is inside the linked issue's "Allowed paths",
            and no new `swiftlint:disable` or skipped tests.
  evidence  Agent PRs: the PR body carries proof for gates G1-G5.
  qa        Agent PRs: the owner's manual QA table is filled in, all PASS,
            for the exact head commit.

An "agent PR" is a PR whose body says `Closes #N` (or Fixes/Resolves) for an
issue labelled `agent-task` or written from the agent-task template.

Stdlib only. The pure functions are unit-tested in
scripts/tests/test_agent_gates.py; main() does the I/O (event file, git, API).
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

OVERRIDE_LABEL = "gates-override"
AGENT_LABEL = "agent-task"
CONTRACT = "docs/agent-gates.md"

# --------------------------------------------------------------------------
# Protected paths
# --------------------------------------------------------------------------

# (regex on the repo-relative path, reason). Any add/modify/delete/rename of a
# matching path is a violation unless the owner applied OVERRIDE_LABEL.
PROTECTED_FILES: list[tuple[str, str]] = [
    (r"^ExportOptions\.plist$", "code signing / export"),
    (r"\.entitlements$", "code signing entitlements"),
    (r"(^|/)[^/]*appcast[^/]*$", "Sparkle appcast / release publishing"),
    (r"^\.github/workflows/", "CI workflows"),
    (r"^\.swiftlint\.yml$", "lint configuration"),
]

# Files that implement the gates. They are protected like the rest, except on
# the bootstrap PR that introduces them (the base branch has no gate script).
GATE_FILES: list[str] = [
    "scripts/agent_gates.py",
    "scripts/tests/test_agent_gates.py",
    "docs/agent-gates.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/agent_task.yml",
]

PBXPROJ = "Ice.xcodeproj/project.pbxproj"
PBXPROJ_PROTECTED = re.compile(
    r"\b(MARKETING_VERSION|CURRENT_PROJECT_VERSION|DEVELOPMENT_TEAM|"
    r"CODE_SIGN[A-Z_]*|PROVISIONING_PROFILE[A-Z_]*|ENABLE_HARDENED_RUNTIME|"
    r"PRODUCT_BUNDLE_IDENTIFIER|OTHER_CODE_SIGN_FLAGS)\b"
)
INFO_PLIST_PROTECTED_KEYS = ("SUFeedURL", "SUPublicEDKey", "CFBundleIdentifier")

# Added lines that weaken a gate instead of passing it (agent PRs only).
WEAKENING_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"swiftlint:disable"), "new `swiftlint:disable`"),
    (re.compile(r"\bXCTSkip\b"), "skipped test (`XCTSkip`)"),
    (re.compile(r"\.disabled\s*\("), "disabled test (`.disabled(...)`)"),
    (re.compile(r"\bfunc\s+DISABLED_|\bfunc\s+xtest"), "disabled test function"),
]


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def protected_file_reason(path: str, bootstrap: bool) -> Optional[str]:
    for pattern, reason in PROTECTED_FILES:
        if re.search(pattern, path):
            return reason
    if path in GATE_FILES and not bootstrap:
        return "quality-gate implementation"
    return None


def parse_unified_diff(diff: str) -> dict[str, list[str]]:
    """Map file path -> changed lines (with their leading '+' or '-')."""
    changes: dict[str, list[str]] = {}
    current: Optional[str] = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current = None
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            target = line[4:].strip()
            if target != "/dev/null" and target[:2] in ("a/", "b/"):
                current = target[2:]
                changes.setdefault(current, [])
            continue
        if current and line[:1] in ("+", "-"):
            changes[current].append(line)
    return changes


def check_protected(
    changed_files: Iterable[str],
    diff_lines: dict[str, list[str]],
    read_at: Callable[[str, str], Optional[bytes]],
    bootstrap: bool,
) -> list[str]:
    """read_at(rev, path) returns file bytes at 'base' or 'head', or None."""
    errors = []
    for path in sorted(set(changed_files)):
        reason = protected_file_reason(path, bootstrap)
        if reason:
            errors.append(f"`{path}` is protected ({reason}).")
            continue
        if path == PBXPROJ:
            hits = [l for l in diff_lines.get(path, []) if PBXPROJ_PROTECTED.search(l)]
            for line in hits[:5]:
                errors.append(
                    f"`{path}` changes a signing/version setting: `{line.strip()[:120]}`"
                )
        if path.endswith("Info.plist"):
            for key in INFO_PLIST_PROTECTED_KEYS:
                before = _plist_value(read_at("base", path), key)
                after = _plist_value(read_at("head", path), key)
                if before != after:
                    errors.append(f"`{path}` changes protected key `{key}`.")
    return errors


def _plist_value(data: Optional[bytes], key: str):
    if data is None:
        return None
    try:
        return plistlib.loads(data).get(key)
    except Exception:  # unparsable plist: compare raw presence instead
        return key.encode() in data


def check_weakening(diff_lines: dict[str, list[str]]) -> list[str]:
    errors = []
    for path, lines in sorted(diff_lines.items()):
        for line in lines:
            if not line.startswith("+"):
                continue
            for pattern, label in WEAKENING_PATTERNS:
                if pattern.search(line):
                    errors.append(f"`{path}` adds a {label}: `{line[1:].strip()[:120]}`")
    return errors


# --------------------------------------------------------------------------
# Issue parsing and scope
# --------------------------------------------------------------------------

LINK_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+"
    r"(?:https://github\.com/[\w.-]+/[\w.-]+/issues/|#)(\d+)",
    re.IGNORECASE,
)


def linked_issue_numbers(pr_body: str) -> list[int]:
    seen: list[int] = []
    for match in LINK_RE.finditer(_strip_comments(pr_body or "")):
        number = int(match.group(1))
        if number not in seen:
            seen.append(number)
    return seen


def _strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def markdown_sections(body: str, level: int) -> dict[str, str]:
    """Split markdown on headings of exactly `level` (#, ##, ###)."""
    sections: dict[str, str] = {}
    heading = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
    current: Optional[str] = None
    buffer: list[str] = []
    for line in _strip_comments(body or "").splitlines():
        match = heading.match(line)
        if match and len(match.group(1)) <= level:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = match.group(2).strip().lower() if len(match.group(1)) == level else None
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def is_agent_issue(issue: dict) -> bool:
    labels = {l.get("name", "") if isinstance(l, dict) else str(l) for l in issue.get("labels", [])}
    return AGENT_LABEL in labels or "allowed paths" in markdown_sections(issue.get("body") or "", 3)


def allowed_paths(issue_body: str) -> list[str]:
    raw = markdown_sections(issue_body, 3).get("allowed paths", "")
    paths = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("```"):
            continue
        line = line.strip("`").strip()
        if line.startswith("- "):
            line = line[2:].strip().strip("`").strip()
        if not line or line.startswith("```") or line.startswith("#") or line == "_No response_":
            continue
        paths.append(line)
    return paths


def qa_level(issue_body: str) -> str:
    """'none', 'smoke' or 'issue' (smoke + issue rows). Defaults to 'smoke'."""
    raw = markdown_sections(issue_body, 3).get("manual qa", "").strip().lower()
    if raw.startswith("none"):
        return "none"
    if "issue" in raw:
        return "issue"
    return "smoke"


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """`**` crosses directories, `*` and `?` don't. A trailing `/` means the
    whole directory."""
    if pattern.endswith("/"):
        pattern += "**"
    out = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(f"^{out}$")


def check_scope(changed_files: Iterable[str], patterns: list[str]) -> list[str]:
    if not patterns:
        return ["The linked issue has no `Allowed paths`, so scope can't be checked. Add them to the issue."]
    regexes = [glob_to_regex(p) for p in patterns]
    return [
        f"`{path}` is outside the issue's Allowed paths."
        for path in sorted(set(changed_files))
        if not any(r.match(path) for r in regexes)
    ]


# --------------------------------------------------------------------------
# PR body: evidence and owner QA
# --------------------------------------------------------------------------

GATES: list[tuple[str, str, re.Pattern[str]]] = [
    ("G1", "Build all app targets", re.compile(r"\*\* BUILD SUCCEEDED \*\*")),
    ("G2", "Build the MCP bridge", re.compile(r"Build complete!")),
    ("G3", "FireLogic tests", re.compile(
        r"Executed \d+ tests?, with 0 failures|Test run with \d+ tests? passed")),
    ("G4", "Release script tests", re.compile(r"Ran \d+ tests?[\s\S]*^OK\b", re.MULTILINE)),
    ("G5", "SwiftLint", re.compile(r"Found 0 violations")),
]


def check_evidence(pr_body: str, repo: str) -> list[str]:
    sections = markdown_sections(pr_body, 3)
    run_url = re.compile(rf"https://github\.com/{re.escape(repo)}/actions/runs/\d+")
    errors = []
    for gate_id, name, marker in GATES:
        key = next((k for k in sections if re.match(rf"{gate_id.lower()}\b", k)), None)
        if key is None:
            errors.append(f"PR body has no `### {gate_id} {name}` section.")
            continue
        content = sections[key]
        if "<paste" in content.lower():
            errors.append(f"{gate_id}: still contains the template placeholder.")
        elif not (marker.search(content) or run_url.search(content)):
            errors.append(
                f"{gate_id}: no passing output (expected `{marker.pattern}`) "
                f"and no link to a CI run of {repo}."
            )
    return errors


SMOKE_ROWS = [f"S{i}" for i in range(1, 8)]


def parse_qa_table(section: str) -> dict[str, str]:
    """Row id (first cell, upper-case) -> result (last cell, upper-case)."""
    rows = {}
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: ") or cells[0].lower() in ("#", "id"):
            continue
        rows[cells[0].upper()] = cells[-1].upper()
    return rows


def check_owner_qa(pr_body: str, level: str, head_sha: str) -> list[str]:
    if level == "none":
        return []
    section = markdown_sections(pr_body, 2).get("manual qa", "")
    if not section:
        return ["PR body has no `## Manual QA` section."]
    errors = []
    tested = re.search(r"Tested commit:\s*`?([0-9a-f]{7,40})`?", section, re.IGNORECASE)
    if not tested:
        errors.append("Manual QA: no `Tested commit: <sha>` line. The owner fills it in after QA.")
    elif not head_sha.lower().startswith(tested.group(1).lower()):
        errors.append(
            f"Manual QA was run on `{tested.group(1)}`, but the PR head is now `{head_sha[:12]}`. "
            "Re-run QA on the new commit."
        )
    if not re.search(r"Tested on:\s*macOS\s*\d+", section, re.IGNORECASE):
        errors.append("Manual QA: no `Tested on: macOS <version>` line.")
    rows = parse_qa_table(section)
    required = list(SMOKE_ROWS)
    for row in required:
        if row not in rows:
            errors.append(f"Manual QA: smoke row {row} is missing.")
    if level == "issue" and not any(re.fullmatch(r"Q\d+", r) for r in rows):
        errors.append("Manual QA: the issue asks for issue-specific rows (Q1, Q2, ...), none found.")
    for row, result in rows.items():
        if result.startswith("FAIL"):
            errors.append(f"Manual QA: {row} failed.")
        elif not (result.startswith("PASS") or result.startswith("N/A")):
            errors.append(f"Manual QA: {row} is `{result or 'empty'}`, waiting for the owner.")
    return errors


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def _git_bytes(rev: str, path: str) -> Optional[bytes]:
    proc = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True)
    return proc.stdout if proc.returncode == 0 else None


def _api(repo: str, path: str) -> dict:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def find_agent_issue(repo: str, pr_body: str, result: Result) -> Optional[dict]:
    issues = []
    for number in linked_issue_numbers(pr_body):
        try:
            issue = _api(repo, f"issues/{number}")
        except Exception as error:  # noqa: BLE001 — report and keep going
            result.errors.append(f"Could not read issue #{number}: {error}")
            continue
        if "pull_request" not in issue and is_agent_issue(issue):
            issues.append(issue)
    if len(issues) > 1:
        result.errors.append(
            "An agent PR must close exactly one agent-task issue, found "
            + ", ".join(f"#{i['number']}" for i in issues) + "."
        )
    return issues[0] if issues else None


def run(command: str) -> Result:
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
        event = json.load(handle)
    pr = event["pull_request"]
    repo = os.environ["GITHUB_REPOSITORY"]
    body = pr.get("body") or ""
    labels = {label["name"] for label in pr.get("labels", [])}
    result = Result()

    issue = find_agent_issue(repo, body, result)
    if issue:
        result.notes.append(f"Agent PR for issue #{issue['number']}: {issue.get('title', '')}")
    else:
        result.notes.append(
            "No linked agent-task issue: treated as an owner PR (only protected paths are checked)."
        )

    if command == "safety":
        base, head = pr["base"]["sha"], pr["head"]["sha"]
        changed = [p for p in _git("diff", "--name-only", "--no-renames", f"{base}...{head}").splitlines() if p]
        diff_lines = parse_unified_diff(_git("diff", "-U0", "--no-renames", f"{base}...{head}"))
        bootstrap = _git_bytes(base, "scripts/agent_gates.py") is None
        if bootstrap:
            result.notes.append("Bootstrap: the base branch has no gate script yet, gate files are not protected.")
        violations = check_protected(
            changed, diff_lines, lambda rev, path: _git_bytes(base if rev == "base" else head, path), bootstrap
        )
        if issue:
            violations += check_scope(changed, allowed_paths(issue.get("body") or ""))
            violations += check_weakening(diff_lines)
        if violations and OVERRIDE_LABEL in labels:
            result.notes.append(f"`{OVERRIDE_LABEL}` label present; the owner accepted these:")
            result.notes += [f"- {v}" for v in violations]
        else:
            result.errors += violations
    elif command == "evidence":
        if issue:
            result.errors += check_evidence(body, repo)
    elif command == "qa":
        if issue:
            level = qa_level(issue.get("body") or "")
            result.notes.append(f"Manual QA level from the issue: {level}")
            result.errors += check_owner_qa(body, level, pr["head"]["sha"])
    return result


def report(command: str, result: Result) -> None:
    status = "passed" if result.ok else "FAILED"
    lines = [f"## Agent gates: {command} {status}", ""]
    lines += result.notes
    if result.errors:
        lines += ["", "**Fix these:**"] + [f"- {e}" for e in result.errors]
    lines += ["", f"Contract: `{CONTRACT}`"]
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    for error in result.errors:
        print(f"::error::{error}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["safety", "evidence", "qa"])
    args = parser.parse_args(argv)
    result = run(args.command)
    report(args.command, result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
