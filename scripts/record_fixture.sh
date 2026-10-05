#!/bin/sh
# Record a small real OpenSky fixture with anonymous access (PLAN §4): COUNT snapshots of
# the region bbox, INTERVAL seconds apart, saved exactly like live mode's raw zone
# (<OUT>/YYYY-MM-DD/HHMMSS.json.gz) so replay can play them back.
#
# Runs inside the backend container (see `make record`). Anonymous quota: 400 credits/day,
# one credit per request for a bbox under 25 square degrees, 10 s time resolution.
set -eu

COUNT=${COUNT:-25}
INTERVAL=${INTERVAL:-10}
OUT=${OUT:-/out}
URL="https://opensky-network.org/api/states/all?lamin=${BBOX_LAMIN:-39.5}&lomin=${BBOX_LOMIN:-26.0}&lamax=${BBOX_LAMAX:-42.0}&lomax=${BBOX_LOMAX:-31.5}&extended=1"

tmp=$(mktemp)
hdr=$(mktemp)
trap 'rm -f "$tmp" "$hdr"' EXIT

i=1
while [ "$i" -le "$COUNT" ]; do
    code=$(curl -sS --connect-timeout 15 --max-time 30 -o "$tmp" -D "$hdr" -w '%{http_code}' "$URL") || code=000
    case "$code" in
        200)
            dir="$OUT/$(date -u +%F)"
            mkdir -p "$dir"
            file="$dir/$(date -u +%H%M%S).json.gz"
            gzip -9 -c "$tmp" > "$file"
            left=$(grep -i '^x-rate-limit-remaining:' "$hdr" | tr -d '\r' | awk '{print $2}')
            echo "[$i/$COUNT] $file ($(wc -c < "$tmp") bytes, credits left: ${left:-?})"
            ;;
        429)
            wait=$(grep -i '^x-rate-limit-retry-after-seconds:' "$hdr" | tr -d '\r' | awk '{print $2}')
            echo "rate limited (429); retry after ${wait:-?} s — stopping" >&2
            exit 1
            ;;
        *)
            echo "[$i/$COUNT] HTTP $code, skipped" >&2
            ;;
    esac
    i=$((i + 1))
    if [ "$i" -le "$COUNT" ]; then sleep "$INTERVAL"; fi
done
