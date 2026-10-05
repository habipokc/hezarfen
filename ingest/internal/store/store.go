// Package store writes cleaned records to the PostGIS tables owned by Django
// (ICD IF-2) and reads the airports the synthetic source flies between.
package store

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/habipokc/hezarfen/ingest/internal/clean"
	"github.com/habipokc/hezarfen/ingest/internal/geo"
	"github.com/habipokc/hezarfen/ingest/internal/source"
)

// Each statement takes whole columns as arrays and unnest()s them back into rows:
// one round trip per table regardless of batch size, while keeping ON CONFLICT
// (which COPY cannot do without a staging table).
const (
	upsertAircraft = `
INSERT INTO aircraft (icao24, callsign, origin_country, category, first_seen, last_seen)
SELECT icao24, callsign, NULLIF(origin_country, ''), category, ts, ts
FROM unnest($1::text[], $2::text[], $3::text[], $4::smallint[], $5::timestamptz[])
     AS t(icao24, callsign, origin_country, category, ts)
ON CONFLICT (icao24) DO UPDATE SET
    -- a snapshot without a callsign does not erase the one we already know
    callsign       = COALESCE(EXCLUDED.callsign, aircraft.callsign),
    origin_country = COALESCE(EXCLUDED.origin_country, aircraft.origin_country),
    category       = COALESCE(EXCLUDED.category, aircraft.category),
    last_seen      = GREATEST(aircraft.last_seen, EXCLUDED.last_seen)`

	stateRows = `
SELECT icao24, ts, ST_SetSRID(ST_MakePoint(lon, lat), 4326), baro, geo_alt, vel, head, vrate, on_ground, squawk, $12::text
FROM unnest($1::text[], $2::timestamptz[], $3::float8[], $4::float8[], $5::float8[], $6::float8[],
            $7::float8[], $8::float8[], $9::float8[], $10::bool[], $11::text[])
     AS t(icao24, ts, lon, lat, baro, geo_alt, vel, head, vrate, on_ground, squawk)`

	stateCols = `(icao24, ts, geom, baro_altitude, geo_altitude, velocity, heading, vertical_rate, on_ground, squawk, source)`

	upsertLatest = `INSERT INTO aircraft_latest ` + stateCols + stateRows + `
ON CONFLICT (icao24) DO UPDATE SET
    ts = EXCLUDED.ts, geom = EXCLUDED.geom, baro_altitude = EXCLUDED.baro_altitude,
    geo_altitude = EXCLUDED.geo_altitude, velocity = EXCLUDED.velocity, heading = EXCLUDED.heading,
    vertical_rate = EXCLUDED.vertical_rate, on_ground = EXCLUDED.on_ground, squawk = EXCLUDED.squawk,
    source = EXCLUDED.source
-- an out-of-order or repeated snapshot must not move an aircraft back in time
WHERE aircraft_latest.ts < EXCLUDED.ts`

	insertPositions = `INSERT INTO positions ` + stateCols + stateRows + `
ON CONFLICT (icao24, ts) DO NOTHING`
)

type Store struct {
	pool *pgxpool.Pool
}

// Connect creates the pool; it does not wait for the database (see Ping).
// searchPath, if set, is prepended to the session search_path (tests use it to
// write into a throwaway schema).
func Connect(ctx context.Context, url, searchPath string) (*Store, error) {
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		return nil, fmt.Errorf("parse database url: %w", err)
	}
	if searchPath != "" {
		cfg.ConnConfig.RuntimeParams["search_path"] = searchPath + ",public"
	}
	cfg.MaxConns = 4
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, err
	}
	return &Store{pool: pool}, nil
}

func (s *Store) Ping(ctx context.Context) error { return s.pool.Ping(ctx) }
func (s *Store) Close()                         { s.pool.Close() }

// Write stores one cycle's records in a single transaction and returns how many
// rows were new in positions (the rest were already there: replays, repeated fixes).
// aircraft goes first: aircraft_latest has a foreign key to it.
func (s *Store) Write(ctx context.Context, src string, recs []clean.Record) (int64, error) {
	if len(recs) == 0 {
		return 0, nil
	}
	n := len(recs)
	var (
		ids       = make([]string, n)
		callsigns = make([]*string, n)
		countries = make([]string, n)
		cats      = make([]*int, n)
		ts        = make([]time.Time, n)
		lons      = make([]float64, n)
		lats      = make([]float64, n)
		baro      = make([]*float64, n)
		geoAlt    = make([]*float64, n)
		vel       = make([]*float64, n)
		head      = make([]*float64, n)
		vrate     = make([]*float64, n)
		ground    = make([]bool, n)
		squawk    = make([]*string, n)
	)
	for i, r := range recs {
		ids[i], callsigns[i], countries[i], cats[i] = r.Icao24, r.Callsign, r.OriginCountry, r.Category
		ts[i], lons[i], lats[i] = time.Unix(r.Ts, 0).UTC(), r.Lon, r.Lat
		baro[i], geoAlt[i], vel[i], head[i], vrate[i] = r.BaroAlt, r.GeoAlt, r.Velocity, r.Heading, r.VRate
		ground[i], squawk[i] = r.OnGround, r.Squawk
	}
	stateArgs := []any{ids, ts, lons, lats, baro, geoAlt, vel, head, vrate, ground, squawk, src}

	var inserted int64
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		// one network round trip for all three statements
		b := &pgx.Batch{}
		b.Queue(upsertAircraft, ids, callsigns, countries, cats, ts)
		b.Queue(upsertLatest, stateArgs...)
		b.Queue(insertPositions, stateArgs...).Exec(func(ct pgconn.CommandTag) error {
			inserted = ct.RowsAffected()
			return nil
		})
		return tx.SendBatch(ctx, b).Close()
	})
	if err != nil {
		return 0, fmt.Errorf("write batch of %d: %w", n, err)
	}
	return inserted, nil
}

// LoadAirports returns the large and medium airports inside bbox, loaded by `make seed`.
func (s *Store) LoadAirports(ctx context.Context, bbox geo.BBox) ([]source.Airport, error) {
	rows, err := s.pool.Query(ctx, `
SELECT ident, ST_X(geom), ST_Y(geom) FROM airports
WHERE type IN ('large_airport', 'medium_airport') AND geom && ST_MakeEnvelope($1, $2, $3, $4, 4326)
ORDER BY ident`, bbox.MinLon, bbox.MinLat, bbox.MaxLon, bbox.MaxLat)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (source.Airport, error) {
		var a source.Airport
		err := row.Scan(&a.Ident, &a.Lon, &a.Lat)
		return a, err
	})
}
