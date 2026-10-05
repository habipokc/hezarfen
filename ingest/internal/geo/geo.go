// Package geo holds the spherical-earth math ingest needs: distances for the jump
// filter, and bearings and great-circle paths for synthetic flights.
//
// A sphere with the mean earth radius is accurate to ~0.5% against the WGS84
// ellipsoid, which is far below what a 400 m/s plausibility check or a demo flight
// can notice. PostGIS geography (spheroid) remains the reference for stored data.
package geo

import "math"

// EarthRadius is the mean earth radius in metres (IUGG).
const EarthRadius = 6_371_008.8

// Point is a WGS84 position, lon/lat order as everywhere in Hezarfen (ICD §2).
type Point struct {
	Lon, Lat float64
}

// BBox is a lon/lat rectangle; edges count as inside.
type BBox struct {
	MinLon, MinLat, MaxLon, MaxLat float64
}

func (b BBox) Contains(p Point) bool {
	return p.Lon >= b.MinLon && p.Lon <= b.MaxLon && p.Lat >= b.MinLat && p.Lat <= b.MaxLat
}

func rad(deg float64) float64 { return deg * math.Pi / 180 }
func deg(rad float64) float64 { return rad * 180 / math.Pi }

// centralAngle is the angle between a and b seen from the earth's centre (haversine).
func centralAngle(a, b Point) float64 {
	φ1, φ2 := rad(a.Lat), rad(b.Lat)
	dφ, dλ := φ2-φ1, rad(b.Lon-a.Lon)
	h := math.Sin(dφ/2)*math.Sin(dφ/2) + math.Cos(φ1)*math.Cos(φ2)*math.Sin(dλ/2)*math.Sin(dλ/2)
	// clamp: rounding can push h a hair above 1 for antipodal points
	return 2 * math.Asin(math.Sqrt(math.Min(1, h)))
}

// Distance is the great-circle distance in metres (haversine formula).
func Distance(a, b Point) float64 {
	return EarthRadius * centralAngle(a, b)
}

// Bearing is the initial true course from a towards b, in degrees [0, 360).
// Along a great circle the course changes as you fly, so callers re-evaluate it
// from the current position rather than keeping the departure value.
func Bearing(a, b Point) float64 {
	φ1, φ2 := rad(a.Lat), rad(b.Lat)
	dλ := rad(b.Lon - a.Lon)
	y := math.Sin(dλ) * math.Cos(φ2)
	x := math.Cos(φ1)*math.Sin(φ2) - math.Sin(φ1)*math.Cos(φ2)*math.Cos(dλ)
	return math.Mod(deg(math.Atan2(y, x))+360, 360)
}

// Interpolate returns the point at fraction f (0 = a, 1 = b) along the great circle
// from a to b (spherical linear interpolation of the two unit vectors).
func Interpolate(a, b Point, f float64) Point {
	δ := centralAngle(a, b)
	if δ == 0 {
		return a
	}
	φ1, λ1, φ2, λ2 := rad(a.Lat), rad(a.Lon), rad(b.Lat), rad(b.Lon)
	wa := math.Sin((1-f)*δ) / math.Sin(δ)
	wb := math.Sin(f*δ) / math.Sin(δ)
	x := wa*math.Cos(φ1)*math.Cos(λ1) + wb*math.Cos(φ2)*math.Cos(λ2)
	y := wa*math.Cos(φ1)*math.Sin(λ1) + wb*math.Cos(φ2)*math.Sin(λ2)
	z := wa*math.Sin(φ1) + wb*math.Sin(φ2)
	return Point{Lon: deg(math.Atan2(y, x)), Lat: deg(math.Atan2(z, math.Hypot(x, y)))}
}

// Destination is the point reached from p after dist metres on initial course bearing.
func Destination(p Point, bearing, dist float64) Point {
	φ1, λ1, θ := rad(p.Lat), rad(p.Lon), rad(bearing)
	δ := dist / EarthRadius
	φ2 := math.Asin(math.Sin(φ1)*math.Cos(δ) + math.Cos(φ1)*math.Sin(δ)*math.Cos(θ))
	λ2 := λ1 + math.Atan2(math.Sin(θ)*math.Sin(δ)*math.Cos(φ1), math.Cos(δ)-math.Sin(φ1)*math.Sin(φ2))
	return Point{Lon: math.Mod(deg(λ2)+540, 360) - 180, Lat: deg(φ2)}
}
