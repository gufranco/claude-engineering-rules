"""Unit tests for hooks/_profile.py.

Run: python3 -m unittest hooks/test_profile.py
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import unittest
from typing import Iterator

_HERE = pathlib.Path(__file__).parent
_SPEC = importlib.util.spec_from_file_location("_profile", _HERE / "_profile.py")
assert _SPEC is not None and _SPEC.loader is not None
_profile = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_profile)


class _EnvSandbox:
    """Save and restore environment variables touched by these tests."""

    KEYS = ("CLAUDE_HOOK_PROFILE", "CLAUDE_DISABLED_HOOKS")

    def __enter__(self) -> "_EnvSandbox":
        self._snapshot = {k: os.environ.get(k) for k in self.KEYS}
        for k in self.KEYS:
            os.environ.pop(k, None)
        return self

    def __exit__(self, *_: object) -> None:
        for k, v in self._snapshot.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _envs() -> Iterator[_EnvSandbox]:
    yield _EnvSandbox()


class ProfileSelectionTests(unittest.TestCase):
    def test_default_profile_runs_all_hooks(self) -> None:
        with _EnvSandbox():
            self.assertTrue(_profile.should_run("dangerous-command-blocker"))
            self.assertTrue(_profile.should_run("conventional-commits"))

    def test_minimal_runs_only_critical(self) -> None:
        with _EnvSandbox():
            os.environ["CLAUDE_HOOK_PROFILE"] = "minimal"
            self.assertTrue(_profile.should_run("dangerous-command-blocker"))
            self.assertTrue(_profile.should_run("secret-scanner"))
            self.assertFalse(_profile.should_run("conventional-commits"))
            self.assertFalse(_profile.should_run("banned-phrases-blocker"))

    def test_strict_runs_strict_only_hooks(self) -> None:
        with _EnvSandbox():
            os.environ["CLAUDE_HOOK_PROFILE"] = "strict"
            self.assertTrue(_profile.should_run("any-hook", require_strict=True))

    def test_standard_skips_strict_only_hooks(self) -> None:
        with _EnvSandbox():
            self.assertFalse(_profile.should_run("any-hook", require_strict=True))

    def test_unknown_profile_falls_back_to_standard(self) -> None:
        with _EnvSandbox():
            os.environ["CLAUDE_HOOK_PROFILE"] = "wat"
            self.assertTrue(_profile.should_run("conventional-commits"))

    def test_profile_value_case_insensitive(self) -> None:
        with _EnvSandbox():
            os.environ["CLAUDE_HOOK_PROFILE"] = "MINIMAL"
            self.assertFalse(_profile.should_run("conventional-commits"))


class DisabledListTests(unittest.TestCase):
    def test_disabled_csv_short_circuits(self) -> None:
        with _EnvSandbox():
            os.environ["CLAUDE_DISABLED_HOOKS"] = "conventional-commits,banned-phrases-blocker"
            self.assertFalse(_profile.should_run("conventional-commits"))
            self.assertFalse(_profile.should_run("banned-phrases-blocker"))
            self.assertTrue(_profile.should_run("dangerous-command-blocker"))

    def test_disabled_overrides_critical(self) -> None:
        with _EnvSandbox():
            os.environ["CLAUDE_DISABLED_HOOKS"] = "dangerous-command-blocker"
            self.assertFalse(_profile.should_run("dangerous-command-blocker"))

    def test_disabled_list_handles_whitespace(self) -> None:
        with _EnvSandbox():
            os.environ["CLAUDE_DISABLED_HOOKS"] = "  conventional-commits  ,  banned-phrases-blocker  "
            self.assertFalse(_profile.should_run("conventional-commits"))
            self.assertFalse(_profile.should_run("banned-phrases-blocker"))

    def test_empty_disabled_list_is_noop(self) -> None:
        with _EnvSandbox():
            os.environ["CLAUDE_DISABLED_HOOKS"] = ""
            self.assertTrue(_profile.should_run("conventional-commits"))


if __name__ == "__main__":
    unittest.main()
