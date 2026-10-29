from __future__ import annotations

HOOK = "transaction-scope-guard"
ENFORCE = {"TRANSACTION_SCOPE_ENFORCE": "1"}


def test_a_file_under_a_test_directory_is_skipped(tool_use, run_hook):
    # Arrange
    content = "await prisma.$transaction(async (tx) => { await fetch(url); });\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/src/test/tx.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert (result.code, result.stdout) == (0, "")


def test_suppressed_io_and_an_unclosed_array_transaction_are_not_flagged(
    tool_use, run_hook
):
    # Arrange
    content = (
        "await prisma.$transaction(async (tx) => {\n"
        "  // eslint-disable-next-line\n"
        "  await fetch(url);\n"
        "});\n"
        "await prisma.$transaction([db.user.create({})\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/tx.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert result.code == 0
