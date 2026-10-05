package source

import (
	"compress/gzip"
	"context"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/geo"
	"github.com/habipokc/hezarfen/ingest/internal/opensky"
)

// lowCreditShare: below this share of the daily budget, polling slows down.
const lowCreditShare = 0.2

type LiveOptions struct {
	Client       *opensky.Client
	BBox         geo.BBox
	RawDir       string // raw zone root; "" disables archiving
	Interval     time.Duration
	SlowInterval time.Duration
	DailyCredits int
	Log          *slog.Logger
	Now          func() time.Time
	Sleep        func(ctx context.Context, d time.Duration) error
}

// Live polls OpenSky, archives every raw response (the ETL raw zone) and adapts the
// polling interval to the remaining credits.
type Live struct {
	o        LiveOptions
	lastPoll time.Time
	credits  *int
	slow     bool
}

func NewLive(o LiveOptions) *Live {
	if o.Now == nil {
		o.Now = time.Now
	}
	if o.Sleep == nil {
		o.Sleep = opensky.Sleep
	}
	return &Live{o: o}
}

func (l *Live) Name() string { return "live" }

// Interval is the current polling interval (adaptive).
func (l *Live) Interval() time.Duration {
	if l.slow {
		return l.o.SlowInterval
	}
	return l.o.Interval
}

func (l *Live) Next(ctx context.Context) (Frame, error) {
	if !l.lastPoll.IsZero() {
		if wait := l.Interval() - l.o.Now().Sub(l.lastPoll); wait > 0 {
			if err := l.o.Sleep(ctx, wait); err != nil {
				return Frame{}, err
			}
		}
	}
	for {
		l.lastPoll = l.o.Now()
		resp, err := l.o.Client.GetStates(ctx, l.o.BBox)
		if wait, ok := opensky.IsRateLimit(err); ok {
			zero := 0
			l.credits = &zero
			l.o.Log.Warn("opensky credits exhausted, pausing", "retry_after", wait.String())
			if err := l.o.Sleep(ctx, wait); err != nil {
				return Frame{}, err
			}
			continue
		}
		if err != nil {
			return Frame{}, err
		}
		l.observeCredits(resp.CreditsRemaining)
		if l.o.RawDir != "" {
			if err := archive(l.o.RawDir, l.lastPoll, resp.Body); err != nil {
				// losing the raw copy must not stop the live map
				l.o.Log.Error("raw zone write failed", "err", err)
			}
		}
		return Frame{Snapshot: resp.Snapshot, Credits: resp.CreditsRemaining}, nil
	}
}

func (l *Live) observeCredits(c *int) {
	l.credits = c
	if c == nil {
		return
	}
	slow := float64(*c) < lowCreditShare*float64(l.o.DailyCredits)
	if slow != l.slow {
		l.slow = slow
		l.o.Log.Info("adaptive polling", "credits_remaining", *c, "interval", l.Interval().String())
	}
}

// archive writes body gzipped to <root>/YYYY-MM-DD/HHMMSS.json.gz (UTC). It writes a
// temporary file first and renames it, so a concurrent replay never reads half a file.
func archive(root string, t time.Time, body []byte) error {
	t = t.UTC()
	dir := filepath.Join(root, t.Format("2006-01-02"))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(dir, ".partial-*")
	if err != nil {
		return err
	}
	defer os.Remove(tmp.Name()) // no-op after a successful rename
	zw := gzip.NewWriter(tmp)
	if _, err := zw.Write(body); err != nil {
		tmp.Close()
		return err
	}
	if err := zw.Close(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Chmod(tmp.Name(), 0o644); err != nil { // CreateTemp makes 0600 files
		return err
	}
	final := filepath.Join(dir, t.Format("150405")+".json.gz")
	if err := os.Rename(tmp.Name(), final); err != nil {
		return fmt.Errorf("rename raw file: %w", err)
	}
	return nil
}
