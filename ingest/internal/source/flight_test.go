package source

import (
	"math"
	"math/rand/v2"
	"testing"

	"github.com/habipokc/hezarfen/ingest/internal/geo"
)

var (
	ltfm = Airport{Ident: "LTFM", Point: geo.Point{Lon: 28.7321, Lat: 41.2749}}
	ltfj = Airport{Ident: "LTFJ", Point: geo.Point{Lon: 29.3092, Lat: 40.8986}}
	ltfd = Airport{Ident: "LTFD", Point: geo.Point{Lon: 27.0102, Lat: 39.5525}}
)

func TestAltitudeProfileStartsAndEndsOnGround(t *testing.T) {
	total := 250_000.0
	cruise := cruiseFor(total)
	if a := altitudeAt(total, cruise, 0); a != 0 {
		t.Errorf("alt at departure = %.1f", a)
	}
	if a := altitudeAt(total, cruise, total); a != 0 {
		t.Errorf("alt at arrival = %.1f", a)
	}
	for s := 0.0; s <= total; s += 1000 {
		if a := altitudeAt(total, cruise, s); a < 0 || a > cruise {
			t.Fatalf("alt(%.0f) = %.1f outside [0, %.0f]", s, a, cruise)
		}
	}
}

func TestCruiseAltitude(t *testing.T) {
	if c := cruiseFor(2_000_000); c != maxCruise {
		t.Errorf("long route cruise = %.0f, want cap %.0f", c, maxCruise)
	}
	// short hop (LTFJ–LTFM ≈ 60 km): low cruise, but still a level segment between climb and descent
	total := geo.Distance(ltfj.Point, ltfm.Point)
	c := cruiseFor(total)
	topOfClimb, topOfDescent := c/climbGradient, total-c/descentGradient
	if c < 600 || c > 3000 || topOfClimb >= topOfDescent {
		t.Errorf("cruise %.0f m, climb ends %.0f m, descent starts %.0f m", c, topOfClimb, topOfDescent)
	}
	if math.Mod(c, 300) != 0 {
		t.Errorf("cruise %.0f is not a multiple of 300 m (flight levels)", c)
	}
}

func TestSpeedProfile(t *testing.T) {
	if v := speedAt(0); v != rotateSpeed {
		t.Errorf("speed at 0 m = %.1f", v)
	}
	if v := speedAt(maxCruise); v != cruiseSpeed {
		t.Errorf("speed at cruise = %.1f", v)
	}
	prev := 0.0
	for alt := 0.0; alt <= 12_000; alt += 250 {
		v := speedAt(alt)
		if v < prev {
			t.Fatalf("speed decreases at %.0f m", alt)
		}
		prev = v
	}
}

// fly runs one leg to completion with dt-second steps and returns every state seen.
func fly(t *testing.T, f *flight, dt float64) []flightState {
	t.Helper()
	var out []flightState
	for i := 0; i < 10_000; i++ {
		f.step(dt, nil)
		st := f.state()
		out = append(out, st)
		if st.onGround {
			return out
		}
	}
	t.Fatal("flight never landed")
	return nil
}

func TestLegFliesToDestinationPlausibly(t *testing.T) {
	f := newLeg(ltfd, ltfm)
	states := fly(t, f, 2)

	last := states[len(states)-1]
	if d := geo.Distance(last.pos, ltfm.Point); d > 100 {
		t.Errorf("landed %.0f m from LTFM", d)
	}
	if last.velocity != 0 || !last.onGround {
		t.Errorf("after landing: %+v", last)
	}
	maxAlt := 0.0
	for i := 1; i < len(states); i++ {
		a, b := states[i-1], states[i]
		if v := geo.Distance(a.pos, b.pos) / 2; v > 300 {
			t.Fatalf("step %d moved at %.0f m/s", i, v)
		}
		if b.onGround {
			continue
		}
		if math.Abs(b.vrate) > 25 {
			t.Errorf("step %d vertical rate %.1f m/s", i, b.vrate)
		}
		if diff := math.Abs(b.heading - geo.Bearing(b.pos, ltfm.Point)); diff > 1 && diff < 359 {
			t.Errorf("step %d heading %.1f does not point at the destination", i, b.heading)
		}
		maxAlt = math.Max(maxAlt, b.alt)
	}
	if maxAlt < 5000 {
		t.Errorf("~210 km leg peaked at only %.0f m", maxAlt)
	}
}

func TestPickDestinationPrefersHubsAndAvoidsHops(t *testing.T) {
	airports := []Airport{ltfm, ltfj, ltfd, {Ident: "LTBX", Point: geo.Point{Lon: 29.2165, Lat: 40.9930}}}
	rng := rand.New(rand.NewPCG(1, 2))
	hubs := 0
	for range 1000 {
		to := pickDestination(rng, airports, ltfd)
		if to.Ident == ltfd.Ident {
			t.Fatal("destination equals origin")
		}
		if to.Ident == "LTFM" || to.Ident == "LTFJ" {
			hubs++
		}
	}
	if hubs < 700 {
		t.Errorf("hub share = %d/1000, want most flights to touch the geofenced hubs", hubs)
	}
	// LTBX (Samandıra) is ~11 km from LTFJ: too short to be a flight
	for range 200 {
		if to := pickDestination(rng, airports, ltfj); to.Ident == "LTBX" {
			t.Fatal("picked a destination closer than minLeg")
		}
	}
}
