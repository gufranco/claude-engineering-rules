from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "mock-internal-blocker"
JS_MOCK = "jest" + ".mock"
PY_PATCH = "pat" + "ch"


def _write(tool_use, path: str, content: str):
    return tool_use("Write", {"file_path": path, "content": content})


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("/repo/test_billing.py", f'@{PY_PATCH}("app.services.billing.charge")\n'),
        (
            "/repo/tests/test_user.py",
            f'{PY_PATCH}("app.repositories.user_repo.Repo.get")\n',
        ),
        ("/repo/tests/test_cache.py", f'{PY_PATCH}("redis.Redis")\n'),
        ("/repo/tests/test_db.py", f'{PY_PATCH}("myapp.db.session")\n'),
        ("/repo/src/queue.test.ts", f'{JS_MOCK}("bullmq")\n'),
    ],
    ids=["root-test-file", "repository", "redis-module", "db-module", "bullmq"],
)
def test_mocking_internal_infrastructure_is_blocked(tool_use, run_hook, path, content):
    # Arrange
    payload = _write(tool_use, path, content)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("/repo/tests/test_http.py", f'{PY_PATCH}("requests.get")\n'),
        ("/repo/src/ui.test.ts", f'{JS_MOCK}("bullet-points")\n'),
        ("/repo/src/ui.test.ts", f'{JS_MOCK}("redisx")\n'),
    ],
    ids=["third-party-http", "bullet-prefix", "redis-prefix"],
)
def test_mocking_third_party_code_is_allowed(tool_use, run_hook, path, content):
    # Arrange
    payload = _write(tool_use, path, content)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
