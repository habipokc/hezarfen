package publish

import (
	"context"
	"encoding/json"
	"os"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/habipokc/hezarfen/ingest/internal/clean"
)

func ptr[T any](v T) *T { return &v }

var records = []clean.Record{
	{Icao24: "4baa0f", Callsign: ptr("THY7AB"), Ts: 1791187198, Lon: 28.8146, Lat: 41.2753,
		BaroAlt: ptr(3350.0), GeoAlt: ptr(3420.5), Velocity: ptr(152.3), Heading: ptr(87.4), VRate: ptr(6.5),
		Squawk: ptr("2341"), Category: ptr(4)},
	{Icao24: "4b1812", Ts: 1791187190, Lon: 29.3, Lat: 40.9, OnGround: true},
}

func TestMessageMatchesICD(t *testing.T) {
	raw, err := json.Marshal(NewMessage("synthetic", 1791187200, records))
	if err != nil {
		t.Fatal(err)
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	if doc["schema"] != "positions.batch/v1" || doc["source"] != "synthetic" || doc["ts"] != 1791187200.0 {
		t.Errorf("envelope = %v", doc)
	}
	aircraft := doc["aircraft"].([]any)
	first := aircraft[0].(map[string]any)
	var keys []string
	for k := range first {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	want := "baro_alt callsign category geo_alt heading icao24 lat lon on_ground squawk ts velocity vrate"
	if strings.Join(keys, " ") != want {
		t.Errorf("keys = %v", keys)
	}
	// ICD §2: missing values are null, fields are never omitted
	second := aircraft[1].(map[string]any)
	for _, k := range []string{"callsign", "baro_alt", "velocity", "squawk", "category"} {
		if v, ok := second[k]; !ok || v != nil {
			t.Errorf("%s = %v (present=%v), want null", k, v, ok)
		}
	}
}

func TestEmptyBatchIsAnArray(t *testing.T) {
	raw, _ := json.Marshal(NewMessage("live", 1, nil))
	if !strings.Contains(string(raw), `"aircraft":[]`) {
		t.Errorf("got %s", raw)
	}
}

func TestPublishReachesSubscriber(t *testing.T) {
	url := os.Getenv("INGEST_TEST_REDIS_URL")
	if url == "" {
		t.Skip("INGEST_TEST_REDIS_URL not set")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	p, err := New(url)
	if err != nil {
		t.Fatal(err)
	}
	defer p.Close()
	// pub/sub channels are global across Redis databases: use a test channel so a
	// running relay never sees these aircraft
	p.channel = "test." + Channel
	opts, _ := redis.ParseURL(url)
	sub := redis.NewClient(opts).Subscribe(ctx, p.channel)
	defer sub.Close()
	if _, err := sub.Receive(ctx); err != nil { // wait for the subscription confirmation
		t.Fatal(err)
	}

	n, err := p.Publish(ctx, NewMessage("synthetic", 1791187200, records))
	if err != nil || n < 1 {
		t.Fatalf("receivers=%d err=%v", n, err)
	}
	msg, err := sub.ReceiveMessage(ctx)
	if err != nil {
		t.Fatal(err)
	}
	var got Message
	if err := json.Unmarshal([]byte(msg.Payload), &got); err != nil {
		t.Fatal(err)
	}
	if len(got.Aircraft) != 2 || got.Aircraft[0].Icao24 != "4baa0f" {
		t.Errorf("received %+v", got)
	}
}
