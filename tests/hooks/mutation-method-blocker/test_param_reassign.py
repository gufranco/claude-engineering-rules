"""Parameter reassignment coverage.

Item 122 of the plan. Validates direct parameter reassignment in function
declarations and arrow functions, and confirms the `no-param-reassign`
allowlist names (acc, ctx, req, etc.) still pass for property mutation.
"""

from __future__ import annotations

import pytest

from conftest import make_write_payload

PARAM_REASSIGN_BLOCKED: list[tuple[str, str]] = [
    (
        "function-direct-assign",
        """function update(items) {
  items = items || [];
  return items;
}
""",
    ),
    (
        "function-compound-assign",
        """function bump(count) {
  count += 1;
  return count;
}
""",
    ),
    (
        "arrow-direct-assign",
        """const update = (items) => {
  items = items || [];
  return items;
};
""",
    ),
    (
        "arrow-property-assign-non-allowlist",
        """const apply = (custom) => {
  custom.flag = true;
};
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), PARAM_REASSIGN_BLOCKED)
def test_param_reassignment_is_blocked(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, f"{label}: expected block, got {code}\n{stderr}"
    assert ("param.reassign" in stderr) or ("property." in stderr), (
        f"{label}: no relevant detector\n{stderr}"
    )


PARAM_REASSIGN_ALLOWED: list[tuple[str, str]] = [
    (
        "acc-property",
        """function totals(items) {
  return items.reduce((acc, item) => {
    acc.count += 1;
    acc.sum += item.value;
    return acc;
  }, { count: 0, sum: 0 });
}
""",
    ),
    (
        "ctx-property",
        """function attachUser(ctx, next) {
  ctx.user = loadUser();
  return next();
}
""",
    ),
    (
        "req-property",
        """function middleware(req) {
  req.id = makeId();
}
""",
    ),
    (
        "res-property",
        """function attachHeader(res) {
  res.headerValue = 'value';
}
""",
    ),
    (
        "draft-property",
        """function update(state) {
  return produce(state, (draft) => {
    draft.count = state.count + 1;
  });
}
""",
    ),
    (
        "copy-and-mutate",
        """function tagged(items) {
  const copy = [...items];
  return copy;
}
""",
    ),
]


@pytest.mark.parametrize(("label", "snippet"), PARAM_REASSIGN_ALLOWED)
def test_param_reassignment_allowlist_passes(run_hook, label, snippet):
    # Arrange
    payload = make_write_payload("/repo/src/app.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"{label}: unexpected block\n{stderr}"
