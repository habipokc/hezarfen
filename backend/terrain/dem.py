"""The region DEM (COG written by `make dem`), opened once per process and sampled on demand."""

import math
import os
import threading

import numpy as np
import rasterio
from django.conf import settings
from rasterio.windows import Window

from .sampling import bilinear, pixel_position

_lock = threading.Lock()
_dataset = None
_version = None  # (inode, mtime) of the file _dataset was opened from


class DemUnavailable(Exception):
    pass


class OutsideDem(Exception):
    pass


def _open():
    """The open dataset; reopened when `make dem` has replaced the file since (one stat call)."""
    global _dataset, _version
    path = settings.TERRAIN_DEM_PATH
    try:
        st = os.stat(path)
    except OSError as exc:
        raise DemUnavailable(str(exc)) from exc
    version = (st.st_ino, st.st_mtime_ns)
    if _dataset is None or version != _version:
        _close()
        try:
            _dataset = rasterio.open(path)
        except rasterio.errors.RasterioIOError as exc:
            raise DemUnavailable(str(exc)) from exc
        _version = version
    return _dataset


def _close() -> None:
    global _dataset, _version
    if _dataset is not None:
        _dataset.close()
    _dataset = _version = None


def reset() -> None:
    """Close the dataset so the next sample reopens it (tests)."""
    with _lock:
        _close()


def _axis(position: float, size: int) -> tuple[int, float]:
    """First of the two pixels around `position` and the weight of the second one; points
    between the outermost pixel centres and the raster edge take the border pixel."""
    position = min(max(position, 0.0), size - 1.0)
    first = min(math.floor(position), max(size - 2, 0))
    return first, position - first


def elevation(lon: float, lat: float) -> float | None:
    """Bilinear elevation in metres at a WGS84 point; None where the DEM has no data."""
    # a rasterio dataset is not thread-safe, and sync views run in a thread pool
    with _lock:
        ds = _open()
        left, bottom, right, top = ds.bounds
        if not (left <= lon <= right and bottom <= lat <= top):
            raise OutsideDem
        col_f, row_f = pixel_position(ds.transform.to_gdal(), lon, lat)
        col, fx = _axis(col_f, ds.width)
        row, fy = _axis(row_f, ds.height)
        nodata = ds.nodata
        # _axis keeps the 2x2 window inside the raster; boundless only matters for 1-pixel sides
        window = ds.read(1, window=Window(col, row, 2, 2), boundless=True, fill_value=nodata or 0)
    values = np.asarray(window, dtype=np.float64).tolist()
    return bilinear(values, fx, fy, nodata)
