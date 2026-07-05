#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit('SHOWCASE R7 OVERLAY ERROR: ' + message)


def read(path: Path) -> str:
    if not path.is_file():
        fail(f'missing staged source: {path}')
    return path.read_text(encoding='utf-8')


def write(path: Path, text: str) -> None:
    path.write_text(text.replace('\r\n', '\n'), encoding='utf-8', newline='\n')


def replace_once(path: Path, old: str, new: str, label: str, expected: int = 1) -> None:
    text = read(path)
    count = text.count(old)
    if count != expected:
        fail(f'{label}: expected {expected} exact anchor(s), found {count}')
    write(path, text.replace(old, new))


SESSION_JS = r'''(function(){
  "use strict";
  if(!window.DASHGO_SHOWCASE)return;
  const sources=["calendars/family.green.ics","calendars/school.blue.ics","calendars/home.amber.ics","calendars/plans.violet.ics"];
  const names={"calendars/family.green.ics":"Family","calendars/school.blue.ics":"School","calendars/home.amber.ics":"Home","calendars/plans.violet.ics":"Plans"};
  function sourceFor(ev){return String(ev&&ev.cal&&ev.cal.url||ev&&ev.calUrl||"");}
  function note(){return el("p","calendar-writeback-note","Studio session only. Every edit resets when Studio closes.");}
  function sessionCard(writeback){
    const card=el("section","calendar-manager-group showcase-session-calendar-settings");
    card.append(el("div","calmanager-heading","Studio session calendars"));
    card.append(el("p","calmanager-note","Family, School, Home, and Plans are editable only inside this Studio session. Use the dashboard to create, edit, delete, or move supported events. Restarting Studio restores the original fixtures."));
    const list=el("div","calmanager-list");
    const known=new Map((Array.isArray(writeback&&writeback.calendars)?writeback.calendars:[]).map(item=>[String(item&&item.source||""),item]));
    for(const source of sources){
      const item=known.get(source)||{};
      const row=el("article","calmanager-row calmanager-writeback showcase-session-calendar");
      const head=el("div","calmanager-head");
      const title=el("div","calmanager-title");
      title.append(el("strong","",String(item.name||names[source])));
      head.append(title,el("span","calmanager-state on","Editable"));
      row.append(head,el("div","calmanager-detail","Studio session calendar - writable - resets when Studio closes"));
      list.appendChild(row);
    }
    card.appendChild(list);
    card.append(el("p","calmanager-note","Real Google, iCloud, and CalDAV connections are intentionally not simulated in Studio. These rows never access an external account or calendar."));
    return card;
  }
  function editsCard(){
    const card=el("section","calendar-manager-group calwriteback-settings showcase-session-writeback");
    card.append(el("div","calmanager-heading","Studio calendar edits"));
    card.append(el("p","calmanager-note","Studio session calendars are already enabled for Dashboard edits without a PIN. Hide a calendar above when needed; all data is reset when Studio closes."));
    return card;
  }
  function installCalendarManager(){
    if(window.__dashGoShowcaseR7CalendarManagerInstalled)return true;
    if(typeof window.ctrlPrivateCalendarSettings!=="function"||typeof window.ctrlCalendarWritebackSettings!=="function"||typeof window.ctrlCalendarManagerRow!=="function"||typeof window.renderCtrlCalendarManagerData!=="function")return false;
    const baseRow=window.ctrlCalendarManagerRow;
    const baseRender=window.renderCtrlCalendarManagerData;
    window.ctrlCalendarManagerRow=function(item){
      const row=baseRow(item);
      if(item&&(item.showcaseSession===true||sources.includes(String(item.url||item.source||"")))&&row){
        row.classList.add("showcase-session-calendar");
        const detail=row.querySelector(".calmanager-detail");
        if(detail)detail.textContent="Studio session calendar - editable - resets when Studio closes";
      }
      return row;
    };
    window.ctrlPrivateCalendarSettings=function(_state,writeback){return sessionCard(writeback);};
    window.ctrlCalendarWritebackSettings=function(_writeback){return editsCard();};
    window.renderCtrlCalendarManagerData=function(wrap,manager){
      baseRender(wrap,manager);
      const noteNode=wrap&&wrap.querySelector(".calmanager-note");
      if(noteNode)noteNode.textContent="Studio keeps four editable session calendars separate from ordinary local and provider controls. Session edits reset when Studio closes.";
    };
    window.__dashGoShowcaseR7CalendarManagerInstalled=true;
    return true;
  }
  function installCalendarManagerAfterControlLoad(){
    if(!installCalendarManager())window.setTimeout(installCalendarManager,0);
  }
  window.addEventListener("dashgo:control-loaded",installCalendarManagerAfterControlLoad);
  if(window.__dashboardControlLoaded)installCalendarManagerAfterControlLoad();
  function controlOpen(){const control=document.getElementById("ctrl");if(!control||control.hidden||control.getAttribute("aria-hidden")==="true")return false;const style=window.getComputedStyle(control);return style.display!=="none"&&style.visibility!=="hidden";}
  function syncControlLayer(){document.documentElement.classList.toggle("showcase-dashboard-control-open",controlOpen());}
  function observeControl(){const root=document.documentElement;if(!root)return;new MutationObserver(syncControlLayer).observe(root,{subtree:true,attributes:true,attributeFilter:["class","hidden","aria-hidden"]});syncControlLayer();}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",observeControl,{once:true});else observeControl();
  window.showcaseMoveCalendarEvent=function(ev,status){
    const source=sourceFor(ev),targets=calendarWritebackActiveCalendars(status).filter(item=>sources.includes(String(item&&item.source||""))&&String(item&&item.source||"")!==source);
    popupOpenTransaction({mode:"showcasemove",title:"Move event",when:"Studio session calendar",loading:"Preparing calendar move..."},()=>{
      const root=el("section","calendar-writeback-recurring");root.append(note(),el("p","",`Move "${ev&&ev.title||"this event"}" to another Studio session calendar:`));
      const actions=el("div","calendar-writeback-action-row");
      targets.forEach(target=>{const button=calendarWritebackButton("Move to "+String(target.name||"Studio calendar"),"primary",async node=>{node.disabled=true;try{const result=await calendarWritebackRequest("/api/calendar/event/move",{calUrl:source,targetCalUrl:String(target.source||""),uid:ev.uid});if(result.warning)calendarWritebackShowError(root,result.warning);await calendarWritebackRefresh();closeScrim();}catch(error){node.disabled=false;calendarWritebackShowError(root,error.message);}});actions.appendChild(button);});
      root.appendChild(actions);return root;
    });
  };
  window.showcaseDeleteCalendarSeries=function(ev){
    popupOpenTransaction({mode:"showcaseseriesdelete",title:"Delete entire series?",when:"Studio session calendar",loading:"Preparing series deletion..."},()=>{
      const root=el("section","calendar-writeback-recurring");root.append(note(),el("p","",`Delete every occurrence of "${ev&&ev.title||"this series"}" from this Studio session?`));
      const actions=el("div","calendar-writeback-action-row");actions.append(calendarWritebackButton("Keep series","",()=>showEventPopup(ev)),calendarWritebackButton("Delete entire series","danger",async node=>{node.disabled=true;try{const result=await calendarWritebackRequest("/api/calendar/event/series/delete",{calUrl:sourceFor(ev),uid:ev.uid});if(result.warning)calendarWritebackShowError(root,result.warning);await calendarWritebackRefresh();closeScrim();}catch(error){node.disabled=false;calendarWritebackShowError(root,error.message);}}));root.appendChild(actions);return root;
    });
  };
})();'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--gofmt', type=Path, required=True)
    args = parser.parse_args()
    app = args.app.resolve()
    gofmt = args.gofmt.resolve()
    if not gofmt.is_file():
        fail(f'gofmt is unavailable: {gofmt}')

    event_sources = app / 'internal/calendar/events/sources.go'
    event_source_old = """\tu := strings.Split(strings.Split(url, "?")[0], "#")[0]\n\tp := filepath.Clean(filepath.Join(s.dashDir, u))"""
    event_source_new = """\tu := strings.Split(strings.Split(url, "?")[0], "#")[0]\n\tif strings.HasPrefix(filepath.ToSlash(u), "calendars/") {\n\t\trel := strings.TrimPrefix(filepath.ToSlash(u), "calendars/")\n\t\tp := filepath.Clean(filepath.Join(s.calendarDir, filepath.FromSlash(rel)))\n\t\tcalendarClean := filepath.Clean(s.calendarDir)\n\t\tif p != calendarClean && strings.HasPrefix(p, calendarClean+string(os.PathSeparator)) {\n\t\t\treturn p\n\t\t}\n\t\treturn ""\n\t}\n\tp := filepath.Clean(filepath.Join(s.dashDir, u))"""
    replace_once(
        event_sources,
        event_source_old,
        event_source_new,
        'Studio event-cache calendar source resolution',
    )
    event_sources_test = app / 'internal/calendar/events/showcase_calendar_source_resolution_test.go'
    write(event_sources_test, r"""package events

import (
	"path/filepath"
	"testing"
)

func TestShowcaseEventCacheResolvesCalendarSourcesFromConfiguredCalendarDir(t *testing.T) {
	root := t.TempDir()
	runtimeDir := filepath.Join(root, "runtime")
	calendarDir := filepath.Join(root, "session", "calendars")
	service := New(ServiceConfig{DashDir: runtimeDir, CalendarDir: calendarDir})

	want := filepath.Join(calendarDir, "plans.violet.ics")
	if got := service.eventURLToPath("calendars/plans.violet.ics"); got != want {
		t.Fatalf("calendar source path = %q, want %q", got, want)
	}
	if got := service.eventURLToPath("calendars/../outside.ics"); got != "" {
		t.Fatalf("calendar traversal escaped the configured calendar directory: %q", got)
	}
	if got := service.eventURLToPath("ui/example.ics"); got != filepath.Join(runtimeDir, "ui", "example.ics") {
		t.Fatalf("non-calendar path = %q, want immutable runtime path", got)
	}
}
""")

    mode = app / 'cmd/dashboard-control-server/showcase_mode.go'
    replace_once(mode, 'case "calendars/family.green.ics", "calendars/home.amber.ics", "calendars/plans.violet.ics":', 'case "calendars/family.green.ics", "calendars/school.blue.ics", "calendars/home.amber.ics", "calendars/plans.violet.ics":', 'School session-write allowlist')

    static_test = app / 'cmd/dashboard-control-server/showcase_static_path_test.go'
    replace_once(static_test, 'TestShowcaseOnlyAllowsItsThreeSessionWritableCalendars', 'TestShowcaseOnlyAllowsItsFourSessionWritableCalendars', 'School session-write test name')
    replace_once(static_test, '[]string{"calendars/family.green.ics", "calendars/home.amber.ics", "calendars/plans.violet.ics"}', '[]string{"calendars/family.green.ics", "calendars/school.blue.ics", "calendars/home.amber.ics", "calendars/plans.violet.ics"}', 'School writable test lists', expected=2)
    replace_once(static_test, '[]string{"calendars/school.blue.ics", "calendars/chore-wheel.ics", "calendars/routines.ics", "calendars/maintenance.ics", "calendars/unknown.ics"}', '[]string{"calendars/chore-wheel.ics", "calendars/routines.ics", "calendars/maintenance.ics", "calendars/unknown.ics"}', 'School read-only permission list')
    replace_once(static_test, '[]string{"calendars/school.blue.ics", "calendars/chore-wheel.ics", "calendars/unknown.ics"}', '[]string{"calendars/chore-wheel.ics", "calendars/unknown.ics"}', 'School read-only delete list')

    writeback = app / 'cmd/dashboard-control-server/calendar_writeback.go'
    replace_once(writeback, "Studio's three user-managed calendars live only in the disposable", "Studio's four user-managed calendars live only in the disposable", 'Studio session calendar explanation')

    sandbox_go = app / 'cmd/dashboard-control-server/showcase_calendar_sandbox.go'
    for token in ('showcaseCalendarManagementStatus', 'showcaseWritableCalendarSource', 'Studio Session Calendars'):
        if token not in read(sandbox_go):
            fail(f'Studio calendar backend overlay is missing {token!r}')

    sandbox_js = app / 'ui/js/showcase-calendar-sandbox.js'
    write(sandbox_js, SESSION_JS + '\n')

    lazy_loader = app / 'ui/js/control-lazy-loader.js'
    replace_once(
        lazy_loader,
        'CTRL_BUNDLE_PROMISE=Promise.all([ensureControlStyles(),ensureControlScript()]).then(()=>{window.__dashboardControlLoaded=true;}).catch(err=>{CTRL_BUNDLE_PROMISE=null;throw err;});return CTRL_BUNDLE_PROMISE;',
        'CTRL_BUNDLE_PROMISE=Promise.all([ensureControlStyles(),ensureControlScript()]).then(()=>{window.__dashboardControlLoaded=true;window.dispatchEvent(new Event("dashgo:control-loaded"));}).catch(err=>{CTRL_BUNDLE_PROMISE=null;throw err;});return CTRL_BUNDLE_PROMISE;',
        'Calendar Manager ready event',
    )

    manifest_path = app / 'ui/js/bundle.manifest.json'
    manifest = json.loads(read(manifest_path))
    app_sources = manifest.get('bundles', {}).get('app')
    if not isinstance(app_sources, list):
        fail('browser bundle manifest has no app source list')
    tail = ['showcase-tour.js', 'showcase-view.js', 'showcase-calendar-sandbox.js']
    if any(item not in app_sources for item in tail):
        fail('browser bundle manifest is missing a required Showcase r7 app source')
    for item in tail:
        while item in app_sources:
            app_sources.remove(item)
    app_sources.extend(tail)
    write(manifest_path, json.dumps(manifest, indent=2) + '\n')

    css = app / 'ui/css/dashboard/showcase-studio.css'
    marker = '/* Showcase Studio r7 control-layer safety */'
    style = read(css)
    if marker not in style:
        write(css, style.rstrip() + '\n\n' + marker + '''
#showcase-view,
#showcase-view-restore {
  z-index: 90 !important;
}
.showcase-dashboard-control-open #showcase-view,
.showcase-dashboard-control-open #showcase-view-restore {
  visibility: hidden !important;
  pointer-events: none !important;
}
''' )

    subprocess.run([str(gofmt), '-w', str(mode), str(static_test), str(sandbox_go), str(writeback), str(event_sources), str(event_sources_test)], check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
