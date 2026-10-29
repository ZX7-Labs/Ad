"""Fail-closed parser for the final unittest outcome in a release log.

A successful test process may legitimately finish with ``OK (skipped=N)``.
Do not turn a failed or truncated test log into a successful release receipt.
"""
from __future__ import annotations

import re

_RUN = re.compile(r"Ran ([0-9]+) tests? in [0-9]+(?:\.[0-9]+)?s")
_OK = re.compile(r"OK(?: \(skipped=([0-9]+)\))?")


def parse_unittest_summary(log: str) -> tuple[int, int]:
    """Return (executed, skipped) from the last complete unittest summary.

    Raise ValueError when the final outcome is not unambiguously successful or
    when the reported skipped count disagrees with verbose test output.
    """
    if not isinstance(log, str):
        raise ValueError("Test output must be text")
    lines = log.splitlines()
    runs = [(index, match) for index, line in enumerate(lines)
            if (match := _RUN.fullmatch(line.strip()))]
    if not runs:
        raise ValueError("No complete unittest run summary")
    index, run = runs[-1]
    statuses = [line.strip() for line in lines[index + 1:] if line.strip()]
    outcome = _OK.fullmatch(statuses[0]) if statuses else None
    if outcome is None:
        raise ValueError("Final unittest run is not successful")
    total = int(run.group(1))
    skipped = int(outcome.group(1) or 0)
    if total == 0 or skipped > total:
        raise ValueError("Invalid unittest run or skip totals")
    # In the release job unittest runs with -v; the verbose markers are
    # independently checked instead of trusting a fabricated OK footer.
    actual_skipped = sum(" ... skipped " in line for line in lines[:index])
    if actual_skipped != skipped:
        raise ValueError("Verbose skipped-test count disagrees with summary")
    return total, skipped
