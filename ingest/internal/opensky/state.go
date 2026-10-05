// Package opensky talks to the OpenSky Network REST API (ICD IF-1): OAuth2 client
// credentials, the /states/all endpoint and its positional-array response format.
package opensky

import (
	"encoding/json"
	"fmt"
)

// State is one state vector. OpenSky sends it as a JSON array whose meaning depends
// on the index; any field except icao24 may be null, so nullable fields are pointers
// (nil = "unknown", which is different from 0 m altitude or 0 m/s speed).
type State struct {
	Icao24         string   // 0
	Callsign       *string  // 1, padded with spaces to 8 chars
	OriginCountry  string   // 2
	TimePosition   *int64   // 3, Unix s of the last position report; null if none in 15 s
	LastContact    int64    // 4, Unix s of the last message of any kind
	Lon            *float64 // 5
	Lat            *float64 // 6
	BaroAltitude   *float64 // 7, m
	OnGround       bool     // 8
	Velocity       *float64 // 9, m/s over ground
	TrueTrack      *float64 // 10, degrees clockwise from north
	VerticalRate   *float64 // 11, m/s
	GeoAltitude    *float64 // 13, m
	Squawk         *string  // 14
	PositionSource int      // 16: 0 ADS-B, 1 ASTERIX, 2 MLAT, 3 FLARM
	Category       *int     // 17, only with extended=1
}

// Snapshot is one /states/all response: the server time and every state in the bbox.
type Snapshot struct {
	Time      int64
	States    []State
	Malformed int // rows that could not be decoded and were skipped
}

// minFields is the length of a state array without the extended category field.
const minFields = 17

// ParseStates decodes a /states/all body. A malformed row is skipped and counted
// rather than failing the whole snapshot: one bad transponder should not blank the map.
func ParseStates(body []byte) (Snapshot, error) {
	var raw struct {
		Time   int64               `json:"time"`
		States [][]json.RawMessage `json:"states"` // null when the bbox is empty
	}
	if err := json.Unmarshal(body, &raw); err != nil {
		return Snapshot{}, fmt.Errorf("decode states response: %w", err)
	}
	snap := Snapshot{Time: raw.Time, States: make([]State, 0, len(raw.States))}
	for _, row := range raw.States {
		s, err := parseRow(row)
		if err != nil {
			snap.Malformed++
			continue
		}
		snap.States = append(snap.States, s)
	}
	return snap, nil
}

func parseRow(row []json.RawMessage) (State, error) {
	if len(row) < minFields {
		return State{}, fmt.Errorf("state has %d fields, want >= %d", len(row), minFields)
	}
	var s State
	var origin *string
	var posSource *int
	// json.Unmarshal of `null` into a pointer leaves it nil, which is exactly "unknown"
	targets := map[int]any{
		0: &s.Icao24, 1: &s.Callsign, 2: &origin, 3: &s.TimePosition, 4: &s.LastContact,
		5: &s.Lon, 6: &s.Lat, 7: &s.BaroAltitude, 8: &s.OnGround, 9: &s.Velocity,
		10: &s.TrueTrack, 11: &s.VerticalRate, 13: &s.GeoAltitude, 14: &s.Squawk, 16: &posSource,
	}
	if len(row) > minFields {
		targets[17] = &s.Category
	}
	for i, dst := range targets {
		if err := json.Unmarshal(row[i], dst); err != nil {
			return State{}, fmt.Errorf("field %d: %w", i, err)
		}
	}
	if s.Icao24 == "" {
		return State{}, fmt.Errorf("empty icao24")
	}
	if origin != nil {
		s.OriginCountry = *origin
	}
	if posSource != nil {
		s.PositionSource = *posSource
	}
	return s, nil
}
