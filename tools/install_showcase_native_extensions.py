#!/usr/bin/env python3
"""Install Studio-owned presentation, safety, and session-calendar extensions onto Contract-v1 Dash-Go."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "tools/native_extension_assets"


class ExtensionError(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise ExtensionError(f"{path}: expected exactly one reviewed anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def copy_asset(name: str, destination: Path) -> None:
    source = ASSETS / name
    if not source.is_file():
        raise ExtensionError(f"missing Studio extension asset: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def append_manifest(path: Path, bundle: str, entries: list[str]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        files = data["bundles"][bundle]
    except Exception as exc:
        raise ExtensionError(f"cannot read bundle manifest {path}: {exc}") from exc
    if not isinstance(files, list) or not files:
        raise ExtensionError(f"bundle manifest {path} has no non-empty {bundle!r} source list")
    for entry in entries:
        if entry in files:
            raise ExtensionError(f"bundle manifest {path} already contains {entry!r}")
        files.append(entry)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def install_policy(app: Path, gofmt: Path) -> None:
    policy = app / "cmd/dashboard-control-server/showcase_studio_extension.go"
    test = app / "cmd/dashboard-control-server/showcase_studio_extension_test.go"
    calendar = app / "cmd/dashboard-control-server/showcase_studio_calendar.go"
    copy_asset("showcase_studio_extension.go.txt", policy)
    copy_asset("showcase_studio_extension_test.go.txt", test)
    copy_asset("showcase_studio_calendar.go.txt", calendar)

    post = app / "cmd/dashboard-control-server/http_routes_post.go"
    replace_once(
        post,
        "\tif res := a.handlePublicPost(w, r, path, body); res {\n",
        "\tif reason := a.showcaseStudioRestrictedPost(path, body); reason != \"\" {\n"
        "\t\ta.err(w, reason, http.StatusForbidden)\n"
        "\t\treturn\n"
        "\t}\n"
        "\tif res := a.handlePublicPost(w, r, path, body); res {\n",
    )

    get = app / "cmd/dashboard-control-server/http_routes_get.go"
    replace_once(
        get,
        "\tif path == \"/api/lock/status\" {\n",
        "\tif path == \"/api/geocode\" && a.showcaseMode() {\n"
        "\t\ta.json(w, a.showcaseStudioGeocode(r.URL.Query().Get(\"q\")))\n"
        "\t\treturn\n"
        "\t}\n"
        "\tif reason := a.showcaseStudioRestrictedGet(path); reason != \"\" {\n"
        "\t\ta.err(w, reason, http.StatusForbidden)\n"
        "\t\treturn\n"
        "\t}\n"
        "\tif path == \"/api/lock/status\" {\n",
    )


    weather = app / "cmd/dashboard-control-server/weather_facade.go"
    replace_once(
        weather,
        "func (a *app) weatherPayload() any          { return a.weatherService().Payload() }\n",
        "func (a *app) weatherPayload() any {\n"
        "\tif a.showcaseMode() {\n"
        "\t\treturn a.showcaseStudioWeatherPayload()\n"
        "\t}\n"
        "\treturn a.weatherService().Payload()\n"
        "}\n",
    )

    maps = app / "cmd/dashboard-control-server/maps_facade.go"
    replace_once(
        maps,
        "func (a *app) eventMapLookup(query string) map[string]any { return a.mapsService().EventLookup(query) }\n",
        "func (a *app) eventMapLookup(query string) map[string]any {\n"
        "\tif a.showcaseMode() {\n"
        "\t\treturn a.showcaseStudioEventMapLookup(query)\n"
        "\t}\n"
        "\treturn a.mapsService().EventLookup(query)\n"
        "}\n",
    )

    updates = app / "cmd/dashboard-control-server/updates.go"
    replace_once(
        updates,
        "func (a *app) systemUpdateStatus() map[string]any {\n\tpath := filepath.Join(a.cacheDir, \"system-update-status.json\")\n",
        "func (a *app) systemUpdateStatus() map[string]any {\n"
        "\tif a.showcaseMode() {\n"
        "\t\treturn a.showcaseStudioSystemUpdateStatus()\n"
        "\t}\n"
        "\tpath := filepath.Join(a.cacheDir, \"system-update-status.json\")\n",
    )
    replace_once(
        updates,
        "func (a *app) startSystemUpdate() (map[string]any, error) {\n\tst := a.systemUpdateStatus()\n",
        "func (a *app) startSystemUpdate() (map[string]any, error) {\n"
        "\tif a.showcaseMode() {\n"
        "\t\treturn nil, showcaseStudioUnavailable(\"system update\")\n"
        "\t}\n"
        "\tst := a.systemUpdateStatus()\n",
    )

    dashboard_update = app / "cmd/dashboard-control-server/dashboard_update.go"
    replace_once(
        dashboard_update,
        "func (a *app) startDashboardUpdate() (map[string]any, error) {\n\ta.updateMu.Lock()\n",
        "func (a *app) startDashboardUpdate() (map[string]any, error) {\n"
        "\tif a.showcaseMode() {\n"
        "\t\treturn nil, showcaseStudioUnavailable(\"dashboard update\")\n"
        "\t}\n"
        "\ta.updateMu.Lock()\n",
    )

    release_current = app / "cmd/dashboard-control-server/release_current.go"
    replace_once(
        release_current,
        "func (a *app) checkUpdateAvailability() map[string]any {\n",
        "func (a *app) checkUpdateAvailability() map[string]any {\n"
        "\tif a.showcaseMode() {\n"
        "\t\treturn a.showcaseStudioUpdateAvailability()\n"
        "\t}\n",
    )

    terminal = app / "internal/platform/terminal.go"
    replace_once(
        terminal,
        "func (s *Service) TerminalAccessEnabled() bool {\n\tb, e := os.ReadFile(s.TerminalAccessFile())\n",
        "func (s *Service) TerminalAccessEnabled() bool {\n"
        "\tif strings.TrimSpace(os.Getenv(\"DASHGO_RUNTIME_PROFILE\")) == \"showcase\" {\n"
        "\t\treturn false\n"
        "\t}\n"
        "\tb, e := os.ReadFile(s.TerminalAccessFile())\n",
    )

    public_post = app / "cmd/dashboard-control-server/http_routes_public_post.go"
    replace_once(
        public_post,
        "\tif path == \"/api/calendar/event/create\" || path == \"/api/calendar/event/update\" || path == \"/api/calendar/event/occurrence/update\" || path == \"/api/calendar/event/series/update\" || path == \"/api/calendar/event/skip-occurrence\" {\n",
        "\tif path == \"/api/calendar/event/move\" && a.showcaseMode() {\n"
        "\t\tresult, err := a.showcaseCalendarMove(body)\n"
        "\t\tif err != nil {\n\t\t\ta.err(w, err.Error(), http.StatusBadRequest)\n\t\t} else {\n\t\t\ta.json(w, result)\n\t\t}\n"
        "\t\treturn true\n\t}\n"
        "\tif path == \"/api/calendar/event/series/delete\" && a.showcaseMode() {\n"
        "\t\tresult, err := a.showcaseCalendarDeleteSeries(body)\n"
        "\t\tif err != nil {\n\t\t\ta.err(w, err.Error(), http.StatusBadRequest)\n\t\t} else {\n\t\t\ta.json(w, result)\n\t\t}\n"
        "\t\treturn true\n\t}\n"
        "\tif path == \"/api/calendar/event/delete\" && a.showcaseMode() && a.showcaseWritableCalendarSource(jsonutil.BodyString(body, \"calUrl\")) {\n"
        "\t\tresult, err := a.handleCalendarWritebackMutation(path, body)\n"
        "\t\tif err != nil {\n\t\t\ta.err(w, err.Error(), http.StatusBadRequest)\n\t\t} else {\n\t\t\ta.json(w, result)\n\t\t}\n"
        "\t\treturn true\n\t}\n"
        "\tif path == \"/api/calendar/event/create\" || path == \"/api/calendar/event/update\" || path == \"/api/calendar/event/occurrence/update\" || path == \"/api/calendar/event/series/update\" || path == \"/api/calendar/event/skip-occurrence\" {\n",
    )

    post_calendar = app / "cmd/dashboard-control-server/http_routes_post_calendar.go"
    replace_once(
        post_calendar,
        "\tcase \"/api/calendar/event/create\", \"/api/calendar/event/update\", \"/api/calendar/event/occurrence/update\", \"/api/calendar/event/series/update\", \"/api/calendar/event/delete\", \"/api/calendar/event/skip-occurrence\":\n\t\tresult, err := a.handleCalendarWritebackMutation(path, body)\n",
        "\tcase \"/api/calendar/event/move\":\n"
        "\t\tresult, err := a.showcaseCalendarMove(body)\n"
        "\t\tif err != nil {\n\t\t\ta.err(w, err.Error(), http.StatusBadRequest)\n\t\t\treturn true\n\t\t}\n"
        "\t\ta.json(w, result)\n"
        "\tcase \"/api/calendar/event/series/delete\":\n"
        "\t\tresult, err := a.showcaseCalendarDeleteSeries(body)\n"
        "\t\tif err != nil {\n\t\t\ta.err(w, err.Error(), http.StatusBadRequest)\n\t\t\treturn true\n\t\t}\n"
        "\t\ta.json(w, result)\n"
        "\tcase \"/api/calendar/event/create\", \"/api/calendar/event/update\", \"/api/calendar/event/occurrence/update\", \"/api/calendar/event/series/update\", \"/api/calendar/event/delete\", \"/api/calendar/event/skip-occurrence\":\n"
        "\t\tresult, err := a.handleCalendarWritebackMutation(path, body)\n",
    )

    calendar_facade = app / "cmd/dashboard-control-server/calendar_facade.go"
    replace_once(
        calendar_facade,
        "\treturn status\n}\nfunc (a *app) archiveLocalCalendar",
        "\tif a.showcaseMode() {\n"
        "\t\treturn a.showcaseCalendarManagementStatus(status, writeback)\n"
        "\t}\n"
        "\treturn status\n}\nfunc (a *app) archiveLocalCalendar",
    )

    calendar_writeback = app / "cmd/dashboard-control-server/calendar_writeback.go"
    replace_once(
        calendar_writeback,
        "func (a *app) calendarWritebackDeleteAllowed(source string) bool {\n"
        "\tif !a.calendarWritebackService().SourceWritable(source) || !a.lockConfigAvailable() {\n",
        "func (a *app) calendarWritebackDeleteAllowed(source string) bool {\n"
        "\tif a.showcaseMode() {\n"
        "\t\treturn a.showcaseWritableCalendarSource(source)\n"
        "\t}\n"
        "\tif !a.calendarWritebackService().SourceWritable(source) || !a.lockConfigAvailable() {\n",
    )
    mutation_anchor = "\taction := map[string]string{\"created\": \"Add calendar event\", \"updated\": \"Manage calendar event\", \"occurrence-updated\": \"Edit calendar occurrence\", \"series-updated\": \"Edit recurring series\", \"deleted\": \"Delete calendar event\", \"skipped\": \"Skip calendar occurrence\"}[result.Action]\n"
    replace_once(
        calendar_writeback,
        mutation_anchor,
        mutation_anchor
        + "\tif a.showcaseMode() && a.showcaseWritableCalendarSource(result.Source) {\n"
        + "\t\tmessage := showcaseSessionCalendarMessage\n"
        + "\t\tseverity := \"success\"\n"
        + "\t\tif refreshErr != nil {\n"
        + "\t\t\tmessage = \"Saved in this Studio session. Dashboard refresh will retry automatically; changes still reset when Studio closes.\"\n"
        + "\t\t\tseverity = \"warning\"\n"
        + "\t\t}\n"
        + "\t\tservice.Record(result.Source, \"saved\", message)\n"
        + "\t\ta.recordAction(\"calendars\", action, severity, message, map[string]any{\"source\": result.Source, \"uid\": result.UID, \"showcase\": true})\n"
        + "\t\tresponse := map[string]any{\"ok\": true, \"source\": result.Source, \"uid\": result.UID, \"action\": result.Action, \"sync\": \"session\"}\n"
        + "\t\tif refreshErr != nil {\n\t\t\tresponse[\"warning\"] = message\n\t\t}\n"
        + "\t\treturn response, nil\n\t}\n",
    )

    result = subprocess.run(
        [str(gofmt), "-w", str(policy), str(test), str(calendar), str(weather), str(maps), str(updates), str(dashboard_update), str(release_current), str(terminal), str(public_post), str(post_calendar), str(calendar_facade), str(calendar_writeback)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise ExtensionError(f"gofmt Studio native extension failed: {result.stdout.strip()}")


def install_browser_assets(app: Path) -> None:
    copy_asset("showcase-tour.js", app / "ui/js/showcase-tour.js")
    copy_asset("showcase-view.js", app / "ui/js/showcase-view.js")
    copy_asset("showcase-calendar-sandbox.js", app / "ui/js/showcase-calendar-sandbox.js")
    copy_asset("showcase-studio.css", app / "ui/css/dashboard/showcase-studio.css")

    append_manifest(app / "ui/js/bundle.manifest.json", "app", ["showcase-tour.js", "showcase-view.js", "showcase-calendar-sandbox.js"])
    append_manifest(app / "ui/css/bundle.manifest.json", "dashboard", ["dashboard/showcase-studio.css"])

    order_test = app / "cmd/dashboard-control-server/runtime_assets_manifest_test.go"
    replace_once(
        order_test,
        '\t\t\t"ui/js/family-board-footer.js",\n',
        '\t\t\t"ui/js/family-board-footer.js",\n'
        '\t\t\t"ui/js/showcase-tour.js",\n'
        '\t\t\t"ui/js/showcase-view.js",\n'
        '\t\t\t"ui/js/showcase-calendar-sandbox.js",\n',
    )
    replace_once(
        order_test,
        '\t\t\t"ui/css/dashboard/family-board-footer.css",\n',
        '\t\t\t"ui/css/dashboard/family-board-footer.css",\n'
        '\t\t\t"ui/css/dashboard/showcase-studio.css",\n',
    )

    location = app / "ui/js/control-location-lock.js"
    replace_once(
        location,
        "      }catch(e){ ctrlMsg(e.message); }\n    }));",
        "      }catch(e){\n"
        "        const message=String(e&&e.message||e);\n"
        "        if(message===\"studio_location_locked\"&&typeof window.showcaseStudioLocationLocked===\"function\"){window.showcaseStudioLocationLocked();return;}\n"
        "        ctrlMsg(message);\n"
        "      }\n"
        "    }));",
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
  // Native summary activation owns open/close. A second pointer-release toggle
  // can immediately undo Chromium's normal details activation.
  document.querySelectorAll("#ctrl details.ctrlsec > summary").forEach(s=>{
    if(s._fastSummaryBound) return;
    s._fastSummaryBound=true;
  });
}
''',
    )

    calendar_writeback_js = app / "ui/js/calendar-writeback.js"
    replace_once(
        calendar_writeback_js,
        '    root.appendChild(el("div","calendar-writeback-note","Dashboard edits save locally first. Remote calendar sync follows."));\n',
        '    root.appendChild(el("div","calendar-writeback-note",window.DASHGO_SHOWCASE?"Studio edits are saved only for this session and reset when Studio closes.":"Dashboard edits save locally first. Remote calendar sync follows."));\n',
    )
    replace_once(
        calendar_writeback_js,
        '    if(cap.canEdit)row.appendChild(calendarWritebackButton("Manage event","primary",()=>openCalendarEventForm({event:ev,scope:"single"})));\n'
        '    if(cap.canOccurrenceEdit||cap.canSeriesEdit||cap.canSkip)row.appendChild(calendarWritebackButton("Manage recurring event","primary",()=>calendarWritebackRecurringManage(ev,cap)));\n',
        '    if(cap.canEdit)row.appendChild(calendarWritebackButton("Manage event","primary",()=>openCalendarEventForm({event:ev,scope:"single"})));\n'
        '    if(window.DASHGO_SHOWCASE&&cap.canEdit&&typeof showcaseMoveCalendarEvent==="function")row.appendChild(calendarWritebackButton("Move event","",()=>showcaseMoveCalendarEvent(ev,status)));\n'
        '    if(cap.canOccurrenceEdit||cap.canSeriesEdit||cap.canSkip)row.appendChild(calendarWritebackButton("Manage recurring event","primary",()=>calendarWritebackRecurringManage(ev,cap)));\n',
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


def validate_native_contract(app: Path) -> None:
    contract = app / "release/showcase-contract.json"
    try:
        data = json.loads(contract.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ExtensionError(f"cannot read native Showcase contract: {exc}") from exc
    if data.get("schema") != 1 or data.get("contract") != "dashgo-showcase/v1":
        raise ExtensionError("Studio native extensions require dashgo-showcase/v1")
    for relative in (
        "cmd/dashboard-control-server/showcase_contract.go",
        "cmd/dashboard-control-server/showcase_contract_calendar.go",
        "cmd/dashboard-control-server/showcase_contract_http.go",
    ):
        if not (app / relative).is_file():
            raise ExtensionError(f"native Showcase source is missing: {relative}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--gofmt", type=Path, required=True)
    args = parser.parse_args()
    app = args.app.resolve()
    gofmt = args.gofmt.resolve()
    if not gofmt.is_file():
        raise ExtensionError(f"gofmt is unavailable: {gofmt}")
    validate_native_contract(app)
    install_browser_assets(app)
    install_policy(app, gofmt)
    print(f"INSTALLED: Studio-owned native presentation, safety, and session-calendar extensions for {app}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExtensionError as exc:
        raise SystemExit(f"SHOWCASE NATIVE EXTENSION ERROR: {exc}")
