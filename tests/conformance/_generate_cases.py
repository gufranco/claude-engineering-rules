from __future__ import annotations

from _case_model import Case, write_numbered
from _cases_allowlist import (
    ALLOWLIST_CASES,
    DOM_CASES,
    IMMER_MUTATIVE_CASES,
    SUPPRESSION_CASES,
    ZUSTAND_JOTAI_CASES,
)
from _cases_array import (
    ARRAY_CASES,
    COLLECTION_CASES,
    EXTRA_ARRAY_CASES,
    TYPED_ARRAY_CASES,
)
from _cases_language import (
    DATE_CASES,
    PRIVATE_FIELD_CASES,
    STATIC_BLOCK_CASES,
    SYMBOL_CASES,
)
from _cases_property import (
    ATOMICS_CASES,
    EXTRA_PROPERTY_CASES,
    GLOBAL_MUTATION_CASES,
    INCREMENT_INDEX_CASES,
    LET_CONST_CASES,
    OBJECT_UTILITY_CASES,
    PARAM_REASSIGN_CASES,
    PROPERTY_CASES,
    URL_HEADERS_FORMDATA_CASES,
)

CASE_GROUPS: tuple[tuple[Case, ...], ...] = (
    ARRAY_CASES,
    COLLECTION_CASES,
    PROPERTY_CASES,
    DATE_CASES,
    SYMBOL_CASES,
    PRIVATE_FIELD_CASES,
    STATIC_BLOCK_CASES,
    ALLOWLIST_CASES,
    OBJECT_UTILITY_CASES,
    GLOBAL_MUTATION_CASES,
    URL_HEADERS_FORMDATA_CASES,
    TYPED_ARRAY_CASES,
    LET_CONST_CASES,
    SUPPRESSION_CASES,
    IMMER_MUTATIVE_CASES,
    INCREMENT_INDEX_CASES,
    ZUSTAND_JOTAI_CASES,
    PARAM_REASSIGN_CASES,
    EXTRA_PROPERTY_CASES,
    EXTRA_ARRAY_CASES,
    DOM_CASES,
    ATOMICS_CASES,
)


def main() -> None:
    total = sum(write_numbered(group) for group in CASE_GROUPS)
    print(f"generated {total} cases")


if __name__ == "__main__":
    main()
