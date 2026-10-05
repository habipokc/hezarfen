// Command ingest produces aircraft state vectors (live OpenSky, replay or synthetic),
// cleans them, writes them to PostGIS and publishes them to Redis.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/clean"
	"github.com/habipokc/hezarfen/ingest/internal/config"
	"github.com/habipokc/hezarfen/ingest/internal/opensky"
	"github.com/habipokc/hezarfen/ingest/internal/publish"
	"github.com/habipokc/hezarfen/ingest/internal/source"
	"github.com/habipokc/hezarfen/ingest/internal/store"
)

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
	cfg, err := config.Load(os.Getenv)
	if err != nil {
		log.Error("invalid configuration", "err", err)
		os.Exit(2)
	}
	mode := source.ResolveMode(cfg)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	// HTTP first, so the container reports healthy while it waits for its dependencies
	srv := newServer(mode)
	httpSrv := &http.Server{Addr: listenAddr, Handler: srv.routes(), ReadHeaderTimeout: 5 * time.Second}
	go func() {
		log.Info("ingest listening", "addr", listenAddr, "mode", mode, "configured_mode", cfg.Mode)
		if err := httpSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("http server failed", "err", err)
			stop()
		}
	}()

	if err := run(ctx, cfg, mode, srv, log); err != nil && ctx.Err() == nil {
		log.Error("ingest stopped", "err", err)
		stop()
		shutdown(httpSrv, log)
		os.Exit(1)
	}
	shutdown(httpSrv, log)
}

func shutdown(httpSrv *http.Server, log *slog.Logger) {
	log.Info("shutting down")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := httpSrv.Shutdown(ctx); err != nil {
		log.Error("graceful shutdown failed", "err", err)
	}
}

// waitFor retries ping every 2 s until it succeeds or ctx ends.
func waitFor(ctx context.Context, log *slog.Logger, name string, ping func(context.Context) error) error {
	for {
		pctx, cancel := context.WithTimeout(ctx, 3*time.Second)
		err := ping(pctx)
		cancel()
		if err == nil {
			return nil
		}
		log.Warn("waiting for dependency", "name", name, "err", err)
		if err := opensky.Sleep(ctx, 2*time.Second); err != nil {
			return err
		}
	}
}

func run(ctx context.Context, cfg config.Config, mode string, srv *server, log *slog.Logger) error {
	st, err := store.Connect(ctx, cfg.DatabaseURL, "")
	if err != nil {
		return err
	}
	defer st.Close()
	pub, err := publish.New(cfg.RedisURL)
	if err != nil {
		return err
	}
	defer pub.Close()
	if err := waitFor(ctx, log, "postgis", st.Ping); err != nil {
		return err
	}
	if err := waitFor(ctx, log, "redis", pub.Ping); err != nil {
		return err
	}

	src, err := newSource(ctx, cfg, mode, st, log)
	if err != nil {
		return err
	}
	return loop(ctx, cfg, src, st, pub, srv, log)
}

func newSource(ctx context.Context, cfg config.Config, mode string, st *store.Store, log *slog.Logger) (source.Source, error) {
	switch mode {
	case config.ModeLive:
		client := &opensky.Client{HTTP: &http.Client{Timeout: 30 * time.Second}, APIURL: cfg.OpenSkyAPIURL, MaxRetries: 3}
		if cfg.HasCredentials() {
			client.Tokens = &opensky.TokenSource{URL: cfg.OpenSkyTokenURL, ClientID: cfg.OpenSkyClientID,
				ClientSecret: cfg.OpenSkyClientSecret, HTTP: client.HTTP}
		} else {
			log.Warn("live mode without credentials: anonymous access, 400 credits/day")
		}
		return source.NewLive(source.LiveOptions{
			Client: client, BBox: cfg.BBox, RawDir: cfg.RawDir(), Interval: cfg.PollInterval,
			SlowInterval: cfg.SlowPollInterval, DailyCredits: cfg.DailyCredits, Log: log,
		}), nil
	case config.ModeReplay:
		r, err := source.NewReplay(cfg.ReplayDir, cfg.ReplaySpeed, nil, nil)
		if err != nil {
			return nil, err
		}
		log.Info("replaying recordings", "dir", cfg.ReplayDir, "files", r.Files(), "speed", cfg.ReplaySpeed)
		return r, nil
	case config.ModeSynthetic:
		airports, err := st.LoadAirports(ctx, cfg.BBox)
		if err != nil || len(airports) < 2 {
			log.Warn("airports table empty or unreadable (run make seed); using built-in airports", "err", err)
			airports = source.FallbackAirports
		}
		log.Info("synthetic traffic", "aircraft", cfg.SyntheticAircraft, "airports", len(airports),
			"tick", cfg.SyntheticTick.String())
		return source.NewSynthetic(source.SyntheticOptions{
			Airports: airports, Count: cfg.SyntheticAircraft, Tick: cfg.SyntheticTick,
			Seed: cfg.SyntheticSeed, BBox: cfg.BBox,
		}), nil
	}
	return nil, fmt.Errorf("unknown mode %q", mode)
}

// loop is the ETL cycle: extract (source) → transform (clean) → load (PostGIS, Redis).
// A failing step is logged and counted; the loop only ends with ctx.
func loop(ctx context.Context, cfg config.Config, src source.Source, st *store.Store, pub *publish.Publisher,
	srv *server, log *slog.Logger) error {
	cleaner := clean.New(cfg.BBox, log)
	for {
		frame, err := src.Next(ctx)
		if ctx.Err() != nil {
			return nil
		}
		if err != nil {
			srv.update(func(m *metrics) { m.ErrorCount++ })
			log.Error("source failed", "err", err)
			if err := opensky.Sleep(ctx, time.Second); err != nil { // never spin on a persistent error
				return nil
			}
			continue
		}
		if frame.Restart {
			cleaner = clean.New(cfg.BBox, log)
		}

		res := cleaner.Clean(frame.Snapshot)
		cycleTs := frame.Time
		if frame.Retime != nil {
			cycleTs = frame.Retime(frame.Time)
			for i := range res.Records {
				res.Records[i].Ts = frame.Retime(res.Records[i].Ts)
			}
		}

		errs := 0
		inserted, err := st.Write(ctx, src.Name(), res.Records)
		if err != nil {
			errs++
			log.Error("database write failed", "err", err)
		}
		// published even if the write failed: the live map should not freeze because of
		// the history table, and a restarted relay re-reads PostGIS anyway
		receivers, err := pub.Publish(ctx, publish.NewMessage(src.Name(), cycleTs, res.Records))
		if err != nil {
			errs++
			log.Error("redis publish failed", "err", err)
		}

		now := time.Now().UTC()
		srv.update(func(m *metrics) {
			m.Cycles++
			m.ErrorCount += int64(errs)
			m.LastPollAt = &now
			m.BatchSize = len(res.Records)
			m.LastInserted = inserted
			m.LastReceivers = receivers
			if frame.Credits != nil {
				m.Credits = frame.Credits
			}
			switch s := src.(type) {
			case *source.Live:
				m.PollInterval = s.Interval().Seconds()
			case *source.Synthetic:
				m.PollInterval = cfg.SyntheticTick.Seconds()
			}
			for reason, n := range res.Rejected {
				m.Rejected[string(reason)] += n
			}
		})
		log.Debug("cycle", "source", src.Name(), "states", len(frame.States), "records", len(res.Records),
			"rejected", res.Rejected, "inserted", inserted, "subscribers", receivers)
	}
}
