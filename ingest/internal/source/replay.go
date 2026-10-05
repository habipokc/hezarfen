package source

import (
	"compress/gzip"
	"context"
	"fmt"
	"io"
	"io/fs"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/opensky"
)

const (
	// maxReplayGap: a longer pause between two recordings (separate recording
	// sessions) is not waited out; replay jumps to the next session after one poll interval.
	maxReplayGap = 60
	defaultGap   = 10
)

// Replay plays recorded raw responses (live mode's raw zone or a test fixture) in
// order, honouring their original spacing divided by speed, and loops forever.
// Timestamps are re-based onto the wall clock so downstream sees "live" data.
type Replay struct {
	files []string
	speed float64
	now   func() time.Time
	sleep func(ctx context.Context, d time.Duration) error

	i                int
	started          bool
	prevOrig         int64 // source time of the previous frame
	segOrig, segWall int64 // current segment: source time ↔ wall clock anchor
}

// listRecordings returns every *.json.gz under dir. Names are YYYY-MM-DD/HHMMSS, so
// lexical order is chronological order.
func listRecordings(dir string) ([]string, error) {
	var files []string
	err := filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !d.IsDir() && strings.HasSuffix(path, ".json.gz") {
			files = append(files, path)
		}
		return nil
	})
	sort.Strings(files)
	return files, err
}

// HasRecordings reports whether dir holds at least one recording.
func HasRecordings(dir string) bool {
	files, _ := listRecordings(dir)
	return len(files) > 0
}

func NewReplay(dir string, speed float64, now func() time.Time, sleep func(context.Context, time.Duration) error) (*Replay, error) {
	files, err := listRecordings(dir)
	if err != nil {
		return nil, fmt.Errorf("list recordings in %s: %w", dir, err)
	}
	if len(files) == 0 {
		return nil, fmt.Errorf("no *.json.gz recordings under %s", dir)
	}
	if now == nil {
		now = time.Now
	}
	if sleep == nil {
		sleep = opensky.Sleep
	}
	return &Replay{files: files, speed: speed, now: now, sleep: sleep}, nil
}

func (r *Replay) Name() string { return "replay" }

// Files is the number of recordings in the loop.
func (r *Replay) Files() int { return len(r.files) }

func (r *Replay) Next(ctx context.Context) (Frame, error) {
	path := r.files[r.i]
	r.i = (r.i + 1) % len(r.files)
	snap, err := readRecording(path)
	if err != nil {
		return Frame{}, fmt.Errorf("%s: %w", path, err)
	}

	restart := r.started && snap.Time < r.prevOrig
	newSegment := !r.started
	if r.started {
		gap := snap.Time - r.prevOrig
		if gap <= 0 || gap > maxReplayGap {
			gap, newSegment = defaultGap, true
		}
		wait := time.Duration(float64(gap) / r.speed * float64(time.Second))
		if err := r.sleep(ctx, wait); err != nil {
			return Frame{}, err
		}
	}
	if newSegment {
		r.segOrig, r.segWall = snap.Time, r.now().Unix()
	}
	r.started, r.prevOrig = true, snap.Time

	segOrig, segWall, speed := r.segOrig, r.segWall, r.speed
	return Frame{
		Snapshot: snap,
		Restart:  restart,
		Retime: func(t int64) int64 {
			return segWall + int64(math.Round(float64(t-segOrig)/speed))
		},
	}, nil
}

func readRecording(path string) (opensky.Snapshot, error) {
	f, err := os.Open(path)
	if err != nil {
		return opensky.Snapshot{}, err
	}
	defer f.Close()
	zr, err := gzip.NewReader(f)
	if err != nil {
		return opensky.Snapshot{}, err
	}
	body, err := io.ReadAll(zr)
	if err != nil {
		return opensky.Snapshot{}, err
	}
	return opensky.ParseStates(body)
}
