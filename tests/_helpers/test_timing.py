from __future__ import annotations

from faker import Faker

from _helpers.timing import timed


def test_timed_returns_the_result_and_a_non_negative_duration(faker: Faker) -> None:
    # Arrange
    value = faker.pyint()

    # Act
    result, duration_ms = timed(lambda number: number * 2, value)

    # Assert
    assert result == value * 2
    assert duration_ms >= 0.0
