package opensky

import (
	"compress/gzip"
	"context"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/geo"
)

var marmara = geo.BBox{MinLon: 26, MinLat: 39.5, MaxLon: 31.5, MaxLat: 42}

// One full state and one with every nullable field null, as OpenSky sends them.
const sampleBody = `{"time": 1791187200, "states": [
 ["4baa0f", "THY7AB  ", "Turkey", 1791187198, 1791187199, 28.8146, 41.2753, 3350.0, false,
  152.3, 87.4, 6.5, null, 3420.5, "2341", false, 0, 4],
 ["4b1812", null, "Turkey", null, 1791187150, null, null, null, true,
  null, null, null, null, null, null, false, 0]
]}`

func noSleep(slept *[]time.Duration) func(context.Context, time.Duration) error {
	return func(_ context.Context, d time.Duration) error {
		*slept = append(*slept, d)
		return nil
	}
}

func TestParseStatesFullAndNullFields(t *testing.T) {
	snap, err := ParseStates([]byte(sampleBody))
	if err != nil {
		t.Fatal(err)
	}
	if snap.Time != 1791187200 || len(snap.States) != 2 {
		t.Fatalf("time=%d states=%d", snap.Time, len(snap.States))
	}
	full := snap.States[0]
	if full.Icao24 != "4baa0f" || *full.Callsign != "THY7AB  " || *full.Lon != 28.8146 ||
		*full.GeoAltitude != 3420.5 || *full.Squawk != "2341" || *full.Category != 4 {
		t.Errorf("full state decoded wrong: %+v", full)
	}
	empty := snap.States[1]
	if empty.Callsign != nil || empty.TimePosition != nil || empty.Lon != nil || empty.Velocity != nil ||
		empty.Squawk != nil || empty.Category != nil || !empty.OnGround {
		t.Errorf("null fields should stay nil: %+v", empty)
	}
}

func TestParseStatesSkipsMalformedRowsAndNullStates(t *testing.T) {
	snap, err := ParseStates([]byte(`{"time": 1, "states": [["abc"], ["4baa0f", null, "T", null, 1,
		null, null, null, "not-a-bool", null, null, null, null, null, null, false, 0]]}`))
	if err != nil {
		t.Fatal(err)
	}
	if len(snap.States) != 0 || snap.Malformed != 2 {
		t.Errorf("states=%d malformed=%d, want 0 and 2", len(snap.States), snap.Malformed)
	}
	snap, err = ParseStates([]byte(`{"time": 5, "states": null}`))
	if err != nil || len(snap.States) != 0 {
		t.Errorf("empty bbox: %v %+v", err, snap)
	}
}

func TestParseRecordedFixture(t *testing.T) {
	files, _ := filepath.Glob("../../testdata/opensky/*/*.json.gz")
	if len(files) == 0 {
		t.Fatal("no fixture under testdata/opensky (make record)")
	}
	f, err := os.Open(files[0])
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	zr, err := gzip.NewReader(f)
	if err != nil {
		t.Fatal(err)
	}
	body, err := io.ReadAll(zr)
	if err != nil {
		t.Fatal(err)
	}
	snap, err := ParseStates(body)
	if err != nil {
		t.Fatal(err)
	}
	if len(snap.States) == 0 || snap.Malformed != 0 {
		t.Fatalf("states=%d malformed=%d", len(snap.States), snap.Malformed)
	}
	withCategory := 0
	for _, s := range snap.States {
		if len(s.Icao24) != 6 {
			t.Errorf("icao24 %q is not 6 chars", s.Icao24)
		}
		if s.Category != nil {
			withCategory++
		}
	}
	if withCategory == 0 {
		t.Error("extended=1 fixture should carry categories")
	}
}

func TestGetStatesSendsBBoxAndReadsCredits(t *testing.T) {
	var query string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		query = r.URL.RawQuery
		if r.Header.Get("Authorization") != "" {
			t.Error("anonymous client sent Authorization")
		}
		w.Header().Set("X-Rate-Limit-Remaining", "3990")
		fmt.Fprint(w, sampleBody)
	}))
	defer srv.Close()

	c := &Client{HTTP: srv.Client(), APIURL: srv.URL}
	resp, err := c.GetStates(context.Background(), marmara)
	if err != nil {
		t.Fatal(err)
	}
	if query != "extended=1&lamax=42&lamin=39.5&lomax=31.5&lomin=26" {
		t.Errorf("query = %s", query)
	}
	if resp.CreditsRemaining == nil || *resp.CreditsRemaining != 3990 || len(resp.States) != 2 {
		t.Errorf("credits=%v states=%d", resp.CreditsRemaining, len(resp.States))
	}
	if string(resp.Body) != sampleBody {
		t.Error("raw body not kept for the raw zone")
	}
}

func TestGetStatesRateLimited(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Rate-Limit-Retry-After-Seconds", "120")
		w.WriteHeader(http.StatusTooManyRequests)
	}))
	defer srv.Close()

	var slept []time.Duration
	c := &Client{HTTP: srv.Client(), APIURL: srv.URL, MaxRetries: 3, Sleep: noSleep(&slept)}
	_, err := c.GetStates(context.Background(), marmara)
	wait, ok := IsRateLimit(err)
	if !ok || wait != 120*time.Second {
		t.Fatalf("err = %v, wait = %s", err, wait)
	}
	if len(slept) != 0 {
		t.Errorf("429 must not be retried internally, slept %v", slept)
	}
}

func TestGetStatesRetries5xxWithBackoff(t *testing.T) {
	var calls atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if calls.Add(1) <= 2 {
			w.WriteHeader(http.StatusBadGateway)
			return
		}
		fmt.Fprint(w, sampleBody)
	}))
	defer srv.Close()

	var slept []time.Duration
	c := &Client{HTTP: srv.Client(), APIURL: srv.URL, MaxRetries: 3, Sleep: noSleep(&slept)}
	if _, err := c.GetStates(context.Background(), marmara); err != nil {
		t.Fatal(err)
	}
	if fmt.Sprint(slept) != "[1s 2s]" {
		t.Errorf("backoff = %v, want [1s 2s]", slept)
	}
}

func TestGetStatesGivesUpAfterMaxRetries(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()

	var slept []time.Duration
	c := &Client{HTTP: srv.Client(), APIURL: srv.URL, MaxRetries: 2, Sleep: noSleep(&slept)}
	if _, err := c.GetStates(context.Background(), marmara); err == nil {
		t.Fatal("want error")
	}
	if fmt.Sprint(slept) != "[1s 2s]" {
		t.Errorf("backoff = %v, want [1s 2s]", slept)
	}
}

// tokenServer issues tok-1, tok-2, … and counts requests.
func tokenServer(t *testing.T, issued *atomic.Int32) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := r.ParseForm(); err != nil || r.Form.Get("grant_type") != "client_credentials" ||
			r.Form.Get("client_id") != "id" || r.Form.Get("client_secret") != "secret" {
			t.Errorf("bad token request: %v", r.Form)
		}
		fmt.Fprintf(w, `{"access_token": "tok-%d", "expires_in": 1800}`, issued.Add(1))
	}))
}

func TestGetStatesRefreshesTokenOn401(t *testing.T) {
	var issued atomic.Int32
	auth := tokenServer(t, &issued)
	defer auth.Close()
	var seen []string
	api := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Header.Get("Authorization"))
		if r.Header.Get("Authorization") == "Bearer tok-1" { // revoked server-side
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		fmt.Fprint(w, sampleBody)
	}))
	defer api.Close()

	tokens := &TokenSource{URL: auth.URL, ClientID: "id", ClientSecret: "secret", HTTP: auth.Client()}
	c := &Client{HTTP: api.Client(), APIURL: api.URL, Tokens: tokens}
	if _, err := c.GetStates(context.Background(), marmara); err != nil {
		t.Fatal(err)
	}
	if fmt.Sprint(seen) != "[Bearer tok-1 Bearer tok-2]" {
		t.Errorf("authorization headers = %v", seen)
	}
}

func TestGetStatesPersistent401Fails(t *testing.T) {
	var issued atomic.Int32
	auth := tokenServer(t, &issued)
	defer auth.Close()
	api := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer api.Close()

	tokens := &TokenSource{URL: auth.URL, ClientID: "id", ClientSecret: "secret", HTTP: auth.Client()}
	c := &Client{HTTP: api.Client(), APIURL: api.URL, Tokens: tokens, MaxRetries: 3}
	if _, err := c.GetStates(context.Background(), marmara); err == nil {
		t.Fatal("want error for persistent 401")
	}
	if issued.Load() != 2 {
		t.Errorf("tokens issued = %d, want 2 (one refresh only)", issued.Load())
	}
}

func TestTokenCachedUntilShortlyBeforeExpiry(t *testing.T) {
	var issued atomic.Int32
	auth := tokenServer(t, &issued)
	defer auth.Close()
	now := time.Unix(0, 0)
	ts := &TokenSource{URL: auth.URL, ClientID: "id", ClientSecret: "secret", HTTP: auth.Client(),
		Now: func() time.Time { return now }}

	get := func() string {
		tok, err := ts.Token(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		return tok
	}
	if get() != "tok-1" {
		t.Fatal("first token")
	}
	now = now.Add(28 * time.Minute) // 2 min left: still valid
	if get() != "tok-1" {
		t.Error("token refreshed too early")
	}
	now = now.Add(90 * time.Second) // 30 s left: inside the 60 s margin
	if get() != "tok-2" {
		t.Error("token not refreshed before expiry")
	}
}

func TestTokenConcurrentCallersShareOneFetch(t *testing.T) {
	var issued atomic.Int32
	auth := tokenServer(t, &issued)
	defer auth.Close()
	ts := &TokenSource{URL: auth.URL, ClientID: "id", ClientSecret: "secret", HTTP: auth.Client()}

	var wg sync.WaitGroup
	for range 20 {
		wg.Go(func() {
			if _, err := ts.Token(context.Background()); err != nil {
				t.Error(err)
			}
		})
	}
	wg.Wait()
	if issued.Load() != 1 {
		t.Errorf("tokens issued = %d, want 1", issued.Load())
	}
}
