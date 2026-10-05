#!/bin/sh
# Load the reference layers (airports, Turkish provinces) into PostGIS with GDAL/OGR.
#
# Runs inside the backend container (see `make seed`), which has ogr2ogr, ogrinfo, curl
# and manage.py. Flow per layer:
#   download (cached in $DATA_DIR/reference) -> ogr2ogr into a stage_* table
#   -> ogrinfo sanity check -> `manage.py import_reference` mirrors stages into the
#   Django-owned tables.
# If a download fails, or REFERENCE_OFFLINE=1, the same ogr2ogr flow runs on the small
# hand-made GeoJSON files in scripts/fixtures/.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
CACHE=${DATA_DIR:-/data}/reference
FIXTURES=$HERE/fixtures
OFFLINE=${REFERENCE_OFFLINE:-0}

AIRPORTS_URL=https://davidmegginson.github.io/ourairports-data/airports.csv
PROVINCES_URL=https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip

# Region from .env; ogr2ogr -spat takes xmin ymin xmax ymax (lon/lat order)
SPAT="${BBOX_LOMIN:-26.0} ${BBOX_LAMIN:-39.5} ${BBOX_LOMAX:-31.5} ${BBOX_LAMAX:-42.0}"

# libpq reads the password from the environment, so it never appears in a command line
export PGPASSWORD="$POSTGRES_PASSWORD"
PG="PG:host=$POSTGRES_HOST port=${POSTGRES_PORT:-5432} dbname=$POSTGRES_DB user=$POSTGRES_USER"

log() { echo "[reference] $*"; }

# fetch URL FILE: download once into the cache; a cached file is reused on the next run
fetch() {
    [ "$OFFLINE" = 1 ] && return 1
    [ -s "$CACHE/$2" ] && { log "using cached $2"; return 0; }
    mkdir -p "$CACHE"
    log "downloading $1"
    # shellcheck disable=SC2015 # intended: a failing mv must clean up as well
    curl -fsSL --retry 2 --connect-timeout 15 -o "$CACHE/$2.part" "$1" \
        && mv "$CACHE/$2.part" "$CACHE/$2" \
        || { rm -f "$CACHE/$2.part"; log "download failed: $1"; return 1; }
}

# to_stage TABLE SOURCE [ogr2ogr options...]: write SOURCE into a fresh staging table
to_stage() {
    table=$1 src=$2
    shift 2
    ogr2ogr -f PostgreSQL "$PG" "$src" -nln "$table" -overwrite \
        -lco GEOMETRY_NAME=geom -lco SPATIAL_INDEX=NONE "$@"
}

# check_stage TABLE MIN: fail unless ogrinfo reports at least MIN features
check_stage() {
    count=$(ogrinfo -ro -so "$PG" "$1" | sed -n 's/^Feature Count: //p')
    log "$1: ${count:-0} features"
    [ "${count:-0}" -ge "$2" ] || { log "expected at least $2 features in $1"; return 1; }
}

AIRPORT_FIELDS=ident,type,name,elevation_ft,iso_country,municipality,iata_code,gps_code
AIRPORT_TYPES="type IN ('large_airport', 'medium_airport', 'small_airport')"

load_airports() {
    if fetch "$AIRPORTS_URL" airports.csv; then
        # CSV has no geometry: build points from the lon/lat columns and declare their CRS
        # shellcheck disable=SC2086 # $SPAT is four numbers, split into four arguments on purpose
        to_stage stage_airports "$CACHE/airports.csv" \
            -oo X_POSSIBLE_NAMES=longitude_deg -oo Y_POSSIBLE_NAMES=latitude_deg \
            -oo AUTODETECT_TYPE=YES -a_srs EPSG:4326 -nlt POINT \
            -select "$AIRPORT_FIELDS" -where "$AIRPORT_TYPES" -spat $SPAT \
            && check_stage stage_airports 10 && return 0
        rm -f "$CACHE/airports.csv"
    fi
    log "airports: falling back to scripts/fixtures/airports.geojson"
    # shellcheck disable=SC2086 # as above
    to_stage stage_airports "$FIXTURES/airports.geojson" -nlt POINT \
        -select "$AIRPORT_FIELDS" -where "$AIRPORT_TYPES" -spat $SPAT
    check_stage stage_airports 5
}

load_provinces() {
    # Natural Earth mixes Polygon and MultiPolygon in one layer; PROMOTE_TO_MULTI makes
    # them all MultiPolygon so they fit one typed column
    if fetch "$PROVINCES_URL" ne_admin1.zip; then
        # /vsizip/ reads the shapefile (.shp + .dbf + .prj + .cpg) straight out of the zip
        to_stage stage_provinces "/vsizip/$CACHE/ne_admin1.zip/ne_10m_admin_1_states_provinces.shp" \
            -t_srs EPSG:4326 -nlt PROMOTE_TO_MULTI \
            -select name,name_tr,iso_3166_2 -where "adm0_a3 = 'TUR'" \
            && check_stage stage_provinces 81 && return 0
        rm -f "$CACHE/ne_admin1.zip"
    fi
    log "provinces: falling back to scripts/fixtures/provinces.geojson"
    to_stage stage_provinces "$FIXTURES/provinces.geojson" \
        -t_srs EPSG:4326 -nlt PROMOTE_TO_MULTI \
        -select name,name_tr,iso_3166_2 -where "adm0_a3 = 'TUR'"
    check_stage stage_provinces 3
}

load_airports
load_provinces
python manage.py import_reference

# Final check on the app tables, through OGR's PostgreSQL driver again
ogrinfo -ro -q "$PG" -sql "SELECT
    (SELECT count(*) FROM airports) AS airports,
    (SELECT count(*) FROM provinces) AS provinces,
    (SELECT count(*) FROM provinces WHERE NOT ST_IsValid(geom)) AS invalid_provinces" \
    | sed -n 's/^ *\([a-z_]*\) ([A-Za-z0-9]*) = /[reference] \1: /p'
