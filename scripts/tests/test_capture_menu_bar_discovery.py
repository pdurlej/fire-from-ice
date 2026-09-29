import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "capture_menu_bar_discovery.py"
SPEC = importlib.util.spec_from_file_location("capture_menu_bar_discovery", SCRIPT)
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)


class CaptureMenuBarDiscoveryTests(unittest.TestCase):
    def run_capture(self, output, error="", returncode=0, timeout=False):
        process = MagicMock(returncode=returncode)
        process.poll.return_value = returncode
        process.communicate.side_effect = (
            [subprocess.TimeoutExpired("log", 1), (output, error)]
            if timeout else [(output, error)]
        )
        with patch.object(capture.subprocess, "Popen", return_value=process), \
                patch.object(capture.sys, "argv", [str(SCRIPT), "--seconds", "1"]), \
                patch("builtins.print") as printer:
            result = capture.main()
        return result, printer, process

    def test_empty_trace_is_not_reported_as_success(self):
        result, _, _ = self.run_capture(
            'Filtering the log data using "composedMessage CONTAINS \\"[FireDiscovery25]\\""\n'
        )
        self.assertEqual(result, 2)

    def test_only_tagged_events_are_emitted(self):
        event = "[FireDiscovery25] stage=cache-rejected reason=missing-hidden-control"
        result, printer, _ = self.run_capture(f"unrelated private message\n{event}\n")
        self.assertEqual(result, 0)
        printer.assert_any_call(event)
        self.assertFalse(any("unrelated private message" in str(call) for call in printer.call_args_list))

    def test_capture_timeout_stops_only_the_log_reader(self):
        result, _, process = self.run_capture(
            "[FireDiscovery25] stage=cache-check changed=0 managed=0 retry=1",
            returncode=-15,
            timeout=True,
        )
        self.assertEqual(result, 0)
        process.terminate.assert_called_once()

    def test_log_access_failure_is_not_silenced(self):
        result, _, _ = self.run_capture("", "Operation not permitted", returncode=1)
        self.assertEqual(result, 1)
