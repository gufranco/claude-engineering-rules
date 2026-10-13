from __future__ import annotations

import sys

try:
    import coverage

    coverage.process_startup()
except Exception as error:
    sys.stderr.write(f"sitecustomize: coverage startup failed: {error!r}\n")
