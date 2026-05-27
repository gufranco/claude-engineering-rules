# Python

Cross-language baselines live in [`rules/code-style.md`](../code-style.md). This file covers Python-specific tooling, typing, project layout, testing, and async patterns. Triggered when the task names Python or the project ships a `pyproject.toml`.

## 2026 Tooling Stack

| Concern | Choice | Notes |
|---------|--------|-------|
| Environment and dependencies | `uv` | Replaces pip, pip-tools, poetry, pyenv, and virtualenv in one tool. 10-100x faster than pip. Always commit `uv.lock` |
| Lint and format | `ruff` | Replaces black, isort, flake8, pyupgrade, and most plugins. Run `ruff check` and `ruff format` in CI. Enable all rule sets the project can pass |
| Type check | `pyright` or `mypy --strict` | Pyright is faster and ships in VSCode. `mypy --strict` is the safer baseline. `ty` (Astral) and `pyrefly` (Meta) are emerging alternatives worth trying once they stabilize |
| Testing | `pytest` | With `asyncio_mode = "auto"` to remove per-test `@pytest.mark.asyncio` decorators |
| Validation at boundaries | `pydantic` v2 | The mainstream choice for request, response, and config validation. Adopt the v2 API; v1 is unsupported |

Never use `pip install` directly in a repo with a `pyproject.toml`. Use `uv add`, `uv sync`, and `uv run`. The lockfile must stay authoritative.

## Project Layout

Use the `src` layout, not the flat layout. The `src` layout prevents accidental imports of the in-development package from the project root, which masks packaging bugs that only surface after install.

```
project/
  pyproject.toml          single source of truth for tool config
  uv.lock                 committed
  src/
    package_name/
      __init__.py
      ...
  tests/
    unit/
    integration/
```

`pyproject.toml` centralizes config for `uv`, `ruff`, `pyright` or `mypy`, `pytest`, and any other tool that supports it. Never split tool config across multiple files like `setup.cfg`, `tox.ini`, and `.flake8`.

## Typing Discipline

Type hints are mandatory on every public function, method, and module-level value. Private helpers may omit hints only when the inference is obvious.

- Never use `Any`. Use `object` when the value is genuinely opaque, or a `Protocol` when the shape matters but the concrete type does not
- Narrow `object`, `Unknown`, and union types through `TypeGuard` for runtime checks or `TypeIs` for type-narrowing helpers
- Prefer `typing.Protocol` for structural subtyping over deep inheritance hierarchies. Protocols decouple business logic from concrete implementations and make mocking easier
- Use `Self`, PEP 673 for fluent APIs and class methods that return the instance type
- Use `LiteralString` for SQL fragments, path components, and any string that must come from source code rather than user input
- Use `ParamSpec` and `Concatenate` when typing decorators that wrap functions

The Python equivalent of the TypeScript readonly rule:

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Order:
    id: str
    customer_id: str
    total_cents: int
```

`frozen=True` makes mutation raise `FrozenInstanceError`. `slots=True` removes the per-instance `__dict__` and locks the attribute set. Both should be the default for value-shaped classes.

For collections, use immutable types from `collections.abc`:

| Mutable | Immutable equivalent |
|---------|---------------------|
| `list[T]` parameter | `Sequence[T]` |
| `dict[K, V]` parameter | `Mapping[K, V]` |
| `set[T]` parameter | `AbstractSet[T]` |
| Internal mutable list | `tuple[T, ...]` when the size is unbounded |

The same logic that drives [`typescript-immutability.md`](typescript-immutability.md) applies: parameters and return values are immutable views; mutation lives behind a function boundary.

## Validation at Boundaries

Pydantic models replace ad hoc dict shape checks at every system boundary: HTTP requests, queue messages, config files, third-party API responses.

- Define a model per boundary. Do not reuse the same model for input, storage, and output. Each boundary has its own constraints
- Use `Field` constraints rather than custom validators when the constraint is expressible declaratively
- Brand validated values: `EmailStr`, `HttpUrl`, `PostgresDsn`, or a custom `Annotated[str, AfterValidator(...)]` type. Once branded, downstream code can trust the value without re-validation. The Python analogue of the TypeScript "parse, don't validate" pattern

## Testing

`pytest` is the default. Use `unittest` only when an existing project requires it.

- Enable `asyncio_mode = "auto"` in `pyproject.toml`. Every async test runs without a per-test decorator
- Split `tests/unit` and `tests/integration`. Unit tests run on every save. Integration tests run in CI and pre-push
- Use the `@pytest.fixture` mechanism for setup and teardown. Avoid `setUp`/`tearDown` style classes
- Use real databases for integration tests, not mocks. See the integration-first philosophy in [`rules/testing.md`](../testing.md)
- Use `faker` for fake data generation. Seed deterministically per test file
- For property-based tests, use `hypothesis`. One property test catches a class of bugs that a hundred example-based tests miss

```python
import pytest
from faker import Faker

@pytest.fixture
def fake() -> Faker:
    fake = Faker()
    fake.seed_instance(12345)
    return fake
```

The strict mock policy from [`rules/testing.md`](../testing.md) applies: mock external third-party APIs, time, and randomness. Never mock the database, Redis, the project's own services, or modules under test.

## Async Patterns

- Default to `async def` for I/O-bound work. Use `asyncio.gather` for concurrent operations on the same loop
- For library code that should work under any event loop, use `anyio`. It runs on `asyncio` and `trio` with the same API
- Always handle `asyncio.CancelledError` correctly: re-raise after cleanup, never swallow. Cancellation propagation is what allows graceful shutdown
- Use `asyncio.TaskGroup`, PEP 654, Python 3.11+ instead of bare `create_task` and manual error aggregation. TaskGroup cancels siblings when one task fails, which is almost always what you want
- Never call blocking I/O inside `async def`. Use `asyncio.to_thread` to offload the call. Blocking the event loop stalls every concurrent request

```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(fetch_user(user_id))
    tg.create_task(fetch_orders(user_id))
    tg.create_task(fetch_recommendations(user_id))
```

When TaskGroup is unavailable, use `asyncio.gather(..., return_exceptions=False)` so the first exception cancels the rest.

## Error Handling

- Catch the narrowest exception possible. `except Exception:` is acceptable only at the top of a request handler or background task, where the alternative is a crashed process
- Re-raise after logging, unless the catch site is the final boundary. The error classification rule in [`rules/code-style.md`](../code-style.md) applies
- Use `raise ... from ...` to preserve the cause chain. `raise NewError("...") from original_error` keeps the traceback readable
- Define domain exceptions as subclasses of a single project-root exception. HTTP-mapping lives in a framework boundary, not in the domain layer
- For Result-style error returns, use a discriminated union via `typing.Literal` and `dataclasses`, or the `result` library if the project benefits from a richer API

## Logging

Use `structlog` or a structured-logging wrapper around `logging`. Never use `print()` in production code. Configure a single logger at the application entry point with JSON output in production and console output in dev.

- Include context: request ID, user ID, tenant ID, operation name. The structured logger handles this; string-formatted logs lose it
- Never log secrets, tokens, or PII. The `secret-scanner.py` hook catches the obvious cases, but design the log call so the sensitive value never reaches the logger in the first place

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Mutable default arguments: `def f(x=[]):` | Use `def f(x: list[int] \| None = None):` and initialize inside |
| Catching `BaseException` | Catch `Exception`. `BaseException` includes `KeyboardInterrupt` and `SystemExit` |
| Using `dict.get(key)` without typing the default | Use `dict.get(key, default)` with a default of the right type, or check membership first |
| Comparing with `==` to `None` | Use `is None` and `is not None`. PEP 8 mandates it; `==` triggers `__eq__` which can be expensive or buggy |
| Using `os.path` for paths | Use `pathlib.Path`. The OO API composes better and avoids string concatenation bugs |
| Calling `time.time()` for timestamps | Use `datetime.now(UTC)` for wall time, `time.monotonic()` for intervals. Never mix the two |
| Using `requests` in async code | Use `httpx` or `aiohttp`. `requests` blocks the event loop |
| Returning `None` to mean "not found" without typing it | Type the return as `T \| None` and force the caller to handle it |

## Versions

- Target Python 3.12 or newer for new projects. 3.13 is current stable as of 2026
- Pin the Python version in `pyproject.toml` under `[project] requires-python` and in `.python-version` for `uv`
- Avoid features behind `from __future__ import annotations` unless the project explicitly chooses delayed evaluation. PEP 695 generic syntax in 3.12+ removes most need for it

## Cross-References

- [`rules/code-style.md`](../code-style.md): cross-language fundamentals, error classification, validation at boundaries
- [`rules/testing.md`](../testing.md): integration-first philosophy, strict mock policy
- [`rules/architecture-defaults.md`](../architecture-defaults.md): DDD, hexagonal, idempotency baseline
- [`standards/database.md`](../../standards/database.md): generic database concerns
- [`standards/postgresql.md`](../../standards/postgresql.md): PostgreSQL specifics, including PG 18 native `uuidv7()`
