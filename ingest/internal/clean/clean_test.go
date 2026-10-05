package clean

import (
	"io"
	"log/slog"
	"testing"

	"github.com/habipokc/hezarfen/ingest/internal/geo"
	"github.com/habipokc/hezarfen/ingest/internal/opensky"
)

var marmara = geo.BBox{MinLon: 26, MinLat: 39.5, MaxLon: 31.5, MaxLat: 42}

func ptr[T any](v T) *T { return &v }

// state builds a valid, fresh state at (lon, lat) reported at time ts.
func state(icao string, lon, lat float64, ts int64) opensky.State {
	return opensky.State{
		Icao24: icao, Callsign: ptr("THY7AB  "), OriginCountry: "Turkey",
		TimePosition: ptr(ts), LastContact: ts, Lon: ptr(lon), Lat: ptr(lat),
		BaroAltitude: ptr(3000.0), Velocity: ptr(150.0), TrueTrack: ptr(90.0), Category: ptr(4),
	}
}

func newCleaner() *Cleaner {
	return New(marmara, slog.New(slog.NewTextHandler(io.Discard, nil)))
}

func TestValidStateBecomesRecord(t *testing.T) {
	res := newCleaner().Clean(opensky.Snapshot{Time: 1000, States: []opensky.State{state("4BAA0F", 29, 41, 998)}})
	if len(res.Records) != 1 {
		t.Fatalf("records = %d, rejected = %v", len(res.Records), res.Rejected)
	}
	r := res.Records[0]
	if r.Icao24 != "4baa0f" || *r.Callsign != "THY7AB" || r.Ts != 998 || r.Lon != 29 || r.Lat != 41 ||
		*r.Heading != 90 || *r.Category != 4 {
		t.Errorf("record = %+v", r)
	}
}

func TestRejectionRules(t *testing.T) {
	noPos := state("4b0001", 29, 41, 1000)
	noPos.Lat = nil
	noTime := state("4b0002", 29, 41, 1000)
	noTime.TimePosition = nil
	cases := []struct {
		name string
		s    opensky.State
		want Reason
	}{
		{"null position", noPos, NoPosition},
		{"outside bbox", state("4b0003", 32.86, 39.93, 1000), OutOfBBox},
		{"stale by 16 s", state("4b0004", 29, 41, 984), Stale},
		{"no time_position", noTime, Stale},
		{"bad icao24", state("xyz", 29, 41, 1000), InvalidID},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			res := newCleaner().Clean(opensky.Snapshot{Time: 1000, States: []opensky.State{c.s}})
			if len(res.Records) != 0 || res.Rejected[c.want] != 1 {
				t.Errorf("records=%d rejected=%v, want one %s", len(res.Records), res.Rejected, c.want)
			}
		})
	}
}

func TestExactly15SecondsIsNotStale(t *testing.T) {
	res := newCleaner().Clean(opensky.Snapshot{Time: 1000, States: []opensky.State{state("4b0001", 29, 41, 985)}})
	if len(res.Records) != 1 {
		t.Errorf("rejected = %v", res.Rejected)
	}
}

func TestCallsignAndSquawkNormalised(t *testing.T) {
	blank := state("4b0001", 29, 41, 1000)
	blank.Callsign = ptr("        ")
	blank.Squawk = ptr(" ")
	blank.TrueTrack = ptr(-90.0)
	res := newCleaner().Clean(opensky.Snapshot{Time: 1000, States: []opensky.State{blank}})
	r := res.Records[0]
	if r.Callsign != nil || r.Squawk != nil || *r.Heading != 270 {
		t.Errorf("callsign=%v squawk=%v heading=%v", r.Callsign, r.Squawk, *r.Heading)
	}
}

func TestHeadingInRangeIsUntouched(t *testing.T) {
	s := state("4b0001", 29, 41, 1000)
	s.TrueTrack = ptr(266.7)
	res := newCleaner().Clean(opensky.Snapshot{Time: 1000, States: []opensky.State{s}})
	if h := *res.Records[0].Heading; h != 266.7 {
		t.Errorf("heading = %v, want exactly 266.7", h)
	}
}

func TestDuplicateIcaoInSnapshotKeepsFirst(t *testing.T) {
	res := newCleaner().Clean(opensky.Snapshot{Time: 1000, States: []opensky.State{
		state("4b0001", 29, 41, 1000), state("4b0001", 29.01, 41, 1000),
	}})
	if len(res.Records) != 1 || res.Rejected[Duplicate] != 1 || res.Records[0].Lon != 29 {
		t.Errorf("records=%+v rejected=%v", res.Records, res.Rejected)
	}
}

func TestImpossibleJumpRejected(t *testing.T) {
	c := newCleaner()
	c.Clean(opensky.Snapshot{Time: 1000, States: []opensky.State{state("4b0001", 29, 41, 1000)}})

	// 0.1° of longitude at 41°N ≈ 8.4 km in 10 s = 840 m/s: impossible for an airliner
	res := c.Clean(opensky.Snapshot{Time: 1010, States: []opensky.State{state("4b0001", 29.1, 41, 1010)}})
	if len(res.Records) != 0 || res.Rejected[Jump] != 1 {
		t.Fatalf("records=%d rejected=%v", len(res.Records), res.Rejected)
	}
	// 2 km in 10 s from the last *accepted* fix = 200 m/s: fine
	res = c.Clean(opensky.Snapshot{Time: 1020, States: []opensky.State{state("4b0001", 29.024, 41, 1020)}})
	if len(res.Records) != 1 {
		t.Errorf("plausible fix rejected: %v", res.Rejected)
	}
}

func TestRepeatedTimestampSkipsJumpCheck(t *testing.T) {
	c := newCleaner()
	c.Clean(opensky.Snapshot{Time: 1000, States: []opensky.State{state("4b0001", 29, 41, 995)}})
	// OpenSky repeats the last position until a new one arrives; same ts is a duplicate
	// for the database (ON CONFLICT DO NOTHING), not a jump
	res := c.Clean(opensky.Snapshot{Time: 1005, States: []opensky.State{state("4b0001", 29, 41, 995)}})
	if len(res.Records) != 1 {
		t.Errorf("rejected = %v", res.Rejected)
	}
}

func TestPersistentJumpsReanchorTrack(t *testing.T) {
	c := newCleaner()
	// a bad first fix far from where the aircraft really is
	c.Clean(opensky.Snapshot{Time: 1000, States: []opensky.State{state("4b0001", 27, 40, 1000)}})
	var accepted int
	for i := int64(1); i <= maxConsecutiveJumps+2; i++ {
		ts := 1000 + 10*i
		res := c.Clean(opensky.Snapshot{Time: ts, States: []opensky.State{state("4b0001", 29+0.01*float64(i), 41, ts)}})
		accepted += len(res.Records)
	}
	// without re-anchoring the track would be rejected forever
	if accepted != 2 {
		t.Errorf("accepted = %d, want 2 (the re-anchoring fix and the one after it)", accepted)
	}
}

func TestWholeSecondTimestampsAllowOneSecondSlack(t *testing.T) {
	c := newCleaner()
	// 460 m apart (230 m/s for 2 s), but whole-second truncation made the timestamps
	// only 1 s apart (fixes at 11.0 s and 12.99 s): the real interval can be up to 2 s
	c.Clean(opensky.Snapshot{Time: 1011, States: []opensky.State{state("4b0001", 29, 41, 1011)}})
	res := c.Clean(opensky.Snapshot{Time: 1012, States: []opensky.State{state("4b0001", 29.00548, 41, 1012)}})
	if len(res.Records) != 1 {
		t.Fatalf("cruise-speed fix rejected: %v", res.Rejected)
	}
	// 1 km "in 1 s" is still impossible even with the slack (≥ 500 m/s)
	res = c.Clean(opensky.Snapshot{Time: 1013, States: []opensky.State{state("4b0001", 29.0174, 41, 1013)}})
	if res.Rejected[Jump] != 1 {
		t.Errorf("rejected = %v", res.Rejected)
	}
}
