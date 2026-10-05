// Package source produces state snapshots from one of three interchangeable modes
// (PLAN §4): live OpenSky polling, replay of recorded raw responses, or synthetic
// flights. Downstream code sees the same Frame from all of them.
package source

import (
	"context"

	"github.com/habipokc/hezarfen/ingest/internal/config"
	"github.com/habipokc/hezarfen/ingest/internal/opensky"
)

// Frame is one ingest cycle's input.
type Frame struct {
	opensky.Snapshot
	// Retime maps a source timestamp to the wall-clock timestamp stored and published.
	// Cleaning runs on source timestamps (so speed checks stay physical even when a
	// replay runs 10× faster); nil means the timestamps are already wall-clock.
	Retime func(int64) int64
	// Restart is true when a replay loops back to its first recording: the stream's
	// time goes backwards, so per-aircraft history (the jump filter) must be reset.
	Restart bool
	// Credits is OpenSky's X-Rate-Limit-Remaining, live mode only.
	Credits *int
}

// Source is implemented by Live, Replay and Synthetic. Next blocks until the next
// frame is due (poll interval, recorded spacing or simulation tick) or ctx ends.
type Source interface {
	Name() string
	Next(ctx context.Context) (Frame, error)
}

// ResolveMode turns "auto" into a concrete mode: live if OpenSky credentials exist,
// else replay if recordings exist, else synthetic (PLAN §4).
func ResolveMode(cfg config.Config) string {
	if cfg.Mode != config.ModeAuto {
		return cfg.Mode
	}
	switch {
	case cfg.HasCredentials():
		return config.ModeLive
	case HasRecordings(cfg.ReplayDir):
		return config.ModeReplay
	default:
		return config.ModeSynthetic
	}
}
