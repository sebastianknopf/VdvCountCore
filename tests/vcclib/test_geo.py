import pytest

from vcclib.geo import haversine_distance


def test_same_point_has_zero_distance():
    assert haversine_distance((48.0, 9.0), (48.0, 9.0)) == 0


def test_one_degree_latitude_is_about_111_km():
    assert haversine_distance((0.0, 0.0), (1.0, 0.0)) == pytest.approx(111195, rel=1e-3)


def test_distance_is_symmetric():
    a, b = (48.78, 9.18), (52.52, 13.40)
    assert haversine_distance(a, b) == pytest.approx(haversine_distance(b, a))
