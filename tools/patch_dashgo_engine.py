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
import shutil
import subprocess
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
    if path.suffix != ".go":
        return
    gofmt = shutil.which("gofmt")
    if not gofmt:
        raise PatchError("gofmt is required to format generated Showcase Go sources")
    result = subprocess.run(
        [gofmt, "-w", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PatchError(f"{path}: gofmt failed{': ' + detail if detail else ''}")


def append_once(path: Path, marker: str, addition: str) -> None:
    source = path.read_text(encoding="utf-8")
    count = source.count(marker)
    if count != 1:
        raise PatchError(f"{path}: expected exactly one append anchor, found {count}")
    path.write_text(source.replace(marker, marker + addition, 1), encoding="utf-8")


def apply(app: Path) -> None:
    cmd = app / "cmd/dashboard-control-server"
    platform = app / "internal/platform"
    fileio = app / "internal/fileio/fileio.go"
    replace_once(
        fileio,
        '\t"errors"\n\t"os"\n\t"path/filepath"\n',
        '\t"errors"\n\t"os"\n\t"path/filepath"\n\t"runtime"\n',
    )
    replace_once(
        fileio,
        '''func syncDirectory(dir string) error {
\thandle, err := os.Open(dir)
''',
        '''func syncDirectory(dir string) error {
\t// Showcase Windows directory-sync contract: Windows has no POSIX-style directory fsync. The file itself was already
\t// synced and atomically renamed before this best-effort durability step.
\tif runtime.GOOS == "windows" {
\t\treturn nil
\t}
\thandle, err := os.Open(dir)
''',
    )

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

    public_post = cmd / "http_routes_public_post.go"
    replace_once(
        public_post,
        '''	if path == "/api/calendar/event/create" || path == "/api/calendar/event/update" || path == "/api/calendar/event/occurrence/update" || path == "/api/calendar/event/series/update" || path == "/api/calendar/event/skip-occurrence" {
''',
        '''	// Studio has no user PIN or remote provider. Permit deletion only for the
	// exact disposable session collections; every normal Dashboard delete still
	// follows the authenticated route below.
	if path == "/api/calendar/event/delete" && a.showcaseMode() && a.showcaseWritableCalendarSource(jsonutil.BodyString(body, "calUrl")) {
		result, err := a.handleCalendarWritebackMutation(path, body)
		if err != nil {
			code := http.StatusBadRequest
			if strings.Contains(err.Error(), "already running") {
				code = http.StatusConflict
			}
			a.err(w, err.Error(), code)
		} else {
			a.json(w, result)
		}
		return true
	}
	if path == "/api/calendar/event/create" || path == "/api/calendar/event/update" || path == "/api/calendar/event/occurrence/update" || path == "/api/calendar/event/series/update" || path == "/api/calendar/event/skip-occurrence" {
''',
    )

    calendar_writeback = cmd / "calendar_writeback.go"
    replace_once(
        calendar_writeback,
        """func (a *app) calendarWritebackDeleteAllowed(source string) bool {
\tif !a.calendarWritebackService().SourceWritable(source) || !a.lockConfigAvailable() {
\t\treturn false
\t}
\treturn a.lockConfig()[\"enabled\"] == true
}
""",
        """func (a *app) calendarWritebackDeleteAllowed(source string) bool {
\tif a.showcaseMode() {
\t\t// Studio's three user-managed calendars live only in the disposable
\t\t// scenario home. Deletion is safe there and resets at the next launch.
\t\treturn a.showcaseWritableCalendarSource(source)
\t}
\tif !a.calendarWritebackService().SourceWritable(source) || !a.lockConfigAvailable() {
\t\treturn false
\t}
\treturn a.lockConfig()[\"enabled\"] == true
}
""",
    )
    replace_once(
        calendar_writeback,
        """\tmessage := \"Saved locally; remote sync queued.\"
\tif refreshErr != nil {
\t\tmessage = \"Saved locally; remote sync queued. Dashboard refresh will retry automatically.\"
\t}
\taction := map[string]string{\"created\": \"Add calendar event\", \"updated\": \"Manage calendar event\", \"occurrence-updated\": \"Edit calendar occurrence\", \"series-updated\": \"Edit recurring series\", \"deleted\": \"Delete calendar event\", \"skipped\": \"Skip calendar occurrence\"}[result.Action]
\tif persistErr := a.recordCalendarWritebackMutation(result.Source, result.Pair, result.Collection, result.FinalDelete); persistErr != nil {
\t\tmessage = \"Saved locally, but Dash-Go could not update its durable private-calendar sync authorization. Remote sync is paused for safety; review the calendar before retrying.\"
\t\tservice.Record(result.Source, \"attention\", message)
\t\ta.recordAction(\"calendars\", action, \"warning\", message, map[string]any{\"source\": result.Source, \"uid\": result.UID})
\t\treturn map[string]any{\"ok\": true, \"source\": result.Source, \"uid\": result.UID, \"action\": result.Action, \"sync\": \"attention\", \"warning\": message}, nil
\t}
\tservice.Record(result.Source, \"saved\", message)
\ta.queueCalendarWritebackSync(result.Source, result.Pair, true)
\tseverity := \"success\"
\tif refreshErr != nil {
\t\tseverity = \"warning\"
\t}
\ta.recordAction(\"calendars\", action, severity, message, map[string]any{\"source\": result.Source, \"uid\": result.UID})
\tresponse := map[string]any{\"ok\": true, \"source\": result.Source, \"uid\": result.UID, \"action\": result.Action, \"sync\": \"queued\"}
\tif refreshErr != nil {
\t\tresponse[\"warning\"] = message
\t}
\treturn response, nil
""",
        """\taction := map[string]string{\"created\": \"Add calendar event\", \"updated\": \"Manage calendar event\", \"occurrence-updated\": \"Edit calendar occurrence\", \"series-updated\": \"Edit recurring series\", \"deleted\": \"Delete calendar event\", \"skipped\": \"Skip calendar occurrence\"}[result.Action]
\tif a.showcaseMode() && a.showcaseWritableCalendarSource(result.Source) {
\t\tmessage := \"Saved in this Studio session. Changes reset when Studio closes.\"
\t\tseverity := \"success\"
\t\tif refreshErr != nil {
\t\t\tmessage = \"Saved in this Studio session. Dashboard refresh will retry automatically; changes still reset when Studio closes.\"
\t\t\tseverity = \"warning\"
\t\t}
\t\tservice.Record(result.Source, \"saved\", message)
\t\ta.recordAction(\"calendars\", action, severity, message, map[string]any{\"source\": result.Source, \"uid\": result.UID, \"showcase\": true})
\t\tresponse := map[string]any{\"ok\": true, \"source\": result.Source, \"uid\": result.UID, \"action\": result.Action, \"sync\": \"session\"}
\t\tif refreshErr != nil {
\t\t\tresponse[\"warning\"] = message
\t\t}
\t\treturn response, nil
\t}
\tmessage := \"Saved locally; remote sync queued.\"
\tif refreshErr != nil {
\t\tmessage = \"Saved locally; remote sync queued. Dashboard refresh will retry automatically.\"
\t}
\tif persistErr := a.recordCalendarWritebackMutation(result.Source, result.Pair, result.Collection, result.FinalDelete); persistErr != nil {
\t\tmessage = \"Saved locally, but Dash-Go could not update its durable private-calendar sync authorization. Remote sync is paused for safety; review the calendar before retrying.\"
\t\tservice.Record(result.Source, \"attention\", message)
\t\ta.recordAction(\"calendars\", action, \"warning\", message, map[string]any{\"source\": result.Source, \"uid\": result.UID})
\t\treturn map[string]any{\"ok\": true, \"source\": result.Source, \"uid\": result.UID, \"action\": result.Action, \"sync\": \"attention\", \"warning\": message}, nil
\t}
\tservice.Record(result.Source, \"saved\", message)
\ta.queueCalendarWritebackSync(result.Source, result.Pair, true)
\tseverity := \"success\"
\tif refreshErr != nil {
\t\tseverity = \"warning\"
\t}
\ta.recordAction(\"calendars\", action, severity, message, map[string]any{\"source\": result.Source, \"uid\": result.UID})
\tresponse := map[string]any{\"ok\": true, \"source\": result.Source, \"uid\": result.UID, \"action\": result.Action, \"sync\": \"queued\"}
\tif refreshErr != nil {
\t\tresponse[\"warning\"] = message
\t}
\treturn response, nil
""",
    )

    maps_facade = cmd / "maps_facade.go"
    replace_once(
        maps_facade,
        """func (a *app) eventMapLookup(query string) map[string]any { return a.mapsService().EventLookup(query) }
""",
        """func (a *app) eventMapLookup(query string) map[string]any {
\tif a.showcaseMode() {
\t\treturn a.showcaseEventMapLookup(query)
\t}
\treturn a.mapsService().EventLookup(query)
}
""",
    )
    replace_once(
        maps_facade,
        """func (a *app) geocode(query string) map[string]any        { return a.mapsService().Geocode(query) }
""",
        """func (a *app) geocode(query string) map[string]any { return a.mapsService().Geocode(query) }
""",
    )

    calendar_writeback_js = app / "ui/js/calendar-writeback.js"
    replace_once(
        calendar_writeback_js,
        """    root.appendChild(el(\"div\",\"calendar-writeback-note\",\"Dashboard edits save locally first. Remote calendar sync follows.\"));
""",
        """    root.appendChild(el(\"div\",\"calendar-writeback-note\",window.DASHGO_SHOWCASE?\"Studio edits are saved only for this session and reset when Studio closes.\":\"Dashboard edits save locally first. Remote calendar sync follows.\"));
""",
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

// showcaseWritableCalendarSource defines the only calendars whose event editor
// may mutate data in Studio. They are private per-session vdir collections,
// not imported providers or generated Dash-Go-owned feeds.
func (a *app) showcaseWritableCalendarSource(source string) bool {
	if !a.showcaseMode() {
		return false
	}
	switch strings.TrimSpace(source) {
	case "calendars/family.green.ics", "calendars/home.amber.ics", "calendars/plans.violet.ics":
		return true
	default:
		return false
	}
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
		"calendars/calendars.json", "calendars/family.green.ics", "calendars/school.blue.ics", "calendars/home.amber.ics", "calendars/plans.violet.ics", "calendars/chore-wheel.ics", "calendars/routines.ics", "calendars/maintenance.ics", "cache/events.cache.json":
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

// showcaseEventMapLookup provides deterministic coordinates for Studio's
// curated public venue catalog. The image route can still use Dash-Go's normal
// cached/fallback renderer, but the lookup itself never needs a network
// geocoder and never searches the operator's personal locations.
func (a *app) showcaseEventMapLookup(query string) map[string]any {
	needle := strings.ToLower(strings.TrimSpace(query))
	if needle == "" {
		return map[string]any{"ok": false, "error": "location required"}
	}
	type venue struct {
		Needle, Label string
		Lat, Lon      float64
	}
	venues := []venue{
		{"chelsea market", "Chelsea Market, New York, NY", 40.7424, -74.0061},
		{"new york public library", "New York Public Library, New York, NY", 40.7536, -73.9822},
		{"riverside park", "Riverside Park, New York, NY", 40.7870, -73.9773},
		{"american museum of natural history", "American Museum of Natural History, New York, NY", 40.7813, -73.9735},
		{"food bank for new york city", "Food Bank For New York City, New York, NY", 40.7051, -74.0116},
		{"whole foods market", "Whole Foods Market, Chicago, IL", 41.8676, -87.6408},
		{"harold washington library", "Harold Washington Library Center, Chicago, IL", 41.8761, -87.6285},
		{"millennium park", "Millennium Park, Chicago, IL", 41.8826, -87.6226},
		{"chicago children's museum", "Chicago Children's Museum, Chicago, IL", 41.8917, -87.6089},
		{"greater chicago food depository", "Greater Chicago Food Depository, Chicago, IL", 41.8147, -87.7282},
		{"ui health dental", "UI Health Dental Center, Chicago, IL", 41.8692, -87.6693},
		{"king soopers", "King Soopers, Denver, CO", 39.7467, -104.9969},
		{"denver central library", "Denver Central Library, Denver, CO", 39.7375, -104.9896},
		{"denver museum of nature", "Denver Museum of Nature & Science, Denver, CO", 39.7475, -104.9420},
		{"food bank of the rockies", "Food Bank of the Rockies, Denver, CO", 39.7790, -104.8620},
		{"grand central market", "Grand Central Market, Los Angeles, CA", 34.0506, -118.2489},
		{"los angeles central library", "Los Angeles Central Library, Los Angeles, CA", 34.0505, -118.2551},
		{"california science center", "California Science Center, Los Angeles, CA", 34.0158, -118.2866},
		{"los angeles regional food bank", "Los Angeles Regional Food Bank, Los Angeles, CA", 34.0074, -118.2290},
		{"new sagaya city market", "New Sagaya City Market, Anchorage, AK", 61.2096, -149.9006},
		{"z. j. loussac library", "Z. J. Loussac Library, Anchorage, AK", 61.1879, -149.8138},
		{"anchorage museum", "Anchorage Museum, Anchorage, AK", 61.2181, -149.8858},
		{"food bank of alaska", "Food Bank of Alaska, Anchorage, AK", 61.1951, -149.8402},
		{"foodland farms", "Foodland Farms Ala Moana, Honolulu, HI", 21.2911, -157.8447},
		{"hawaii state library", "Hawaii State Library, Honolulu, HI", 21.3076, -157.8587},
		{"honolulu museum of art", "Honolulu Museum of Art, Honolulu, HI", 21.3028, -157.8486},
		{"hawaii foodbank", "Hawaii Foodbank, Honolulu, HI", 21.3330, -157.9014},
	}
	for _, venue := range venues {
		if strings.Contains(needle, venue.Needle) {
			return map[string]any{"ok": true, "lat": venue.Lat, "lon": venue.Lon, "label": venue.Label, "queryUsed": query, "geocoder": "showcase-venue-catalog", "cached": true, "defaultZoom": 15, "defaultStyle": "standard"}
		}
	}
	for _, fallback := range []venue{
		{"new york", "New York, NY — Studio Preview", 40.7128, -74.0060},
		{"chicago", "Chicago, IL — Studio Preview", 41.8781, -87.6298},
		{"denver", "Denver, CO — Studio Preview", 39.7392, -104.9903},
		{"los angeles", "Los Angeles, CA — Studio Preview", 34.0522, -118.2437},
		{"anchorage", "Anchorage, AK — Studio Preview", 61.2181, -149.9003},
		{"honolulu", "Honolulu, HI — Studio Preview", 21.3069, -157.8583},
	} {
		if strings.Contains(needle, fallback.Needle) {
			return map[string]any{"ok": true, "lat": fallback.Lat, "lon": fallback.Lon, "label": fallback.Label, "queryUsed": query, "geocoder": "showcase-city-catalog", "cached": true, "defaultZoom": 13, "defaultStyle": "standard"}
		}
	}
	return map[string]any{"ok": false, "error": "This Studio location is not in the curated public venue catalog.", "queryUsed": query}
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

import (
	"path/filepath"
	"testing"
)

func TestShowcaseStaticRelativePathUsesURLSeparators(t *testing.T) {
	cases := map[string]string{
		"/config/config.local.js":            "config/config.local.js",
		"config/../calendars/calendars.json": "calendars/calendars.json",
		"//calendars/family.green.ics":       "calendars/family.green.ics",
	}
	for requestPath, want := range cases {
		if got := showcaseStaticRelativePath(requestPath); got != want {
			t.Fatalf("showcaseStaticRelativePath(%q) = %q, want %q", requestPath, got, want)
		}
	}
}

func TestShowcaseStaticDataPathAllowsEverySeededCalendar(t *testing.T) {
	root := t.TempDir()
	t.Setenv("DASHGO_SHOWCASE", "1")
	t.Setenv("DASHGO_SHOWCASE_DATA_ROOT", root)
	a := &app{dash: filepath.Join(root, "assets")}

	for _, rel := range []string{
		"calendars/calendars.json",
		"calendars/family.green.ics",
		"calendars/school.blue.ics",
		"calendars/home.amber.ics",
		"calendars/plans.violet.ics",
		"calendars/chore-wheel.ics",
		"calendars/routines.ics",
		"calendars/maintenance.ics",
	} {
		got, ok := a.showcaseStaticDataPath(rel)
		want := filepath.Join(root, filepath.FromSlash(rel))
		if !ok || got != want {
			t.Fatalf("showcaseStaticDataPath(%q) = %q, %v; want %q, true", rel, got, ok, want)
		}
	}

	if _, ok := a.showcaseStaticDataPath("calendars/showcase-studio.ics"); ok {
		t.Fatal("retired one-calendar fixture path was unexpectedly allowed")
	}
	if _, ok := a.showcaseStaticDataPath("calendars/unknown.ics"); ok {
		t.Fatal("unknown calendar path was unexpectedly allowed")
	}
}

func TestShowcaseOnlyAllowsItsThreeSessionWritableCalendars(t *testing.T) {
	t.Setenv("DASHGO_SHOWCASE", "1")
	a := &app{}
	for _, source := range []string{"calendars/family.green.ics", "calendars/home.amber.ics", "calendars/plans.violet.ics"} {
		if !a.showcaseWritableCalendarSource(source) {
			t.Fatalf("expected Studio session-write permission for %s", source)
		}
	}
	for _, source := range []string{"calendars/school.blue.ics", "calendars/chore-wheel.ics", "calendars/routines.ics", "calendars/maintenance.ics", "calendars/unknown.ics"} {
		if a.showcaseWritableCalendarSource(source) {
			t.Fatalf("unexpected Studio session-write permission for %s", source)
		}
	}
}

func TestShowcaseSessionDeleteIsLimitedToWritableCalendars(t *testing.T) {
	t.Setenv("DASHGO_SHOWCASE", "1")
	a := &app{}
	for _, source := range []string{"calendars/family.green.ics", "calendars/home.amber.ics", "calendars/plans.violet.ics"} {
		if !a.calendarWritebackDeleteAllowed(source) {
			t.Fatalf("expected Studio session delete permission for %s", source)
		}
	}
	for _, source := range []string{"calendars/school.blue.ics", "calendars/chore-wheel.ics", "calendars/unknown.ics"} {
		if a.calendarWritebackDeleteAllowed(source) {
			t.Fatalf("unexpected Studio session delete permission for %s", source)
		}
	}
}

func TestShowcaseEventMapLookupUsesCuratedVenueCatalog(t *testing.T) {
	t.Setenv("DASHGO_SHOWCASE", "1")
	a := &app{}
	lookup := a.showcaseEventMapLookup("Whole Foods Market, 1101 S Canal St, Chicago, IL 60607")
	if lookup["ok"] != true || lookup["geocoder"] != "showcase-venue-catalog" || lookup["lat"] == nil || lookup["lon"] == nil {
		t.Fatalf("unexpected Studio map lookup: %#v", lookup)
	}
	if fallback := a.showcaseEventMapLookup("Unknown private address"); fallback["ok"] == true {
		t.Fatalf("unknown non-catalog address unexpectedly resolved: %#v", fallback)
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
    cmd = app / "cmd/dashboard-control-server"
    public_post = cmd / "http_routes_public_post.go"
    calendar_writeback_js = app / "ui/js/calendar-writeback.js"
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

    # r6: the original r5 overlay seeded writable session calendars but the
    # stage-to-live path rebase is handled by Studio itself. These additions
    # complete the actual Studio interaction surface: local-only move and
    # series delete operations, truthful Calendar Manager labels, and larger
    # presentation controls.
    replace_once(
        asset_order_test,
        "\t\t\t\"ui/js/showcase-view.js\",\n",
        "\t\t\t\"ui/js/showcase-view.js\",\n\t\t\t\"ui/js/showcase-calendar-sandbox.js\",\n",
    )
    write(cmd / "showcase_calendar_sandbox.go", r'''
package main

import (
    "errors"
    "fmt"
    "os"
    "path/filepath"
    "strings"

    "github.com/DashDashGoApp/Dash-Go/app/internal/calendar/icalwrite"
    writebackpkg "github.com/DashDashGoApp/Dash-Go/app/internal/calendar/writeback"
    "github.com/DashDashGoApp/Dash-Go/app/internal/fileio"
    "github.com/DashDashGoApp/Dash-Go/app/internal/jsonutil"
)

const showcaseSessionCalendarMessage = "Saved in this Studio session. Changes reset when Studio closes."

func showcaseCalendarUIDValid(uid string) bool {
    uid = strings.TrimSpace(uid)
    if uid == "" || len(uid) > 180 {
        return false
    }
    for _, r := range uid {
        if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || strings.ContainsRune("-_.@", r) {
            continue
        }
        return false
    }
    return true
}

// showcaseFindCalendarItem reads only direct regular vdir object files. The
// UID check is strict, preventing a crafted request from moving/deleting an
// aggregate or another collection's event.
func showcaseFindCalendarItem(collection, uid string) (string, []byte, error) {
    entries, err := os.ReadDir(collection)
    if err != nil {
        return "", nil, err
    }
    var foundPath string
    var foundBody []byte
    for _, entry := range entries {
        if entry.IsDir() || strings.ToLower(filepath.Ext(entry.Name())) != ".ics" {
            continue
        }
        info, err := entry.Info()
        if err != nil {
            return "", nil, err
        }
        if !info.Mode().IsRegular() {
            continue
        }
        if info.Size() > 1024*1024 {
            return "", nil, fmt.Errorf("calendar item %q is unexpectedly large", entry.Name())
        }
        path := filepath.Join(collection, entry.Name())
        body, err := os.ReadFile(path)
        if err != nil {
            return "", nil, err
        }
        if !icalwrite.HasUID(string(body), uid) {
            continue
        }
        if foundPath != "" {
            return "", nil, errors.New("calendar contains more than one item for this event")
        }
        foundPath, foundBody = path, body
    }
    if foundPath == "" {
        return "", nil, os.ErrNotExist
    }
    return foundPath, foundBody, nil
}

func (a *app) showcaseCalendarMutationResponse(service *writebackpkg.Service, sources []string, uid, action, label string, mutate func() error) (map[string]any, error) {
    warning := ""
    err := service.WithSyncLock(func() error {
        if err := mutate(); err != nil {
            return err
        }
        for _, source := range sources {
            calendar, err := service.Resolve(source)
            if err != nil {
                return err
            }
            if err := service.MergeCollection(source, calendar.Collection); err != nil {
                warning = "Saved in this Studio session, but the calendar display will refresh after the next dashboard refresh. Changes still reset when Studio closes."
                return nil
            }
        }
        if _, err := a.refreshEventCache(true, 90, 365); err != nil {
            warning = "Saved in this Studio session, but the dashboard display will refresh after the next dashboard refresh. Changes still reset when Studio closes."
        }
        return nil
    })
    if err != nil {
        if errors.Is(err, writebackpkg.ErrBusy) {
            return nil, errors.New("calendar sync is already running; try again shortly")
        }
        return nil, err
    }
    message := showcaseSessionCalendarMessage
    severity := "success"
    if warning != "" {
        message, severity = warning, "warning"
    }
    for _, source := range sources {
        service.Record(source, "saved", message)
    }
    a.recordAction("calendars", label, severity, message, map[string]any{"source": sources[0], "uid": uid, "showcase": true})
    response := map[string]any{"ok": true, "source": sources[len(sources)-1], "uid": uid, "action": action, "sync": "session"}
    if warning != "" {
        response["warning"] = warning
    }
    return response, nil
}

func (a *app) showcaseCalendarMove(body map[string]any) (map[string]any, error) {
    if !a.showcaseMode() {
        return nil, errors.New("moving calendar events is available only in Showcase Studio")
    }
    source := strings.TrimSpace(jsonutil.BodyString(body, "calUrl"))
    target := strings.TrimSpace(jsonutil.BodyString(body, "targetCalUrl"))
    uid := strings.TrimSpace(jsonutil.BodyString(body, "uid"))
    if !a.showcaseWritableCalendarSource(source) || !a.showcaseWritableCalendarSource(target) || source == target {
        return nil, errors.New("choose two different Studio session calendars")
    }
    if !showcaseCalendarUIDValid(uid) {
        return nil, errors.New("calendar event required")
    }
    service := a.calendarWritebackService()
    return a.showcaseCalendarMutationResponse(service, []string{source, target}, uid, "moved", "Move Studio calendar event", func() error {
        if err := a.calendarWritebackSourceBlocked(source); err != nil {
            return err
        }
        if err := a.calendarWritebackSourceBlocked(target); err != nil {
            return err
        }
        sourceCalendar, err := service.Resolve(source)
        if err != nil {
            return err
        }
        targetCalendar, err := service.Resolve(target)
        if err != nil {
            return err
        }
        sourcePath, item, err := showcaseFindCalendarItem(sourceCalendar.Collection, uid)
        if err != nil {
            if errors.Is(err, os.ErrNotExist) {
                return errors.New("calendar event is no longer available to move")
            }
            return err
        }
        text := string(item)
        if icalwrite.IsRecurring(text) || icalwrite.HasRecurrenceID(text) || icalwrite.HasSchedulingProperties(text) {
            return errors.New("Studio can move one-time events only; manage a recurring series instead")
        }
        if _, _, err := showcaseFindCalendarItem(targetCalendar.Collection, uid); err == nil {
            return errors.New("the destination calendar already has this event")
        } else if !errors.Is(err, os.ErrNotExist) {
            return err
        }
        destinationPath := filepath.Join(targetCalendar.Collection, uid+".ics")
        if err := fileio.WriteAtomic(destinationPath, item, 0600); err != nil {
            return fmt.Errorf("copy event to destination calendar: %w", err)
        }
        if err := fileio.RemoveDurable(sourcePath); err != nil {
            _ = fileio.RemoveDurable(destinationPath)
            return fmt.Errorf("remove source calendar event: %w", err)
        }
        return nil
    })
}

func (a *app) showcaseCalendarDeleteSeries(body map[string]any) (map[string]any, error) {
    if !a.showcaseMode() {
        return nil, errors.New("deleting a calendar series is available only in Showcase Studio")
    }
    source := strings.TrimSpace(jsonutil.BodyString(body, "calUrl"))
    uid := strings.TrimSpace(jsonutil.BodyString(body, "uid"))
    if !a.showcaseWritableCalendarSource(source) || !showcaseCalendarUIDValid(uid) {
        return nil, errors.New("calendar event required")
    }
    service := a.calendarWritebackService()
    return a.showcaseCalendarMutationResponse(service, []string{source}, uid, "series-deleted", "Delete Studio calendar series", func() error {
        if err := a.calendarWritebackSourceBlocked(source); err != nil {
            return err
        }
        calendar, err := service.Resolve(source)
        if err != nil {
            return err
        }
        path, item, err := showcaseFindCalendarItem(calendar.Collection, uid)
        if err != nil {
            if errors.Is(err, os.ErrNotExist) {
                return errors.New("calendar series is no longer available")
            }
            return err
        }
        if !icalwrite.IsRecurring(string(item)) {
            return errors.New("this event is not a repeating series")
        }
        if err := fileio.RemoveDurable(path); err != nil {
            return fmt.Errorf("delete calendar series: %w", err)
        }
        return nil
    })
}

func (a *app) showcaseCalendarManagementStatus(status, writeback map[string]any) map[string]any {
    status["showcaseSession"] = map[string]any{
        "enabled": true,
        "label":   "Studio Session Calendars",
        "detail":  "Edits are private to this Studio session and reset when Studio closes.",
    }
    registered := map[string]bool{}
    for _, raw := range jsonutil.List(writeback["calendars"]) {
        row := jsonutil.Map(raw)
        source := strings.TrimSpace(jsonutil.StringValue(row["source"]))
        if a.showcaseWritableCalendarSource(source) {
            registered[source] = true
        }
    }
    for _, raw := range jsonutil.List(status["calendars"]) {
        row := jsonutil.Map(raw)
        source := strings.TrimSpace(jsonutil.StringValue(row["url"]))
        if a.showcaseWritableCalendarSource(source) {
            row["kind"] = "writeback"
            row["deleteMode"] = "hide-only"
            row["sourceLabel"] = "Studio session calendar · writable · resets when Studio closes"
            row["writebackRegistered"] = registered[source]
            row["privateSelected"] = false
            row["showcaseSession"] = true
            continue
        }
        row["showcaseSession"] = false
        row["showcaseReadOnly"] = true
        if source != "" {
            row["sourceLabel"] = "Studio demonstration feed · read-only"
        }
    }
    return status
}
''')

    # Let the public Studio route expose the two Studio-only operations without
    # a user PIN. Both helpers independently enforce the exact source allowlist.
    replace_once(
        public_post,
        '''	// Studio has no user PIN or remote provider. Permit deletion only for the
	// exact disposable session collections; every normal Dashboard delete still
	// follows the authenticated route below.
	if path == "/api/calendar/event/delete" && a.showcaseMode() && a.showcaseWritableCalendarSource(jsonutil.BodyString(body, "calUrl")) {
''',
        '''	// Studio has no user PIN or remote provider. Its move and recurring-series
	// delete operations are limited to the three disposable session collections.
	if path == "/api/calendar/event/move" && a.showcaseMode() {
		result, err := a.showcaseCalendarMove(body)
		if err != nil {
			a.err(w, err.Error(), http.StatusBadRequest)
		} else {
			a.json(w, result)
		}
		return true
	}
	if path == "/api/calendar/event/series/delete" && a.showcaseMode() {
		result, err := a.showcaseCalendarDeleteSeries(body)
		if err != nil {
			a.err(w, err.Error(), http.StatusBadRequest)
		} else {
			a.json(w, result)
		}
		return true
	}
	// Studio has no user PIN or remote provider. Permit deletion only for the
	// exact disposable session collections; every normal Dashboard delete still
	// follows the authenticated route below.
	if path == "/api/calendar/event/delete" && a.showcaseMode() && a.showcaseWritableCalendarSource(jsonutil.BodyString(body, "calUrl")) {
''',
    )

    post_calendar = cmd / "http_routes_post_calendar.go"
    replace_once(
        post_calendar,
        '''	case "/api/calendar/event/create", "/api/calendar/event/update", "/api/calendar/event/occurrence/update", "/api/calendar/event/series/update", "/api/calendar/event/delete", "/api/calendar/event/skip-occurrence":
		result, err := a.handleCalendarWritebackMutation(path, body)
''',
        '''	case "/api/calendar/event/move":
		result, err := a.showcaseCalendarMove(body)
		if err != nil {
			a.err(w, err.Error(), http.StatusBadRequest)
			return true
		}
		a.json(w, result)
	case "/api/calendar/event/series/delete":
		result, err := a.showcaseCalendarDeleteSeries(body)
		if err != nil {
			a.err(w, err.Error(), http.StatusBadRequest)
			return true
		}
		a.json(w, result)
	case "/api/calendar/event/create", "/api/calendar/event/update", "/api/calendar/event/occurrence/update", "/api/calendar/event/series/update", "/api/calendar/event/delete", "/api/calendar/event/skip-occurrence":
		result, err := a.handleCalendarWritebackMutation(path, body)
''',
    )

    calendar_facade = cmd / "calendar_facade.go"
    replace_once(
        calendar_facade,
        '''	return status
}
func (a *app) archiveLocalCalendar''',
        '''	if a.showcaseMode() {
		return a.showcaseCalendarManagementStatus(status, writeback)
	}
	return status
}
func (a *app) archiveLocalCalendar''',
    )

    # Add Move Event for one-time items and Delete Entire Series for Studio-only
    # recurring masters. The backend still validates source, UID, and ICS shape.
    replace_once(
        calendar_writeback_js,
        '''    if(cap.canEdit)row.appendChild(calendarWritebackButton("Manage event","primary",()=>openCalendarEventForm({event:ev,scope:"single"})));
    if(cap.canOccurrenceEdit||cap.canSeriesEdit||cap.canSkip)row.appendChild(calendarWritebackButton("Manage recurring event","primary",()=>calendarWritebackRecurringManage(ev,cap)));
''',
        '''    if(cap.canEdit)row.appendChild(calendarWritebackButton("Manage event","primary",()=>openCalendarEventForm({event:ev,scope:"single"})));
    if(window.DASHGO_SHOWCASE&&cap.canEdit&&typeof showcaseMoveCalendarEvent==="function")row.appendChild(calendarWritebackButton("Move event","",()=>showcaseMoveCalendarEvent(ev,status)));
    if(cap.canOccurrenceEdit||cap.canSeriesEdit||cap.canSkip)row.appendChild(calendarWritebackButton("Manage recurring event","primary",()=>calendarWritebackRecurringManage(ev,cap)));
''',
    )
    replace_once(
        calendar_writeback_js,
        '''    const series=el("section","calendar-writeback-recurring-scope");
    series.appendChild(el("h3","","Entire series"));
    if(cap.canSeriesEdit){
      series.appendChild(el("p","","Change the title, date, time, location, or notes for this simple repeating series. Its repeat rule stays unchanged."));
      const seriesActions=el("div","calendar-writeback-action-row");
      seriesActions.appendChild(calendarWritebackButton("Edit entire series","",()=>openCalendarEventForm({event:ev,scope:"series"})));
      series.appendChild(seriesActions);
    }else{
      series.appendChild(el("p","calendar-writeback-note","This series has an advanced repeat pattern. You can change this occurrence here; manage the repeating rule in Google, iCloud, or its original calendar app."));
    }
''',
        '''    const series=el("section","calendar-writeback-recurring-scope");
    series.appendChild(el("h3","","Entire series"));
    const seriesActions=el("div","calendar-writeback-action-row");
    if(cap.canSeriesEdit){
      series.appendChild(el("p","","Change the title, date, time, location, or notes for this simple repeating series. Its repeat rule stays unchanged."));
      seriesActions.appendChild(calendarWritebackButton("Edit entire series","",()=>openCalendarEventForm({event:ev,scope:"series"})));
    }else{
      series.appendChild(el("p","calendar-writeback-note",window.DASHGO_SHOWCASE?"This advanced series cannot have its repeat rule edited in Studio, but it can be removed from this temporary session.":"This series has an advanced repeat pattern. You can change this occurrence here; manage the repeating rule in Google, iCloud, or its original calendar app."));
    }
    if(window.DASHGO_SHOWCASE&&typeof showcaseDeleteCalendarSeries==="function")seriesActions.appendChild(calendarWritebackButton("Delete entire series","danger",()=>showcaseDeleteCalendarSeries(ev)));
    if(seriesActions.childNodes.length)series.appendChild(seriesActions);
''',
    )

    calendar_event_form = app / "ui/js/calendar-event-form.js"
    replace_once(
        calendar_event_form,
        '''function calendarWritebackFormLabels(event,scope){
  if(!event)return {title:"New event",when:"Add to a writable calendar",save:"Save event",note:"Changes appear on Dash-Go immediately. Remote sync follows in the background."};
  if(scope==="occurrence")return {title:"Edit this occurrence",when:"Recurring calendar event",save:"Save this occurrence",note:"This changes only the selected occurrence. The repeating series stays unchanged; remote sync follows in the background."};
  if(scope==="series")return {title:"Edit entire series",when:"Recurring calendar event",save:"Save entire series",note:"This changes the title, date, time, location, and notes for the series. Its repeat rule stays unchanged; remote sync follows in the background."};
  return {title:"Manage event",when:"Calendar event",save:"Save event",note:"Changes appear on Dash-Go immediately. Remote sync follows in the background."};
}
''',
        '''function calendarWritebackFormLabels(event,scope){
  const studio=window.DASHGO_SHOWCASE===true;
  const local=studio?"Saved only in this Studio session and reset when Studio closes.":"Changes appear on Dash-Go immediately. Remote sync follows in the background.";
  if(!event)return {title:"New event",when:"Add to a writable calendar",save:"Save event",note:local};
  if(scope==="occurrence")return {title:"Edit this occurrence",when:"Recurring calendar event",save:"Save this occurrence",note:studio?"This changes only the selected occurrence. The Studio session resets when it closes.":"This changes only the selected occurrence. The repeating series stays unchanged; remote sync follows in the background."};
  if(scope==="series")return {title:"Edit entire series",when:"Recurring calendar event",save:"Save entire series",note:studio?"This changes the title, date, time, location, and notes for this Studio session. Its repeat rule stays unchanged.":"This changes the title, date, time, location, and notes for the series. Its repeat rule stays unchanged; remote sync follows in the background."};
  return {title:"Manage event",when:"Calendar event",save:"Save event",note:local};
}
''',
    )

    sandbox_js = app / "ui/js/showcase-calendar-sandbox.js"
    write(sandbox_js, r'''(function(){
  if(!window.DASHGO_SHOWCASE)return;
  function sourceFor(ev){return String(ev&&ev.cal&&ev.cal.url||ev&&ev.calUrl||"");}
  function nameFor(status,source){const found=(Array.isArray(status&&status.calendars)?status.calendars:[]).find(item=>item&&String(item.source||"")===source);return String(found&&found.name||"Studio calendar");}
  function sessionNote(){return el("p","calendar-writeback-note","Studio session only. Every edit resets when Studio closes.");}
  window.showcaseMoveCalendarEvent=function(ev,status){
    const source=sourceFor(ev),targets=calendarWritebackActiveCalendars(status).filter(item=>String(item&&item.source||"")!==source);
    popupOpenTransaction({mode:"showcasemove",title:"Move event",when:"Studio session calendar",loading:"Preparing calendar move…"},()=>{
      const root=el("section","calendar-writeback-recurring");root.append(sessionNote(),el("p","",`Move “${ev&&ev.title||"this event"}” from ${nameFor(status,source)} to:`));
      const actions=el("div","calendar-writeback-action-row");
      targets.forEach(target=>{const button=calendarWritebackButton("Move to "+String(target.name||"Studio calendar"),"primary",async node=>{node.disabled=true;try{const result=await calendarWritebackRequest("/api/calendar/event/move",{calUrl:source,targetCalUrl:String(target.source||""),uid:ev.uid});if(result.warning)calendarWritebackShowError(root,result.warning);await calendarWritebackRefresh();closeScrim();}catch(error){node.disabled=false;calendarWritebackShowError(root,error.message);}});actions.appendChild(button);});
      root.appendChild(actions);const back=el("div","calendar-writeback-form-actions");back.appendChild(calendarWritebackButton("Back to event","",()=>showEventPopup(ev)));root.appendChild(back);return root;
    });
  };
  window.showcaseDeleteCalendarSeries=function(ev){
    popupOpenTransaction({mode:"showcaseseriesdelete",title:"Delete entire series?",when:"Studio session calendar",loading:"Preparing series deletion…"},()=>{
      const root=el("section","calendar-writeback-recurring");root.append(sessionNote(),el("p","",`Delete every occurrence of “${ev&&ev.title||"this series"}” from this Studio session?`));
      const actions=el("div","calendar-writeback-action-row");actions.append(calendarWritebackButton("Keep series","",()=>showEventPopup(ev)),calendarWritebackButton("Delete entire series","danger",async node=>{node.disabled=true;try{const result=await calendarWritebackRequest("/api/calendar/event/series/delete",{calUrl:sourceFor(ev),uid:ev.uid});if(result.warning)calendarWritebackShowError(root,result.warning);await calendarWritebackRefresh();closeScrim();}catch(error){node.disabled=false;calendarWritebackShowError(root,error.message);}}));root.appendChild(actions);return root;
    });
  };
})();''')

    # R6 presentation controls distinguish large native presentation sizing from
    # exact device preview emulation. They remain session-only and never touch
    # Windows display scale/settings.
    write(view, r'''(function(){
  const query=new URLSearchParams(window.location.search);
  if(query.get("showcaseStudio")!=="1")return;
  const hubURL=query.get("showcaseHub")||"",token=query.get("showcaseToken")||"";
  if(!hubURL||!token)return;
  const presets=[
    ["presentation","fit","Presentation Fit","Use this display · high-DPI"],
    ["landscape","wall-landscape","Wall Display Preview","1920 × 1080 CSS"],
    ["landscape","laptop","Laptop Preview","1366 × 768 CSS"],
    ["landscape","wide-tablet","16:10 Preview","1280 × 800 CSS"],
    ["portrait","portrait-wall","Portrait Wall Preview","1080 × 1920 CSS"],
    ["portrait","portrait-tablet","Portrait Tablet Preview","800 × 1280 CSS"],
    ["portrait","portrait-four-three","4:3 Portrait Preview","768 × 1024 CSS"],
  ];
  const root=document.createElement("aside");root.id="showcase-view";
  root.innerHTML="<button class='showcase-view-toggle' aria-expanded='false'>Presentation <span>▾</span></button><section class='showcase-view-panel' hidden><div class='showcase-view-head'><strong>Presentation &amp; Preview</strong><button data-clean>Clean View</button></div><p class='showcase-view-copy'>Presentation Fit uses your Windows display and DPI. Device previews emulate exact CSS viewports.</p><div data-groups></div><p class='showcase-view-status'>Presentation Fit · Native high-DPI presentation</p></section>";
  document.body.appendChild(root);
  const panel=root.querySelector(".showcase-view-panel"),toggle=root.querySelector(".showcase-view-toggle"),groups=root.querySelector("[data-groups]"),status=root.querySelector(".showcase-view-status");
  const restore=document.createElement("button");restore.id="showcase-view-restore";restore.textContent="View ▸";restore.hidden=true;document.body.appendChild(restore);
  function group(name){const box=document.createElement("section");box.className="showcase-view-group";box.innerHTML="<p>"+name+"</p><div class='showcase-view-grid'></div>";groups.appendChild(box);return box.querySelector(".showcase-view-grid");}
  const presentation=group("Presentation"),landscape=group("Device previews"),portrait=group("Portrait previews");
  async function pick(id,label){
    status.textContent="Switching to "+label+"…";
    const response=await fetch(hubURL+"/api/viewport?token="+encodeURIComponent(token),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({preset:id})});
    const result=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(result.error||"Presentation could not change.");
    status.textContent=result.fit?"Presentation Fit · "+result.presentation:result.width+" × "+result.height+" · "+result.orientation+" · "+result.presentation;
    panel.hidden=true;toggle.setAttribute("aria-expanded","false");
  }
  presets.forEach(([groupName,id,label,size])=>{const button=document.createElement("button");button.type="button";button.innerHTML="<b>"+label+"</b><small>"+size+"</small>";button.onclick=()=>pick(id,label).catch(error=>{status.textContent=error.message;});({presentation,landscape,portrait}[groupName]).appendChild(button);});
  toggle.onclick=()=>{const open=panel.hidden;panel.hidden=!open;toggle.setAttribute("aria-expanded",String(open));};
  root.querySelector("[data-clean]").onclick=()=>{root.hidden=true;restore.hidden=false;document.documentElement.classList.add("showcase-clean-view");};
  restore.onclick=()=>{root.hidden=false;restore.hidden=true;document.documentElement.classList.remove("showcase-clean-view");};
})();''')

    write(css, r'''html.showcase-clean-view #showcase-tour{display:none}#showcase-tour{position:fixed;right:28px;bottom:28px;z-index:2147483000;width:min(600px,calc(100vw - 56px));padding:30px 32px;border:1px solid #78c3f1;border-radius:22px;background:#102333;color:#f7fbff;box-shadow:0 24px 68px #000b;font:19px/1.62 system-ui,-apple-system,"Segoe UI",sans-serif}#showcase-tour h2{margin:.55rem 0 .75rem;font-size:1.72rem;line-height:1.22;letter-spacing:-.015em}#showcase-tour p{margin:.45rem 0 1.35rem;color:#e8f3fb}.showcase-kicker{margin:0;color:#a9dcff;font-size:.78rem;font-weight:850;letter-spacing:.16em}.showcase-actions{display:flex;gap:11px;flex-wrap:wrap}.showcase-actions button,.showcase-dismiss,#showcase-view button,#showcase-view-restore{border:0;border-radius:12px;padding:12px 16px;background:#eef8ff;color:#0d2638;font:inherit;font-weight:780;cursor:pointer;min-height:50px}.showcase-actions button[data-next]{background:#5cbcf7;color:#062035;font-weight:850}.showcase-actions button[data-restart],.showcase-actions button[data-skip]{background:#1e3a51;color:#dceefb}.showcase-actions button:focus-visible,.showcase-dismiss:focus-visible,#showcase-view button:focus-visible{outline:3px solid #a9dcff;outline-offset:3px}.showcase-actions button:disabled{opacity:.5;cursor:default}.showcase-dismiss{position:absolute;right:13px;top:13px;min-height:0;padding:3px 10px;font-size:1.55rem;line-height:1}.showcase-lock-card{width:min(620px,calc(100vw - 42px));padding:32px;border-radius:22px;background:#102333;color:#f7fbff;box-shadow:0 24px 68px #000b;font:19px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}#showcase-location-lock{position:fixed;inset:0;z-index:2147483001;display:grid;place-items:center;padding:22px;background:#000a}#showcase-location-lock h2{margin:.45rem 0;font-size:1.7rem}#showcase-view{position:fixed;left:18px;top:18px;z-index:2147482999;font:16px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}.showcase-view-toggle{background:#102333!important;color:#f7fbff!important;box-shadow:0 10px 30px #0009}.showcase-view-panel{margin-top:8px;width:min(450px,calc(100vw - 36px));padding:20px;border:1px solid #78c3f1;border-radius:18px;background:#102333;color:#f7fbff;box-shadow:0 22px 62px #000b}.showcase-view-head{display:flex;align-items:center;justify-content:space-between;gap:14px}.showcase-view-head button{min-height:40px;padding:8px 12px}.showcase-view-copy{margin:13px 0 0;color:#d4e5f3;font-size:.92rem}.showcase-view-group>p{margin:18px 0 8px;color:#a9dcff;font-size:.76rem;font-weight:850;letter-spacing:.11em;text-transform:uppercase}.showcase-view-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.showcase-view-grid button{min-height:66px;text-align:left}.showcase-view-grid b,.showcase-view-grid small{display:block}.showcase-view-grid small{opacity:.76;margin-top:3px;font-size:.82rem}.showcase-view-status{margin:16px 0 0;color:#d4e5f3;font-size:.9rem;line-height:1.45}#showcase-view-restore{position:fixed;left:0;top:18px;z-index:2147482999;border-radius:0 12px 12px 0;background:#102333;color:#f7fbff;box-shadow:0 10px 30px #0009}@media(min-width:2200px){#showcase-tour{width:min(650px,calc(100vw - 72px));padding:36px;font-size:21px}#showcase-tour h2{font-size:1.95rem}.showcase-actions button{min-height:56px;padding:14px 18px}#showcase-view{font-size:17px}.showcase-view-panel{width:min(490px,calc(100vw - 40px));padding:23px}.showcase-view-grid button{min-height:72px}}@media(max-width:720px),(max-aspect-ratio:3/4){#showcase-tour{left:10px;right:10px;bottom:10px;width:auto;max-height:56vh;overflow:auto;padding:18px 19px;font-size:16px}#showcase-tour h2{font-size:1.42rem}.showcase-actions button{min-height:44px;padding:9px 11px}#showcase-view{left:8px;top:8px;font-size:14px}.showcase-view-panel{width:min(340px,calc(100vw - 16px));padding:15px}.showcase-view-grid{grid-template-columns:1fr}.showcase-view-grid button{min-height:52px}}
''')

    manifest = app / "ui/js/bundle.manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    files = data["bundles"]["app"]
    for name in ("showcase-tour.js", "showcase-view.js", "showcase-calendar-sandbox.js"):
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
