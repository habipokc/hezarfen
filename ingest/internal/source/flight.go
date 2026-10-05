package source

import (
	"math"
	"math/rand/v2"

	"github.com/habipokc/hezarfen/ingest/internal/geo"
)

// Flight model constants. The profile is a function of distance flown, not time, so
// climb, cruise and descent always fit the leg, however short it is.
const (
	climbGradient   = 0.08     // m gained per m flown ≈ 4.6° (≈2,000 ft/min at 150 kt)
	descentGradient = 0.0524   // tan(3°): the standard ILS glide slope
	maxCruise       = 10_800.0 // ≈ FL350, a multiple of 300 m
	rotateSpeed     = 75.0     // m/s at lift-off (≈145 kt)
	lowSpeed        = 128.0    // m/s at 3,000 m (the 250 kt below FL100 rule)
	cruiseSpeed     = 230.0    // m/s (≈450 kt ground speed)
	minLeg          = 40_000.0
	hubShare        = 0.75 // share of flights that start or end at a hub (LTFM/LTFJ)
)

// hubs are the airports with seed geofences, so most synthetic traffic crosses them.
var hubs = map[string]bool{"LTFM": true, "LTFJ": true}

// Airport is a possible origin or destination.
type Airport struct {
	Ident string
	geo.Point
}

// cruiseFor picks a cruise altitude that leaves a level segment: the profile
// min(s·climb, (total−s)·descent) peaks at total·climb·descent/(climb+descent);
// cruising at 85% of that peak guarantees top of climb comes before top of descent.
// Rounded down to 300 m, roughly a 1,000 ft flight level.
func cruiseFor(total float64) float64 {
	peak := total * climbGradient * descentGradient / (climbGradient + descentGradient)
	return math.Floor(math.Min(maxCruise, 0.85*peak)/300) * 300
}

// altitudeAt is the altitude after s metres of a total-metre leg.
func altitudeAt(total, cruise, s float64) float64 {
	return math.Max(0, math.Min(cruise, math.Min(s*climbGradient, (total-s)*descentGradient)))
}

// speedAt is the ground speed for an altitude: slow near the ground, cruise speed
// from 9,000 m up.
func speedAt(alt float64) float64 {
	if alt < 3000 {
		return rotateSpeed + (lowSpeed-rotateSpeed)*alt/3000
	}
	return lowSpeed + (cruiseSpeed-lowSpeed)*math.Min(1, (alt-3000)/6000)
}

// flight is one aircraft's simulated state. An airport flight flies legs between
// airports and parks for a while after each landing; an overflight crosses the
// region at constant altitude between two points on the bbox edge.
type flight struct {
	icao24, callsign, country, squawk string
	category                          int

	from, to   Airport
	total      float64 // great-circle leg length, m
	flown      float64 // distance flown along the leg, m
	cruise     float64
	overfly    bool
	parked     float64 // seconds left on the ground; > 0 means on ground
	turnaround float64 // seconds to park after the next landing
	lastAlt    float64
	vrate      float64
	lastHead   float64
	geoOffset  float64 // geometric minus barometric altitude, m
}

// flightState is what a flight reports for one tick.
type flightState struct {
	pos      geo.Point
	alt      float64
	velocity float64
	heading  float64
	vrate    float64
	onGround bool
}

func newLeg(from, to Airport) *flight {
	f := &flight{}
	f.startLeg(from, to)
	return f
}

func (f *flight) startLeg(from, to Airport) {
	f.from, f.to = from, to
	f.total = geo.Distance(from.Point, to.Point)
	f.flown = 0
	f.parked = 0
	f.lastAlt = 0
	if !f.overfly {
		f.cruise = cruiseFor(f.total)
	}
	f.lastHead = geo.Bearing(from.Point, to.Point)
}

// step advances the simulation by dt seconds. next starts a new leg once the
// aircraft has turned around (or an overflight has left); nil keeps it where it is,
// which tests use to fly a single leg.
func (f *flight) step(dt float64, next func(f *flight)) {
	if f.parked > 0 {
		f.parked -= dt
		f.vrate = 0
		if f.parked <= 0 && next != nil {
			next(f)
		}
		return
	}
	f.flown += f.speed() * dt
	if f.flown >= f.total {
		f.flown = f.total
		if f.overfly {
			if next != nil {
				next(f)
			}
			return
		}
		f.parked = math.Max(f.turnaround, dt)
		f.vrate = 0
		f.lastAlt = 0
		return
	}
	newAlt := f.altitude()
	f.vrate = (newAlt - f.lastAlt) / dt
	f.lastAlt = newAlt
	if f.total-f.flown > 100 { // the bearing to a point you are on top of is noise
		f.lastHead = geo.Bearing(f.position(), f.to.Point)
	}
}

func (f *flight) altitude() float64 {
	if f.overfly {
		return f.cruise
	}
	return altitudeAt(f.total, f.cruise, f.flown)
}

func (f *flight) speed() float64 {
	if f.overfly {
		return cruiseSpeed
	}
	return speedAt(f.altitude())
}

func (f *flight) position() geo.Point {
	if f.total == 0 {
		return f.from.Point
	}
	return geo.Interpolate(f.from.Point, f.to.Point, f.flown/f.total)
}

func (f *flight) state() flightState {
	if f.parked > 0 || (!f.overfly && f.flown >= f.total) {
		return flightState{pos: f.to.Point, heading: f.lastHead, onGround: true}
	}
	return flightState{pos: f.position(), alt: f.altitude(), velocity: f.speed(), heading: f.lastHead, vrate: f.vrate}
}

// pickDestination chooses where a flight from `from` goes next: preferably a hub,
// never an airport closer than minLeg (or the origin itself).
func pickDestination(rng *rand.Rand, airports []Airport, from Airport) Airport {
	var hubCands, others []Airport
	for _, a := range airports {
		if a.Ident == from.Ident || geo.Distance(a.Point, from.Point) < minLeg {
			continue
		}
		if hubs[a.Ident] {
			hubCands = append(hubCands, a)
		} else {
			others = append(others, a)
		}
	}
	// a flight that starts at a hub may go to the other hub or anywhere else
	if len(hubCands) > 0 && (len(others) == 0 || (!hubs[from.Ident] && rng.Float64() < hubShare)) {
		return hubCands[rng.IntN(len(hubCands))]
	}
	if all := append(others, hubCands...); len(all) > 0 {
		return all[rng.IntN(len(all))]
	}
	// every other airport is a hop away: take the farthest one
	best := airports[0]
	for _, a := range airports {
		if a.Ident != from.Ident && geo.Distance(a.Point, from.Point) > geo.Distance(best.Point, from.Point) {
			best = a
		}
	}
	return best
}
