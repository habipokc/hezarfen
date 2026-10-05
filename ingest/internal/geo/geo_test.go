package geo

import (
	"math"
	"testing"
)

var (
	istanbul = Point{Lon: 28.9784, Lat: 41.0082}
	ankara   = Point{Lon: 32.8597, Lat: 39.9334}
	ltfm     = Point{Lon: 28.7321, Lat: 41.2749}
	ltfj     = Point{Lon: 29.3092, Lat: 40.8986}
)

func near(t *testing.T, name string, got, want, tol float64) {
	t.Helper()
	if math.Abs(got-want) > tol {
		t.Errorf("%s = %.4f, want %.4f ± %g", name, got, want, tol)
	}
}

func TestDistanceIstanbulAnkara(t *testing.T) {
	// city centres are ~350 km apart along the great circle
	near(t, "distance km", Distance(istanbul, ankara)/1000, 350, 5)
}

func TestDistanceIsSymmetricAndZeroForSamePoint(t *testing.T) {
	near(t, "a->b - b->a", Distance(ltfm, ltfj)-Distance(ltfj, ltfm), 0, 1e-6)
	near(t, "same point", Distance(ltfm, ltfm), 0, 1e-9)
}

func TestDistanceOneDegreeLatitude(t *testing.T) {
	// one degree of latitude on the mean-radius sphere = 2πR/360 ≈ 111.195 km
	near(t, "1° lat km", Distance(Point{29, 40}, Point{29, 41})/1000, 111.195, 0.01)
}

func TestBearingCardinalDirections(t *testing.T) {
	o := Point{Lon: 29, Lat: 41}
	near(t, "north", Bearing(o, Point{29, 42}), 0, 1e-9)
	near(t, "south", Bearing(o, Point{29, 40}), 180, 1e-9)
	// due east on a great circle starts slightly north of 90° and is never exactly 90 off the equator
	near(t, "east", Bearing(o, Point{30, 41}), 89.67, 0.05)
	near(t, "west", Bearing(o, Point{28, 41}), 270.33, 0.05)
}

func TestBearingIsNormalised(t *testing.T) {
	b := Bearing(ltfj, ltfm) // north-west
	if b < 0 || b >= 360 {
		t.Fatalf("bearing %.2f outside [0, 360)", b)
	}
	near(t, "LTFJ->LTFM", b, 311.4, 1)
}

func TestInterpolateEndpointsAndMidpoint(t *testing.T) {
	start := Interpolate(istanbul, ankara, 0)
	end := Interpolate(istanbul, ankara, 1)
	near(t, "start", Distance(start, istanbul), 0, 0.01)
	near(t, "end", Distance(end, ankara), 0, 0.01)

	mid := Interpolate(istanbul, ankara, 0.5)
	half := Distance(istanbul, ankara) / 2
	near(t, "mid->istanbul", Distance(mid, istanbul), half, 0.5)
	near(t, "mid->ankara", Distance(mid, ankara), half, 0.5)
}

func TestInterpolateSamePoint(t *testing.T) {
	p := Interpolate(ltfm, ltfm, 0.3)
	if p != ltfm {
		t.Fatalf("got %+v, want %+v", p, ltfm)
	}
}

func TestDestinationRoundTrip(t *testing.T) {
	d := Destination(ltfj, 311.4, 15_000)
	near(t, "distance", Distance(ltfj, d), 15_000, 0.5)
	near(t, "bearing", Bearing(ltfj, d), 311.4, 1e-6)
}

func TestBBoxContains(t *testing.T) {
	b := BBox{MinLon: 26, MinLat: 39.5, MaxLon: 31.5, MaxLat: 42}
	cases := []struct {
		p    Point
		want bool
	}{
		{ltfm, true},
		{Point{26, 39.5}, true}, // edges are inside
		{Point{25.99, 41}, false},
		{Point{29, 42.01}, false},
		{ankara, false},
	}
	for _, c := range cases {
		if got := b.Contains(c.p); got != c.want {
			t.Errorf("Contains(%+v) = %v, want %v", c.p, got, c.want)
		}
	}
}
