from __future__ import annotations


import pytest
from faker import Faker


SECTION_HEADINGS = (
    "Overview",
    "When to Use",
    "Process",
    "Common Rationalizations",
    "Red Flags",
    "Verification",
)


@pytest.fixture
def full_body(faker: Faker) -> str:
    return "".join(f"## {heading}\n{faker.word()}\n" for heading in SECTION_HEADINGS)
