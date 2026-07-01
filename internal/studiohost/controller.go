package studiohost

import (
	"crypto/rand"
	"crypto/subtle"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/DashDashGoApp/Dash-Go-Showcase-Studio/internal/fixtures"
)

//go:embed web/hub.html
var hubHTML string

//go:embed web/hub.js
var hubJS string

//go:embed web/hub.css
var hubCSS string

type controller struct {
	app      *App
	token    string
	listener net.Listener
	server   *http.Server
	baseURL  string
}

func (a *App) startHub() error {
	ctl, err := newController(a)
	if err != nil {
		return err
	}
	defer ctl.close()
	defer a.stopActiveRuntime()
	defer func() { _ = a.clean() }()
	if a.options.Trace {
		fmt.Println("Studio Hub:", ctl.baseURL)
	}
	return a.launchBrowser(ctl.baseURL + "?token=" + ctl.token)
}

func newController(app *App) (*controller, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, fmt.Errorf("start Studio Hub: %w", err)
	}
	ctl := &controller{app: app, token: randomToken(), listener: listener}
	ctl.baseURL = "http://" + listener.Addr().String()
	mux := http.NewServeMux()
	mux.HandleFunc("/", ctl.handleHub)
	mux.HandleFunc("/assets/hub.js", ctl.handleJS)
	mux.HandleFunc("/assets/hub.css", ctl.handleCSS)
	mux.HandleFunc("/api/status", ctl.handleStatus)
	mux.HandleFunc("/api/start-tour", ctl.handleStartTour)
	mux.HandleFunc("/api/restart-tour", ctl.handleRestartTour)
	mux.HandleFunc("/api/stop", ctl.handleStop)
	mux.HandleFunc("/api/return-home", ctl.handleReturnHome)
	mux.HandleFunc("/api/viewport", ctl.handleViewport)
	ctl.server = &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	go func() { _ = ctl.server.Serve(listener) }()
	return ctl, nil
}

func (c *controller) close() { _ = c.server.Close() }

func (c *controller) handleHub(w http.ResponseWriter, r *http.Request) {
	if !c.authorized(r) {
		http.Error(w, "Studio Hub access denied", http.StatusForbidden)
		return
	}
	locations, _ := json.Marshal(fixtures.AllLocations())
	page := strings.ReplaceAll(hubHTML, "__LOCATIONS_JSON__", string(locations))
	page = strings.ReplaceAll(page, "__TOKEN__", c.token)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(page))
}

func (c *controller) handleJS(w http.ResponseWriter, r *http.Request) {
	if !c.authorized(r) {
		http.Error(w, "Studio Hub access denied", http.StatusForbidden)
		return
	}
	w.Header().Set("Content-Type", "application/javascript; charset=utf-8")
	_, _ = w.Write([]byte(hubJS))
}

func (c *controller) handleCSS(w http.ResponseWriter, r *http.Request) {
	if !c.authorized(r) {
		http.Error(w, "Studio Hub access denied", http.StatusForbidden)
		return
	}
	w.Header().Set("Content-Type", "text/css; charset=utf-8")
	_, _ = w.Write([]byte(hubCSS))
}

func (c *controller) handleStatus(w http.ResponseWriter, r *http.Request) {
	if !c.authorized(r) || r.Method != http.MethodGet {
		http.Error(w, "Studio Hub access denied", http.StatusForbidden)
		return
	}
	browser, browserErr := findBrowser()
	payload := map[string]any{
		"studio":              "Dash-Go Showcase Studio",
		"dashGoVersion":       "1.5.2 feature baseline",
		"runtimePresent":      true,
		"browser":             browser.path,
		"browserReady":        browserErr == nil,
		"defaultLocation":     fixtures.DefaultLocation().ID,
		"sessionIsDisposable": true,
		"viewportPresets":     allShowcaseViewports(),
	}
	if browserErr != nil {
		payload["browserDetail"] = browserErr.Error()
	}
	writeJSON(w, payload)
}

func (c *controller) handleStartTour(w http.ResponseWriter, r *http.Request) {
	if c.handleCORS(w, r) {
		return
	}
	if !c.authorized(r) || r.Method != http.MethodPost {
		http.Error(w, "Studio Hub access denied", http.StatusForbidden)
		return
	}
	location, err := locationFromRequest(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if err := c.app.prepareScenarioForLocation(fixtures.DefaultScenario, location); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	runtime, err := c.app.startRuntime()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, map[string]any{"ok": true, "location": location, "dashboardURL": c.tourURL(runtime.url, location)})
}

func (c *controller) handleRestartTour(w http.ResponseWriter, r *http.Request) {
	c.handleStartTour(w, r)
}

func (c *controller) tourURL(baseURL, location string) string {
	parsed, _ := url.Parse(baseURL)
	query := parsed.Query()
	profile, _ := fixtures.LookupLocation(location)
	query.Set("showcaseStudio", "1")
	query.Set("showcaseTour", "1")
	query.Set("showcaseHub", c.baseURL)
	query.Set("showcaseToken", c.token)
	query.Set("showcaseLocation", location)
	query.Set("showcaseCity", profile.City+", "+profile.Region)
	query.Set("showcaseAlertEvent", profile.AlertEvent)
	query.Set("showcaseAlertSeverity", profile.AlertSeverity)
	parsed.RawQuery = query.Encode()
	return parsed.String()
}

func (c *controller) handleStop(w http.ResponseWriter, r *http.Request) {
	if c.handleCORS(w, r) {
		return
	}
	if !c.authorized(r) || r.Method != http.MethodPost {
		http.Error(w, "Studio Hub access denied", http.StatusForbidden)
		return
	}
	c.app.stopActiveRuntime()
	writeJSON(w, map[string]any{"ok": true})
}

func (c *controller) handleReturnHome(w http.ResponseWriter, r *http.Request) {
	if c.handleCORS(w, r) {
		return
	}
	if !c.authorized(r) || r.Method != http.MethodPost {
		http.Error(w, "Studio Hub access denied", http.StatusForbidden)
		return
	}
	c.app.stopActiveRuntime()
	writeJSON(w, map[string]any{"ok": true, "hubURL": c.baseURL + "?token=" + url.QueryEscape(c.token)})
}

func (c *controller) handleViewport(w http.ResponseWriter, r *http.Request) {
	if c.handleCORS(w, r) {
		return
	}
	if !c.authorized(r) || r.Method != http.MethodPost {
		http.Error(w, "Studio Hub access denied", http.StatusForbidden)
		return
	}
	var body struct {
		Preset string `json:"preset"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 16*1024)).Decode(&body); err != nil {
		http.Error(w, "invalid Studio viewport request", http.StatusBadRequest)
		return
	}
	result, err := c.app.applyViewportPreset(body.Preset)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	writeJSON(w, result)
}

func (c *controller) handleCORS(w http.ResponseWriter, r *http.Request) bool {
	origin := strings.TrimSpace(r.Header.Get("Origin"))
	if origin != "" {
		parsed, err := url.Parse(origin)
		if err == nil && (parsed.Hostname() == "127.0.0.1" || parsed.Hostname() == "localhost") {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Showcase-Token")
		}
	}
	if r.Method != http.MethodOptions {
		return false
	}
	if !c.authorized(r) {
		http.Error(w, "Studio Hub access denied", http.StatusForbidden)
		return true
	}
	w.WriteHeader(http.StatusNoContent)
	return true
}

func (c *controller) authorized(r *http.Request) bool {
	token := r.URL.Query().Get("token")
	if token == "" {
		token = r.Header.Get("X-Showcase-Token")
	}
	return len(token) == len(c.token) && subtle.ConstantTimeCompare([]byte(token), []byte(c.token)) == 1
}

func locationFromRequest(r *http.Request) (string, error) {
	var body struct {
		Location string `json:"location"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 16*1024)).Decode(&body); err != nil {
		return "", fmt.Errorf("invalid Studio request")
	}
	body.Location = strings.TrimSpace(body.Location)
	if _, ok := fixtures.LookupLocation(body.Location); !ok {
		return "", fmt.Errorf("unknown Showcase demo location")
	}
	return body.Location, nil
}

func writeJSON(w http.ResponseWriter, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	_ = json.NewEncoder(w).Encode(value)
}

func randomToken() string {
	raw := make([]byte, 24)
	if _, err := rand.Read(raw); err == nil {
		return hex.EncodeToString(raw)
	}
	return randomSuffix() + randomSuffix()
}
