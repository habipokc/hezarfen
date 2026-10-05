package source

import (
	"compress/gzip"
	"context"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/config"
	"github.com/habipokc/hezarfen/ingest/internal/opensky"
)

func body(ts int64) string {
	return fmt.Sprintf(`{"time": %d, "states": [["4baa0f", "THY7AB  ", "Turkey", %d, %d,
		28.8, 41.2, 3000.0, false, 150.0, 90.0, 0.0, null, 3050.0, "2341", false, 0, 4]]}`, ts, ts-2, ts)
}

func writeGz(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	zw := gzip.NewWriter(f)
	if _, err := io.WriteString(zw, content); err != nil {
		t.Fatal(err)
	}
	zw.Close()
	f.Close()
}

type fakeClock struct {
	now   time.Time
	slept []time.Duration
}

func (c *fakeClock) Now() time.Time { return c.now }
func (c *fakeClock) Sleep(_ context.Context, d time.Duration) error {
	c.slept = append(c.slept, d)
	c.now = c.now.Add(d)
	return nil
}

func TestReplayTimingRetimeAndLoop(t *testing.T) {
	dir := t.TempDir()
	// two sessions: 1000, 1010, 1030 and, a day later, 87400
	for name, ts := range map[string]int64{
		"2026-10-04/000000.json.gz": 1000, "2026-10-04/000010.json.gz": 1010,
		"2026-10-04/000030.json.gz": 1030, "2026-10-05/000000.json.gz": 87400,
	} {
		writeGz(t, filepath.Join(dir, name), body(ts))
	}
	clock := &fakeClock{now: time.Unix(5000, 0)}
	r, err := NewReplay(dir, 2, clock.Now, clock.Sleep)
	if err != nil {
		t.Fatal(err)
	}

	var frames []Frame
	for range 5 {
		f, err := r.Next(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		frames = append(frames, f)
	}
	// spacing /2; the day-long gap and the loop back are replaced by one 10 s poll (/2)
	if fmt.Sprint(clock.slept) != "[5s 10s 5s 5s]" {
		t.Errorf("slept %v, want [5s 10s 5s 5s]", clock.slept)
	}
	if frames[0].Retime(1000) != 5000 || frames[1].Retime(1010) != 5005 || frames[2].Retime(1030) != 5015 {
		t.Errorf("retime within a segment wrong: %d %d %d",
			frames[0].Retime(1000), frames[1].Retime(1010), frames[2].Retime(1030))
	}
	if frames[3].Retime(87400) != 5020 {
		t.Errorf("new session should start at wall clock, got %d", frames[3].Retime(87400))
	}
	if frames[4].Time != 1000 || !frames[4].Restart || frames[3].Restart {
		t.Errorf("loop: time=%d restart=%v (prev restart=%v)", frames[4].Time, frames[4].Restart, frames[3].Restart)
	}
	if frames[4].Retime(1000) <= frames[3].Retime(87400) {
		t.Error("timestamps must keep moving forward after the loop")
	}
}

func TestReplayNeedsRecordings(t *testing.T) {
	if _, err := NewReplay(t.TempDir(), 1, nil, nil); err == nil {
		t.Fatal("want error for empty dir")
	}
}

func TestReplayPlaysRecordedFixture(t *testing.T) {
	clock := &fakeClock{now: time.Unix(5000, 0)}
	r, err := NewReplay("../../testdata/opensky", 1, clock.Now, clock.Sleep)
	if err != nil {
		t.Fatal(err)
	}
	for i := range r.Files() {
		f, err := r.Next(context.Background())
		if err != nil {
			t.Fatalf("frame %d: %v", i, err)
		}
		if len(f.States) == 0 {
			t.Fatalf("frame %d is empty", i)
		}
	}
}

func TestResolveMode(t *testing.T) {
	withRaw := t.TempDir()
	writeGz(t, filepath.Join(withRaw, "2026-10-05/120000.json.gz"), body(1000))
	cases := []struct {
		name string
		cfg  config.Config
		want string
	}{
		{"explicit wins", config.Config{Mode: "synthetic", OpenSkyClientID: "a", OpenSkyClientSecret: "b"}, "synthetic"},
		{"credentials", config.Config{Mode: "auto", OpenSkyClientID: "a", OpenSkyClientSecret: "b", ReplayDir: withRaw}, "live"},
		{"recordings", config.Config{Mode: "auto", ReplayDir: withRaw}, "replay"},
		{"nothing", config.Config{Mode: "auto", ReplayDir: t.TempDir()}, "synthetic"},
		{"missing dir", config.Config{Mode: "auto", ReplayDir: "/does/not/exist"}, "synthetic"},
	}
	for _, c := range cases {
		if got := ResolveMode(c.cfg); got != c.want {
			t.Errorf("%s: got %s, want %s", c.name, got, c.want)
		}
	}
}

func TestLiveArchivesAndAdaptsInterval(t *testing.T) {
	credits := []string{"3000", "700", "900"} // 4000/day: 700 is below 20%
	call := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Rate-Limit-Remaining", credits[call])
		call++
		fmt.Fprint(w, body(1000))
	}))
	defer srv.Close()

	raw := t.TempDir()
	clock := &fakeClock{now: time.Date(2026, 10, 5, 12, 0, 0, 0, time.UTC)}
	live := NewLive(LiveOptions{
		Client: &opensky.Client{HTTP: srv.Client(), APIURL: srv.URL}, BBox: marmara, RawDir: raw,
		Interval: 10 * time.Second, SlowInterval: 30 * time.Second, DailyCredits: 4000,
		Log: slog.New(slog.NewTextHandler(io.Discard, nil)), Now: clock.Now, Sleep: clock.Sleep,
	})
	for range 3 {
		f, err := live.Next(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		if len(f.States) != 1 || f.Credits == nil {
			t.Fatalf("frame = %+v", f)
		}
	}
	// first poll immediately, then 10 s, then 30 s because 700 < 800
	if fmt.Sprint(clock.slept) != "[10s 30s]" {
		t.Errorf("slept %v, want [10s 30s]", clock.slept)
	}
	if live.Interval() != 10*time.Second {
		t.Error("900 credits is still below 20%? interval should be back to 10 s only above 800")
	}
	files, _ := listRecordings(raw)
	want := []string{"2026-10-05/120000.json.gz", "2026-10-05/120010.json.gz", "2026-10-05/120040.json.gz"}
	if len(files) != 3 {
		t.Fatalf("archived %v", files)
	}
	for i, f := range files {
		if rel, _ := filepath.Rel(raw, f); rel != want[i] {
			t.Errorf("file %d = %s, want %s", i, rel, want[i])
		}
	}
	if fi, _ := os.Stat(files[0]); fi.Mode().Perm() != 0o644 {
		t.Errorf("raw file mode = %v, want 0644", fi.Mode().Perm())
	}
	snap, err := readRecording(files[0])
	if err != nil || snap.Time != 1000 {
		t.Errorf("archived file unreadable: %v %+v", err, snap)
	}
}

func TestLiveWaitsOutRateLimit(t *testing.T) {
	call := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		call++
		if call == 1 {
			w.Header().Set("X-Rate-Limit-Retry-After-Seconds", "300")
			w.WriteHeader(http.StatusTooManyRequests)
			return
		}
		fmt.Fprint(w, body(1000))
	}))
	defer srv.Close()

	clock := &fakeClock{now: time.Unix(0, 0)}
	live := NewLive(LiveOptions{
		Client: &opensky.Client{HTTP: srv.Client(), APIURL: srv.URL}, BBox: marmara,
		Interval: 10 * time.Second, SlowInterval: 30 * time.Second, DailyCredits: 400,
		Log: slog.New(slog.NewTextHandler(io.Discard, nil)), Now: clock.Now, Sleep: clock.Sleep,
	})
	if _, err := live.Next(context.Background()); err != nil {
		t.Fatal(err)
	}
	if fmt.Sprint(clock.slept) != "[5m0s]" || call != 2 {
		t.Errorf("slept %v after %d calls", clock.slept, call)
	}
}
