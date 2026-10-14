from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CACHE = Path.home() / ".claude" / "cache"
CACHE_ENV = "CLAUDE_ANALYZER_CACHE"
UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def cache_dir() -> Path:
    override = os.environ.get(CACHE_ENV)
    return Path(override) if override else DEFAULT_CACHE


@dataclass(frozen=True, slots=True)
class AnalyzerBatch:
    directory: Path
    session_id: str

    @property
    def _stem(self) -> str:
        return f"analyzer-batch-{UNSAFE.sub('', self.session_id) or 'default'}"

    @property
    def _paths_file(self) -> Path:
        return self.directory / f"{self._stem}.txt"

    @property
    def _last_file(self) -> Path:
        return self.directory / f"{self._stem}.last"

    def record(self, path: Path) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._paths_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{path}\n")

    def pending(self) -> tuple[Path, ...]:
        if not self._paths_file.is_file():
            return ()
        lines = self._paths_file.read_text(encoding="utf-8").splitlines()
        unique = dict.fromkeys(Path(line) for line in lines if line.strip())
        return tuple(path for path in unique if path.is_file())

    def clear(self) -> None:
        self._paths_file.unlink(missing_ok=True)
        self._last_file.unlink(missing_ok=True)

    def replace(self, paths: tuple[Path, ...]) -> None:
        if not paths:
            self.clear()
            return
        self._last_file.unlink(missing_ok=True)
        staged = self._paths_file.with_suffix(".tmp")
        staged.write_text("".join(f"{path}\n" for path in paths), encoding="utf-8")
        os.replace(staged, self._paths_file)

    def remember(self, digest: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._last_file.write_text(digest, encoding="utf-8")

    def remembered(self) -> str:
        return (
            self._last_file.read_text(encoding="utf-8")
            if self._last_file.is_file()
            else ""
        )
