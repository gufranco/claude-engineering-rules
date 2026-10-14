from __future__ import annotations

import sys
from pathlib import Path

from faker import Faker


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import ai_review  # noqa: E402

LOGIN_LENGTH = 12


def login(faker: Faker) -> str:
    return faker.pystr(min_chars=LOGIN_LENGTH, max_chars=LOGIN_LENGTH).lower()


NOW = 1_800_000_000.0


def run(
    gh: object,
    account: str,
    cache: Path,
    *,
    dry_run: bool = False,
    now: float = NOW,
    number: int = 42,
) -> str:
    return ai_review.request_reviews(
        ai_review.Target(owner="acme", name="app", number=number),
        account=account,
        token="t0k",
        runner=gh,
        cache_path=cache,
        now=now,
        dry_run=dry_run,
    )


__all__ = [
    "HOOKS_DIR",
    "LOGIN_LENGTH",
    "NOW",
    "REPO_ROOT",
    "ai_review",
    "login",
    "run",
]
