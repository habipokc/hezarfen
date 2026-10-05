package config

import (
	"strings"
	"testing"
	"time"
)

func env(kv map[string]string) func(string) string {
	return func(k string) string { return kv[k] }
}

func TestDefaults(t *testing.T) {
	c, err := Load(env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if c.Mode != ModeAuto || c.PollInterval != 10*time.Second || c.SlowPollInterval != 30*time.Second {
		t.Errorf("unexpected defaults: %+v", c)
	}
	if c.DailyCredits != 400 {
		t.Errorf("anonymous daily credits = %d, want 400", c.DailyCredits)
	}
	if c.ReplayDir != "/data/raw" {
		t.Errorf("replay dir = %q", c.ReplayDir)
	}
	if c.BBox.MinLon != 26 || c.BBox.MaxLat != 42 {
		t.Errorf("bbox = %+v", c.BBox)
	}
	if c.DatabaseURL != "postgres://hezarfen:hezarfen@db:5432/hezarfen" {
		t.Errorf("database url = %q", c.DatabaseURL)
	}
}

func TestCredentialsRaiseDailyBudget(t *testing.T) {
	c, err := Load(env(map[string]string{"OPENSKY_CLIENT_ID": "id", "OPENSKY_CLIENT_SECRET": "s"}))
	if err != nil {
		t.Fatal(err)
	}
	if !c.HasCredentials() || c.DailyCredits != 4000 {
		t.Errorf("HasCredentials=%v DailyCredits=%d", c.HasCredentials(), c.DailyCredits)
	}
}

func TestPasswordIsURLEscaped(t *testing.T) {
	c, _ := Load(env(map[string]string{"POSTGRES_PASSWORD": "p@ss/word"}))
	if !strings.Contains(c.DatabaseURL, "p%40ss%2Fword@db") {
		t.Errorf("database url = %q", c.DatabaseURL)
	}
}

func TestInvalidValuesAreAllReported(t *testing.T) {
	_, err := Load(env(map[string]string{
		"SOURCE_MODE":            "fast",
		"POLL_INTERVAL_SECONDS":  "1",
		"SYNTHETIC_TICK_SECONDS": "x",
		"BBOX_LOMIN":             "32",
		"OPENSKY_CLIENT_ID":      "only-id",
	}))
	if err == nil {
		t.Fatal("want error")
	}
	for _, want := range []string{"SOURCE_MODE", "POLL_INTERVAL_SECONDS", "SYNTHETIC_TICK_SECONDS", "bbox", "OPENSKY_CLIENT_SECRET"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("error does not mention %s:\n%v", want, err)
		}
	}
}
