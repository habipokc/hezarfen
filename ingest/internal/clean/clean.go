// Package clean is the "clean" step of the ETL: it turns raw state vectors from any
// source into Records that satisfy ICD §4.2, and counts what it throws away.
package clean

import (
	"log/slog"
	"math"
	"regexp"
	"strings"

	"github.com/habipokc/hezarfen/ingest/internal/geo"
	"github.com/habipokc/hezarfen/ingest/internal/opensky"
)

const (
	// MaxAge: a position older than this relative to the snapshot is stale (PLAN §7 Faz 2).
	MaxAge = 15
	// MaxSpeed in m/s between two fixes; airliners cruise at ~250 m/s ground speed,
	// so 400 leaves room for jet-stream tailwinds but not for teleporting.
	MaxSpeed = 400.0
	// After this many jumps in a row, the stored fix is the suspect, not the new ones.
	maxConsecutiveJumps = 3
	// Forget an aircraft's last fix after this long, so the map does not grow forever.
	forgetAfter = 600
)

// Record is a cleaned position: position fields are guaranteed, the rest may be nil.
type Record struct {
	Icao24        string
	Callsign      *string
	OriginCountry string
	Ts            int64 // position time, Unix s
	Lon, Lat      float64
	BaroAlt       *float64
	GeoAlt        *float64
	Velocity      *float64
	Heading       *float64
	VRate         *float64
	OnGround      bool
	Squawk        *string
	Category      *int
}

// Reason names a rejection rule; used as a metrics and log key.
type Reason string

const (
	InvalidID  Reason = "invalid_icao24"
	NoPosition Reason = "no_position"
	OutOfBBox  Reason = "out_of_bbox"
	Stale      Reason = "stale"
	Duplicate  Reason = "duplicate"
	Jump       Reason = "impossible_jump"
)

type Result struct {
	Records  []Record
	Rejected map[Reason]int
}

type fix struct {
	p     geo.Point
	ts    int64
	jumps int // consecutive rejected jumps against this fix
}

// Cleaner keeps the last accepted fix per aircraft for the jump filter, so one
// Cleaner must see every snapshot of a stream in order. Not safe for concurrent use.
type Cleaner struct {
	bbox geo.BBox
	log  *slog.Logger
	last map[string]*fix
}

func New(bbox geo.BBox, log *slog.Logger) *Cleaner {
	return &Cleaner{bbox: bbox, log: log, last: make(map[string]*fix)}
}

var icaoRe = regexp.MustCompile(`^[0-9a-f]{6}$`)

func (c *Cleaner) Clean(snap opensky.Snapshot) Result {
	res := Result{Records: make([]Record, 0, len(snap.States)), Rejected: make(map[Reason]int)}
	seen := make(map[string]bool, len(snap.States))
	for _, s := range snap.States {
		r, reason := c.check(s, snap.Time, seen)
		if reason != "" {
			res.Rejected[reason]++
			continue
		}
		res.Records = append(res.Records, r)
	}
	for id, f := range c.last {
		if snap.Time-f.ts > forgetAfter {
			delete(c.last, id)
		}
	}
	return res
}

func (c *Cleaner) check(s opensky.State, now int64, seen map[string]bool) (Record, Reason) {
	id := strings.ToLower(strings.TrimSpace(s.Icao24))
	if !icaoRe.MatchString(id) {
		return Record{}, InvalidID
	}
	if s.Lon == nil || s.Lat == nil {
		return Record{}, NoPosition
	}
	p := geo.Point{Lon: *s.Lon, Lat: *s.Lat}
	if !c.bbox.Contains(p) {
		return Record{}, OutOfBBox
	}
	if s.TimePosition == nil || now-*s.TimePosition > MaxAge {
		return Record{}, Stale
	}
	if seen[id] {
		// two rows for one aircraft would make the batch upsert touch a row twice
		return Record{}, Duplicate
	}
	seen[id] = true
	ts := *s.TimePosition
	if c.isJump(id, p, ts) {
		return Record{}, Jump
	}

	r := Record{
		Icao24: id, Callsign: trimmed(s.Callsign), OriginCountry: s.OriginCountry, Ts: ts,
		Lon: p.Lon, Lat: p.Lat, BaroAlt: s.BaroAltitude, GeoAlt: s.GeoAltitude, Velocity: s.Velocity,
		VRate: s.VerticalRate, OnGround: s.OnGround, Squawk: trimmed(s.Squawk), Category: s.Category,
	}
	if h := s.TrueTrack; h != nil {
		if *h < 0 || *h >= 360 { // ICD: [0, 360); only touch values outside it, since
			v := math.Mod(math.Mod(*h, 360)+360, 360) // (x+360) mod 360 adds float noise
			h = &v
		}
		r.Heading = h
	}
	return r, ""
}

// isJump compares a fix with the aircraft's last accepted fix and records it if
// accepted. A rejected fix does not move the anchor, so one glitch cannot drag the
// track; but after maxConsecutiveJumps rejections the anchor itself is presumed bad
// and the new fix replaces it.
func (c *Cleaner) isJump(id string, p geo.Point, ts int64) bool {
	prev, ok := c.last[id]
	if !ok {
		c.last[id] = &fix{p: p, ts: ts}
		return false
	}
	if dt := ts - prev.ts; dt > 0 {
		// Timestamps are whole seconds, so the true interval can be up to dt+1: judge
		// by the slowest speed the fixes allow, or 2 s ticks read as 1 s double the speed.
		speed := geo.Distance(prev.p, p) / float64(dt+1)
		if speed > MaxSpeed {
			prev.jumps++
			if prev.jumps <= maxConsecutiveJumps {
				c.log.Warn("impossible jump rejected", "icao24", id, "speed_ms", math.Round(speed), "dt_s", dt)
				return true
			}
			c.log.Warn("re-anchoring track after repeated jumps", "icao24", id, "speed_ms", math.Round(speed))
		}
	}
	if ts >= prev.ts {
		*prev = fix{p: p, ts: ts}
	}
	return false
}

func trimmed(s *string) *string {
	if s == nil {
		return nil
	}
	t := strings.TrimSpace(*s)
	if t == "" {
		return nil
	}
	return &t
}
