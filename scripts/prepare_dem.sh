#!/bin/sh
# DEM pipeline (`make dem`): Copernicus GLO-90 -> VRT mosaic -> region COG (EPSG:4326, for
# elevation sampling) and a Web Mercator hillshade cut into XYZ PNG tiles (zoom 6-11).
# Runs in the `gdal` tools container: /data is ./data, /scripts is ./scripts.
#
#   DEM_SOURCE=auto       download Copernicus; fall back to a synthetic surface if nothing downloads
#   DEM_SOURCE=copernicus download only (fail instead of falling back)
#   DEM_SOURCE=synthetic  skip the download, use the synthetic surface
set -eu

DEM_SOURCE=${DEM_SOURCE:-auto}
LOMIN=${BBOX_LOMIN:-26.0}
LAMIN=${BBOX_LAMIN:-39.5}
LOMAX=${BBOX_LOMAX:-31.5}
LAMAX=${BBOX_LAMAX:-42.0}
MINZOOM=6
MAXZOOM=11
# sun azimuth (from north, clockwise) and altitude in degrees; NW light reads as "lit from above"
AZIMUTH=315
ALTITUDE=45

OUT=/data/dem
SRC=$OUT/src
TILES=/data/tiles/hillshade
BASE=${DEM_BASE_URL:-https://copernicus-dem-90m.s3.amazonaws.com}
mkdir -p "$SRC" "$OUT"

log() { printf '\n== %s\n' "$*"; }

# --- 1. Download -------------------------------------------------------------------------
# GLO-90 tiles are 1x1 degree, named after their south-west corner. Tiles that are all sea do
# not exist (404); the mosaic fills their area with 0, which is what Copernicus uses for sea.
# Any other failure would turn land into "sea" the same way, so it stops the pipeline.
download() {
  ok=0
  failed=0
  lat=$(awk -v v="$LAMIN" 'BEGIN { printf "%d", (v < 0 && v != int(v)) ? int(v) - 1 : int(v) }')
  lat_end=$(awk -v v="$LAMAX" 'BEGIN { print (v == int(v)) ? v - 1 : int(v) }')
  while [ "$lat" -le "$lat_end" ]; do
    lon=$(awk -v v="$LOMIN" 'BEGIN { printf "%d", int(v) }')
    lon_end=$(awk -v v="$LOMAX" 'BEGIN { print (v == int(v)) ? v - 1 : int(v) }')
    while [ "$lon" -le "$lon_end" ]; do
      name=$(printf 'Copernicus_DSM_COG_30_N%02d_00_E%03d_00_DEM' "$lat" "$lon")
      file=$SRC/$name.tif
      if [ -s "$file" ]; then
        echo "cached    $name"
        ok=$((ok + 1))
      else
        code=$(curl -sS --retry 3 -o "$file.part" -w '%{http_code}' "$BASE/$name/$name.tif") || true
        if [ "$code" = 200 ]; then
          mv "$file.part" "$file"
          echo "download  $name"
          ok=$((ok + 1))
        elif [ "$code" = 404 ]; then
          rm -f "$file.part"
          echo "sea       $name (no such tile)"
        else
          rm -f "$file.part"
          echo "FAILED    $name (HTTP ${code:-none})"
          failed=$((failed + 1))
        fi
      fi
      lon=$((lon + 1))
    done
    lat=$((lat + 1))
  done
  if [ "$failed" -gt 0 ] && [ "$ok" -gt 0 ]; then
    echo "$failed tile(s) failed to download; run make dem again (downloaded tiles are kept)" >&2
    exit 1
  fi
  [ "$ok" -gt 0 ]
}

source_name=copernicus
case "$DEM_SOURCE" in
  synthetic) source_name=synthetic ;;
  copernicus) log "Downloading Copernicus GLO-90"; download || { echo "no tiles downloaded" >&2; exit 1; } ;;
  auto)
    log "Downloading Copernicus GLO-90"
    if ! download; then
      echo "download failed: falling back to the synthetic surface" >&2
      source_name=synthetic
    fi
    ;;
  *) echo "DEM_SOURCE must be auto, copernicus or synthetic" >&2; exit 2 ;;
esac

if [ "$source_name" = synthetic ]; then
  log "Generating a synthetic elevation surface"
  python3 /scripts/dem/synthetic_dem.py "$LOMIN" "$LAMIN" "$LOMAX" "$LAMAX" "$OUT/synthetic.tif"
  inputs=$OUT/synthetic.tif
else
  inputs=$(ls "$SRC"/Copernicus_*.tif)
fi

# --- 2. Inspect --------------------------------------------------------------------------
log "Inspecting one input (size, pixel size, CRS, bands, nodata)"
first=$(echo "$inputs" | head -n 1)
gdalinfo "$first" | grep -E 'Size is|Pixel Size|ID\["EPSG"|^Band|NoData|AREA_OR_POINT' || true

# --- 3. Mosaic ---------------------------------------------------------------------------
log "Building the VRT mosaic"
# shellcheck disable=SC2086 # one path per word is intended
gdalbuildvrt -q -overwrite "$OUT/mosaic.vrt" $inputs

# --- 4a. Analysis COG (EPSG:4326, native grid) ----------------------------------------------
# Same CRS as the source: a crop on the native grid needs no resampling, so every sampled
# value is an original elevation. -32767 marks nodata (outside the inputs).
log "Writing the region COG (EPSG:4326)"
gdal_translate -q -projwin "$LOMIN" "$LAMAX" "$LOMAX" "$LAMIN" -a_nodata -32767 \
  -of COG -co COMPRESS=DEFLATE -co PREDICTOR=YES -co RESAMPLING=AVERAGE -co BLOCKSIZE=512 \
  "$OUT/mosaic.vrt" "$OUT/dem_4326_cog.tif.part"
mv "$OUT/dem_4326_cog.tif.part" "$OUT/dem_4326_cog.tif"

# --- 4b. Web Mercator DEM for the hillshade -------------------------------------------------
# Elevation is continuous, so bilinear (nearest would leave stair steps that the hillshade
# turns into stripes; cubic can overshoot near cliffs and the coast).
log "Reprojecting to EPSG:3857 (bilinear)"
gdalwarp -q -overwrite -t_srs EPSG:3857 -te_srs EPSG:4326 -te "$LOMIN" "$LAMIN" "$LOMAX" "$LAMAX" \
  -r bilinear -co TILED=YES -co COMPRESS=DEFLATE -co PREDICTOR=3 \
  "$OUT/mosaic.vrt" "$OUT/dem_3857.tif"

# --- 5. Hillshade ----------------------------------------------------------------------------
# Web Mercator stretches distances by 1/cos(lat): a slope looks flatter than it is. Raising the
# heights by the same factor (taken at the middle of the region) restores the true slope.
zfactor=$(awk -v a="$LAMIN" -v b="$LAMAX" 'BEGIN { printf "%.3f", 1 / cos((a + b) / 2 * atan2(0, -1) / 180) }')
log "Hillshade (azimuth $AZIMUTH, altitude $ALTITUDE, z-factor $zfactor)"
gdaldem hillshade -q -az "$AZIMUTH" -alt "$ALTITUDE" -z "$zfactor" -compute_edges \
  -co TILED=YES -co COMPRESS=DEFLATE "$OUT/dem_3857.tif" "$OUT/hillshade.tif"
# grey hillshade -> black/white with alpha, so flat ground (and the sea) stays transparent
python3 /scripts/dem/shade_rgba.py "$OUT/hillshade.tif" "$OUT/hillshade_rgba.tif" "$ALTITUDE"

# --- 6. Tiles ----------------------------------------------------------------------------
log "Cutting XYZ tiles, zoom $MINZOOM-$MAXZOOM"
rm -rf "$TILES.part"
gdal2tiles --xyz -q -z "$MINZOOM-$MAXZOOM" -r average -w none --processes="$(nproc)" \
  "$OUT/hillshade_rgba.tif" "$TILES.part"
cat > "$TILES.part/meta.json" <<EOF
{
  "source": "$source_name",
  "minzoom": $MINZOOM,
  "maxzoom": $MAXZOOM,
  "bounds": [$LOMIN, $LAMIN, $LOMAX, $LAMAX],
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
rm -rf "$TILES"
mv "$TILES.part" "$TILES"

log "Done ($source_name)"
du -sh "$OUT/dem_4326_cog.tif" "$TILES"
echo "tiles: $(find "$TILES" -name '*.png' | wc -l)"
