package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealthz(t *testing.T) {
	ts := httptest.NewServer(newServer("synthetic").routes())
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/healthz")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
}

func TestMetricsReportsModeAndUpdates(t *testing.T) {
	s := newServer("replay")
	s.update(func(m *metrics) {
		m.BatchSize = 64
		m.Rejected["stale"] += 3
	})
	ts := httptest.NewServer(s.routes())
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/metrics")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	var got map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatal(err)
	}
	if got["mode"] != "replay" || got["last_batch_size"] != 64.0 {
		t.Errorf("metrics = %v", got)
	}
	// ICD IF-8: unknown values are null until known
	if v, ok := got["last_poll_at"]; !ok || v != nil {
		t.Errorf("last_poll_at = %v (present=%v), want null", v, ok)
	}
	if got["rejected_total"].(map[string]any)["stale"] != 3.0 {
		t.Errorf("rejected_total = %v", got["rejected_total"])
	}
}

func TestUnknownMethodRejected(t *testing.T) {
	ts := httptest.NewServer(newServer("auto").routes())
	defer ts.Close()

	resp, err := http.Post(ts.URL+"/healthz", "application/json", nil)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Errorf("status = %d, want 405", resp.StatusCode)
	}
}

func TestDailyCreditsOnlyInLiveMode(t *testing.T) {
	if got := liveBudget("live", 4000); got == nil || *got != 4000 {
		t.Errorf("live: got %v, want 4000", got)
	}
	for _, mode := range []string{"replay", "synthetic"} {
		if got := liveBudget(mode, 4000); got != nil {
			t.Errorf("%s: got %v, want nil (no OpenSky credits are spent)", mode, *got)
		}
	}

	s := newServer("synthetic")
	ts := httptest.NewServer(s.routes())
	defer ts.Close()
	resp, err := http.Get(ts.URL + "/metrics")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var got map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatal(err)
	}
	if v, ok := got["daily_credits"]; !ok || v != nil {
		t.Errorf("daily_credits = %v (present=%v), want null", v, ok)
	}
}
