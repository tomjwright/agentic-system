"""Seam 2: distance targets and route validation."""

import pytest

from route_feasibility.checks import Boundary, parse_target, validate_loop


def test_single_target_accepts_ten_percent_either_side() -> None:
    target = parse_target("10")

    assert target.accepts(9_000)
    assert target.accepts(11_000)
    assert not target.accepts(8_990)
    assert not target.accepts(11_010)


def test_explicit_range_is_never_widened() -> None:
    target = parse_target("60-70")

    assert target.accepts(60_000)
    assert target.accepts(70_000)
    assert not target.accepts(59_990)
    assert not target.accepts(70_010)


@pytest.mark.parametrize("text", ["70-60", "0", "-5", "sixty"])
def test_unusable_targets_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        parse_target(text)


# A square "Singapore" so the tests do not depend on the real boundary file.
SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[103.80, 1.25], [103.90, 1.25], [103.90, 1.35], [103.80, 1.35], [103.80, 1.25]]
    ],
}


def test_closed_loop_inside_singapore_has_no_problems() -> None:
    loop = [[103.8291, 1.2766], [103.8400, 1.2800], [103.8350, 1.2900], [103.8291, 1.2766]]

    assert validate_loop(loop, Boundary([SQUARE])) == []


def test_route_that_ends_away_from_its_start_is_not_a_loop() -> None:
    # The last point is 0.01 degrees of latitude (about 1.1 km) north of the start.
    route = [[103.8291, 1.2766], [103.8400, 1.2800], [103.8291, 1.2866]]

    problems = validate_loop(route, Boundary([SQUARE]))

    assert problems == ["loop does not close: it ends 1112 m from where it starts"]


def test_points_outside_singapore_are_reported() -> None:
    loop = [[103.8291, 1.2766], [103.9500, 1.2800], [103.9600, 1.2800], [103.8291, 1.2766]]

    problems = validate_loop(loop, Boundary([SQUARE]))

    assert problems == ["2 of 4 points are outside Singapore"]


def test_points_just_past_the_coastline_count_as_inside() -> None:
    # The boundary coastline is approximate: 0.0003 degrees (about 33 m) past the
    # edge is a coastal path, 0.002 degrees (about 220 m) past it is not Singapore.
    loop = [[103.8291, 1.2766], [103.9003, 1.2800], [103.9020, 1.2900], [103.8291, 1.2766]]

    problems = validate_loop(loop, Boundary([SQUARE]))

    assert problems == ["1 of 4 points are outside Singapore"]


def test_non_finite_coordinates_are_rejected() -> None:
    loop = [[103.8291, 1.2766], [float("nan"), 1.2800], [103.8291, 1.2766]]

    problems = validate_loop(loop, Boundary([SQUARE]))

    assert problems == ["1 points are not finite numbers"]
