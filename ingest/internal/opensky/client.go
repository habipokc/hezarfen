package opensky

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/habipokc/hezarfen/ingest/internal/geo"
)

// refreshMargin renews a token this long before it expires, so a request never
// leaves with a token that dies in flight.
const refreshMargin = 60 * time.Second

// TokenSource hands out OAuth2 access tokens (client credentials grant) and caches
// them until shortly before expiry. Safe for concurrent use.
type TokenSource struct {
	URL, ClientID, ClientSecret string
	HTTP                        *http.Client
	Now                         func() time.Time // injectable clock for tests

	mu     sync.Mutex
	token  string
	expiry time.Time
}

// Token returns a valid access token, fetching a new one if needed. The mutex is held
// during the fetch on purpose: concurrent callers wait for one refresh instead of
// each hitting the auth server.
func (t *TokenSource) Token(ctx context.Context) (string, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	now := t.now()
	if t.token != "" && now.Before(t.expiry.Add(-refreshMargin)) {
		return t.token, nil
	}
	form := url.Values{
		"grant_type":    {"client_credentials"},
		"client_id":     {t.ClientID},
		"client_secret": {t.ClientSecret},
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.URL, strings.NewReader(form.Encode()))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := t.HTTP.Do(req)
	if err != nil {
		return "", fmt.Errorf("token request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return "", fmt.Errorf("token request: HTTP %d: %s", resp.StatusCode, body)
	}
	var tok struct {
		AccessToken string `json:"access_token"`
		ExpiresIn   int    `json:"expires_in"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&tok); err != nil || tok.AccessToken == "" {
		return "", fmt.Errorf("token response without access_token (%v)", err)
	}
	if tok.ExpiresIn <= 0 {
		tok.ExpiresIn = 1800 // OpenSky's documented lifetime: 30 minutes
	}
	t.token, t.expiry = tok.AccessToken, now.Add(time.Duration(tok.ExpiresIn)*time.Second)
	return t.token, nil
}

// Invalidate drops the cached token; the next Token call fetches a fresh one.
func (t *TokenSource) Invalidate() {
	t.mu.Lock()
	t.token = ""
	t.mu.Unlock()
}

func (t *TokenSource) now() time.Time {
	if t.Now != nil {
		return t.Now()
	}
	return time.Now()
}

// RateLimitError is returned on HTTP 429: the daily credits are spent.
type RateLimitError struct {
	RetryAfter time.Duration
}

func (e *RateLimitError) Error() string {
	return fmt.Sprintf("opensky rate limit reached, retry after %s", e.RetryAfter)
}

// Response is a successful /states/all call.
type Response struct {
	Snapshot
	Body             []byte // raw JSON, archived by live mode's raw zone
	CreditsRemaining *int   // X-Rate-Limit-Remaining; nil if the header is absent
}

// Client calls /states/all. Tokens nil means anonymous access.
type Client struct {
	HTTP       *http.Client
	APIURL     string
	Tokens     *TokenSource
	MaxRetries int                                              // retries for 5xx and network errors
	Sleep      func(ctx context.Context, d time.Duration) error // injectable for tests
}

// GetStates fetches every state vector inside bbox. 5xx answers and network errors
// are retried with exponential backoff (1 s, 2 s, 4 s …); a 401 refreshes the token
// once; a 429 returns *RateLimitError without retrying, since waiting is the caller's
// scheduling decision.
func (c *Client) GetStates(ctx context.Context, bbox geo.BBox) (Response, error) {
	q := url.Values{
		"lamin":    {strconv.FormatFloat(bbox.MinLat, 'f', -1, 64)},
		"lomin":    {strconv.FormatFloat(bbox.MinLon, 'f', -1, 64)},
		"lamax":    {strconv.FormatFloat(bbox.MaxLat, 'f', -1, 64)},
		"lomax":    {strconv.FormatFloat(bbox.MaxLon, 'f', -1, 64)},
		"extended": {"1"},
	}
	endpoint := strings.TrimRight(c.APIURL, "/") + "/states/all?" + q.Encode()

	refreshed := false
	for attempt := 0; ; attempt++ {
		resp, err := c.do(ctx, endpoint)
		var retryable error
		switch {
		case err != nil:
			if ctx.Err() != nil {
				return Response{}, ctx.Err()
			}
			retryable = err
		case resp.StatusCode == http.StatusOK:
			return readStates(resp)
		case resp.StatusCode == http.StatusUnauthorized && c.Tokens != nil && !refreshed:
			drain(resp)
			c.Tokens.Invalidate()
			refreshed = true
			attempt-- // a token refresh is not a failed attempt
			continue
		case resp.StatusCode == http.StatusTooManyRequests:
			drain(resp)
			return Response{}, &RateLimitError{RetryAfter: retryAfter(resp.Header)}
		case resp.StatusCode >= 500:
			drain(resp)
			retryable = fmt.Errorf("opensky: HTTP %d", resp.StatusCode)
		default:
			body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
			resp.Body.Close()
			return Response{}, fmt.Errorf("opensky: HTTP %d: %s", resp.StatusCode, body)
		}
		if attempt >= c.MaxRetries {
			return Response{}, fmt.Errorf("giving up after %d attempts: %w", attempt+1, retryable)
		}
		if err := c.sleep(ctx, time.Second<<attempt); err != nil {
			return Response{}, err
		}
	}
}

func (c *Client) do(ctx context.Context, endpoint string) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, err
	}
	if c.Tokens != nil {
		tok, err := c.Tokens.Token(ctx)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "Bearer "+tok)
	}
	return c.HTTP.Do(req)
}

func (c *Client) sleep(ctx context.Context, d time.Duration) error {
	if c.Sleep != nil {
		return c.Sleep(ctx, d)
	}
	return Sleep(ctx, d)
}

// Sleep waits for d or until ctx is cancelled, whichever comes first.
func Sleep(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

func readStates(resp *http.Response) (Response, error) {
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return Response{}, fmt.Errorf("read states body: %w", err)
	}
	snap, err := ParseStates(body)
	if err != nil {
		return Response{}, err
	}
	out := Response{Snapshot: snap, Body: body}
	if v, err := strconv.Atoi(resp.Header.Get("X-Rate-Limit-Remaining")); err == nil {
		out.CreditsRemaining = &v
	}
	return out, nil
}

func retryAfter(h http.Header) time.Duration {
	if s, err := strconv.Atoi(h.Get("X-Rate-Limit-Retry-After-Seconds")); err == nil && s > 0 {
		return time.Duration(s) * time.Second
	}
	return time.Minute
}

// drain lets the transport reuse the keep-alive connection.
func drain(resp *http.Response) {
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 64<<10))
	resp.Body.Close()
}

// IsRateLimit reports whether err is a 429 and returns how long to wait.
func IsRateLimit(err error) (time.Duration, bool) {
	var rl *RateLimitError
	if errors.As(err, &rl) {
		return rl.RetryAfter, true
	}
	return 0, false
}
