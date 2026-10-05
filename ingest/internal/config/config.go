// Package config reads ingest's environment variables (documented in .env.example)
// into a validated Config. Load takes a getenv function so tests need no real env.
package config

import (
	"errors"
	"fmt"
	"net/url"
	"path/filepath"
	"strconv"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/geo"
)

// Source modes (PLAN §4). Auto is resolved to one of the others at startup.
const (
	ModeAuto      = "auto"
	ModeLive      = "live"
	ModeReplay    = "replay"
	ModeSynthetic = "synthetic"
)

type Config struct {
	Mode string

	OpenSkyClientID     string
	OpenSkyClientSecret string
	OpenSkyAPIURL       string
	OpenSkyTokenURL     string
	// DailyCredits is the account's daily budget; adaptive polling compares the
	// remaining credits against 20% of it.
	DailyCredits     int
	PollInterval     time.Duration
	SlowPollInterval time.Duration

	ReplayDir   string
	ReplaySpeed float64

	SyntheticAircraft int
	SyntheticTick     time.Duration
	SyntheticSeed     int64

	BBox        geo.BBox
	DataDir     string
	DatabaseURL string
	RedisURL    string
}

// HasCredentials reports whether OAuth2 client credentials are configured.
func (c Config) HasCredentials() bool {
	return c.OpenSkyClientID != "" && c.OpenSkyClientSecret != ""
}

// RawDir is the raw zone: live responses are archived here and replay reads from here.
func (c Config) RawDir() string { return filepath.Join(c.DataDir, "raw") }

// parser accumulates every invalid variable so one run reports all of them.
type parser struct {
	getenv func(string) string
	errs   []error
}

func (p *parser) str(key, def string) string {
	if v := p.getenv(key); v != "" {
		return v
	}
	return def
}

func (p *parser) float(key string, def, lo, hi float64) float64 {
	raw := p.getenv(key)
	if raw == "" {
		return def
	}
	v, err := strconv.ParseFloat(raw, 64)
	if err != nil || v < lo || v > hi {
		p.errs = append(p.errs, fmt.Errorf("%s=%q: want a number in [%g, %g]", key, raw, lo, hi))
		return def
	}
	return v
}

func (p *parser) int(key string, def, lo, hi int) int {
	return int(p.float(key, float64(def), float64(lo), float64(hi)))
}

func (p *parser) seconds(key string, def, lo, hi int) time.Duration {
	return time.Duration(p.int(key, def, lo, hi)) * time.Second
}

func Load(getenv func(string) string) (Config, error) {
	p := &parser{getenv: getenv}
	c := Config{
		Mode:                p.str("SOURCE_MODE", ModeAuto),
		OpenSkyClientID:     p.getenv("OPENSKY_CLIENT_ID"),
		OpenSkyClientSecret: p.getenv("OPENSKY_CLIENT_SECRET"),
		OpenSkyAPIURL:       p.str("OPENSKY_API_URL", "https://opensky-network.org/api"),
		OpenSkyTokenURL: p.str("OPENSKY_TOKEN_URL",
			"https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"),
		PollInterval:      p.seconds("POLL_INTERVAL_SECONDS", 10, 5, 3600),
		SlowPollInterval:  p.seconds("POLL_INTERVAL_SLOW_SECONDS", 30, 5, 3600),
		ReplaySpeed:       p.float("REPLAY_SPEED", 1, 0.1, 100),
		SyntheticAircraft: p.int("SYNTHETIC_AIRCRAFT", 60, 1, 500),
		SyntheticTick:     p.seconds("SYNTHETIC_TICK_SECONDS", 2, 1, 5),
		// a fixed default seed: every restart (and every hot reload) flies the same
		// fleet instead of adding 60 new aircraft to the database
		SyntheticSeed: int64(p.int("SYNTHETIC_SEED", 1, 0, 1<<31-1)),
		DataDir:       p.str("DATA_DIR", "/data"),
		RedisURL:      p.str("REDIS_URL", "redis://redis:6379/0"),
		BBox: geo.BBox{
			MinLat: p.float("BBOX_LAMIN", 39.5, -90, 90),
			MinLon: p.float("BBOX_LOMIN", 26.0, -180, 180),
			MaxLat: p.float("BBOX_LAMAX", 42.0, -90, 90),
			MaxLon: p.float("BBOX_LOMAX", 31.5, -180, 180),
		},
	}
	c.ReplayDir = p.str("REPLAY_DIR", c.RawDir())

	// anonymous users get 400 credits/day, registered API clients 4000 (PLAN §4)
	defCredits := 400
	if c.HasCredentials() {
		defCredits = 4000
	}
	c.DailyCredits = p.int("OPENSKY_DAILY_CREDITS", defCredits, 1, 1_000_000)

	db := url.URL{
		Scheme: "postgres",
		User:   url.UserPassword(p.str("POSTGRES_USER", "hezarfen"), p.str("POSTGRES_PASSWORD", "hezarfen")),
		Host:   p.str("POSTGRES_HOST", "db") + ":" + p.str("POSTGRES_PORT", "5432"),
		Path:   "/" + p.str("POSTGRES_DB", "hezarfen"),
	}
	c.DatabaseURL = db.String()

	switch c.Mode {
	case ModeAuto, ModeLive, ModeReplay, ModeSynthetic:
	default:
		p.errs = append(p.errs, fmt.Errorf("SOURCE_MODE=%q: want auto, live, replay or synthetic", c.Mode))
	}
	if c.BBox.MinLon >= c.BBox.MaxLon || c.BBox.MinLat >= c.BBox.MaxLat {
		p.errs = append(p.errs, fmt.Errorf("bbox %+v: min must be below max", c.BBox))
	}
	if (c.OpenSkyClientID == "") != (c.OpenSkyClientSecret == "") {
		p.errs = append(p.errs, errors.New("set both OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET, or neither"))
	}
	return c, errors.Join(p.errs...)
}
