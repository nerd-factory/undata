from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from undata.dcid import (
    Dimension,
    build_dcid,
    child_countries_of,
    describe_dcid,
    parse_dcid,
)


def test_parses_a_disaggregated_variable() -> None:
    parsed = parse_dcid("undata/sdg/VC_DTH_TOTN.AGE--Y0T17__SEX--F")

    assert parsed is not None
    assert parsed.namespace == "undata"
    assert parsed.agency == "sdg"
    assert parsed.code == "VC_DTH_TOTN"
    assert parsed.dimensions == (Dimension("AGE", "Y0T17"), Dimension("SEX", "F"))
    assert parsed.base == "undata/sdg/VC_DTH_TOTN"
    assert not parsed.is_total


def test_a_variable_with_no_dimensions_is_the_total() -> None:
    parsed = parse_dcid("undata/unodc/VC_IHR_PSRC")

    assert parsed is not None
    assert parsed.is_total
    assert parsed.dimensions == ()


def test_unknown_category_slice_keeps_its_leading_underscore() -> None:
    parsed = parse_dcid("undata/sdg/VC_DTH_TOTN.AGE--_U")

    assert parsed is not None
    assert parsed.dimensions == (Dimension("AGE", "_U"),)


def test_dimension_values_may_contain_the_binding_delimiter() -> None:
    parsed = parse_dcid("undata/ilo/X.CLASS--A--B")

    assert parsed is not None
    assert parsed.dimensions == (Dimension("CLASS", "A--B"),)


def test_topic_dcids_keep_their_nested_tail() -> None:
    parsed = parse_dcid("undata/topic/sdg/goal16")

    assert parsed is not None
    assert parsed.code == "sdg/goal16"


@pytest.mark.parametrize(
    "dcid", ["", "   ", "Count_Person", "country/BGD", "//X", "undata//X", "undata/sdg/"]
)
def test_non_variable_identifiers_parse_to_none(dcid: str) -> None:
    assert parse_dcid(dcid) is None


def test_build_sorts_dimensions_so_one_slice_has_one_identifier() -> None:
    a = build_dcid("undata/sdg/VC_DTH_TOTN", {"SEX": "F", "AGE": "Y0T17"})
    b = build_dcid("undata/sdg/VC_DTH_TOTN", {"AGE": "Y0T17", "SEX": "F"})

    assert a == b == "undata/sdg/VC_DTH_TOTN.AGE--Y0T17__SEX--F"


def test_build_without_dimensions_returns_the_base() -> None:
    assert build_dcid("undata/sdg/X") == "undata/sdg/X"
    assert build_dcid("undata/sdg/X", {}) == "undata/sdg/X"


_token = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=12)


@given(code=_token, dimensions=st.dictionaries(_token, _token, max_size=4))
def test_build_then_parse_round_trips(code: str, dimensions: dict[str, str]) -> None:
    parsed = parse_dcid(build_dcid(f"undata/sdg/{code}", dimensions))

    assert parsed is not None
    assert parsed.code == code
    assert {d.name: d.value for d in parsed.dimensions} == dimensions
    assert [d.name for d in parsed.dimensions] == sorted(dimensions)


def test_describe_names_the_collection_and_the_slice() -> None:
    assert describe_dcid("undata/sdg/SH_STA_MORT.SEX--F") == (
        "Global SDG Indicators Database · SH_STA_MORT [SEX=F]"
    )
    assert describe_dcid("undata/unodc/VC_IHR_PSRC") == "UNODC · VC_IHR_PSRC (total)"
    assert describe_dcid("undata/newbody/X") == "NEWBODY · X (total)"
    assert describe_dcid("Count_Person") == "Count_Person"


def test_child_countries_expression() -> None:
    assert child_countries_of("africa") == "africa<-containedInPlace+{typeOf:Country}"
