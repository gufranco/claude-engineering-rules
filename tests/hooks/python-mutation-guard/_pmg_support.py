from __future__ import annotations

HOOK = "python-mutation-guard"


PARAM_MUTATION = (
    "def add_tag(items: list[str], tag: str) -> list[str]:\n"
    "    items.append(tag)\n"
    "    return items\n"
)


OFFENDING = PARAM_MUTATION


OFFENDING_PATH = "/repo/app/services/tags.py"


def _run_raw(hook_name: str, stdin_text: str, env_extra=None):
    import os
    import subprocess
    import sys
    from pathlib import Path

    hook_path = Path(__file__).resolve().parents[3] / "hooks" / f"{hook_name}.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    for key in ("COVERAGE_PROCESS_START", "PYTHONPATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )
    return proc.returncode, proc.stderr
