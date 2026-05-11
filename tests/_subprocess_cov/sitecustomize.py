"""Auto-start coverage in spawned subprocesses.

Activated when this directory is on PYTHONPATH and COVERAGE_PROCESS_START
is set. The test harness sets both for hook subprocess invocations so that
coverage can stitch hook execution into the parent test run via
`coverage combine`.
"""

from __future__ import annotations

try:
    import coverage

    coverage.process_startup()
except Exception:
    pass
