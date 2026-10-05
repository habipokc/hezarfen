// Command ingest pulls aircraft state vectors, writes them to PostGIS and
// publishes them to Redis. Phase 0: only the HTTP health/metrics surface exists.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"
)

const listenAddr = ":8080"

// metrics is the JSON document served on /metrics. Fields are filled in by later phases.
type metrics struct {
	Mode       string    `json:"mode"`
	StartedAt  time.Time `json:"started_at"`
	LastPollAt *string   `json:"last_poll_at"`
	Credits    *int      `json:"credits_remaining"`
	BatchSize  int       `json:"last_batch_size"`
	ErrorCount int64     `json:"error_count"`
}

type server struct {
	startedAt time.Time
	mode      string
	errors    atomic.Int64
}

func (s *server) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("GET /metrics", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, metrics{
			Mode:       s.mode,
			StartedAt:  s.startedAt,
			ErrorCount: s.errors.Load(),
		})
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

func newLogger() *slog.Logger {
	var level slog.Level
	if err := level.UnmarshalText([]byte(os.Getenv("INGEST_LOG_LEVEL"))); err != nil {
		level = slog.LevelInfo
	}
	return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level}))
}

func main() {
	check := flag.Bool("healthcheck", false, "probe the local /healthz endpoint and exit")
	flag.Parse()
	if *check {
		os.Exit(healthcheck())
	}

	log := newLogger()
	slog.SetDefault(log)

	mode := os.Getenv("SOURCE_MODE")
	if mode == "" {
		mode = "auto"
	}
	s := &server{startedAt: time.Now().UTC(), mode: mode}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	srv := &http.Server{Addr: listenAddr, Handler: s.routes(), ReadHeaderTimeout: 5 * time.Second}
	go func() {
		log.Info("ingest listening", "addr", listenAddr, "mode", mode)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("http server failed", "err", err)
			stop()
		}
	}()

	<-ctx.Done()
	log.Info("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Error("graceful shutdown failed", "err", err)
	}
}
