#!/usr/bin/env python3
"""Apply the narrow Dash-Go 1.5.7 Showcase portability overlay to a staged copy.

The script intentionally uses exact replacement anchors. A changed upstream source
must fail here rather than silently producing a partial or guessed port.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path


class PatchError(RuntimeError):
    pass


def replace_once(path: Path, before: str, after: str) -> None:
    source = path.read_text(encoding="utf-8")
    count = source.count(before)
    if count != 1:
        raise PatchError(f"{path}: expected exactly one patch anchor, found {count}")
    path.write_text(source.replace(before, after), encoding="utf-8")


def remove_import(path: Path, literal: str) -> None:
    source = path.read_text(encoding="utf-8")
    if literal not in source:
        raise PatchError(f"{path}: required import anchor missing: {literal!r}")
    path.write_text(source.replace(literal, "", 1), encoding="utf-8")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip(), encoding="utf-8")


def apply(app: Path) -> None:
    cmd = app / "cmd/dashboard-control-server"
    platform = app / "internal/platform"

    action_history = cmd / "action_history.go"
    remove_import(action_history, '\t"syscall"\n')
    replace_once(
        action_history,
        '''func withActionHistoryLock(path string, fn func() error) error {
\tif err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
\t\treturn err
\t}
\tlock, err := os.OpenFile(actionHistoryLockPath(path), os.O_CREATE|os.O_RDWR, 0600)
\tif err != nil {
\t\treturn err
\t}
\tdefer lock.Close()
\tif err := lock.Chmod(0600); err != nil {
\t\treturn err
\t}
\tif err := syscall.Flock(int(lock.Fd()), syscall.LOCK_EX); err != nil {
\t\treturn err
\t}
\tdefer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
\treturn fn()
}
''',
        '''func withActionHistoryLock(path string, fn func() error) error {
\treturn withPortableFileLock(actionHistoryLockPath(path), fn)
}
''',
    )

    recovery = cmd / "dashboard_update_recovery.go"
    for literal in ['\t"errors"\n', '\t"os"\n', '\t"syscall"\n']:
        remove_import(recovery, literal)
    replace_once(
        recovery,
        '''func (a *app) updateLockHeld() (bool, error) {
\tpath := a.updateLockPath()
\tif err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
\t\treturn false, err
\t}
\tfile, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0600)
\tif err != nil {
\t\treturn false, err
\t}
\tdefer file.Close()
\tif err := syscall.Flock(int(file.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
\t\tif errors.Is(err, syscall.EWOULDBLOCK) || errors.Is(err, syscall.EAGAIN) {
\t\t\treturn true, nil
\t\t}
\t\treturn false, err
\t}
\tdefer syscall.Flock(int(file.Fd()), syscall.LOCK_UN)
\treturn false, nil
}
''',
        '''func (a *app) updateLockHeld() (bool, error) {
\treturn portableLockHeld(a.updateLockPath())
}
''',
    )

    updates = cmd / "updates.go"
    remove_import(updates, '\t"syscall"\n')
    replace_once(updates, 'return p.Signal(syscall.Signal(0)) == nil', 'return portableProcessRunning(p)')
    replace_once(updates, '\tcmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}\n', '\tprepareDetachedCommand(cmd)\n')
    replace_once(
        updates,
        '''func (a *app) systemUpdateStatus() map[string]any {
\tpath := filepath.Join(a.cacheDir, "system-update-status.json")
''',
        '''func (a *app) systemUpdateStatus() map[string]any {
\tif a.showcaseMode() {
\t\treturn a.showcaseSystemUpdateStatus()
\t}
\tpath := filepath.Join(a.cacheDir, "system-update-status.json")
''',
    )
    replace_once(
        updates,
        '''func (a *app) startSystemUpdate() (map[string]any, error) {
\tst := a.systemUpdateStatus()
''',
        '''func (a *app) startSystemUpdate() (map[string]any, error) {
\tif a.showcaseMode() {
\t\treturn nil, showcaseUnavailable("system update")
\t}
\tst := a.systemUpdateStatus()
''',
    )

    system = platform / "system.go"
    remove_import(system, '\t"syscall"\n')
    replace_once(
        system,
        '''func DiskFreeMB(path string) int {
\tvar st syscall.Statfs_t
\tif syscall.Statfs(path, &st) != nil || st.Bsize <= 0 {
\t\treturn 0
\t}
\treturn int((st.Bavail * uint64(st.Bsize)) / 1024 / 1024)
}
''',
        '''func DiskFreeMB(path string) int {
\treturn portableDiskFreeMB(path)
}
''',
    )

    terminal = platform / "terminal.go"
    remove_import(terminal, '\t"syscall"\n')
    replace_once(terminal, '\tcmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}\n', '\tprepareDetachedTerminalCommand(cmd)\n')
    replace_once(
        terminal,
        '''func (s *Service) TerminalAccessEnabled() bool {
\tb, e := os.ReadFile(s.TerminalAccessFile())
''',
        '''func (s *Service) TerminalAccessEnabled() bool {
\tif strings.TrimSpace(os.Getenv("DASHGO_SHOWCASE")) == "1" {
\t\treturn false
\t}
\tb, e := os.ReadFile(s.TerminalAccessFile())
''',
    )

    main = cmd / "main.go"
    replace_once(
        main,
        '''func newAppFromRuntime() *app {
\texe, _ := os.Executable()
\tdash := filepath.Dir(filepath.Dir(exe))
\tif _, err := os.Stat(filepath.Join(dash, "index.html")); err != nil {
\t\tif wd, err := os.Getwd(); err == nil {
\t\t\tdash = wd
\t\t}
\t}
\thome, _ := os.UserHomeDir()
\ta := &app{dash: dash, home: home, configDir: filepath.Join(dash, "config"), calDir: filepath.Join(dash, "calendars"), cacheDir: filepath.Join(dash, "cache"), logDir: filepath.Join(dash, "logs"), binDir: filepath.Join(dash, "bin"), settingsFile: filepath.Join(dash, "config", "settings.json"), configLocal: filepath.Join(dash, "config", "config.local.js"), celebrationsFile: filepath.Join(home, ".dashboard-celebrations"), todoDir: filepath.Join(dash, "config", "todo"), todoTokenFile: filepath.Join(home, ".dashboard-todo.json"), fontsDir: filepath.Join(dash, "fonts"), todoStreams: map[chan []byte]bool{}, releaseVersion: fileio.ReadString(filepath.Join(dash, "VERSION"), "")}
\ta.settings = settingspkg.New(a.settingsConfig())
\treturn a
}
''',
        '''func newAppFromRuntime() *app {
\texe, _ := os.Executable()
\tdash := filepath.Dir(filepath.Dir(exe))
\tif _, err := os.Stat(filepath.Join(dash, "index.html")); err != nil {
\t\tif wd, err := os.Getwd(); err == nil {
\t\t\tdash = wd
\t\t}
\t}
\thome := dashGoRuntimeHome()
\tdata := dashGoShowcaseDataRoot(dash)
\ta := &app{dash: dash, home: home, configDir: filepath.Join(data, "config"), calDir: filepath.Join(data, "calendars"), cacheDir: filepath.Join(data, "cache"), logDir: filepath.Join(data, "logs"), binDir: filepath.Join(dash, "bin"), settingsFile: filepath.Join(data, "config", "settings.json"), configLocal: filepath.Join(data, "config", "config.local.js"), celebrationsFile: filepath.Join(home, ".dashboard-celebrations"), todoDir: filepath.Join(data, "config", "todo"), todoTokenFile: filepath.Join(home, ".dashboard-todo.json"), fontsDir: filepath.Join(data, "fonts"), todoStreams: map[chan []byte]bool{}, releaseVersion: fileio.ReadString(filepath.Join(dash, "VERSION"), "")}
\ta.settings = settingspkg.New(a.settingsConfig())
\treturn a
}
''',
    )
    replace_once(
        main,
        '''\t// A server restart during an update can happen between writing the terminal
\t// job record and the runner finalizing Recent Actions. Repair that narrow
\t// window before the HTTP server accepts its first request.
\ta.reconcileInterruptedUpdateState()
\ta.reconcileUpdateActionHistory()
\ta.ensureSettingsSafeAtBoot()
\tif err := a.todoNormalizeInboundSyncSetting(); err != nil {
\t\tlog.Printf("could not normalize retired Microsoft To Do cadence: %v", err)
\t}
\ta.startTodoArchiveJanitor()
\ta.startTodoInboundScheduler()
\ta.startAppriseNotifier()
''',
        '''\t// The Showcase runtime intentionally avoids appliance maintenance,
\t// provider polling, and notification workers. The same UI and local data
\t// paths remain available, but Studio has no device side effects.
\tif !a.showcaseMode() {
\t\ta.reconcileInterruptedUpdateState()
\t\ta.reconcileUpdateActionHistory()
\t\ta.ensureSettingsSafeAtBoot()
\t\tif err := a.todoNormalizeInboundSyncSetting(); err != nil {
\t\t\tlog.Printf("could not normalize retired Microsoft To Do cadence: %v", err)
\t\t}
\t\ta.startTodoArchiveJanitor()
\t\ta.startTodoInboundScheduler()
\t\ta.startAppriseNotifier()
\t}
''',
    )

    post = cmd / "http_routes_post.go"
    replace_once(
        post,
        '''\tif !autoDisplay && !a.tokenOK(r.Header.Get("X-Dashboard-Token")) && !a.consumeOneShot(oneShot, path) {
\t\ta.err(w, "locked", 401)
\t\treturn
\t}
\tif a.handleHouseholdPeoplePost(w, r, path, body) {
''',
        '''\tif !autoDisplay && !a.tokenOK(r.Header.Get("X-Dashboard-Token")) && !a.consumeOneShot(oneShot, path) {
\t\ta.err(w, "locked", 401)
\t\treturn
\t}
\tif reason := a.showcaseRestrictedPost(path, body); reason != "" {
\t\ta.err(w, reason, http.StatusForbidden)
\t\treturn
\t}
\tif a.handleHouseholdPeoplePost(w, r, path, body) {
''',
    )

    http_server = cmd / "http_server.go"
    replace_once(
        http_server,
        '''\tclean := filepath.Clean("/" + strings.TrimPrefix(path, "/"))
\trel := strings.TrimPrefix(clean, "/")
''',
        '''\t// URLs use '/' even on Windows. filepath.Clean is host-OS-specific
\t// and turns this key into a backslash-prefixed path on Windows, which misses
\t// the Showcase browser-data allowlist. Keep URL normalization portable.
\t// Use a URL-path helper before staticPrivatePath and showcaseStaticDataPath.
\trel := showcaseStaticRelativePath(path)
''',
    )
    replace_once(
        http_server,
        '''\tfull := filepath.Join(a.dash, rel)
\tif !strings.HasPrefix(full, a.dash) || staticPrivatePath(rel) {
\t\tsetNoStore(w)
\t\thttp.NotFound(w, r)
\t\treturn
\t}
''',
        '''\tfull := filepath.Join(a.dash, rel)
\tif staticPrivatePath(rel) {
\t\tsetNoStore(w)
\t\thttp.NotFound(w, r)
\t\treturn
\t}
\tif showcasePath, ok := a.showcaseStaticDataPath(rel); ok {
\t\tfull = showcasePath
\t} else if !strings.HasPrefix(full, a.dash) {
\t\tsetNoStore(w)
\t\thttp.NotFound(w, r)
\t\treturn
\t}
''',
    )

    get = cmd / "http_routes_get.go"
    replace_once(
        get,
        '''\tif !a.tokenOK(r.Header.Get("X-Dashboard-Token")) {
\t\ta.err(w, "locked", 401)
\t\treturn
\t}
\tif a.handleHouseholdPeopleGet(w, r, path) {
''',
        '''\tif !a.tokenOK(r.Header.Get("X-Dashboard-Token")) {
\t\ta.err(w, "locked", 401)
\t\treturn
\t}
\tif reason := a.showcaseRestrictedGet(path); reason != "" {
\t\ta.json(w, map[string]any{"ok": false, "error": reason, "detail": "This read is simulated or unavailable in Dash-Go Showcase Studio."})
\t\treturn
\t}
\tif a.handleHouseholdPeopleGet(w, r, path) {
''',
    )
    replace_once(
        get,
        '''\tif a.handleHouseholdPeopleGet(w, r, path) {
\t\treturn
\t}
\tswitch path {
''',
        '''\tif a.handleHouseholdPeopleGet(w, r, path) {
\t\treturn
\t}
\tif path == "/api/geocode" && a.showcaseMode() {
\t\ta.json(w, a.showcaseGeocode(r.URL.Query().Get("q")))
\t\treturn
\t}
\tswitch path {
''',
    )

    weather_facade = cmd / "weather_facade.go"
    replace_once(
        weather_facade,
        '''func (a *app) weatherPayload() any          { return a.weatherService().Payload() }
''',
        '''func (a *app) weatherPayload() any {
	if a.showcaseMode() {
		return a.showcaseWeatherPayload()
	}
	return a.weatherService().Payload()
}
''',
    )

    dashboard_update = cmd / "dashboard_update.go"
    replace_once(
        dashboard_update,
        '''func (a *app) startDashboardUpdate() (map[string]any, error) {
\ta.updateMu.Lock()
''',
        '''func (a *app) startDashboardUpdate() (map[string]any, error) {
\tif a.showcaseMode() {
\t\treturn nil, showcaseUnavailable("dashboard update")
\t}
\ta.updateMu.Lock()
''',
    )

    release_current = cmd / "release_current.go"
    replace_once(
        release_current,
        '''func (a *app) checkUpdateAvailability() map[string]any {
''',
        '''func (a *app) checkUpdateAvailability() map[string]any {
\tif a.showcaseMode() {
\t\treturn a.showcaseUpdateAvailability()
\t}
''',
    )

    write(cmd / "showcase_mode.go", r'''
package main

import (
	"errors"
	"os"
	pathpkg "path"
	"path/filepath"
	"strings"
	"time"
)

func dashGoRuntimeHome() string {
	if home := strings.TrimSpace(os.Getenv("DASHGO_HOME")); home != "" {
		return home
	}
	home, _ := os.UserHomeDir()
	return home
}

func dashGoShowcaseDataRoot(assetRoot string) string {
	if strings.TrimSpace(os.Getenv("DASHGO_SHOWCASE")) != "1" {
		return assetRoot
	}
	if root := strings.TrimSpace(os.Getenv("DASHGO_SHOWCASE_DATA_ROOT")); root != "" {
		return filepath.Clean(root)
	}
	return assetRoot
}

func (a *app) showcaseMode() bool {
	// The data-root contract is sufficient to identify an isolated Studio
	// runtime. Keeping it as a fallback makes the browser-data route resilient
	// if a Windows child-process environment normalizes or omits the companion
	// boolean flag while preserving the explicit private data root.
	return strings.TrimSpace(os.Getenv("DASHGO_SHOWCASE")) == "1" ||
		strings.TrimSpace(os.Getenv("DASHGO_SHOWCASE_DATA_ROOT")) != ""
}

// showcaseStaticRelativePath normalizes an HTTP URL path, not an operating
// system filename. The standard path package always uses '/', whereas
// filepath.Clean converts to '\\' on Windows and can make the allowlist key
// fail to match the browser-visible Showcase data files.
func showcaseStaticRelativePath(requestPath string) string {
	clean := pathpkg.Clean("/" + strings.TrimPrefix(requestPath, "/"))
	return strings.TrimPrefix(clean, "/")
}

// showcaseStaticDataPath is deliberately narrow. Studio's immutable package
// omits mutable config, calendar, and cache trees, while Dash-Go's browser
// still reads a small set of local files directly. Resolve every allowlisted
// path directly from the configured private data root rather than through
// app-initialization fields, so the browser route remains tied to the same
// explicit runtime contract on every platform.
func (a *app) showcaseStaticDataPath(rel string) (string, bool) {
	if !a.showcaseMode() {
		return "", false
	}
	switch rel {
	case "config/config.local.js", "config/compliments.json", "config/message-cache.json", "config/temp-messages.json", "config/scheduled-messages.json", "config/settings.json",
		"calendars/calendars.json", "calendars/showcase-studio.ics", "cache/events.cache.json":
		return filepath.Join(dashGoShowcaseDataRoot(a.dash), filepath.FromSlash(rel)), true
	default:
		return "", false
	}
}

func showcaseUnavailable(action string) error {
	return errors.New(action + " is unavailable in Dash-Go Showcase Studio")
}

func (a *app) showcaseSystemUpdateStatus() map[string]any {
	return map[string]any{
		"state": "unavailable", "running": false, "ready": false,
		"label":    "Unavailable in Showcase Studio",
		"detail":   "Studio never runs device package updates.",
		"problems": []any{"Studio is a disposable local demonstration environment."},
	}
}

func (a *app) showcaseUpdateAvailability() map[string]any {
	return map[string]any{
		"ok": false, "available": false, "ready": false,
		"label":    "Unavailable in Showcase Studio",
		"detail":   "Studio never checks, downloads, or installs Dash-Go releases.",
		"problems": []any{"Studio uses a pinned local runtime."},
		"track":    "showcase", "installedVersion": a.releaseVersion,
	}
}

// showcaseWeatherPayload is deliberately offline and deterministic in shape,
// while using today's local date so the dashboard has a useful forecast during
// every Studio session. It never calls an external provider.
func (a *app) showcaseWeatherPayload() map[string]any {
	now := time.Now()
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())

	highs := []int{78, 80, 76, 73, 75, 79, 82}
	lows := []int{61, 63, 60, 57, 58, 62, 65}
	codes := []int{2, 1, 61, 3, 2, 0, 1}
	precipitation := []float64{0, 0, 0.18, 0.04, 0, 0, 0}
	probability := []int{5, 5, 55, 25, 10, 5, 5}
	winds := []int{9, 11, 14, 12, 10, 8, 10}
	uv := []int{6, 7, 4, 5, 6, 7, 7}
	daily := map[string]any{
		"time":                          []any{},
		"weather_code":                  []any{},
		"temperature_2m_max":            []any{},
		"temperature_2m_min":            []any{},
		"apparent_temperature_max":      []any{},
		"precipitation_sum":             []any{},
		"precipitation_probability_max": []any{},
		"wind_speed_10m_max":            []any{},
		"uv_index_max":                  []any{},
		"sunrise":                       []any{},
		"sunset":                        []any{},
	}
	for i := range highs {
		date := today.AddDate(0, 0, i)
		daily["time"] = append(daily["time"].([]any), date.Format("2006-01-02"))
		daily["weather_code"] = append(daily["weather_code"].([]any), codes[i])
		daily["temperature_2m_max"] = append(daily["temperature_2m_max"].([]any), highs[i])
		daily["temperature_2m_min"] = append(daily["temperature_2m_min"].([]any), lows[i])
		daily["apparent_temperature_max"] = append(daily["apparent_temperature_max"].([]any), highs[i]-1)
		daily["precipitation_sum"] = append(daily["precipitation_sum"].([]any), precipitation[i])
		daily["precipitation_probability_max"] = append(daily["precipitation_probability_max"].([]any), probability[i])
		daily["wind_speed_10m_max"] = append(daily["wind_speed_10m_max"].([]any), winds[i])
		daily["uv_index_max"] = append(daily["uv_index_max"].([]any), uv[i])
		daily["sunrise"] = append(daily["sunrise"].([]any), date.Add(6*time.Hour+12*time.Minute).Format(time.RFC3339))
		daily["sunset"] = append(daily["sunset"].([]any), date.Add(19*time.Hour+48*time.Minute).Format(time.RFC3339))
	}

	hourlyTimes := []any{}
	hourlyTemperatures := []any{}
	hourlyCodes := []any{}
	hourlyProbability := []any{}
	for _, hour := range []int{6, 9, 12, 15, 18, 21} {
		hourlyTimes = append(hourlyTimes, today.Add(time.Duration(hour)*time.Hour).Format(time.RFC3339))
		hourlyTemperatures = append(hourlyTemperatures, 64+(hour-6)/3*4)
		hourlyCodes = append(hourlyCodes, 2)
		hourlyProbability = append(hourlyProbability, 5)
	}
	hourly := map[string]any{
		"time":                      hourlyTimes,
		"temperature_2m":            hourlyTemperatures,
		"weather_code":              hourlyCodes,
		"precipitation_probability": hourlyProbability,
	}
	current := map[string]any{
		"temperature_2m":       72,
		"apparent_temperature": 71,
		"weather_code":         2,
		"wind_speed_10m":       9,
		"relative_humidity_2m": 54,
	}
	source := map[string]any{
		"_source":      "showcase",
		"_sourceLabel": "Studio Preview Forecast",
		"current":      current,
		"daily":        daily,
		"hourly":       hourly,
		"alerts":       []any{},
	}
	status := []any{map[string]any{
		"id": "showcase", "label": "Studio Preview Forecast", "tier": "offline fixture",
		"ok": true, "freshness": "synthetic", "generator": "showcase",
	}}
	return map[string]any{
		"current": current, "daily": daily, "hourly": hourly, "alerts": []any{},
		"selected": []any{"showcase"}, "sources": []any{source},
		"status": status, "sourceHealth": status,
		"cache":              map[string]any{"hit": true, "synthetic": true, "generatedAt": now.Unix()},
		"weatherBlend":       map[string]any{"ok": true, "method": "offline Studio fixture", "sourceCount": 1, "generator": "showcase"},
		"keysInServedConfig": false, "source": "showcase-fixture", "generator": "showcase",
	}
}

func (a *app) showcaseRestrictedPost(path string, body map[string]any) string {
	if !a.showcaseMode() {
		return ""
	}
	switch path {
	case "/api/location":
		return "studio_location_locked"
	case "/api/weather/refresh":
		return "studio_offline_weather_fixture"
	case "/api/display/off", "/api/display/on", "/api/browser/restart", "/api/terminal/open",
		"/api/system-update", "/api/doctor", "/api/update/track/toggle", "/api/update",
		"/api/reboot", "/api/poweroff", "/api/moon/update", "/api/calendars/sync":
		return "studio_system_action_locked"
	case "/api/backup", "/api/backup/prune", "/api/backup/restore", "/api/backup/delete":
		return "studio_file_import_locked"
	case "/api/lock/set", "/api/lock/change", "/api/lock/remove", "/api/lock/config":
		return "studio_security_locked"
	}
	if strings.HasPrefix(path, "/api/backup/") || strings.HasPrefix(path, "/api/calendar/import") || strings.HasPrefix(path, "/api/calendars/import") {
		return "studio_file_import_locked"
	}
	if strings.HasPrefix(path, "/api/todo/microsoft") || strings.HasPrefix(path, "/api/todo/graph") || strings.HasPrefix(path, "/api/apprise") || strings.HasPrefix(path, "/api/notify") {
		return "studio_external_integration_locked"
	}
	if path == "/api/settings" {
		for _, key := range []string{"weatherProviders", "weatherApi", "weatherApiKey", "weatherAlerts", "radarProvider", "displaySleep", "displayPower", "terminalAccess"} {
			if _, present := body[key]; present {
				return "studio_network_or_system_setting_locked"
			}
		}
	}
	return ""
}

func (a *app) showcaseRestrictedGet(path string) string {
	if !a.showcaseMode() {
		return ""
	}
	switch path {
	case "/api/update/status", "/api/update/progress", "/api/update/availability", "/api/update/log":
		return "studio_update_locked"
	case "/api/logs", "/api/terminal/status", "/api/action-history", "/api/doctor/status", "/api/memory/status":
		return "studio_diagnostics_simulated"
	default:
		return ""
	}
}

func (a *app) showcaseGeocode(query string) map[string]any {
	needle := strings.ToLower(strings.TrimSpace(query))
	type place struct {
		Label, City string
		Lat, Lon    float64
	}
	places := []place{
		{"New York, New York — Studio Preview", "New York", 40.7128, -74.0060},
		{"Chicago, Illinois — Studio Preview", "Chicago", 41.8781, -87.6298},
		{"Denver, Colorado — Studio Preview", "Denver", 39.7392, -104.9903},
		{"Los Angeles, California — Studio Preview", "Los Angeles", 34.0522, -118.2437},
		{"Anchorage, Alaska — Studio Preview", "Anchorage", 61.2181, -149.9003},
		{"Honolulu, Hawaii — Studio Preview", "Honolulu", 21.3069, -157.8583},
	}
	results := make([]map[string]any, 0, len(places))
	for _, place := range places {
		if needle == "" || strings.Contains(strings.ToLower(place.Label), needle) || strings.Contains(needle, strings.ToLower(place.City)) {
			results = append(results, map[string]any{"label": place.Label, "city": place.City, "lat": place.Lat, "lon": place.Lon})
		}
	}
	if len(results) == 0 {
		results = append(results, map[string]any{"label": strings.TrimSpace(query) + " — Studio preview only", "city": strings.TrimSpace(query), "lat": 39.8283, "lon": -98.5795})
	}
	return map[string]any{"results": results, "studioPreview": true}
}
''')
    write(cmd / "showcase_static_path_test.go", r'''
package main

import "testing"

func TestShowcaseStaticRelativePathUsesURLSeparators(t *testing.T) {
	cases := map[string]string{
		"/config/config.local.js":            "config/config.local.js",
		"config/../calendars/calendars.json": "calendars/calendars.json",
		"//calendars/showcase-studio.ics":    "calendars/showcase-studio.ics",
	}
	for requestPath, want := range cases {
		if got := showcaseStaticRelativePath(requestPath); got != want {
			t.Fatalf("showcaseStaticRelativePath(%q) = %q, want %q", requestPath, got, want)
		}
	}
}
''')

    write(cmd / "portable_runtime_unix.go", r'''

//go:build !windows

package main

import (
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
)

func withPortableFileLock(path string, fn func() error) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	lock, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return err
	}
	defer lock.Close()
	if err := lock.Chmod(0600); err != nil {
		return err
	}
	if err := syscall.Flock(int(lock.Fd()), syscall.LOCK_EX); err != nil {
		return err
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	return fn()
}

func portableLockHeld(path string) (bool, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return false, err
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return false, err
	}
	defer file.Close()
	if err := syscall.Flock(int(file.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		if errors.Is(err, syscall.EWOULDBLOCK) || errors.Is(err, syscall.EAGAIN) {
			return true, nil
		}
		return false, err
	}
	defer syscall.Flock(int(file.Fd()), syscall.LOCK_UN)
	return false, nil
}

func portableProcessRunning(process *os.Process) bool {
	return process != nil && process.Signal(syscall.Signal(0)) == nil
}
func prepareDetachedCommand(cmd *exec.Cmd) { cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true} }
''')
    write(cmd / "portable_runtime_windows.go", r'''
//go:build windows

package main

import (
	"os"
	"os/exec"
	"sync"
)

var portableLocks sync.Map

func withPortableFileLock(path string, fn func() error) error {
	value, _ := portableLocks.LoadOrStore(path, &sync.Mutex{})
	lock := value.(*sync.Mutex)
	lock.Lock()
	defer lock.Unlock()
	return fn()
}

// Studio disables updater paths on Windows, so no cross-process updater lock is
// needed. The function stays explicit rather than pretending an arbitrary lock
// can be safely inferred from a Windows PID.
func portableLockHeld(path string) (bool, error)      { return false, nil }
func portableProcessRunning(process *os.Process) bool { return false }
func prepareDetachedCommand(cmd *exec.Cmd)            {}
''')

    write(platform / "disk_free_unix.go", r'''
//go:build !windows

package platform

import "syscall"

func portableDiskFreeMB(path string) int {
	var st syscall.Statfs_t
	if syscall.Statfs(path, &st) != nil || st.Bsize <= 0 {
		return 0
	}
	return int((st.Bavail * uint64(st.Bsize)) / (1024 * 1024))
}
''')
    write(platform / "disk_free_windows.go", r'''
//go:build windows

package platform

// Showcase never presents device-storage repair on Windows. Returning zero
// means the existing health surface stays conservative instead of guessing.
func portableDiskFreeMB(path string) int { return 0 }
''')
    write(platform / "terminal_detach_unix.go", r'''
//go:build !windows

package platform

import (
	"os/exec"
	"syscall"
)

func prepareDetachedTerminalCommand(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
}
''')
    write(platform / "terminal_detach_windows.go", r'''
//go:build windows

package platform

import "os/exec"

func prepareDetachedTerminalCommand(cmd *exec.Cmd) {}
''')

    install_showcase_studio_overlay(app)

def install_showcase_studio_overlay(app: Path) -> None:
    # Dash-Go freezes reviewed bundle ordering in a Go test. Studio adds only
    # staged assets and updates that semantic oracle exactly rather than
    # weakening the baseline test.
    asset_order_test = app / "cmd/dashboard-control-server/runtime_assets_manifest_test.go"
    replace_once(
        asset_order_test,
        "\t\t\t\"ui/js/family-board-footer.js\",\n",
        "\t\t\t\"ui/js/family-board-footer.js\",\n\t\t\t\"ui/js/showcase-tour.js\",\n\t\t\t\"ui/js/showcase-view.js\",\n",
    )

    replace_once(
        asset_order_test,
        "\t\t\t\"ui/css/dashboard/family-board-footer.css\",\n",
        "\t\t\t\"ui/css/dashboard/family-board-footer.css\",\n\t\t\t\"ui/css/dashboard/showcase-studio.css\",\n",
    )

    location = app / "ui/js/control-location-lock.js"
    replace_once(
        location,
        "      }catch(e){ ctrlMsg(e.message); }\n    }));",
        "      }catch(e){\n        const message=String(e&&e.message||e);\n        if(message===\"studio_location_locked\"&&typeof window.showcaseStudioLocationLocked===\"function\"){window.showcaseStudioLocationLocked();return;}\n        ctrlMsg(message);\n      }\n    }));",
    )

    navigation = app / "ui/js/control-navigation.js"
    replace_once(
        navigation,
        '''function bindCtrlSummaryTaps(){
  document.querySelectorAll("#ctrl details.ctrlsec > summary").forEach(s=>{
    if(s._fastSummaryBound) return;
    s._fastSummaryBound=true;
    bindTap(s,()=>{
      const d=s.parentElement;
      if(d && d.tagName==="DETAILS") d.open=!d.open;
    },{preventDefault:true});
  });
}
''',
        '''function bindCtrlSummaryTaps(){
  // Native summary activation owns open/close. The former custom bindTap handler
  // raced the browser click path in desktop Chromium and could require multiple
  // attempts to expand a Dashboard Control card.
  document.querySelectorAll("#ctrl details.ctrlsec > summary").forEach(s=>{
    if(s._fastSummaryBound) return;
    s._fastSummaryBound=true;
  });
}
''',
    )

    tour = app / "ui/js/showcase-tour.js"
    write(tour, r'''(function(){
  const query=new URLSearchParams(window.location.search);
  if(query.get("showcaseStudio")!=="1")return;
  const hubURL=query.get("showcaseHub")||"",token=query.get("showcaseToken")||"";
  const city=query.get("showcaseCity")||"your selected city",locationID=query.get("showcaseLocation")||"chicago";
  const alertEvent=query.get("showcaseAlertEvent")||"Weather Advisory",alertSeverity=query.get("showcaseAlertSeverity")||"moderate";
  const isTour=()=>query.get("showcaseTour")==="1";
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  let index=0,card=null,alertItem=null,listsPreview=false,active=isTour();
  const surfaceSelectors=["#ctrl.show","#scrim.show","#applauncher.show","#chorewheel.show","#familyboard.show","#maintenance.show","#routines.show","#listsapp.show"];
  const call=(name,...args)=>typeof window[name]==="function"?window[name](...args):undefined;
  function primaryVisible(){return surfaceSelectors.filter(selector=>document.querySelector(selector));}
  async function clearPrimarySurface(){
    call("closeOverlaysForIdle");
    call("closeAppLauncher");call("closeChoreWheel");call("closeFamilyBoard");call("closeMaintenance");call("closeRoutines");call("closeListsApp");call("closeCtrl");call("closeScrim");
    for(let attempt=0;attempt<18&&primaryVisible().length;attempt++)await wait(35);
  }
  async function showListsPreview(){
    if(listsPreview)return;
    for(let attempt=0;attempt<20;attempt++){
      if(typeof window.dashboardListsDockEnable==="function"){await window.dashboardListsDockEnable();listsPreview=true;return;}
      await wait(75);
    }
  }
  function hideListsPreview(){
    if(typeof window.dashboardListsDockDisable==="function")window.dashboardListsDockDisable();
    listsPreview=false;
  }
  function addAlertPreview(){
    if(alertItem)return;
    // ALERTS is a lexical global in the compiled Dash-Go bundle, not a window
    // property. Keep this Studio-only preview inside the real alert renderer.
    if(typeof ALERTS==="undefined"||!Array.isArray(ALERTS))return;
    alertItem={_test:true,_showcase:true,event:alertEvent,severity:alertSeverity,headline:"Sample Weather Alert — Studio Preview",description:"This is fictional, offline showcase data for "+city+". Dash-Go can surface important weather conditions without making the dashboard feel noisy.",instruction:"No action is needed. This sample clears when the Studio tour ends.",ends:new Date(Date.now()+90*60000)};
    ALERTS.unshift(alertItem);
    if(typeof renderAlerts==="function")renderAlerts();
    if(typeof showAlertPopup==="function")showAlertPopup(alertItem);
  }
  function removeAlertPreview(){
    if(!alertItem)return;
    if(typeof ALERTS!=="undefined"&&Array.isArray(ALERTS))ALERTS=ALERTS.filter(item=>item!==alertItem&&!item._showcase);
    alertItem=null;
    if(typeof renderAlerts==="function")renderAlerts();
    const title=document.getElementById("poptitle");
    if(title&&String(title.textContent||"").includes("Sample Weather Alert"))call("closeScrim");
  }
  function removeCard(){if(card){card.remove();card=null;}}
  async function cleanTourPresentation(closeSurface){
    removeCard();removeAlertPreview();hideListsPreview();
    if(closeSurface)await clearPrimarySurface();
  }
  async function hubPost(path,body){
    if(!hubURL||!token)throw new Error("Studio Home is unavailable.");
    const response=await fetch(hubURL+path+"?token="+encodeURIComponent(token),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});
    if(!response.ok)throw new Error(await response.text()||"Studio action could not finish.");
    return response.json();
  }
  async function returnHome(){
    await cleanTourPresentation(true);
    const result=await hubPost("/api/return-home",{});
    window.location.assign(result.hubURL);
  }
  async function restart(){
    await cleanTourPresentation(true);
    const result=await hubPost("/api/restart-tour",{location:locationID});
    window.location.assign(result.dashboardURL);
  }
  async function finish(){
    active=false;await cleanTourPresentation(true);
    const next=new URL(window.location.href);next.searchParams.delete("showcaseTour");
    window.history.replaceState({},document.title,next.pathname+(next.search||"")+next.hash);
  }
  function locationModal(){
    const prior=document.getElementById("showcase-location-lock");if(prior)prior.remove();
    const modal=document.createElement("section");modal.id="showcase-location-lock";modal.setAttribute("role","dialog");modal.setAttribute("aria-modal","true");
    modal.innerHTML="<div class='showcase-lock-card'><p class='showcase-kicker'>SHOWCASE STUDIO</p><h2>Ah ah ah, you didn’t say the magic word.</h2><p>This Studio session stays in <strong>"+escapeHTML(city)+"</strong> so its calendar, weather, maps, and sample household data remain consistent.</p><div class='showcase-actions'><button data-keep>Keep Exploring</button><button data-city>Choose Another City</button></div></div>";
    document.body.appendChild(modal);
    modal.querySelector("[data-keep]").onclick=()=>modal.remove();
    modal.querySelector("[data-city]").onclick=()=>returnHome().catch(error=>console.warn(error));
    modal.querySelector("[data-keep]").focus();
  }
  function escapeHTML(value){const box=document.createElement("div");box.textContent=String(value||"");return box.innerHTML;}
  window.showcaseStudioLocationLocked=locationModal;
  async function openOnly(open,target){
    await clearPrimarySurface();
    await Promise.resolve(open());
    for(let attempt=0;attempt<20;attempt++){
      if(document.querySelector(target))return;
      await wait(45);
    }
    console.warn("Showcase tour target did not become visible",target);
  }
  const steps=[
    {title:"Welcome to Dash-Go",text:"This is the real Dash-Go dashboard with safe, disposable data for "+city+".",open:async()=>{await clearPrimarySurface();await showListsPreview();}},
    {title:"Lists dock",text:"This scrolling strip keeps grocery and household tasks visible at a glance. It is off by default and can be enabled in Dashboard Control.",open:async()=>{await clearPrimarySurface();await showListsPreview();}},
    {title:"Weather awareness",text:"Dash-Go can surface important weather conditions. This is a clearly labeled sample alert, not live weather data.",open:async()=>{await clearPrimarySurface();await showListsPreview();addAlertPreview();}},
    {title:"Apps for the household",text:"Dash-Go keeps focused household tools one tap away.",open:()=>openOnly(()=>call("openAppLauncher"),"#applauncher.show")},
    {title:"Grocery",text:"This is the real local Grocery list, seeded for this Studio session.",open:()=>openOnly(()=>call("openListsApp","grocery"),"#listsapp.show")},
    {title:"Chore Wheel",text:"Try a fair rotation built around the fictional household.",open:()=>openOnly(()=>call("openChoreWheel"),"#chorewheel.show")},
    {title:"Routines",text:"Routines coordinate recurring household moments without leaving the dashboard.",open:()=>openOnly(()=>call("openRoutines"),"#routines.show")},
    {title:"Family Message Board",text:"Household notes and private inboxes stay together.",open:()=>openOnly(()=>call("openFamilyBoard"),"#familyboard.show")},
    {title:"Dashboard Control",text:"Explore themes and display choices. You can search locations, but Studio keeps this demo city locked so the scenario stays consistent.",open:()=>openOnly(()=>call("openDashboardControl"),"#ctrl.show")},
    {title:"Explore freely",text:"The tour is complete. The Lists preview and sample alert disappear now; any remaining changes last only for this Studio session.",open:async()=>{removeAlertPreview();hideListsPreview();await clearPrimarySurface();}}
  ];
  function render(){
    if(!active)return;removeCard();
    const step=steps[index];
    Promise.resolve(step.open()).catch(error=>console.warn("Showcase tour target could not open",error)).finally(()=>{
      if(!active)return;
      card=document.createElement("aside");card.id="showcase-tour";card.setAttribute("role","dialog");card.setAttribute("aria-live","polite");
      card.innerHTML="<button class='showcase-dismiss' data-dismiss aria-label='Close tour'>×</button><p class='showcase-kicker'>SHOWCASE TOUR "+(index+1)+" / "+steps.length+"</p><h2>"+escapeHTML(step.title)+"</h2><p>"+escapeHTML(step.text)+"</p><div class='showcase-actions'><button data-back>Back</button><button data-next>"+(index===steps.length-1?"Explore Freely":"Next")+"</button><button data-restart>Restart Tour</button><button data-skip>Skip Tour</button></div>";
      document.body.appendChild(card);
      card.querySelector("[data-back]").disabled=index===0;
      card.querySelector("[data-back]").onclick=()=>{index=Math.max(0,index-1);render();};
      card.querySelector("[data-next]").onclick=()=>{if(index===steps.length-1){finish().catch(error=>console.warn(error));return;}index++;render();};
      card.querySelector("[data-restart]").onclick=()=>restart().catch(error=>console.warn(error));
      card.querySelector("[data-skip]").onclick=()=>finish().catch(error=>console.warn(error));
      card.querySelector("[data-dismiss]").onclick=()=>finish().catch(error=>console.warn(error));
    });
  }
  window.addEventListener("pagehide",()=>{if(active){removeAlertPreview();hideListsPreview();}});
  document.addEventListener("keydown",event=>{if(event.key==="Escape"&&active&&card){event.preventDefault();finish().catch(error=>console.warn(error));}});
  if(active)window.setTimeout(render,650);
})();''')

    view = app / "ui/js/showcase-view.js"
    write(view, r'''(function(){
  const query=new URLSearchParams(window.location.search);
  if(query.get("showcaseStudio")!=="1")return;
  const hubURL=query.get("showcaseHub")||"",token=query.get("showcaseToken")||"";
  if(!hubURL||!token)return;
  const presets=[
    ["landscape","fit","Fit Display","Fit display"],
    ["landscape","wall-landscape","Wall Display","1920 × 1080"],
    ["landscape","laptop","Common Laptop","1366 × 768"],
    ["landscape","wide-tablet","16:10 Display","1280 × 800"],
    ["portrait","portrait-wall","Portrait Wall","1080 × 1920"],
    ["portrait","portrait-tablet","Portrait Tablet","800 × 1280"],
    ["portrait","portrait-four-three","4:3 Portrait","768 × 1024"],
  ];
  const root=document.createElement("aside");root.id="showcase-view";
  root.innerHTML="<button class='showcase-view-toggle' aria-expanded='false'>Showcase View <span>▾</span></button><section class='showcase-view-panel' hidden><div class='showcase-view-head'><strong>Showcase View</strong><button data-clean>Clean View</button></div><div data-groups></div><p class='showcase-view-status'>Fit Display · Fit display</p></section>";
  document.body.appendChild(root);
  const panel=root.querySelector(".showcase-view-panel"),toggle=root.querySelector(".showcase-view-toggle"),groups=root.querySelector("[data-groups]"),status=root.querySelector(".showcase-view-status");
  const restore=document.createElement("button");restore.id="showcase-view-restore";restore.textContent="View ▸";restore.hidden=true;document.body.appendChild(restore);
  function group(name){const box=document.createElement("section");box.className="showcase-view-group";box.innerHTML="<p>"+name+"</p><div class='showcase-view-grid'></div>";groups.appendChild(box);return box.querySelector(".showcase-view-grid");}
  const landscape=group("Landscape"),portrait=group("Portrait");
  async function pick(id,label){
    status.textContent="Switching to "+label+"…";
    const response=await fetch(hubURL+"/api/viewport?token="+encodeURIComponent(token),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({preset:id})});
    const result=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(result.error||"Viewport could not change.");
    status.textContent=result.fit?"Fit Display · "+result.presentation:result.width+" × "+result.height+" · "+result.orientation+" · "+result.presentation;
    panel.hidden=true;toggle.setAttribute("aria-expanded","false");
  }
  presets.forEach(([orientation,id,label,size])=>{const button=document.createElement("button");button.type="button";button.innerHTML="<b>"+label+"</b><small>"+size+"</small>";button.onclick=()=>pick(id,label).catch(error=>{status.textContent=error.message;});(orientation==="portrait"?portrait:landscape).appendChild(button);});
  toggle.onclick=()=>{const open=panel.hidden;panel.hidden=!open;toggle.setAttribute("aria-expanded",String(open));};
  root.querySelector("[data-clean]").onclick=()=>{root.hidden=true;restore.hidden=false;document.documentElement.classList.add("showcase-clean-view");};
  restore.onclick=()=>{root.hidden=false;restore.hidden=true;document.documentElement.classList.remove("showcase-clean-view");};
})();''')

    css = app / "ui/css/dashboard/showcase-studio.css"
    write(css, r'''html.showcase-clean-view #showcase-tour{display:none}#showcase-tour{position:fixed;right:22px;bottom:22px;z-index:2147483000;width:min(470px,calc(100vw - 44px));padding:22px;border:1px solid #6eb7e8;border-radius:18px;background:#132434;color:#f6fbff;box-shadow:0 18px 55px #000a;font:17px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}#showcase-tour h2{margin:.4rem 0;font-size:1.35rem;line-height:1.25;letter-spacing:-.01em}#showcase-tour p{margin:.4rem 0 1.1rem;color:#e6f1fa}.showcase-kicker{margin:0;color:#a6d6ff;font-size:.78rem;font-weight:800;letter-spacing:.14em}.showcase-actions{display:flex;gap:10px;flex-wrap:wrap}.showcase-actions button,.showcase-dismiss,#showcase-view button,#showcase-view-restore{border:0;border-radius:10px;padding:10px 14px;background:#eaf5fd;color:#102333;font:inherit;font-weight:750;cursor:pointer}.showcase-actions button[data-next]{background:#58b4f5;color:#082033;font-weight:800}.showcase-actions button[data-restart],.showcase-actions button[data-skip]{background:#1d3347;color:#d3e5f3}.showcase-actions button:focus-visible,.showcase-dismiss:focus-visible{outline:3px solid #a6d6ff;outline-offset:2px}.showcase-actions button:disabled{opacity:.5;cursor:default}.showcase-dismiss{position:absolute;right:10px;top:10px;padding:2px 8px;font-size:1.35rem}.showcase-lock-card{width:min(520px,calc(100vw - 36px));padding:26px;border-radius:18px;background:#132434;color:#f6fbff;box-shadow:0 18px 55px #000a;font:16px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}#showcase-location-lock{position:fixed;inset:0;z-index:2147483001;display:grid;place-items:center;padding:18px;background:#0009}#showcase-location-lock h2{margin:.4rem 0}#showcase-view{position:fixed;left:12px;top:12px;z-index:2147482999;font:14px/1.3 system-ui,-apple-system,"Segoe UI",sans-serif}.showcase-view-toggle{background:#132434!important;color:#f6fbff!important;box-shadow:0 8px 26px #0008}.showcase-view-panel{margin-top:7px;width:min(360px,calc(100vw - 24px));padding:14px;border:1px solid #6eb7e8;border-radius:14px;background:#132434;color:#f6fbff;box-shadow:0 18px 55px #000a}.showcase-view-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.showcase-view-head button{padding:6px 9px}.showcase-view-group>p{margin:14px 0 6px;color:#9ed6ff;font-size:.72rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase}.showcase-view-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.showcase-view-grid button{min-height:54px;text-align:left}.showcase-view-grid b,.showcase-view-grid small{display:block}.showcase-view-grid small{opacity:.7;margin-top:2px}.showcase-view-status{margin:12px 0 0;color:#c9d9e7;font-size:.82rem}#showcase-view-restore{position:fixed;left:0;top:14px;z-index:2147482999;border-radius:0 10px 10px 0;background:#132434;color:#f6fbff;box-shadow:0 8px 26px #0008}@media (max-width:720px),(max-aspect-ratio:3/4){#showcase-tour{left:10px;right:10px;bottom:10px;width:auto;max-height:48vh;overflow:auto;padding:16px;font-size:15px}#showcase-view{left:8px;top:8px}.showcase-view-panel{width:min(320px,calc(100vw - 16px))}.showcase-view-grid{grid-template-columns:1fr}.showcase-actions button{padding:8px 10px}}
''')

    manifest = app / "ui/js/bundle.manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    files = data["bundles"]["app"]
    for name in ("showcase-tour.js", "showcase-view.js"):
        if name not in files:
            files.append(name)
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    css_manifest = app / "ui/css/bundle.manifest.json"
    css_data = json.loads(css_manifest.read_text(encoding="utf-8"))
    css_files = css_data["bundles"]["dashboard"]
    if "dashboard/showcase-studio.css" not in css_files:
        css_files.append("dashboard/showcase-studio.css")
    css_manifest.write_text(json.dumps(css_data, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, type=Path)
    args = parser.parse_args()
    app = args.app.resolve()
    if not (app / "cmd/dashboard-control-server/main.go").is_file():
        raise PatchError(f"not a Dash-Go app root: {app}")
    apply(app)
    print(f"PATCHED: {app}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PatchError as exc:
        raise SystemExit(f"PATCH ERROR: {exc}")
