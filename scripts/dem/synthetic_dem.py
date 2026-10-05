"""Fallback elevation surface for `make dem` when Copernicus cannot be downloaded.

A few Gaussian hills placed roughly where the region's real mountains are (Uludag, Kaz Daglari,
Samanli, Istranca), on the same 3-arcsecond EPSG:4326 grid as GLO-90. Everything below 0 is
clipped to 0, so the low ground between hills reads as sea. It is clearly not real terrain:
the UI and README say so when the tiles come from here.

usage: synthetic_dem.py <lomin> <lamin> <lomax> <lamax> <out.tif>
"""

import sys

import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()

STEP = 1 / 1200  # 3 arcseconds, like GLO-90
# lon, lat, height (m), radius (degrees)
HILLS = [
    (29.20, 40.07, 2500, 0.25),  # Uludag
    (26.85, 39.70, 1700, 0.30),  # Kaz Daglari
    (29.30, 40.55, 1300, 0.25),  # Samanli
    (27.60, 41.85, 1000, 0.35),  # Istranca
    (30.60, 40.40, 1500, 0.40),
    (28.20, 39.70, 900, 0.50),
]
BASE = -150  # offset so the plains between hills fall below 0 and become "sea"


def surface(lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    x, y = np.meshgrid(lons, lats)
    z = np.full(x.shape, BASE, dtype=np.float32)
    for lon, lat, height, radius in HILLS:
        z += height * np.exp(-((x - lon) ** 2 + (y - lat) ** 2) / (2 * radius**2))
    return np.clip(z, 0, None)


def main(lomin: float, lamin: float, lomax: float, lamax: float, out: str) -> None:
    width = round((lomax - lomin) / STEP)
    height = round((lamax - lamin) / STEP)
    # pixel centres, north-up: row 0 is the northern edge
    lons = lomin + (np.arange(width) + 0.5) * STEP
    lats = lamax - (np.arange(height) + 0.5) * STEP
    ds = gdal.GetDriverByName("GTiff").Create(
        out, width, height, 1, gdal.GDT_Float32, options=["TILED=YES", "COMPRESS=DEFLATE"]
    )
    ds.SetGeoTransform((lomin, STEP, 0, lamax, 0, -STEP))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())
    ds.GetRasterBand(1).WriteArray(surface(lons, lats))
    ds.FlushCache()


if __name__ == "__main__":
    *bbox, path = sys.argv[1:]
    main(*(float(v) for v in bbox), path)
