import pytest

from terrain.sampling import bilinear, pixel_position

# 0.1-degree pixels, north-up, top-left corner at (28.0, 41.0): GDAL geotransform order
GT = (28.0, 0.1, 0.0, 41.0, 0.0, -0.1)
NODATA = -32767.0


def test_pixel_position_is_relative_to_pixel_centres():
    # the centre of pixel (col 0, row 0) is half a pixel in from the corner
    assert pixel_position(GT, 28.05, 40.95) == pytest.approx((0.0, 0.0))
    assert pixel_position(GT, 28.10, 40.90) == pytest.approx((0.5, 0.5))
    assert pixel_position(GT, 28.25, 40.75) == pytest.approx((2.0, 2.0))
    # lon moves the column, lat moves the row (downwards as lat decreases)
    assert pixel_position(GT, 28.15, 40.95) == pytest.approx((1.0, 0.0))


def test_bilinear_at_a_corner_returns_that_value():
    window = [[10.0, 20.0], [30.0, 40.0]]
    assert bilinear(window, 0.0, 0.0, NODATA) == 10.0
    assert bilinear(window, 1.0, 0.0, NODATA) == 20.0
    assert bilinear(window, 0.0, 1.0, NODATA) == 30.0
    assert bilinear(window, 1.0, 1.0, NODATA) == 40.0


def test_bilinear_interpolates_between_four_pixels():
    window = [[10.0, 20.0], [30.0, 40.0]]
    assert bilinear(window, 0.5, 0.0, NODATA) == pytest.approx(15.0)
    assert bilinear(window, 0.0, 0.5, NODATA) == pytest.approx(20.0)
    assert bilinear(window, 0.5, 0.5, NODATA) == pytest.approx(25.0)
    assert bilinear(window, 0.25, 0.75, NODATA) == pytest.approx(10 + 0.25 * 10 + 0.75 * 20)


def test_bilinear_with_a_nodata_neighbour_falls_back_to_the_nearest_pixel():
    # averaging -32767 into a height would be nonsense; use the closest real pixel instead
    window = [[10.0, NODATA], [30.0, 40.0]]
    assert bilinear(window, 0.2, 0.2, NODATA) == 10.0
    assert bilinear(window, 0.9, 0.9, NODATA) == 40.0


def test_bilinear_returns_none_when_the_nearest_pixel_is_nodata():
    window = [[10.0, NODATA], [30.0, 40.0]]
    assert bilinear(window, 0.9, 0.1, NODATA) is None


def test_bilinear_without_a_nodata_value():
    assert bilinear([[1.0, 3.0], [1.0, 3.0]], 0.5, 0.5, None) == pytest.approx(2.0)


def test_bilinear_treats_nan_as_nodata():
    nan = float("nan")
    assert bilinear([[nan, nan], [nan, nan]], 0.5, 0.5, None) is None
