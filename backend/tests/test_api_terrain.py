import os
import time

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from terrain import dem

NODATA = -32767.0


def write_dem(path, offset=0.0):
    """A 4x4 DEM: 0.1-degree pixels from (28.0, 41.0); value = 100 * row + 10 * col; one hole."""
    values = np.array([[100 * r + 10 * c for c in range(4)] for r in range(4)], dtype=np.float32)
    values += offset
    values[3, 3] = NODATA
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(28.0, 41.0, 0.1, 0.1),
        nodata=NODATA,
    ) as ds:
        ds.write(values, 1)


@pytest.fixture
def dem_file(tmp_path, settings):
    path = tmp_path / "dem.tif"
    write_dem(path)
    settings.TERRAIN_DEM_PATH = str(path)
    dem.reset()
    yield path
    dem.reset()


def get(api, **params):
    return api.get("/api/terrain/elevation", params)


def test_value_at_a_pixel_centre(api, dem_file):
    r = get(api, lon="28.15", lat="40.85")  # col 1, row 1
    assert r.status_code == 200
    assert r.json() == {"lon": 28.15, "lat": 40.85, "elevation_m": 110.0}


def test_bilinear_between_pixel_centres(api, dem_file):
    # halfway between cols 1-2 and rows 1-2: mean of 110, 120, 210, 220
    r = get(api, lon="28.2", lat="40.8")
    assert r.json()["elevation_m"] == pytest.approx(165.0)


def test_nodata_pixel_gives_null(api, dem_file):
    r = get(api, lon="28.35", lat="40.65")
    assert r.status_code == 200
    assert r.json()["elevation_m"] is None


def test_next_to_nodata_uses_the_nearest_pixel(api, dem_file):
    # nearest centre is (col 2, row 2) = 220; the (3, 3) neighbour is a hole
    r = get(api, lon="28.27", lat="40.73")
    assert r.json()["elevation_m"] == 220.0


def test_edge_of_the_raster_clamps_to_the_border_pixel(api, dem_file):
    # inside the top-left pixel but outside the ring of pixel centres
    r = get(api, lon="28.01", lat="40.99")
    assert r.json()["elevation_m"] == 0.0


@pytest.mark.parametrize("lon,lat", [("27.9", "40.8"), ("28.2", "41.2"), ("28.41", "40.8")])
def test_outside_the_dem_is_out_of_region(api, dem_file, lon, lat):
    r = get(api, lon=lon, lat=lat)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "out_of_region"


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"lon": "28.2"},
        {"lon": "x", "lat": "40.8"},
        {"lon": "nan", "lat": "40.8"},
        {"lon": "200", "lat": "40.8"},
        {"lon": "28.2", "lat": "-91"},
    ],
)
def test_invalid_coordinates(api, dem_file, params):
    r = get(api, **params)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_parameter"


def test_missing_dem_is_unavailable(api, settings, tmp_path):
    settings.TERRAIN_DEM_PATH = str(tmp_path / "absent.tif")
    dem.reset()
    r = get(api, lon="28.2", lat="40.8")
    assert r.status_code == 503
    body = r.json()["error"]
    assert body["code"] == "terrain_unavailable"
    assert "make dem" in body["message"]
    dem.reset()


def test_dataset_is_opened_once(api, dem_file, monkeypatch):
    opened = []
    real_open = rasterio.open

    def counting_open(*args, **kwargs):
        opened.append(args)
        return real_open(*args, **kwargs)

    monkeypatch.setattr(dem.rasterio, "open", counting_open)
    for _ in range(3):
        assert get(api, lon="28.15", lat="40.85").status_code == 200
    assert len(opened) == 1


def test_a_rebuilt_dem_is_picked_up_without_a_restart(api, dem_file, tmp_path):
    # `make dem` writes a new file and renames it over the old one
    assert get(api, lon="28.15", lat="40.85").json()["elevation_m"] == 110.0
    fresh = tmp_path / "fresh.tif"
    write_dem(fresh, offset=1000)
    os.utime(fresh, ns=(time.time_ns() + 10**9,) * 2)  # coarse filesystem clocks
    fresh.replace(dem_file)
    assert get(api, lon="28.15", lat="40.85").json()["elevation_m"] == 1110.0
