package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/config"
)

const listenAddr = ":8080"

// metrics is the JSON document served on /metrics (ICD IF-8). The first six fields
// are the Phase 0 contract; the rest were added in ICD 1.2, daily_credits in 1.6.
type metrics struct {
	Mode          string         `json:"mode"`
	StartedAt     time.Time      `json:"started_at"`
	LastPollAt    *time.Time     `json:"last_poll_at"`
	Credits       *int           `json:"credits_remaining"`
	DailyCredits  *int           `json:"daily_credits"`
	BatchSize     int            `json:"last_batch_size"`
	ErrorCount    int64          `json:"error_count"`
	Cycles        int64          `json:"cycles"`
	PollInterval  float64        `json:"poll_interval_seconds"`
	LastInserted  int64          `json:"last_positions_inserted"`
	LastReceivers int64          `json:"last_subscribers"`
	Rejected      map[string]int `json:"rejected_total"`
}

// server owns the metrics; the ingest loop updates them, HTTP handlers read them.
type server struct {
	mu sync.Mutex
	m  metrics
}

// liveBudget is the daily OpenSky credit budget to report: only live mode spends credits.
func liveBudget(mode string, daily int) *int {
	if mode != config.ModeLive {
		return nil
	}
	return &daily
}

func newServer(mode string) *server {
	return &server{m: metrics{Mode: mode, StartedAt: time.Now().UTC(), Rejected: map[string]int{}}}
}

// update runs f with the lock held.
func (s *server) update(f func(m *metrics)) {
	s.mu.Lock()
	defer s.mu.Unlock()
	f(&s.m)
}

func (s *server) snapshot() metrics {
	s.mu.Lock()
	defer s.mu.Unlock()
	m := s.m
	m.Rejected = make(map[string]int, len(s.m.Rejected))
	for k, v := range s.m.Rejected {
		m.Rejected[k] = v
	}
	return m
}

func (s *server) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("GET /metrics", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, s.snapshot())
	})
	return mux
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// healthcheck lets the distroless image probe itself: it has no shell or curl.
func healthcheck() int {
	client := http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get("http://127.0.0.1" + listenAddr + "/healthz")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 1
	}
	return 0
}
