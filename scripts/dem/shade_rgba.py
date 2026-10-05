"""Turn a grey gdaldem hillshade into black/white RGBA with alpha.

gdaldem gives flat ground the value 1 + 254 * sin(altitude), a mid grey that would wash a
dark basemap (and the whole sea) out. Here shadows become black and lit slopes white, each
with an alpha that grows with the distance from that flat value; flat ground is transparent.

usage: shade_rgba.py <hillshade.tif> <out.tif> <sun altitude in degrees>
"""

import math
import sys

import numpy as np
from osgeo import gdal

gdal.UseExceptions()


def shade_to_rgba(shade: np.ndarray, altitude: float) -> np.ndarray:
    flat = 1 + 254 * math.sin(math.radians(altitude))
    s = shade.astype(np.float32)
    dark = np.clip((flat - s) / (flat - 1), 0, 1)
    light = np.clip((s - flat) / (255 - flat), 0, 1)
    rgba = np.zeros((4, *shade.shape), dtype=np.uint8)
    rgba[0:3] = np.where(light > 0, 255, 0).astype(np.uint8)
    rgba[3] = np.round(255 * np.maximum(dark, light)).astype(np.uint8)
    rgba[3][shade == 0] = 0  # gdaldem nodata
    return rgba


def main(src_path: str, dst_path: str, altitude: float) -> None:
    src = gdal.Open(src_path)
    rgba = shade_to_rgba(src.GetRasterBand(1).ReadAsArray(), altitude)
    dst = gdal.GetDriverByName("GTiff").Create(
        dst_path, src.RasterXSize, src.RasterYSize, 4, gdal.GDT_Byte,
        options=["TILED=YES", "COMPRESS=DEFLATE", "PHOTOMETRIC=RGB", "ALPHA=YES"],
    )
    dst.SetGeoTransform(src.GetGeoTransform())
    dst.SetProjection(src.GetProjection())
    for i in range(4):
        dst.GetRasterBand(i + 1).WriteArray(rgba[i])
    dst.FlushCache()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
