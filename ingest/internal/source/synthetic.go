package source

import (
	"context"
	"fmt"
	"math"
	"math/rand/v2"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/geo"
	"github.com/habipokc/hezarfen/ingest/internal/opensky"
)

const (
	overflightShare = 0.2
	parkedAtStart   = 0.15
	// edgeInset keeps overflight endpoints inside the bbox: a great circle between two
	// points on the northern edge bulges ~0.1° further north.
	edgeInset = 0.2
)

type airline struct{ code, country, icaoPrefix string }

var (
	domestic = []airline{{"THY", "Turkey", "4b"}, {"PGT", "Turkey", "4b"}, {"AJA", "Turkey", "4b"}, {"SXS", "Turkey", "4b"}}
	foreign  = []airline{
		{"DLH", "Germany", "3c"}, {"BAW", "United Kingdom", "40"}, {"AFR", "France", "39"},
		{"UAE", "United Arab Emirates", "89"}, {"QTR", "Qatar", "06"}, {"WZZ", "Hungary", "47"},
	}
)

type SyntheticOptions struct {
	Airports []Airport // at least two
	Count    int
	Tick     time.Duration
	Seed     int64 // 0 picks a random seed per start
	BBox     geo.BBox
	Now      func() time.Time
	Sleep    func(ctx context.Context, d time.Duration) error
}

// Synthetic simulates traffic between the region's airports plus overflights,
// with no network. Every aircraft always reports a fresh, plausible fix, so the
// whole pipeline (cleaning included) can be exercised deterministically.
type Synthetic struct {
	opts    SyntheticOptions
	rng     *rand.Rand
	flights []*flight
	ids     map[string]bool
	started bool
}

func NewSynthetic(o SyntheticOptions) *Synthetic {
	if o.Seed == 0 {
		o.Seed = time.Now().UnixNano()
	}
	if o.Now == nil {
		o.Now = time.Now
	}
	if o.Sleep == nil {
		o.Sleep = opensky.Sleep
	}
	s := &Synthetic{
		opts: o,
		rng:  rand.New(rand.NewPCG(uint64(o.Seed), uint64(o.Seed)>>1^0x9e3779b97f4a7c15)),
		ids:  make(map[string]bool),
	}
	for range o.Count {
		f := &flight{}
		if s.rng.Float64() < overflightShare {
			s.startOverflight(f)
		} else {
			s.startAirportFlight(f)
		}
		s.flights = append(s.flights, f)
	}
	return s
}

func (s *Synthetic) Name() string { return "synthetic" }

func (s *Synthetic) Next(ctx context.Context) (Frame, error) {
	if s.started {
		if err := s.opts.Sleep(ctx, s.opts.Tick); err != nil {
			return Frame{}, err
		}
		dt := s.opts.Tick.Seconds()
		for _, f := range s.flights {
			f.step(dt, s.nextLeg)
		}
	}
	s.started = true
	now := s.opts.Now().Unix()
	snap := opensky.Snapshot{Time: now, States: make([]opensky.State, 0, len(s.flights))}
	for _, f := range s.flights {
		snap.States = append(snap.States, f.toState(now))
	}
	return Frame{Snapshot: snap}, nil
}

// nextLeg is called by a flight that finished: parked airliners depart again from
// where they are; an overflight that left the region is replaced by a new aircraft
// entering elsewhere (reusing its identity would look like a teleport).
func (s *Synthetic) nextLeg(f *flight) {
	if f.overfly {
		delete(s.ids, f.icao24)
		s.startOverflight(f)
		f.flown = 0
		return
	}
	from := f.to
	f.startLeg(from, pickDestination(s.rng, s.opts.Airports, from))
	f.turnaround = 60 + 120*s.rng.Float64()
}

func (s *Synthetic) startAirportFlight(f *flight) {
	al := domestic[s.rng.IntN(len(domestic))]
	s.identify(f, al)
	f.category = 4 // large: A320/B737 class
	from := s.opts.Airports[s.rng.IntN(len(s.opts.Airports))]
	f.startLeg(from, pickDestination(s.rng, s.opts.Airports, from))
	f.turnaround = 60 + 120*s.rng.Float64()
	if s.rng.Float64() < parkedAtStart {
		// parked at the origin, about to depart
		f.to, f.flown, f.parked = from, f.total, 1+120*s.rng.Float64()
		return
	}
	// spread the fleet along its routes so the map is busy from the first tick
	f.flown = f.total * s.rng.Float64()
	f.lastAlt = f.altitude()
}

func (s *Synthetic) startOverflight(f *flight) {
	al := foreign[s.rng.IntN(len(foreign))]
	s.identify(f, al)
	f.overfly = true
	f.category = 4 + 2*s.rng.IntN(2) // large or heavy
	f.cruise = 9000 + 300*float64(s.rng.IntN(11))
	for {
		a, b := s.edgePoint(-1)
		c, _ := s.edgePoint(b)
		if geo.Distance(a, c) >= 150_000 {
			f.startLeg(Airport{Ident: "edge", Point: a}, Airport{Ident: "edge", Point: c})
			break
		}
	}
	f.flown = f.total * s.rng.Float64()
	f.lastAlt = f.cruise
}

// edgePoint returns a random point on one bbox edge (other than skip) and the edge index.
func (s *Synthetic) edgePoint(skip int) (geo.Point, int) {
	b := s.opts.BBox
	for {
		e := s.rng.IntN(4)
		if e == skip {
			continue
		}
		u := s.rng.Float64()
		lon := b.MinLon + edgeInset + u*(b.MaxLon-b.MinLon-2*edgeInset)
		lat := b.MinLat + edgeInset + u*(b.MaxLat-b.MinLat-2*edgeInset)
		switch e {
		case 0:
			return geo.Point{Lon: lon, Lat: b.MaxLat - edgeInset}, e
		case 1:
			return geo.Point{Lon: b.MaxLon - edgeInset, Lat: lat}, e
		case 2:
			return geo.Point{Lon: lon, Lat: b.MinLat + edgeInset}, e
		default:
			return geo.Point{Lon: b.MinLon + edgeInset, Lat: lat}, e
		}
	}
}

// identify gives f a new unique icao24 from the airline's country block, a callsign
// and a squawk code.
func (s *Synthetic) identify(f *flight, al airline) {
	for {
		id := fmt.Sprintf("%s%04x", al.icaoPrefix, s.rng.IntN(0x10000))
		if !s.ids[id] {
			s.ids[id] = true
			f.icao24 = id
			break
		}
	}
	f.callsign = fmt.Sprintf("%s%d", al.code, 100+s.rng.IntN(9900))
	f.country = al.country
	// 4 octal digits; first digit 1–6 keeps clear of 7500/7600/7700 emergencies
	f.squawk = fmt.Sprintf("%d%d%d%d", 1+s.rng.IntN(6), s.rng.IntN(8), s.rng.IntN(8), s.rng.IntN(8))
	f.geoOffset = 20 + 60*s.rng.Float64()
}

func (f *flight) toState(now int64) opensky.State {
	st := f.state()
	lon, lat := round(st.pos.Lon, 5), round(st.pos.Lat, 5)
	velocity, heading, vrate := round(st.velocity, 2), round(st.heading, 2), round(st.vrate, 2)
	callsign, squawk, category := f.callsign, f.squawk, f.category
	s := opensky.State{
		Icao24: f.icao24, Callsign: &callsign, OriginCountry: f.country,
		TimePosition: &now, LastContact: now, Lon: &lon, Lat: &lat,
		OnGround: st.onGround, Velocity: &velocity, TrueTrack: &heading, VerticalRate: &vrate,
		Squawk: &squawk, Category: &category,
	}
	if !st.onGround { // like OpenSky, aircraft on the ground report no altitude
		baro, geoAlt := round(st.alt, 2), round(st.alt+f.geoOffset, 2)
		s.BaroAltitude, s.GeoAltitude = &baro, &geoAlt
	}
	return s
}

func round(v float64, places int) float64 {
	p := math.Pow(10, float64(places))
	return math.Round(v*p) / p
}
