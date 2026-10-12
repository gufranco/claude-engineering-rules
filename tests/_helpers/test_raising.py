from __future__ import annotations

import pytest
from faker import Faker

from _helpers.raising import raising


def test_raising_raises_the_given_error_for_any_arguments(faker: Faker) -> None:
    # Arrange
    message = faker.sentence()
    stub = raising(OSError(message))

    # Act
    with pytest.raises(OSError) as raised:
        stub(faker.word(), key=faker.word())

    # Assert
    assert str(raised.value) == message
