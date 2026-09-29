#!/usr/bin/env python3
"""Capture only Fire #25 discovery diagnostics for a bounded local reproduction."""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=30, help="Capture duration (1-120 seconds)")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error("--seconds must be between 1 and 120")

    print(f"Capture started for {args.seconds} seconds. Click Fire once, then reopen it after 10 seconds.", flush=True)
    command = [
        "/usr/bin/log", "stream", "--style", "compact", "--level", "debug",
        "--predicate", 'eventMessage CONTAINS "[FireDiscovery25]"',
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timed_out = False
    try:
        try:
            output, error = process.communicate(timeout=args.seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                output, error = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                output, error = process.communicate()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()

    if process.returncode != 0 and not (timed_out and process.returncode in (-15, -9)):
        print(f"log stream failed (exit {process.returncode}): {error.strip()}", file=sys.stderr)
        return 1

    # Only emit the numeric/enum diagnostics from the patched app and helper;
    # omit unrelated system messages and log-stream headers.
    lines = [line for line in output.splitlines() if "[FireDiscovery25] stage=" in line]
    for line in lines:
        print(line)
    if not lines:
        print("No FireDiscovery25 events captured. Use the instrumented build and reproduce while capture is active.", file=sys.stderr)
        return 2
    print(f"Captured {len(lines)} diagnostic events. This is a trace, not a PASS verdict.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
