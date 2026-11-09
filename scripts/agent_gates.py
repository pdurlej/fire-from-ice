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

The workflow runs on `pull_request_target`, so this file always comes from the
base branch and a PR can't rewrite the checks that judge it. The PR's code is
never checked out or executed: the diff, file contents and runs are read
through the GitHub API.

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
import urllib.parse
import sys
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

# Files that implement the gates.
GATE_FILES: list[str] = [
    ".github/workflows/agent-gates.yml",
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
# (pattern, label, only in test files). `.disabled(` is also a SwiftUI
# modifier, so it only counts inside tests.
WEAKENING_PATTERNS: list[tuple[re.Pattern[str], str, bool]] = [
    (re.compile(r"swiftlint:disable"), "new `swiftlint:disable`", False),
    (re.compile(r"\bXCTSkip\b"), "skipped test (`XCTSkip`)", False),
    (re.compile(r"\.disabled\s*\("), "disabled test (`.disabled(...)`)", True),
    (re.compile(r"\bfunc\s+DISABLED_|\bfunc\s+xtest"), "disabled test function", True),
]


def is_test_path(path: str) -> bool:
    return bool(re.search(r"(^|/)(Tests|tests)/", path))


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def protected_file_reason(path: str) -> Optional[str]:
    if path in GATE_FILES:
        return "quality-gate implementation"
    for pattern, reason in PROTECTED_FILES:
        if re.search(pattern, path):
            return reason
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


def patch_lines(patch: Optional[str]) -> list[str]:
    """Changed lines of one file's patch as the GitHub API returns it."""
    return [l for l in (patch or "").splitlines() if l[:1] in ("+", "-")]


def check_protected(
    changed_files: Iterable[str],
    diff_lines: dict[str, list[str]],
    read_at: Callable[[str, str], Optional[bytes]],
) -> list[str]:
    """read_at(rev, path) returns file bytes at 'base' (the merge base) or
    'head', or None."""
    errors = []
    for path in sorted(set(changed_files)):
        reason = protected_file_reason(path)
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
            for pattern, label, tests_only in WEAKENING_PATTERNS:
                if tests_only and not is_test_path(path):
                    continue
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


def issue_qa_rows(issue_body: str) -> list[str]:
    """Row ids (Q1, Q2, ...) the issue lists under `### Issue QA rows`."""
    section = markdown_sections(issue_body, 3).get("issue qa rows", "")
    return list(dict.fromkeys(re.findall(r"^\s*\|\s*(Q\d+)\s*\|", section, re.MULTILINE | re.IGNORECASE)))


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


# The CI workflow whose green run may stand in for local output.
GATE_WORKFLOWS = {"G1": "Verify macOS", "G2": "Verify macOS", "G3": "Verify macOS",
                  "G4": "Verify macOS", "G5": "Lint Swift Files"}
NO_SWIFT_RE = re.compile(r"\bno swift (?:files? )?chang", re.IGNORECASE)


def check_evidence(
    pr_body: str,
    repo: str,
    check_run: Optional[Callable[[int, str], Optional[str]]] = None,
    swift_changed: bool = True,
) -> list[str]:
    """check_run(run_id, workflow_name) returns an error, or None when that run
    is a green run of that workflow on the PR's head commit."""
    sections = markdown_sections(pr_body, 3)
    run_url = re.compile(rf"https://github\.com/{re.escape(repo)}/actions/runs/(\d+)")
    errors = []
    for gate_id, name, marker in GATES:
        key = next((k for k in sections if re.match(rf"{gate_id.lower()}\b", k)), None)
        if key is None:
            errors.append(f"PR body has no `### {gate_id} {name}` section.")
            continue
        content = sections[key]
        if "<paste" in content.lower():
            errors.append(f"{gate_id}: still contains the template placeholder.")
            continue
        if marker.search(content):
            continue
        if gate_id == "G5" and not swift_changed and NO_SWIFT_RE.search(content):
            continue
        runs = [int(m) for m in run_url.findall(content)]
        if not runs:
            errors.append(
                f"{gate_id}: no passing output (expected `{marker.pattern}`) "
                f"and no link to a CI run of {repo}."
            )
            continue
        run_errors = [check_run(r, GATE_WORKFLOWS[gate_id]) for r in runs] if check_run else []
        if run_errors and all(run_errors):
            errors.append(f"{gate_id}: {run_errors[0]}")
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


def check_owner_qa(pr_body: str, level: str, head_sha: str, issue_rows: Iterable[str] = ()) -> list[str]:
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
    issue_rows = [r.upper() for r in issue_rows]
    if level == "issue":
        for row in issue_rows:
            if row not in rows:
                errors.append(f"Manual QA: issue row {row} is missing.")
        if not issue_rows and not any(re.fullmatch(r"Q\d+", r) for r in rows):
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


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


def _require(pattern: re.Pattern[str], value: str, what: str) -> str:
    if not pattern.fullmatch(value or ""):
        raise SystemExit(f"Refusing unexpected {what}: {value!r}")
    return value


def _gh(path: str, raw: bool = False) -> subprocess.CompletedProcess:
    """GET a REST path with the gh CLI (preinstalled on GitHub runners, uses GH_TOKEN)."""
    args = ["gh", "api"]
    if raw:
        args += ["-H", "Accept: application/vnd.github.raw"]
    return subprocess.run([*args, path], capture_output=True, timeout=60)


def _gh_json(path: str) -> dict:
    proc = _gh(path)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or f"gh api {path} failed")
    return json.loads(proc.stdout)


def _issue(repo: str, number: int) -> dict:
    return _gh_json(f"repos/{repo}/issues/{int(number)}")


def _content(repo: str, sha: str, path: str) -> Optional[bytes]:
    proc = _gh(f"repos/{repo}/contents/{urllib.parse.quote(path)}?ref={sha}", raw=True)
    return proc.stdout if proc.returncode == 0 else None


def _compare(repo: str, base: str, head: str) -> tuple[str, list[dict]]:
    """(merge base sha, changed files with patches) for the PR's three-dot diff."""
    data = _gh_json(f"repos/{repo}/compare/{base}...{head}")
    return data["merge_base_commit"]["sha"], data.get("files", [])


def _changed_paths(files: list[dict]) -> list[str]:
    paths = []
    for entry in files:
        paths.append(entry["filename"])
        if entry.get("previous_filename"):
            paths.append(entry["previous_filename"])
    return paths


def _run_checker(repo: str, head: str) -> Callable[[int, str], Optional[str]]:
    def check(run_id: int, workflow: str) -> Optional[str]:
        try:
            data = _gh_json(f"repos/{repo}/actions/runs/{int(run_id)}")
        except Exception as error:  # noqa: BLE001
            return f"CI run {run_id} could not be read ({error})."
        if data.get("name") != workflow:
            return f"CI run {run_id} is `{data.get('name')}`, expected `{workflow}`."
        if data.get("head_sha") != head:
            return f"CI run {run_id} is for commit {str(data.get('head_sha'))[:12]}, not the PR head {head[:12]}."
        if data.get("conclusion") != "success":
            return f"CI run {run_id} is `{data.get('conclusion') or data.get('status')}`, not green."
        return None
    return check


def find_agent_issue(repo: str, pr_body: str, result: Result) -> Optional[dict]:
    issues = []
    for number in linked_issue_numbers(pr_body):
        try:
            issue = _issue(repo, number)
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
    repo = _require(REPO_RE, os.environ["GITHUB_REPOSITORY"], "repository")
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

    base = _require(SHA_RE, pr["base"]["sha"], "base sha")
    head = _require(SHA_RE, pr["head"]["sha"], "head sha")

    if command == "safety":
        merge_base, files = _compare(repo, base, head)
        changed = _changed_paths(files)
        diff_lines = {entry["filename"]: patch_lines(entry.get("patch")) for entry in files}
        violations = []
        if len(files) >= 300:
            violations.append("The PR changes 300 or more files, too many to inspect. Split it.")
        if PBXPROJ in diff_lines and not diff_lines[PBXPROJ]:
            violations.append(f"`{PBXPROJ}` changed but its diff is too large to inspect.")
        violations += check_protected(
            changed, diff_lines, lambda rev, path: _content(repo, merge_base if rev == "base" else head, path)
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
            _, files = _compare(repo, base, head)
            swift_changed = any(p.endswith(".swift") for p in _changed_paths(files))
            result.errors += check_evidence(body, repo, _run_checker(repo, head), swift_changed)
    elif command == "qa":
        if issue:
            issue_body = issue.get("body") or ""
            level = qa_level(issue_body)
            result.notes.append(f"Manual QA level from the issue: {level}")
            result.errors += check_owner_qa(body, level, head, issue_qa_rows(issue_body))
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
