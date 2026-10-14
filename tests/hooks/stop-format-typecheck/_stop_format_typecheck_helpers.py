from __future__ import annotations
import importlib.util as _util
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from _helpers.cov_env import apply_coverage_env


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hooks"))

HOOK = ROOT / "hooks" / "stop-format-typecheck.py"

TIMEOUT_S = 30

TSC_ARGS = [
    "--no-install",
    "tsc",
    "--noEmit",
    "--incremental",
    "--tsBuildInfoFile",
    "node_modules/.cache/tsc-hook.tsbuildinfo",
]


def _make_recording_stub(bin_dir: Path, name: str, log_file: Path) -> None:
    body = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import sys, json
        from pathlib import Path
        log = Path({str(log_file)!r})
        existing = json.loads(log.read_text()) if log.exists() else []
        existing.append({{"tool": {name!r}, "args": sys.argv[1:]}})
        log.write_text(json.dumps(existing))
        sys.exit(0)
        """
    )
    target = bin_dir / name
    target.write_text(body, encoding="utf-8")
    target.chmod(0o755)


def _run(
    batch: Path,
    *,
    bin_dir: Path | None = None,
    env: dict | None = None,
    stdin: str = "",
) -> subprocess.CompletedProcess[str]:
    merged = {
        **os.environ,
        "CLAUDE_FORMATTER_BATCH": str(batch),
        "CLAUDE_HOOK_AUDIT_DISABLE": "1",
        "CLAUDE_BYPASS_STATE": os.devnull,
    }
    if bin_dir is not None:
        merged["PATH"] = f"{bin_dir}:{merged.get('PATH', '')}"
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=TIMEOUT_S,
        check=False,
    )


def _load(name: str):
    spec = _util.spec_from_file_location(name, str(HOOK))
    assert spec is not None
    assert spec.loader is not None
    module = _util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
