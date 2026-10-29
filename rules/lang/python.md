# Python

Applies to Python work or any project with a `pyproject.toml`.

- `uv` with a committed `uv.lock`, never bare `pip install`; `ruff check` and `ruff format`; `mypy --strict` or strict `pyright`; `pytest`.
- `src` layout; all tool config lives in `pyproject.toml`.
- Type every public function; never `Any`; value types use `@dataclass(frozen=True, slots=True)`.
- Never block the event loop; prefer `asyncio.TaskGroup`; always re-raise `CancelledError`.

Full rule, examples, and rationale: [`standards/python.md`](../../standards/python.md). Read it before writing Python.
