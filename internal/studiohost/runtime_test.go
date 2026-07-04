package studiohost

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"
)

func showcaseClientVisibleResponses() map[string]string {
	return map[string]string{
		"/config/config.local.js":  "// Generated for Dash-Go Showcase Studio.\n",
		"/config/compliments.json": `{"messages":[{"origin":"studio-normal"}]}`,
		"/calendars/calendars.json": `[
			{"url":"calendars/family.green.ics"},
			{"url":"calendars/school.blue.ics"},
			{"url":"calendars/home.amber.ics"},
			{"url":"calendars/plans.violet.ics"},
			{"url":"calendars/chore-wheel.ics"},
			{"url":"calendars/routines.ics"},
			{"url":"calendars/maintenance.ics"}
		]`,
		"/calendars/family.green.ics": "BEGIN:VCALENDAR\r\nSUMMARY:Family meal plan\r\nEND:VCALENDAR\r\n",
		"/calendars/school.blue.ics":  "BEGIN:VCALENDAR\r\nSUMMARY:Summer learning camp\r\nEND:VCALENDAR\r\n",
		"/calendars/home.amber.ics":   "BEGIN:VCALENDAR\r\nSUMMARY:Grocery pickup\r\nEND:VCALENDAR\r\n",
		"/calendars/plans.violet.ics": "BEGIN:VCALENDAR\r\nSUMMARY:Saturday farmers market\r\nEND:VCALENDAR\r\n",
		"/calendars/chore-wheel.ics":  "BEGIN:VCALENDAR\r\nSUMMARY:Kitchen reset —\r\nEND:VCALENDAR\r\n",
		"/calendars/routines.ics":     "BEGIN:VCALENDAR\r\nSUMMARY:Morning ready — Avery\r\nEND:VCALENDAR\r\n",
		"/calendars/maintenance.ics":  "BEGIN:VCALENDAR\r\nSUMMARY:Test smoke detectors\r\nEND:VCALENDAR\r\n",
		"/api/weather":                `{"source":"showcase-fixture","sources":[{"_source":"showcase"}]}`,
	}
}

func TestRetryScenarioRenameRetriesTransientWindowsAccessDenied(t *testing.T) {
	calls := 0
	sleeps := 0
	err := retryScenarioRename(
		func(_, _ string) error {
			calls++
			if calls < 3 {
				return syscall.EACCES
			}
			return nil
		},
		func(time.Duration) { sleeps++ },
		true,
		"stage",
		"scenario",
	)
	if err != nil {
		t.Fatalf("retryScenarioRename returned error: %v", err)
	}
	if calls != 3 || sleeps != 2 {
		t.Fatalf("calls=%d sleeps=%d, want calls=3 sleeps=2", calls, sleeps)
	}
}

func TestRetryScenarioRenameDoesNotRetryOutsideWindows(t *testing.T) {
	calls := 0
	err := retryScenarioRename(
		func(_, _ string) error {
			calls++
			return syscall.EACCES
		},
		func(time.Duration) { t.Fatal("sleep should not be called outside Windows") },
		false,
		"stage",
		"scenario",
	)
	if err == nil || calls != 1 {
		t.Fatalf("err=%v calls=%d, want one failed call", err, calls)
	}
	if !errors.Is(err, syscall.EACCES) {
		t.Fatalf("error does not preserve access denied: %v", err)
	}
}

func TestRetryScenarioRenameDoesNotRetryNonTransientWindowsFailure(t *testing.T) {
	calls := 0
	err := retryScenarioRename(
		func(_, _ string) error {
			calls++
			return fmt.Errorf("rename failed: %w", syscall.ENOENT)
		},
		func(time.Duration) { t.Fatal("sleep should not be called for a non-transient error") },
		true,
		"stage",
		"scenario",
	)
	if err == nil || calls != 1 {
		t.Fatalf("err=%v calls=%d, want one failed call", err, calls)
	}
	if !errors.Is(err, syscall.ENOENT) {
		t.Fatalf("error does not preserve ENOENT: %v", err)
	}
}

func TestScenarioRenameBackoffIsBounded(t *testing.T) {
	if got := scenarioRenameBackoff(0); got != scenarioRenameInitialDelay {
		t.Fatalf("first delay=%s, want %s", got, scenarioRenameInitialDelay)
	}
	if got := scenarioRenameBackoff(20); got != scenarioRenameMaximumDelay {
		t.Fatalf("late delay=%s, want %s", got, scenarioRenameMaximumDelay)
	}
}

func TestAssertClientVisibleScenarioData(t *testing.T) {
	responses := showcaseClientVisibleResponses()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, ok := responses[r.URL.Path]
		if !ok {
			http.NotFound(w, r)
			return
		}
		if r.URL.Path == "/config/compliments.json" || r.URL.Path == "/calendars/calendars.json" || r.URL.Path == "/api/weather" {
			w.Header().Set("Content-Type", "application/json")
		}
		_, _ = w.Write([]byte(body))
	}))
	defer server.Close()

	if err := (&App{}).assertClientVisibleScenarioData(server.URL); err != nil {
		t.Fatalf("assertClientVisibleScenarioData returned error: %v", err)
	}
}

func TestAssertClientVisibleScenarioDataRetriesTransientFixtureVisibility(t *testing.T) {
	responses := showcaseClientVisibleResponses()
	configRequests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/config/config.local.js" {
			configRequests++
			if configRequests < 3 {
				http.NotFound(w, r)
				return
			}
		}
		body, ok := responses[r.URL.Path]
		if !ok {
			http.NotFound(w, r)
			return
		}
		if r.URL.Path == "/config/compliments.json" || r.URL.Path == "/calendars/calendars.json" || r.URL.Path == "/api/weather" {
			w.Header().Set("Content-Type", "application/json")
		}
		_, _ = w.Write([]byte(body))
	}))
	defer server.Close()

	if err := assertClientVisibleScenarioDataWithRetry(server.URL, 3, time.Millisecond, func(time.Duration) {}); err != nil {
		t.Fatalf("assertClientVisibleScenarioDataWithRetry returned error: %v", err)
	}
	if configRequests != 3 {
		t.Fatalf("config requests=%d, want 3", configRequests)
	}
}

func TestAssertClientVisibleScenarioDataRejectsFallbackContent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte("{}"))
	}))
	defer server.Close()

	if err := assertClientVisibleScenarioDataWithRetry(server.URL, 1, 0, nil); err == nil {
		t.Fatal("assertClientVisibleScenarioData accepted a missing fixture marker")
	}
}

func TestDiscardSessionScenarioRemovesOnlySessionData(t *testing.T) {
	root := t.TempDir()
	scenario := filepath.Join(root, "scenario")
	outside := filepath.Join(root, "outside", "keep.txt")
	if err := os.MkdirAll(filepath.Dir(outside), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(scenario, "config"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(scenario, "config", "calendar-writeback.json"), []byte("{}"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(outside, []byte("keep"), 0600); err != nil {
		t.Fatal(err)
	}

	a := &App{paths: paths{scenarioRoot: scenario}}
	if err := a.discardSessionScenario(); err != nil {
		t.Fatalf("discardSessionScenario returned error: %v", err)
	}
	if _, err := os.Stat(scenario); !os.IsNotExist(err) {
		t.Fatalf("scenario root remains after discard: %v", err)
	}
	if _, err := os.Stat(outside); err != nil {
		t.Fatalf("discardSessionScenario touched outside state: %v", err)
	}
}

func TestCleanupScenarioAfterRuntimeStopRetainsOnlySelfTestState(t *testing.T) {
	root := t.TempDir()
	scenario := filepath.Join(root, "scenario")
	marker := filepath.Join(scenario, "SHOWCASE_RUNTIME.json")
	if err := os.MkdirAll(filepath.Join(scenario, "data"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(marker, []byte(`{"scenario":"everyday-household"}`), 0600); err != nil {
		t.Fatal(err)
	}

	a := &App{paths: paths{scenarioRoot: scenario}}
	if err := a.cleanupScenarioAfterRuntimeStop(&runningRuntime{retainScenarioAfterStop: true}); err != nil {
		t.Fatalf("self-test retention cleanup returned error: %v", err)
	}
	if _, err := os.Stat(marker); err != nil {
		t.Fatalf("self-test retention removed private scenario state: %v", err)
	}

	if err := a.cleanupScenarioAfterRuntimeStop(&runningRuntime{}); err != nil {
		t.Fatalf("normal session cleanup returned error: %v", err)
	}
	if _, err := os.Stat(scenario); !os.IsNotExist(err) {
		t.Fatalf("normal session cleanup left scenario state behind: %v", err)
	}
}

func TestRebaseSessionCalendarWritebackRegistryUsesLiveScenarioHome(t *testing.T) {
	root := t.TempDir()
	stageHome := filepath.Join(root, ".scenario-stage-test", "home")
	activeHome := filepath.Join(root, "scenario", "home")
	stageCollections := filepath.Join(stageHome, ".dashboard-vdirsyncer", "collections")
	activeCollections := filepath.Join(activeHome, ".dashboard-vdirsyncer", "collections")
	for _, name := range []string{"showcase-family.green", "showcase-home.amber", "showcase-plans.violet"} {
		if err := os.MkdirAll(filepath.Join(stageCollections, name), 0700); err != nil {
			t.Fatal(err)
		}
		if err := os.MkdirAll(filepath.Join(activeCollections, name), 0700); err != nil {
			t.Fatal(err)
		}
	}
	registryPath := filepath.Join(root, "registry.json")
	body := `{
  "version": 2,
  "enabled": true,
  "requirePin": false,
  "calendars": [
    {"source":"calendars/family.green.ics","collection":"` + filepath.ToSlash(filepath.Join(stageCollections, "showcase-family.green")) + `","writable":true,"enabled":true,"name":"Family"},
    {"source":"calendars/home.amber.ics","collection":"` + filepath.ToSlash(filepath.Join(stageCollections, "showcase-home.amber")) + `","writable":true,"enabled":true,"name":"Home"},
    {"source":"calendars/plans.violet.ics","collection":"` + filepath.ToSlash(filepath.Join(stageCollections, "showcase-plans.violet")) + `","writable":true,"enabled":true,"name":"Plans"}
  ]
}`
	if err := os.WriteFile(registryPath, []byte(body), 0600); err != nil {
		t.Fatal(err)
	}
	if err := rebaseSessionCalendarWritebackRegistry(registryPath, stageHome, activeHome); err != nil {
		t.Fatalf("rebaseSessionCalendarWritebackRegistry returned error: %v", err)
	}
	if err := assertSessionCalendarWritebackRegistry(registryPath, activeHome); err != nil {
		t.Fatalf("rebased registry did not validate against live scenario home: %v", err)
	}
	registry, err := readSessionCalendarWritebackRegistry(registryPath)
	if err != nil {
		t.Fatal(err)
	}
	for _, calendar := range registry.Calendars {
		rel, err := filepath.Rel(activeCollections, calendar.Collection)
		if err != nil || rel == "." || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || filepath.IsAbs(rel) {
			t.Fatalf("calendar %q was not rebased under live scenario home: %q", calendar.Source, calendar.Collection)
		}
		if strings.HasPrefix(filepath.ToSlash(calendar.Collection), filepath.ToSlash(stageCollections)+"/") {
			t.Fatalf("calendar %q still references staging collection: %q", calendar.Source, calendar.Collection)
		}
	}
}

func TestAssertSessionCalendarWritebackReadyRequiresAllSessionCapabilities(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/calendar/writeback/status" {
			http.NotFound(w, r)
			return
		}
		_, _ = w.Write([]byte(`{"enabled":true,"requirePin":false,"calendars":[
{"source":"calendars/family.green.ics","writable":true,"enabled":true,"deleteAllowed":true},
{"source":"calendars/home.amber.ics","writable":true,"enabled":true,"deleteAllowed":true},
{"source":"calendars/plans.violet.ics","writable":true,"enabled":true,"deleteAllowed":true}
]}`))
	}))
	defer server.Close()
	if err := assertSessionCalendarWritebackReadyWithRetry(server.URL, 1, 0, nil); err != nil {
		t.Fatalf("full Studio writeback status was rejected: %v", err)
	}
}

func TestAssertSessionCalendarWritebackReadyRejectsMissingDeleteCapability(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"enabled":true,"requirePin":false,"calendars":[
{"source":"calendars/family.green.ics","writable":true,"enabled":true,"deleteAllowed":true},
{"source":"calendars/home.amber.ics","writable":true,"enabled":true,"deleteAllowed":true},
{"source":"calendars/plans.violet.ics","writable":true,"enabled":true,"deleteAllowed":false}
]}`))
	}))
	defer server.Close()
	if err := assertSessionCalendarWritebackReadyWithRetry(server.URL, 1, 0, nil); err == nil {
		t.Fatal("writeback readiness accepted a calendar without delete capability")
	}
}
