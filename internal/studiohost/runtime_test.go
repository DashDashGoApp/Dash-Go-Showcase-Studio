package studiohost

import (
	"encoding/json"
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

type runtimeContractMatrixTestDocument struct {
	Schema         int `json:"schema"`
	NativeContract struct {
		Schema               int    `json:"schema"`
		Contract             string `json:"contract"`
		DeclarationPath      string `json:"declarationPath"`
		RequiredCapabilities []struct {
			ID string `json:"id"`
		} `json:"requiredCapabilities"`
		Activation struct {
			RuntimeProfile struct {
				Environment string `json:"environment"`
				Value       string `json:"value"`
			} `json:"runtimeProfile"`
			ScenarioManifest struct {
				Environment  string `json:"environment"`
				RelativePath string `json:"relativePath"`
			} `json:"scenarioManifest"`
			DataRoot struct {
				Environment  string `json:"environment"`
				RelativePath string `json:"relativePath"`
			} `json:"dataRoot"`
		} `json:"activation"`
		Readiness struct {
			LivenessPath string `json:"livenessPath"`
			StatusPath   string `json:"statusPath"`
			Profile      string `json:"profile"`
			Cache        struct {
				Rebuilt                    bool `json:"rebuilt"`
				MinimumEvents              int  `json:"minimumEvents"`
				MinimumWritebackCandidates int  `json:"minimumWritebackCandidates"`
			} `json:"cache"`
		} `json:"readiness"`
		Calendars []struct {
			Source                     string `json:"source"`
			Mode                       string `json:"mode"`
			ExpectedEventMarker        string `json:"expectedEventMarker"`
			MinimumWritebackCandidates int    `json:"minimumWritebackCandidates"`
		} `json:"calendars"`
		BrowserRoutes []struct {
			Path      string `json:"path"`
			Contains  string `json:"contains"`
			ParseJSON bool   `json:"parseJSON"`
		} `json:"browserRoutes"`
	} `json:"nativeContract"`
	LegacyBridge struct {
		BrowserRoutes []struct {
			Path      string `json:"path"`
			Contains  string `json:"contains"`
			ParseJSON bool   `json:"parseJSON"`
		} `json:"browserRoutes"`
	} `json:"legacyBridge"`
}

func loadRuntimeContractMatrixForTest(t *testing.T) runtimeContractMatrixTestDocument {
	t.Helper()
	body, err := os.ReadFile("dashgo_runtime_contract_matrix.json")
	if err != nil {
		t.Fatalf("read runtime contract matrix: %v", err)
	}
	var matrix runtimeContractMatrixTestDocument
	if err := json.Unmarshal(body, &matrix); err != nil {
		t.Fatalf("decode runtime contract matrix: %v", err)
	}
	return matrix
}

func TestRuntimeContractMatrixMatchesNativeRuntimeAssumptions(t *testing.T) {
	matrix := loadRuntimeContractMatrixForTest(t)
	if matrix.Schema != 1 || matrix.NativeContract.Schema != 1 {
		t.Fatalf("unexpected runtime contract matrix schema: %#v", matrix)
	}
	if matrix.NativeContract.Contract != nativeShowcaseContractName {
		t.Fatalf("native contract=%q, want %q", matrix.NativeContract.Contract, nativeShowcaseContractName)
	}
	if matrix.NativeContract.DeclarationPath != "release/showcase-contract.json" {
		t.Fatalf("native declaration path=%q", matrix.NativeContract.DeclarationPath)
	}
	if matrix.NativeContract.Activation.RuntimeProfile.Environment != "DASHGO_RUNTIME_PROFILE" || matrix.NativeContract.Activation.RuntimeProfile.Value != "showcase" {
		t.Fatalf("unexpected runtime-profile activation: %#v", matrix.NativeContract.Activation.RuntimeProfile)
	}
	if matrix.NativeContract.Activation.ScenarioManifest.Environment != "DASHGO_SHOWCASE_MANIFEST" || matrix.NativeContract.Activation.ScenarioManifest.RelativePath != "scenario/data/showcase-manifest.json" {
		t.Fatalf("unexpected scenario-manifest activation: %#v", matrix.NativeContract.Activation.ScenarioManifest)
	}
	if matrix.NativeContract.Activation.DataRoot.Environment != "DASHGO_DATA_ROOT" || matrix.NativeContract.Activation.DataRoot.RelativePath != "scenario/data" {
		t.Fatalf("unexpected data-root activation: %#v", matrix.NativeContract.Activation.DataRoot)
	}
	if matrix.NativeContract.Readiness.LivenessPath != showcaseLivenessPath || matrix.NativeContract.Readiness.StatusPath != showcaseStatusPath || matrix.NativeContract.Readiness.Profile != "showcase" {
		t.Fatalf("unexpected native readiness contract: %#v", matrix.NativeContract.Readiness)
	}
	if !matrix.NativeContract.Readiness.Cache.Rebuilt || matrix.NativeContract.Readiness.Cache.MinimumEvents != 1 || matrix.NativeContract.Readiness.Cache.MinimumWritebackCandidates != len(sessionCalendarWritableSources) {
		t.Fatalf("unexpected native cache readiness contract: %#v", matrix.NativeContract.Readiness.Cache)
	}

	if len(matrix.NativeContract.RequiredCapabilities) != len(nativeShowcaseRequiredCapabilities) {
		t.Fatalf("matrix capabilities=%d, runtime capabilities=%d", len(matrix.NativeContract.RequiredCapabilities), len(nativeShowcaseRequiredCapabilities))
	}
	for index, capability := range nativeShowcaseRequiredCapabilities {
		if got := matrix.NativeContract.RequiredCapabilities[index].ID; got != capability {
			t.Fatalf("matrix capability[%d]=%q, want %q", index, got, capability)
		}
	}

	writable := map[string]struct{}{}
	calendarRoutes := map[string]string{}
	for _, calendar := range matrix.NativeContract.Calendars {
		if calendar.Mode == "writable" {
			writable[calendar.Source] = struct{}{}
			calendarRoutes["/"+calendar.Source] = calendar.ExpectedEventMarker
		}
	}
	if len(writable) != len(sessionCalendarWritableSources) {
		t.Fatalf("matrix writable calendars=%d, runtime writable calendars=%d", len(writable), len(sessionCalendarWritableSources))
	}
	for source := range sessionCalendarWritableSources {
		if _, ok := writable[source]; !ok {
			t.Fatalf("runtime writable calendar %q is missing from matrix", source)
		}
	}

	if len(matrix.NativeContract.BrowserRoutes) != len(nativeContractClientVisibleScenarioData) {
		t.Fatalf("matrix native browser routes=%d, runtime native browser probes=%d", len(matrix.NativeContract.BrowserRoutes), len(nativeContractClientVisibleScenarioData))
	}
	for index, probe := range nativeContractClientVisibleScenarioData {
		row := matrix.NativeContract.BrowserRoutes[index]
		if row.Path != probe.Path || row.Contains != probe.Contains || row.ParseJSON != probe.ParseJSON {
			t.Fatalf("matrix native browser route[%d]=%#v, runtime probe=%#v", index, row, probe)
		}
	}
	allMatrixRoutes := append(append([]struct {
		Path      string `json:"path"`
		Contains  string `json:"contains"`
		ParseJSON bool   `json:"parseJSON"`
	}{}, matrix.NativeContract.BrowserRoutes...), matrix.LegacyBridge.BrowserRoutes...)
	if len(allMatrixRoutes) != len(requiredClientVisibleScenarioData) {
		t.Fatalf("matrix total browser routes=%d, runtime all browser probes=%d", len(allMatrixRoutes), len(requiredClientVisibleScenarioData))
	}
	for index, probe := range requiredClientVisibleScenarioData {
		row := allMatrixRoutes[index]
		if row.Path != probe.Path || row.Contains != probe.Contains || row.ParseJSON != probe.ParseJSON {
			t.Fatalf("matrix total browser route[%d]=%#v, runtime browser probe=%#v", index, row, probe)
		}
	}
	for path, marker := range calendarRoutes {
		found := false
		for _, probe := range nativeContractClientVisibleScenarioData {
			if probe.Path == path && probe.Contains == marker {
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("matrix calendar fixture %q (%q) lacks a native browser probe", path, marker)
		}
	}
}

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

	if err := (&App{}).assertClientVisibleScenarioData(server.URL, false); err != nil {
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

	if err := assertClientVisibleScenarioDataWithRetry(server.URL, requiredClientVisibleScenarioData, 3, time.Millisecond, func(time.Duration) {}); err != nil {
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

	if err := assertClientVisibleScenarioDataWithRetry(server.URL, requiredClientVisibleScenarioData, 1, 0, nil); err == nil {
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
	for _, name := range []string{"showcase-family.green", "showcase-school.blue", "showcase-home.amber", "showcase-plans.violet"} {
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
    {"source":"calendars/school.blue.ics","collection":"` + filepath.ToSlash(filepath.Join(stageCollections, "showcase-school.blue")) + `","writable":true,"enabled":true,"name":"School"},
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
{"source":"calendars/school.blue.ics","writable":true,"enabled":true,"deleteAllowed":true},
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
{"source":"calendars/school.blue.ics","writable":true,"enabled":true,"deleteAllowed":true},
{"source":"calendars/home.amber.ics","writable":true,"enabled":true,"deleteAllowed":true},
{"source":"calendars/plans.violet.ics","writable":true,"enabled":true,"deleteAllowed":false}
]}`))
	}))
	defer server.Close()
	if err := assertSessionCalendarWritebackReadyWithRetry(server.URL, 1, 0, nil); err == nil {
		t.Fatal("writeback readiness accepted a calendar without delete capability")
	}
}

func TestNativeShowcaseContractAvailabilityAndReadiness(t *testing.T) {
	root := t.TempDir()
	runtimeApp := filepath.Join(root, "runtime", "app")
	if err := os.MkdirAll(filepath.Join(runtimeApp, "release"), 0700); err != nil {
		t.Fatal(err)
	}
	contract := `{"schema":1,"contract":"dashgo-showcase/v1","capabilities":{"separateDataRoot":true,"scenarioManifest":true,"scenarioCalendars":true,"calendarWritebackAllowlist":true,"cacheRebuildReport":true,"statusEndpoint":true,"staticScenarioAssets":true}}`
	if err := os.WriteFile(filepath.Join(runtimeApp, "release", "showcase-contract.json"), []byte(contract), 0600); err != nil {
		t.Fatal(err)
	}
	a := &App{paths: paths{runtimeApp: runtimeApp}}
	available, err := a.nativeShowcaseContractAvailable()
	if err != nil || !available {
		t.Fatalf("nativeShowcaseContractAvailable() = %v, %v", available, err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/showcase/status" {
			http.NotFound(w, r)
			return
		}
		_, _ = w.Write([]byte(`{"contract":"dashgo-showcase/v1","profile":"showcase","ready":true,"calendars":[{"source":"calendars/family.green.ics","writable":true,"enabled":true,"fixturePresent":true,"writebackRegistered":true,"events":6,"expectedEvents":6,"writebackCandidates":1},{"source":"calendars/school.blue.ics","writable":true,"enabled":true,"fixturePresent":true,"writebackRegistered":true,"events":6,"expectedEvents":6,"writebackCandidates":1},{"source":"calendars/home.amber.ics","writable":true,"enabled":true,"fixturePresent":true,"writebackRegistered":true,"events":6,"expectedEvents":6,"writebackCandidates":1},{"source":"calendars/plans.violet.ics","writable":true,"enabled":true,"fixturePresent":true,"writebackRegistered":true,"events":6,"expectedEvents":6,"writebackCandidates":1}],"cache":{"rebuilt":true,"events":24,"writebackCandidates":4},"problems":[]}`))
	}))
	defer server.Close()
	if err := assertNativeShowcaseContractReadyWithRetry(server.URL, 1, 0, nil); err != nil {
		t.Fatalf("native Showcase readiness = %v", err)
	}
}

func TestNativeShowcaseContractRejectsIncompleteInputs(t *testing.T) {
	root := t.TempDir()
	runtimeApp := filepath.Join(root, "runtime", "app")
	if err := os.MkdirAll(filepath.Join(runtimeApp, "release"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(runtimeApp, "release", "showcase-contract.json"), []byte(`{"schema":1,"contract":"dashgo-showcase/v1","capabilities":{}}`), 0600); err != nil {
		t.Fatal(err)
	}
	a := &App{paths: paths{runtimeApp: runtimeApp}}
	if available, err := a.nativeShowcaseContractAvailable(); err == nil || available {
		t.Fatalf("nativeShowcaseContractAvailable accepted incomplete contract: %v, %v", available, err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"contract":"dashgo-showcase/v1","ready":false,"calendars":[],"cache":{"rebuilt":false,"events":0,"writebackCandidates":0},"problems":["not ready"]}`))
	}))
	defer server.Close()
	if err := assertNativeShowcaseContractReadyWithRetry(server.URL, 1, 0, nil); err == nil {
		t.Fatal("native Showcase readiness accepted incomplete status")
	}
}
