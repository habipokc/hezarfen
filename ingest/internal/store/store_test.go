package store

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/habipokc/hezarfen/ingest/internal/clean"
	"github.com/habipokc/hezarfen/ingest/internal/geo"
)

// testStore points a Store at a throwaway schema whose tables are copies of the
// Django-migrated ones (LIKE … INCLUDING ALL keeps defaults, identity, indexes and
// unique constraints), so the test exercises the real DDL without touching data.
// Skips unless INGEST_TEST_DATABASE_URL is set (make test-ingest sets it).
func testStore(t *testing.T) (*Store, *pgx.Conn) {
	t.Helper()
	url := os.Getenv("INGEST_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("INGEST_TEST_DATABASE_URL not set")
	}
	ctx := context.Background()
	admin, err := pgx.Connect(ctx, url)
	if err != nil {
		t.Fatal(err)
	}
	var migrated bool
	if err := admin.QueryRow(ctx, `SELECT to_regclass('public.positions') IS NOT NULL`).Scan(&migrated); err != nil || !migrated {
		t.Skip("database is not migrated yet (start the stack once)")
	}
	schema := fmt.Sprintf("ingest_test_%d", time.Now().UnixNano())
	ddl := fmt.Sprintf(`CREATE SCHEMA %[1]s;
		CREATE TABLE %[1]s.aircraft (LIKE public.aircraft INCLUDING ALL);
		CREATE TABLE %[1]s.aircraft_latest (LIKE public.aircraft_latest INCLUDING ALL);
		CREATE TABLE %[1]s.positions (LIKE public.positions INCLUDING ALL);
		CREATE TABLE %[1]s.airports (LIKE public.airports INCLUDING ALL);`, schema)
	if _, err := admin.Exec(ctx, ddl); err != nil {
		t.Fatal(err)
	}
	s, err := Connect(ctx, url, schema)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		s.Close()
		_, _ = admin.Exec(context.Background(), "DROP SCHEMA "+schema+" CASCADE")
		admin.Close(context.Background())
	})
	if _, err := admin.Exec(ctx, "SET search_path = "+schema+",public"); err != nil {
		t.Fatal(err)
	}
	return s, admin
}

func ptr[T any](v T) *T { return &v }

func rec(icao string, ts int64, lon, lat float64, callsign *string) clean.Record {
	return clean.Record{
		Icao24: icao, Callsign: callsign, OriginCountry: "Turkey", Ts: ts, Lon: lon, Lat: lat,
		BaroAlt: ptr(3000.0), Velocity: ptr(150.0), Heading: ptr(87.5), Category: ptr(4), Squawk: ptr("2341"),
	}
}

func count(t *testing.T, db *pgx.Conn, table string) int {
	t.Helper()
	var n int
	if err := db.QueryRow(context.Background(), "SELECT count(*) FROM "+table).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestWriteIsIdempotentAndKeepsLatestNewest(t *testing.T) {
	s, db := testStore(t)
	ctx := context.Background()
	batch := []clean.Record{rec("4baa0f", 1000, 28.8146, 41.2753, ptr("THY7AB")), rec("4b1812", 1000, 29.3, 40.9, nil)}

	inserted, err := s.Write(ctx, "synthetic", batch)
	if err != nil {
		t.Fatal(err)
	}
	if inserted != 2 || count(t, db, "aircraft") != 2 || count(t, db, "aircraft_latest") != 2 {
		t.Fatalf("inserted=%d", inserted)
	}

	// the same snapshot again (a replay, a repeated poll): nothing new
	if inserted, err = s.Write(ctx, "synthetic", batch); err != nil || inserted != 0 {
		t.Fatalf("re-write inserted=%d err=%v", inserted, err)
	}
	if count(t, db, "positions") != 2 {
		t.Fatal("positions grew on a repeated snapshot")
	}

	// newer fix moves latest; an older fix becomes history but does not move latest back
	if _, err := s.Write(ctx, "synthetic", []clean.Record{rec("4baa0f", 1010, 28.83, 41.28, nil)}); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Write(ctx, "synthetic", []clean.Record{rec("4baa0f", 990, 28.70, 41.20, nil)}); err != nil {
		t.Fatal(err)
	}
	var lon float64
	var ts time.Time
	var source string
	if err := db.QueryRow(ctx, `SELECT ST_X(geom), ts, source FROM aircraft_latest WHERE icao24 = '4baa0f'`).
		Scan(&lon, &ts, &source); err != nil {
		t.Fatal(err)
	}
	if lon != 28.83 || ts.Unix() != 1010 || source != "synthetic" {
		t.Errorf("latest = lon %.4f ts %d source %s", lon, ts.Unix(), source)
	}
	if count(t, db, "positions") != 4 {
		t.Errorf("positions = %d, want 4", count(t, db, "positions"))
	}

	// identity: callsign survives a null, first_seen stays, last_seen is the max
	var callsign string
	var first, last time.Time
	if err := db.QueryRow(ctx, `SELECT callsign, first_seen, last_seen FROM aircraft WHERE icao24 = '4baa0f'`).
		Scan(&callsign, &first, &last); err != nil {
		t.Fatal(err)
	}
	if callsign != "THY7AB" || first.Unix() != 1000 || last.Unix() != 1010 {
		t.Errorf("aircraft = %s first %d last %d", callsign, first.Unix(), last.Unix())
	}
}

func TestWriteStoresNullsAndGeometry(t *testing.T) {
	s, db := testStore(t)
	ctx := context.Background()
	r := clean.Record{Icao24: "4b0001", Ts: 2000, Lon: 29.1, Lat: 40.95, OnGround: true}
	if _, err := s.Write(ctx, "replay", []clean.Record{r}); err != nil {
		t.Fatal(err)
	}
	var srid int
	var baro *float64
	var onGround bool
	var country *string
	if err := db.QueryRow(ctx, `SELECT ST_SRID(p.geom), p.baro_altitude, p.on_ground, a.origin_country
		FROM positions p JOIN aircraft a USING (icao24)`).Scan(&srid, &baro, &onGround, &country); err != nil {
		t.Fatal(err)
	}
	if srid != 4326 || baro != nil || !onGround || country != nil {
		t.Errorf("srid=%d baro=%v on_ground=%v country=%v", srid, baro, onGround, country)
	}
}

func TestLoadAirportsFiltersTypeAndBBox(t *testing.T) {
	s, db := testStore(t)
	ctx := context.Background()
	if _, err := db.Exec(ctx, `INSERT INTO airports (ident, type, name, iso_country, geom) VALUES
		('LTFM', 'large_airport', 'Istanbul', 'TR', ST_SetSRID(ST_MakePoint(28.7321, 41.2749), 4326)),
		('LTBX', 'medium_airport', 'Samandira', 'TR', ST_SetSRID(ST_MakePoint(29.2165, 40.9930), 4326)),
		('LT01', 'small_airport', 'Strip', 'TR', ST_SetSRID(ST_MakePoint(29.0, 41.0), 4326)),
		('LTAC', 'large_airport', 'Ankara', 'TR', ST_SetSRID(ST_MakePoint(32.995, 40.128), 4326))`); err != nil {
		t.Fatal(err)
	}
	got, err := s.LoadAirports(ctx, geo.BBox{MinLon: 26, MinLat: 39.5, MaxLon: 31.5, MaxLat: 42})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 || got[0].Ident != "LTBX" || got[1].Ident != "LTFM" || got[1].Lon != 28.7321 {
		t.Errorf("airports = %+v", got)
	}
}
