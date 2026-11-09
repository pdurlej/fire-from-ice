from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import agent_gates as gates  # noqa: E402

REPO = "pdurlej/fire-from-ice"
HEAD = "0123456789abcdef0123456789abcdef01234567"

ISSUE_BODY = """### Goal

Make the thing work.

### Allowed paths

```text
Ice/MenuBar/Hiding/**
FireLogic/Sources/FireLogic/Allowlist.swift
FireLogic/Tests/
```

### Manual QA

smoke + issue rows (the issue lists extra rows)
"""

PLIST = b"""<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
<key>SUFeedURL</key><string>https://example.invalid/appcast.xml</string>
<key>SUPublicEDKey</key><string>%s</string>
<key>CFBundleIdentifier</key><string>com.jordanbaird.Ice</string>
</dict></plist>"""


def evidence_body(**override: str) -> str:
    blocks = {
        "G1": "```\n** BUILD SUCCEEDED **\n```",
        "G2": "```\nBuild complete! (3.1s)\n```",
        "G3": "```\nExecuted 42 tests, with 0 failures (0 unexpected) in 0.2 seconds\n```",
        "G4": "```\nRan 7 tests in 0.01s\n\nOK\n```",
        "G5": "```\nDone linting! Found 0 violations, 0 serious in 301 files.\n```",
    }
    blocks.update(override)
    parts = ["## Gate evidence", ""]
    for gate_id, name, _ in gates.GATES:
        parts += [f"### {gate_id} {name}", blocks[gate_id], ""]
    return "\n".join(parts)


def qa_body(rows: dict[str, str], tested: str = HEAD[:9], macos: str = "27.2") -> str:
    lines = [
        "## Manual QA",
        "",
        f"Tested on: macOS {macos}",
        f"Tested commit: `{tested}`",
        "",
        "| # | Step | Result |",
        "|---|------|--------|",
    ]
    lines += [f"| {row} | something | {result} |" for row, result in rows.items()]
    return "\n".join(lines)


ALL_SMOKE_PASS = {row: "PASS" for row in gates.SMOKE_ROWS}


class LinkingTests(unittest.TestCase):
    def test_closing_keywords_and_urls(self):
        body = "Closes #12\nfixes: #3\nResolves https://github.com/pdurlej/fire-from-ice/issues/40\nsee #99"
        self.assertEqual(gates.linked_issue_numbers(body), [12, 3, 40])

    def test_template_comment_is_ignored(self):
        self.assertEqual(gates.linked_issue_numbers("<!-- Closes #1 -->\nCloses #7"), [7])

    def test_agent_issue_detection(self):
        self.assertTrue(gates.is_agent_issue({"labels": [{"name": "agent-task"}], "body": ""}))
        self.assertTrue(gates.is_agent_issue({"labels": [], "body": ISSUE_BODY}))
        self.assertFalse(gates.is_agent_issue({"labels": [{"name": "Bug"}], "body": "### Description\nx"}))


class ScopeTests(unittest.TestCase):
    def test_allowed_paths_parsed_from_issue_form(self):
        self.assertEqual(
            gates.allowed_paths(ISSUE_BODY),
            ["Ice/MenuBar/Hiding/**", "FireLogic/Sources/FireLogic/Allowlist.swift", "FireLogic/Tests/"],
        )

    def test_globs(self):
        self.assertTrue(gates.glob_to_regex("Ice/**").match("Ice/a/b/c.swift"))
        self.assertTrue(gates.glob_to_regex("Ice/**/*.swift").match("Ice/x.swift"))
        self.assertTrue(gates.glob_to_regex("Ice/*.swift").match("Ice/x.swift"))
        self.assertFalse(gates.glob_to_regex("Ice/*.swift").match("Ice/sub/x.swift"))
        self.assertTrue(gates.glob_to_regex("FireLogic/Tests/").match("FireLogic/Tests/A/B.swift"))

    def test_out_of_scope_file_fails(self):
        errors = gates.check_scope(
            ["Ice/MenuBar/Hiding/Backend.swift", "Ice/Settings/Pane.swift"], gates.allowed_paths(ISSUE_BODY)
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("Ice/Settings/Pane.swift", errors[0])

    def test_missing_allowed_paths_fails(self):
        self.assertTrue(gates.check_scope(["a.swift"], []))

    def test_qa_level(self):
        self.assertEqual(gates.qa_level(ISSUE_BODY), "issue")
        self.assertEqual(gates.qa_level("### Manual QA\n\nnone (no runtime change)"), "none")
        self.assertEqual(gates.qa_level("### Manual QA\n\nsmoke"), "smoke")
        self.assertEqual(gates.qa_level("no section at all"), "smoke")


class ProtectedTests(unittest.TestCase):
    def check(self, files, diff="", base=None, head=None, bootstrap=False):
        lines = gates.parse_unified_diff(diff)
        files_at = {"base": base or {}, "head": head or {}}
        return gates.check_protected(files, lines, lambda rev, path: files_at[rev].get(path), bootstrap)

    def test_release_and_signing_files(self):
        errors = self.check([
            "ExportOptions.plist",
            "Ice/Ice.entitlements",
            "scripts/publish-appcast.sh",
            ".github/workflows/build-dmg.yml",
            ".swiftlint.yml",
            "Ice/Main.swift",
        ])
        self.assertEqual(len(errors), 5)

    def test_gate_files_protected_except_bootstrap(self):
        self.assertTrue(self.check(["scripts/agent_gates.py"]))
        self.assertFalse(self.check(["scripts/agent_gates.py"], bootstrap=True))
        self.assertTrue(self.check([".github/workflows/agent-gates.yml"], bootstrap=True))

    def test_pbxproj_version_bump(self):
        diff = (
            "diff --git a/Ice.xcodeproj/project.pbxproj b/Ice.xcodeproj/project.pbxproj\n"
            "--- a/Ice.xcodeproj/project.pbxproj\n+++ b/Ice.xcodeproj/project.pbxproj\n"
            "@@ -523 +523 @@\n-\t\t\t\tCURRENT_PROJECT_VERSION = 1181;\n+\t\t\t\tCURRENT_PROJECT_VERSION = 1182;\n"
        )
        self.assertEqual(len(self.check([gates.PBXPROJ], diff)), 2)

    def test_pbxproj_other_change_is_fine(self):
        diff = (
            "--- a/Ice.xcodeproj/project.pbxproj\n+++ b/Ice.xcodeproj/project.pbxproj\n"
            "+\t\t\t\tSWIFT_VERSION = 6.0;\n"
        )
        self.assertEqual(self.check([gates.PBXPROJ], diff), [])

    def test_info_plist_keys(self):
        path = "Ice/Resources/Info.plist"
        same = self.check([path], base={path: PLIST % b"key"}, head={path: PLIST % b"key"})
        changed = self.check([path], base={path: PLIST % b"key"}, head={path: PLIST % b"other"})
        self.assertEqual(same, [])
        self.assertEqual(len(changed), 1)
        self.assertIn("SUPublicEDKey", changed[0])


class WeakeningTests(unittest.TestCase):
    def test_added_disables_and_skips(self):
        diff = (
            "--- a/Ice/A.swift\n+++ b/Ice/A.swift\n"
            "+// swiftlint:disable force_unwrapping\n"
            "-// swiftlint:disable old_rule\n"
            "--- a/FireLogic/Tests/FireLogicTests/T.swift\n+++ b/FireLogic/Tests/FireLogicTests/T.swift\n"
            "+        throw XCTSkip(\"flaky\")\n"
        )
        errors = gates.check_weakening(gates.parse_unified_diff(diff))
        self.assertEqual(len(errors), 2)


class EvidenceTests(unittest.TestCase):
    def test_full_evidence_passes(self):
        self.assertEqual(gates.check_evidence(evidence_body(), REPO), [])

    def test_ci_link_is_accepted(self):
        body = evidence_body(G1=f"Not run locally (Linux). CI: https://github.com/{REPO}/actions/runs/123")
        self.assertEqual(gates.check_evidence(body, REPO), [])

    def test_failed_or_placeholder_output_fails(self):
        body = evidence_body(G3="```\nExecuted 42 tests, with 1 failure\n```", G5="```\n<paste the tail>\n```")
        errors = gates.check_evidence(body, REPO)
        self.assertEqual(len(errors), 2)

    def test_missing_section_fails(self):
        body = evidence_body().replace("### G2 Build the MCP bridge", "### Bridge")
        self.assertEqual(len(gates.check_evidence(body, REPO)), 1)


class OwnerQATests(unittest.TestCase):
    def test_none_level_skips(self):
        self.assertEqual(gates.check_owner_qa("", "none", HEAD), [])

    def test_all_pass(self):
        self.assertEqual(gates.check_owner_qa(qa_body(ALL_SMOKE_PASS), "smoke", HEAD), [])

    def test_pending_rows_wait_for_owner(self):
        rows = dict(ALL_SMOKE_PASS, S3="pending")
        errors = gates.check_owner_qa(qa_body(rows), "smoke", HEAD)
        self.assertEqual(len(errors), 1)
        self.assertIn("waiting for the owner", errors[0])

    def test_fail_row(self):
        rows = dict(ALL_SMOKE_PASS, S5="FAIL - bar flashes")
        self.assertIn("Manual QA: S5 failed.", gates.check_owner_qa(qa_body(rows), "smoke", HEAD))

    def test_stale_commit(self):
        errors = gates.check_owner_qa(qa_body(ALL_SMOKE_PASS, tested="fedcba9"), "smoke", HEAD)
        self.assertEqual(len(errors), 1)
        self.assertIn("Re-run QA", errors[0])

    def test_issue_rows_required(self):
        self.assertEqual(len(gates.check_owner_qa(qa_body(ALL_SMOKE_PASS), "issue", HEAD)), 1)
        rows = dict(ALL_SMOKE_PASS, Q1="PASS")
        self.assertEqual(gates.check_owner_qa(qa_body(rows), "issue", HEAD), [])

    def test_missing_smoke_row(self):
        rows = {k: v for k, v in ALL_SMOKE_PASS.items() if k != "S7"}
        self.assertEqual(len(gates.check_owner_qa(qa_body(rows), "smoke", HEAD)), 1)


if __name__ == "__main__":
    unittest.main()
