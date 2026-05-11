"""Phase 39 detector tests: private fields, symbol keys, static blocks.

Plan items 382-384. Verifies the hook flags:

  * `this.#field = v`, compound, increment on private class fields
  * `obj[Symbol.iterator] = fn` and well-known Symbol-keyed property assignment
  * Multiple `static {}` blocks per class and branching inside a static block
"""

from __future__ import annotations

from conftest import make_edit_payload, make_write_payload


def test_private_field_assignment_blocks(run_hook):
    # Arrange
    snippet = (
        "class Counter {\n"
        "  #count = 0;\n"
        "  bump() { this.#count = this.#count + 1 }\n"
        "}\n"
    )
    payload = make_edit_payload("/repo/src/business/counter.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, (
        f"expected block (2) for private field mutation, got {code}\n{stderr}"
    )
    assert "#count" in stderr or "private-field" in stderr


def test_private_field_compound_assignment_blocks(run_hook):
    # Arrange
    snippet = "class Counter {\n  #count = 0;\n  bump() { this.#count += 1 }\n}\n"
    payload = make_edit_payload("/repo/src/business/counter.ts", snippet)

    # Act
    code, _stderr = run_hook(payload)

    # Assert
    assert code == 2


def test_private_field_increment_blocks(run_hook):
    # Arrange
    snippet = "class Counter {\n  #count = 0;\n  bump() { this.#count++ }\n}\n"
    payload = make_edit_payload("/repo/src/business/counter.ts", snippet)

    # Act
    code, _stderr = run_hook(payload)

    # Assert
    assert code == 2


def test_private_field_declaration_does_not_block(run_hook):
    # Arrange
    snippet = (
        "class Counter {\n"
        "  #count = 0;\n"
        "  current(): number { return this.#count }\n"
        "}\n"
    )
    payload = make_write_payload("/repo/src/business/counter.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"declaration must not block. stderr:\n{stderr}"


def test_symbol_key_iterator_assignment_blocks(run_hook):
    # Arrange
    snippet = "const obj = {}\nobj[Symbol.iterator] = function* () { yield 1 }\n"
    payload = make_edit_payload("/repo/src/business/iterable.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, (
        f"expected block (2) for Symbol-key assignment, got {code}\n{stderr}"
    )
    assert "Symbol" in stderr or "symbol-key" in stderr


def test_symbol_key_async_iterator_assignment_blocks(run_hook):
    # Arrange
    snippet = (
        "const stream = {}\n"
        "stream[Symbol.asyncIterator] = async function* () { yield 1 }\n"
    )
    payload = make_edit_payload("/repo/src/business/stream.ts", snippet)

    # Act
    code, _stderr = run_hook(payload)

    # Assert
    assert code == 2


def test_symbol_key_in_literal_does_not_block(run_hook):
    # Arrange
    snippet = "const obj = {\n  [Symbol.iterator]: function* () { yield 1 }\n}\n"
    payload = make_write_payload("/repo/src/business/iterable.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"literal form must not block. stderr:\n{stderr}"


def test_static_block_with_branching_blocks(run_hook):
    # Arrange
    snippet = (
        "class Cache {\n"
        "  static items: Map<string, number>;\n"
        "  static {\n"
        "    if (globalThis.testEnv) {\n"
        "      Cache.items = new Map()\n"
        "    } else {\n"
        "      Cache.items = new Map([['default', 0]])\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    payload = make_write_payload("/repo/src/business/cache.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2, (
        f"expected block (2) for static block branching, got {code}\n{stderr}"
    )


def test_static_block_canonical_does_not_block(run_hook):
    # Arrange
    snippet = (
        "class Config {\n"
        "  static endpoint: string;\n"
        "  static timeout: number;\n"
        "  static {\n"
        "    Config.endpoint = 'https://api.example.com'\n"
        "    Config.timeout = 3000\n"
        "  }\n"
        "}\n"
    )
    payload = make_write_payload("/repo/src/business/config.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"canonical static block must not block. stderr:\n{stderr}"


def test_state_management_filename_allows_private_field_mutation(run_hook):
    # Arrange
    snippet = "class CounterStore {\n  #count = 0;\n  bump() { this.#count += 1 }\n}\n"
    payload = make_write_payload("/repo/src/business/counterStore.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, f"state-management filename must auto-allow. stderr:\n{stderr}"
