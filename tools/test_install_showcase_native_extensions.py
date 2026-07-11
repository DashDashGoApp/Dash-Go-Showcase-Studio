#!/usr/bin/env python3
"""Hermetic regression for the Contract-v1 Studio extension installer."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools/install_showcase_native_extensions.py"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(app: Path) -> None:
    contract = {"schema": 1, "contract": "dashgo-showcase/v1", "capabilities": {}}
    write(app / "release/showcase-contract.json", json.dumps(contract) + "\n")
    for name in ("showcase_contract.go", "showcase_contract_calendar.go", "showcase_contract_http.go"):
        write(app / "cmd/dashboard-control-server" / name, "package main\n")
    write(
        app / "go.mod",
        "module github.com/DashDashGoApp/Dash-Go/app\n\ngo 1.26\n",
    )
    write(
        app / "cmd/dashboard-control-server/test_support.go",
        '''package main

import (
    "net/http"
    "sync"

    writebackpkg "github.com/DashDashGoApp/Dash-Go/app/internal/calendar/writeback"
)

type showcaseCalendar struct {
    Writable bool
    Enabled bool
}
type showcaseRuntime struct { calendars map[string]showcaseCalendar }
type app struct {
    showcase *showcaseRuntime
    releaseVersion string
    cacheDir string
    updateMu sync.Mutex
}
func (a *app) showcaseMode() bool { return a.showcase != nil }
func (a *app) handlePublicPost(http.ResponseWriter, *http.Request, string, map[string]any) bool { return false }
func (a *app) json(http.ResponseWriter, any, ...int) {}
func (a *app) err(http.ResponseWriter, string, int) {}
type weatherServiceStub struct{}
func (weatherServiceStub) Payload() any { return nil }
func (a *app) weatherService() weatherServiceStub { return weatherServiceStub{} }
type mapsServiceStub struct{}
func (mapsServiceStub) EventLookup(string) map[string]any { return nil }
func (a *app) mapsService() mapsServiceStub { return mapsServiceStub{} }
func (a *app) calendarWritebackService() *writebackpkg.Service { return &writebackpkg.Service{} }
func (a *app) calendarWritebackSourceBlocked(string) error { return nil }
func (a *app) recordAction(string, string, string, string, map[string]any) {}
func (a *app) refreshEventCache(bool, int, int) (any, error) { return nil, nil }
func (a *app) lockConfigAvailable() bool { return true }
func (a *app) lockConfig() map[string]any { return map[string]any{"enabled": true} }
func (a *app) queueCalendarWritebackSync(string, string, bool) {}
func (a *app) recordCalendarWritebackMutation(string, string, string, bool) error { return nil }
''',
    )
    write(
        app / "internal/calendar/icalwrite/icalwrite.go",
        '''package icalwrite

type Event struct{}
func HasUID(string, string) bool { return false }
func IsRecurring(string) bool { return false }
func HasRecurrenceID(string) bool { return false }
func HasSchedulingProperties(string) bool { return false }
''',
    )
    write(
        app / "internal/calendar/writeback/writeback.go",
        '''package writeback

import "errors"

var ErrBusy = errors.New("busy")
type Calendar struct { Collection string }
type Service struct{}
func (s *Service) WithSyncLock(fn func() error) error { return fn() }
func (s *Service) Resolve(string) (Calendar, error) { return Calendar{}, nil }
func (s *Service) MergeCollection(string, string) error { return nil }
func (s *Service) Record(string, string, string) {}
func (s *Service) SourceWritable(string) bool { return true }
''',
    )
    write(
        app / "internal/fileio/fileio.go",
        '''package fileio
func WriteAtomic(string, []byte, uint32) error { return nil }
func RemoveDurable(string) error { return nil }
''',
    )
    write(
        app / "internal/jsonutil/jsonutil.go",
        '''package jsonutil
import "fmt"
func BodyString(body map[string]any, key string) string { v, _ := body[key].(string); return v }
func List(v any) []any { rows, _ := v.([]any); return rows }
func Map(v any) map[string]any { row, _ := v.(map[string]any); return row }
func StringValue(v any) string { return fmt.Sprint(v) }
''',
    )
    write(
        app / "internal/platform/terminal.go",
        '''package platform
import (
    "os"
    "strings"
)
type Service struct{}
func (s *Service) TerminalAccessFile() string { return "" }
func ParseTerminalAccess([]byte) (bool, bool) { return true, true }
func (s *Service) TerminalAccessEnabled() bool {
	b, e := os.ReadFile(s.TerminalAccessFile())
    if e != nil { return true }
    enabled, valid := ParseTerminalAccess(b)
    if !valid { return true }
    _ = strings.TrimSpace("")
    return enabled
}
''',
    )
    write(
        app / "cmd/dashboard-control-server/runtime_assets_manifest_test.go",
        'package main\n\nvar want = []string{\n\t\t\t"ui/js/family-board-footer.js",\n\t\t\t"ui/css/dashboard/family-board-footer.css",\n}\n',
    )
    write(
        app / "cmd/dashboard-control-server/http_routes_post.go",
        '''package main
import "net/http"
func (a *app) handlePost(w http.ResponseWriter, r *http.Request, path string) {
    body := map[string]any{}
	if res := a.handlePublicPost(w, r, path, body); res {
		return
	}
}
''',
    )
    write(
        app / "cmd/dashboard-control-server/http_routes_get.go",
        '''package main
import "net/http"
func (a *app) handleGet(w http.ResponseWriter, r *http.Request, path string) {
	if path == "/api/lock/status" {
		return
	}
}
''',
    )
    write(
        app / "cmd/dashboard-control-server/http_routes_public_post.go",
        '''package main
import (
    "net/http"
    "github.com/DashDashGoApp/Dash-Go/app/internal/jsonutil"
)
func (a *app) handlePublicCalendarPost(w http.ResponseWriter, r *http.Request, path string, body map[string]any) bool {
    _ = r
    _ = jsonutil.BodyString
	if path == "/api/calendar/event/create" || path == "/api/calendar/event/update" || path == "/api/calendar/event/occurrence/update" || path == "/api/calendar/event/series/update" || path == "/api/calendar/event/skip-occurrence" {
		return true
	}
    return false
}
''',
    )
    write(
        app / "cmd/dashboard-control-server/http_routes_post_calendar.go",
        '''package main
import "net/http"
func (a *app) handleCalendarPost(w http.ResponseWriter, path string, body map[string]any) bool {
    switch path {
	case "/api/calendar/event/create", "/api/calendar/event/update", "/api/calendar/event/occurrence/update", "/api/calendar/event/series/update", "/api/calendar/event/delete", "/api/calendar/event/skip-occurrence":
		result, err := a.handleCalendarWritebackMutation(path, body)
        if err != nil { a.err(w, err.Error(), http.StatusBadRequest); return true }
        a.json(w, result)
    }
    return true
}
''',
    )
    write(
        app / "cmd/dashboard-control-server/weather_facade.go",
        "package main\n\nfunc (a *app) weatherPayload() any          { return a.weatherService().Payload() }\n",
    )
    write(
        app / "cmd/dashboard-control-server/maps_facade.go",
        "package main\n\nfunc (a *app) eventMapLookup(query string) map[string]any { return a.mapsService().EventLookup(query) }\n",
    )
    write(
        app / "cmd/dashboard-control-server/updates.go",
        '''package main
import "path/filepath"
func (a *app) systemUpdateStatus() map[string]any {
	path := filepath.Join(a.cacheDir, "system-update-status.json")
    _ = path
	return map[string]any{}
}
func (a *app) startSystemUpdate() (map[string]any, error) {
	st := a.systemUpdateStatus()
    return st, nil
}
''',
    )
    write(
        app / "cmd/dashboard-control-server/dashboard_update.go",
        '''package main
func (a *app) startDashboardUpdate() (map[string]any, error) {
	a.updateMu.Lock()
    defer a.updateMu.Unlock()
    return map[string]any{}, nil
}
''',
    )
    write(
        app / "cmd/dashboard-control-server/release_current.go",
        '''package main
func (a *app) checkUpdateAvailability() map[string]any {
	return map[string]any{}
}
''',
    )
    write(
        app / "cmd/dashboard-control-server/calendar_facade.go",
        '''package main

type calendarTrashRecord struct{}
func (a *app) calendarManagementStatus() map[string]any {
    status := map[string]any{"calendars": []any{}}
    writeback := map[string]any{"calendars": []any{}}
    _ = writeback
	return status
}
func (a *app) archiveLocalCalendar(url, displayName string) (calendarTrashRecord, error) { return calendarTrashRecord{}, nil }
''',
    )
    write(
        app / "cmd/dashboard-control-server/calendar_writeback.go",
        '''package main

import writebackpkg "github.com/DashDashGoApp/Dash-Go/app/internal/calendar/writeback"

type calendarMutationResult struct { Source, UID, Action, Pair, Collection string; FinalDelete bool }
func (a *app) calendarWritebackDeleteAllowed(source string) bool {
	if !a.calendarWritebackService().SourceWritable(source) || !a.lockConfigAvailable() {
		return false
	}
    return a.lockConfig()["enabled"] == true
}
func (a *app) handleCalendarWritebackMutation(path string, body map[string]any) (map[string]any, error) {
    _ = path; _ = body
    service := a.calendarWritebackService()
    result := calendarMutationResult{Source: "calendars/family.green.ics", UID: "event-1", Action: "updated"}
    var refreshErr error
	action := map[string]string{"created": "Add calendar event", "updated": "Manage calendar event", "occurrence-updated": "Edit calendar occurrence", "series-updated": "Edit recurring series", "deleted": "Delete calendar event", "skipped": "Skip calendar occurrence"}[result.Action]
    _ = action
    _ = refreshErr
    _ = service
    _ = writebackpkg.ErrBusy
    return map[string]any{"ok": true}, nil
}
''',
    )
    write(
        app / "ui/js/control-location-lock.js",
        'function locationResultCard(){return cbtn("Use this location","on",async()=>{\n      try{\n        await api("/api/location","POST",{});\n      }catch(e){ ctrlMsg(e.message); }\n    }));}\n',
    )
    write(
        app / "ui/js/control-navigation.js",
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
    )
    write(
        app / "ui/js/calendar-writeback.js",
        '''function calendarWritebackUI(root,ev,status,cap){
    root.appendChild(el("div","calendar-writeback-note","Dashboard edits save locally first. Remote calendar sync follows."));
    const row=el("div","calendar-writeback-action-row");
    if(cap.canEdit)row.appendChild(calendarWritebackButton("Manage event","primary",()=>openCalendarEventForm({event:ev,scope:"single"})));
    if(cap.canOccurrenceEdit||cap.canSeriesEdit||cap.canSkip)row.appendChild(calendarWritebackButton("Manage recurring event","primary",()=>calendarWritebackRecurringManage(ev,cap)));
    const series=el("section","calendar-writeback-recurring-scope");
    series.appendChild(el("h3","","Entire series"));
    if(cap.canSeriesEdit){
      series.appendChild(el("p","","Change the title, date, time, location, or notes for this simple repeating series. Its repeat rule stays unchanged."));
      const seriesActions=el("div","calendar-writeback-action-row");
      seriesActions.appendChild(calendarWritebackButton("Edit entire series","",()=>openCalendarEventForm({event:ev,scope:"series"})));
      series.appendChild(seriesActions);
    }else{
      series.appendChild(el("p","calendar-writeback-note","This series has an advanced repeat pattern. You can change this occurrence here; manage the repeating rule in Google, iCloud, or its original calendar app."));
    }
}
''',
    )
    write(
        app / "ui/js/calendar-event-form.js",
        '''function calendarWritebackFormLabels(event,scope){
  if(!event)return {title:"New event",when:"Add to a writable calendar",save:"Save event",note:"Changes appear on Dash-Go immediately. Remote sync follows in the background."};
  if(scope==="occurrence")return {title:"Edit this occurrence",when:"Recurring calendar event",save:"Save this occurrence",note:"This changes only the selected occurrence. The repeating series stays unchanged; remote sync follows in the background."};
  if(scope==="series")return {title:"Edit entire series",when:"Recurring calendar event",save:"Save entire series",note:"This changes the title, date, time, location, and notes for the series. Its repeat rule stays unchanged; remote sync follows in the background."};
  return {title:"Manage event",when:"Calendar event",save:"Save event",note:"Changes appear on Dash-Go immediately. Remote sync follows in the background."};
}
''',
    )
    write(
        app / "ui/js/bundle.manifest.json",
        json.dumps({"schema": 1, "bundles": {"app": ["family-board-footer.js"], "control": ["control-navigation.js"]}}) + "\n",
    )
    write(
        app / "ui/css/bundle.manifest.json",
        json.dumps({"schema": 1, "bundles": {"dashboard": ["dashboard/family-board-footer.css"], "control": ["control/layout.css"]}}) + "\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gofmt", required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="studio-native-extension-") as raw:
        app = Path(raw) / "app"
        build_fixture(app)
        result = subprocess.run(
            [sys.executable, str(INSTALLER), "--app", str(app), "--gofmt", args.gofmt],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stdout)
        js = json.loads((app / "ui/js/bundle.manifest.json").read_text(encoding="utf-8"))["bundles"]["app"]
        expected_js = ["showcase-tour.js", "showcase-view.js", "showcase-calendar-sandbox.js"]
        if js[-3:] != expected_js:
            raise AssertionError(f"unexpected native extension JS tail: {js}")
        for relative in (
            "ui/js/showcase-tour.js",
            "ui/js/showcase-view.js",
            "ui/js/showcase-calendar-sandbox.js",
            "ui/css/dashboard/showcase-studio.css",
            "cmd/dashboard-control-server/showcase_studio_extension.go",
            "cmd/dashboard-control-server/showcase_studio_extension_test.go",
            "cmd/dashboard-control-server/showcase_studio_calendar.go",
        ):
            if not (app / relative).is_file():
                raise AssertionError(f"native extension output is missing: {relative}")
        required_tokens = {
            "cmd/dashboard-control-server/http_routes_post.go": "showcaseStudioRestrictedPost",
            "cmd/dashboard-control-server/weather_facade.go": "showcaseStudioWeatherPayload",
            "cmd/dashboard-control-server/maps_facade.go": "showcaseStudioEventMapLookup",
            "cmd/dashboard-control-server/updates.go": "showcaseStudioSystemUpdateStatus",
            "cmd/dashboard-control-server/dashboard_update.go": "showcaseStudioUnavailable",
            "cmd/dashboard-control-server/release_current.go": "showcaseStudioUpdateAvailability",
            "cmd/dashboard-control-server/http_routes_public_post.go": "showcaseCalendarMove",
            "cmd/dashboard-control-server/http_routes_post_calendar.go": "showcaseCalendarDeleteSeries",
            "cmd/dashboard-control-server/calendar_facade.go": "showcaseCalendarManagementStatus",
            "cmd/dashboard-control-server/calendar_writeback.go": '"sync": "session"',
            "internal/platform/terminal.go": 'DASHGO_RUNTIME_PROFILE',
            "ui/js/control-location-lock.js": "showcaseStudioLocationLocked",
            "ui/js/calendar-writeback.js": "showcaseMoveCalendarEvent",
            "ui/js/calendar-event-form.js": "Saved only in this Studio session",
        }
        for relative, token in required_tokens.items():
            text = (app / relative).read_text(encoding="utf-8")
            if token not in text:
                raise AssertionError(f"native extension did not install {token!r} into {relative}")

        go = Path(args.gofmt).resolve().with_name("go")
        if not go.is_file():
            raise AssertionError(f"matching Go compiler is unavailable: {go}")
        env = os.environ.copy()
        env.update({"GOTOOLCHAIN": "local", "GOWORK": "off", "GOFLAGS": "-mod=readonly"})
        compiled = subprocess.run(
            [str(go), "test", "./..."],
            cwd=app,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if compiled.returncode != 0:
            raise AssertionError("native extension compile/test failed:\n" + compiled.stdout)

    print("PASS: Contract-v1 Studio presentation, safety, and session-calendar extension is hermetic and compilable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
