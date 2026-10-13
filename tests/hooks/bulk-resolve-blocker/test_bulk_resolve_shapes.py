from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "bulk-resolve-blocker"
GH = "g" + "h"
GLAB = "gl" + "ab"
MUTATION = "resolve" + "ReviewThread"


@pytest.mark.parametrize(
    "command",
    [
        f'{GH} api graphql -f query=\'mutation {{ a: {MUTATION}(input: {{threadId: "1"}}) '
        f'{{ thread {{ id }} }} b: {MUTATION}(input: {{threadId: "2"}}) {{ thread {{ id }} }} }}\'',
        f'{GH} api graphql \\\n  -f query=\'mutation {{\n    a: {MUTATION}(input: {{threadId: "1"}}) {{ thread {{ id }} }}\n'
        f'    b: {MUTATION}(input: {{threadId: "2"}}) {{ thread {{ id }} }}\n  }}\'',
        f'for d in 1 2; do {GLAB} api \\\n  "projects/1/merge_requests/2/discussions/$d" \\\n  -X PUT \\\n  --field resolved=true; done',
    ],
    ids=["aliased-mutations", "multi-line-query", "continued-glab-loop"],
)
def test_resolving_several_threads_at_once_is_blocked(tool_use, run_hook, command):
    # Arrange
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)


def test_resolving_one_thread_across_lines_is_allowed(tool_use, run_hook):
    # Arrange
    command = (
        f"{GH} api graphql \\\n  -f query='mutation {{\n"
        f'    {MUTATION}(input: {{threadId: "1"}}) {{ thread {{ id }} }}\n  }}\''
    )
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_commit_message_naming_the_mutation_is_data(tool_use, run_hook):
    # Arrange
    body = (
        f"fix: count every {MUTATION} in a {GH} api call\n\nfor each thread in a loop"
    )
    payload = tool_use("Bash", {"command": f"git commit -F - <<'EOF'\n{body}\nEOF"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_a_query_fed_to_the_api_by_heredoc_is_still_counted(tool_use, run_hook):
    # Arrange
    query = (
        f'mutation {{ a: {MUTATION}(input: {{threadId: "1"}}) {{ thread {{ id }} }} '
        f'b: {MUTATION}(input: {{threadId: "2"}}) {{ thread {{ id }} }} }}'
    )
    command = f"{GH} api graphql -F query=@- <<'EOF'\n{query}\nEOF"
    payload = tool_use("Bash", {"command": command})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result)
