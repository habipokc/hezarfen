package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestHealthz(t *testing.T) {
	s := &server{startedAt: time.Now(), mode: "synthetic"}
	ts := httptest.NewServer(s.routes())
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

func TestMetricsReportsMode(t *testing.T) {
	s := &server{startedAt: time.Now(), mode: "replay"}
	ts := httptest.NewServer(s.routes())
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/metrics")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	var got metrics
	if err := json.NewDecoder(resp.Body).Decode(&got); err != nil {
		t.Fatal(err)
	}
	if got.Mode != "replay" {
		t.Errorf("mode = %q, want replay", got.Mode)
	}
}

func TestUnknownMethodRejected(t *testing.T) {
	s := &server{startedAt: time.Now(), mode: "auto"}
	ts := httptest.NewServer(s.routes())
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
