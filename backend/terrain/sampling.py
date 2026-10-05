"""Raster sampling maths. Pure functions: no I/O, no Django, no rasterio."""

import math

GeoTransform = tuple[float, float, float, float, float, float]


def pixel_position(gt: GeoTransform, lon: float, lat: float) -> tuple[float, float]:
    """Fractional (col, row) of a point, measured from the centre of pixel (0, 0).

    `gt` is a north-up GDAL geotransform (origin x, pixel width, 0, origin y, 0, -pixel height)
    whose origin is the outer corner of the first pixel; values describe pixel centres, hence
    the half-pixel shift.
    """
    x0, width, _, y0, _, height = gt
    return (lon - x0) / width - 0.5, (lat - y0) / height - 0.5


def _missing(value: float, nodata: float | None) -> bool:
    return math.isnan(value) or (nodata is not None and value == nodata)


def bilinear(window, fx: float, fy: float, nodata: float | None) -> float | None:
    """Interpolate inside a 2x2 window of pixel centres; fx, fy in [0, 1] from the top-left.

    A nodata neighbour cannot be averaged into a height, so then the nearest pixel is used
    as is; if that one is nodata too, there is no value.
    """
    (a, b), (c, d) = window
    if any(_missing(v, nodata) for v in (a, b, c, d)):
        nearest = window[round(fy)][round(fx)]
        return None if _missing(nearest, nodata) else float(nearest)
    top = a + (b - a) * fx
    bottom = c + (d - c) * fx
    return float(top + (bottom - top) * fy)
