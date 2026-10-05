#!/bin/sh
# HTTP smoke test of a running stack through nginx: the checks a person would do with curl
# after `make up` / `make up-prod` and `make seed`. Used by `make smoke` and the CI stack job.
# Needs only curl and python3 (for JSON).
set -eu

BASE=${BASE:-http://localhost:8800}
WAIT=${WAIT:-60}
failures=0

pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; failures=$((failures + 1)); }

# json URL EXPR: evaluate a Python expression on the parsed body (`d`); prints the result
json() {
    curl -fsS --max-time 10 "$BASE$1" | python3 -c "import json,sys; d=json.load(sys.stdin); print($2)"
}

check() { # check NAME COMMAND...: run the command, pass if it succeeds
    name=$1
    shift
    if "$@" >/dev/null 2>&1; then pass "$name"; else fail "$name"; fi
}

# curl prints 000 when it cannot connect; that is a result to report, not a reason to abort
status_of() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@" || true; }

echo "smoke: $BASE"

# --- gateway and health -----------------------------------------------------------
check "nginx answers" curl -fsS --max-time 5 "$BASE/nginx-health"
check "api/health is ok (PostGIS + Redis)" sh -c "[ \"\$(curl -fsS '$BASE/api/health' | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"status\"])')\" = ok ]"
check "SPA index is served" sh -c "curl -fsS '$BASE/' | grep -q '<div id=\"root\"'"

# --- data flowing: ingest -> PostGIS -> REST ----------------------------------------
live=0
i=0
while [ "$i" -lt "$WAIT" ]; do
    live=$(json "/api/aircraft/live" "len(d['features'])" 2>/dev/null || echo 0)
    [ "$live" -gt 0 ] && break
    i=$((i + 2))
    sleep 2
done
if [ "$live" -gt 0 ]; then pass "live aircraft: $live"; else fail "no live aircraft after ${WAIT}s"; fi
check "ingest status ok in /api/stats" sh -c "[ \"\$(curl -fsS '$BASE/api/stats' | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"ingest\"][\"status\"])')\" = ok ]"

# --- reference data (needs `make seed`) -------------------------------------------
airports=$(json "/api/airports/" "len(d['features'])" 2>/dev/null || echo 0)
fences=$(json "/api/geofences/" "len(d['features'])" 2>/dev/null || echo 0)
if [ "$airports" -gt 0 ]; then pass "airports: $airports"; else fail "no airports (run make seed)"; fi
if [ "$fences" -ge 2 ]; then pass "geofences: $fences"; else fail "fewer than 2 geofences (run make seed)"; fi

# --- terrain: built by `make dem`, optional ----------------------------------------
code=$(status_of "$BASE/api/terrain/elevation?lon=29.2213&lat=40.0703")
case $code in
    200) pass "terrain elevation (Uludag): $(json '/api/terrain/elevation?lon=29.2213&lat=40.0703' "d['elevation_m']") m" ;;
    503) pass "terrain not built (503 terrain_unavailable; make dem builds it)" ;;
    *) fail "terrain elevation returned $code" ;;
esac

# --- ops panel (Django templates + HTMX) --------------------------------------------
check "/ops redirects to /ops/ on the same port" sh -c "curl -sI '$BASE/ops' | grep -qi '^location: /ops/'"
page=$(curl -fsS --max-time 10 "$BASE/ops/" 2>/dev/null || true)
for section in ingest events geofences retention; do
    if printf '%s' "$page" | grep -q "id=\"$section\""; then pass "ops section #$section"; else fail "ops section #$section missing"; fi
done
htmx=$(printf '%s' "$page" | sed -n 's/.*<script src="\([^"]*htmx[^"]*\)".*/\1/p' | head -n 1)
check "htmx is served (${htmx:-not found})" curl -fsS --max-time 5 "$BASE$htmx"
check "ops ingest fragment" sh -c "curl -fsS -H 'HX-Request: true' '$BASE/ops/ingest' | grep -q 'status-ok'"
code=$(status_of -X POST -d active=false "$BASE/ops/geofences/1/active")
if [ "$code" = 403 ]; then pass "ops POST without CSRF token is refused (403)"; else fail "ops POST without CSRF token returned $code"; fi

if [ "$failures" -gt 0 ]; then
    echo "smoke: $failures check(s) failed"
    exit 1
fi
echo "smoke: all checks passed"
