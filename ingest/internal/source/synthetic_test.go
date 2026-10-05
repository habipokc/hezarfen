package source

import (
	"context"
	"io"
	"log/slog"
	"testing"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/clean"
	"github.com/habipokc/hezarfen/ingest/internal/geo"
)

var marmara = geo.BBox{MinLon: 26, MinLat: 39.5, MaxLon: 31.5, MaxLat: 42}

func TestSyntheticTrafficPassesCleaningAndCrossesGeofences(t *testing.T) {
	now := time.Unix(1_791_187_200, 0)
	syn := NewSynthetic(SyntheticOptions{
		Airports: []Airport{ltfm, ltfj, ltfd, {Ident: "LTBU", Point: geo.Point{Lon: 27.9191, Lat: 41.1382}},
			{Ident: "LTBR", Point: geo.Point{Lon: 29.5626, Lat: 40.2552}}},
		Count: 60, Tick: 2 * time.Second, Seed: 42, BBox: marmara,
		Now:   func() time.Time { return now },
		Sleep: func(context.Context, time.Duration) error { now = now.Add(2 * time.Second); return nil },
	})
	cleaner := clean.New(marmara, slog.New(slog.NewTextHandler(io.Discard, nil)))

	inFence := map[string]bool{}
	for tick := 0; tick < 900; tick++ { // 30 simulated minutes
		frame, err := syn.Next(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		if len(frame.States) != 60 {
			t.Fatalf("tick %d: %d states, want 60", tick, len(frame.States))
		}
		res := cleaner.Clean(frame.Snapshot)
		if len(res.Rejected) != 0 {
			t.Fatalf("tick %d: cleaner rejected synthetic data: %v", tick, res.Rejected)
		}
		for _, r := range res.Records {
			p := geo.Point{Lon: r.Lon, Lat: r.Lat}
			if !r.OnGround && (geo.Distance(p, ltfm.Point) < 15_000 || geo.Distance(p, ltfj.Point) < 15_000) {
				inFence[r.Icao24] = true
			}
		}
	}
	if len(inFence) < 10 {
		t.Errorf("only %d aircraft flew through the LTFM/LTFJ 15 km geofences", len(inFence))
	}
}

func TestSyntheticIdentitiesAreUniqueAndStable(t *testing.T) {
	now := time.Unix(1_791_187_200, 0)
	syn := NewSynthetic(SyntheticOptions{
		Airports: []Airport{ltfm, ltfj, ltfd}, Count: 80, Tick: time.Second, Seed: 7, BBox: marmara,
		Now:   func() time.Time { return now },
		Sleep: func(context.Context, time.Duration) error { now = now.Add(time.Second); return nil },
	})
	first, _ := syn.Next(context.Background())
	second, _ := syn.Next(context.Background())
	ids := map[string]bool{}
	for i, s := range first.States {
		if ids[s.Icao24] {
			t.Fatalf("duplicate icao24 %s", s.Icao24)
		}
		ids[s.Icao24] = true
		if second.States[i].Icao24 != s.Icao24 || *second.States[i].Callsign != *s.Callsign {
			t.Fatal("identity changed between ticks")
		}
		if *s.TimePosition != first.Time {
			t.Fatal("synthetic time_position must be the tick time")
		}
	}
	if second.Time-first.Time != 1 {
		t.Errorf("tick spacing = %d s", second.Time-first.Time)
	}
}
