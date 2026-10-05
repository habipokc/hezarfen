// Package publish sends each cycle's cleaned aircraft to Redis as the
// positions.batch/v1 message (ICD IF-3).
package publish

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"

	"github.com/habipokc/hezarfen/ingest/internal/clean"
)

const (
	Channel = "positions.batch"
	Schema  = "positions.batch/v1"
)

// Message is ICD §4.1. Field names and units are part of the contract.
type Message struct {
	Schema   string     `json:"schema"`
	Source   string     `json:"source"`
	Ts       int64      `json:"ts"`
	Aircraft []Aircraft `json:"aircraft"`
}

// Aircraft carries every documented field; unknown values are JSON null, never omitted.
type Aircraft struct {
	Icao24   string   `json:"icao24"`
	Callsign *string  `json:"callsign"`
	Lon      float64  `json:"lon"`
	Lat      float64  `json:"lat"`
	BaroAlt  *float64 `json:"baro_alt"`
	GeoAlt   *float64 `json:"geo_alt"`
	Velocity *float64 `json:"velocity"`
	Heading  *float64 `json:"heading"`
	VRate    *float64 `json:"vrate"`
	OnGround bool     `json:"on_ground"`
	Squawk   *string  `json:"squawk"`
	Category *int     `json:"category"`
	Ts       int64    `json:"ts"` // position time (ICD 1.2, additive)
}

func NewMessage(source string, ts int64, recs []clean.Record) Message {
	m := Message{Schema: Schema, Source: source, Ts: ts, Aircraft: make([]Aircraft, len(recs))}
	for i, r := range recs {
		m.Aircraft[i] = Aircraft{
			Icao24: r.Icao24, Callsign: r.Callsign, Lon: r.Lon, Lat: r.Lat, BaroAlt: r.BaroAlt,
			GeoAlt: r.GeoAlt, Velocity: r.Velocity, Heading: r.Heading, VRate: r.VRate,
			OnGround: r.OnGround, Squawk: r.Squawk, Category: r.Category, Ts: r.Ts,
		}
	}
	return m
}

type Publisher struct {
	rdb     *redis.Client
	channel string
}

func New(redisURL string) (*Publisher, error) {
	opts, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, fmt.Errorf("parse redis url: %w", err)
	}
	return &Publisher{rdb: redis.NewClient(opts), channel: Channel}, nil
}

func (p *Publisher) Ping(ctx context.Context) error { return p.rdb.Ping(ctx).Err() }
func (p *Publisher) Close() error                   { return p.rdb.Close() }

// Publish sends m and returns how many subscribers received it. Zero is not an
// error: pub/sub is fire-and-forget and the database stays the source of truth.
func (p *Publisher) Publish(ctx context.Context, m Message) (int64, error) {
	payload, err := json.Marshal(m)
	if err != nil {
		return 0, err
	}
	return p.rdb.Publish(ctx, p.channel, payload).Result()
}
