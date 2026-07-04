package fixtures

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestRealityLayerSeedsSevenBrowserCalendarsAndSessionWriteback(t *testing.T) {
	ids := stableScenarioIDs()
	if len(ids) < 4 || ids[0] == "" {
		t.Fatalf("scenario catalog is incomplete: %#v", ids)
	}
	root := t.TempDir()
	app := filepath.Join(root, "app")
	home := filepath.Join(root, "home")
	now := time.Date(2026, time.July, 1, 12, 0, 0, 0, time.UTC)
	if err := Seed(app, home, DefaultScenario, now); err != nil {
		t.Fatal(err)
	}

	for _, rel := range []string{
		"config/household-people.json",
		"config/chore-wheel.json",
		"config/routines.json",
		"config/maintenance-tracker.json",
		"config/household-schedules.json",
		"config/calendar-writeback.json",
		"config/showcase-session-calendar.json",
		"config/todo/_lists.json",
		"calendars/calendars.json",
		"calendars/family.green.ics",
		"calendars/school.blue.ics",
		"calendars/home.amber.ics",
		"calendars/plans.violet.ics",
		"calendars/chore-wheel.ics",
		"calendars/routines.ics",
		"calendars/maintenance.ics",
	} {
		if _, err := os.Stat(filepath.Join(app, rel)); err != nil {
			t.Fatalf("missing %s: %v", rel, err)
		}
	}

	manifest, err := os.ReadFile(filepath.Join(app, "calendars", "calendars.json"))
	if err != nil {
		t.Fatalf("read browser calendar manifest: %v", err)
	}
	var calendars []map[string]any
	if err := json.Unmarshal(manifest, &calendars); err != nil {
		t.Fatalf("parse browser calendar manifest: %v", err)
	}
	wantCalendars := map[string]string{
		"calendars/family.green.ics": "Family",
		"calendars/school.blue.ics":  "School",
		"calendars/home.amber.ics":   "Home",
		"calendars/plans.violet.ics": "Plans",
		"calendars/chore-wheel.ics":  "Chores",
		"calendars/routines.ics":     "Routines",
		"calendars/maintenance.ics":  "Maintenance",
	}
	if len(calendars) != len(wantCalendars) {
		t.Fatalf("calendar manifest entries = %d, want %d: %s", len(calendars), len(wantCalendars), manifest)
	}
	for _, calendar := range calendars {
		url, _ := calendar["url"].(string)
		name, _ := calendar["name"].(string)
		if want, ok := wantCalendars[url]; !ok || name != want {
			t.Fatalf("unexpected calendar manifest entry: %#v", calendar)
		}
		if enabled, ok := calendar["enabled"].(bool); !ok || !enabled {
			t.Fatalf("calendar is not enabled: %#v", calendar)
		}
		delete(wantCalendars, url)
	}
	if len(wantCalendars) != 0 {
		t.Fatalf("browser calendar manifest is missing: %#v", wantCalendars)
	}

	for rel, markers := range map[string][]string{
		"family.green.ics": {"SUMMARY:Family meal plan", "RRULE:FREQ=WEEKLY;BYDAY=SU", "SUMMARY:Lake cabin weekend", "RECURRENCE-ID:", "DESCRIPTION:Review the coming week"},
		"school.blue.ics":  {"SUMMARY:Summer learning camp", "SUMMARY:Library maker lab", "LOCATION:Harold Washington Library Center"},
		"home.amber.ics":   {"SUMMARY:Set out trash and recycling", "SUMMARY:Trash pickup", "RRULE:FREQ=WEEKLY;BYDAY=TU", "LOCATION:Whole Foods Market"},
		"plans.violet.ics": {"SUMMARY:Payday", "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=FR", "SUMMARY:Saturday farmers market", "RRULE:FREQ=WEEKLY;BYDAY=SA", "EXDATE:", "SUMMARY:Food pantry volunteer shift", "LOCATION:Greater Chicago Food Depository"},
		"chore-wheel.ics":  {"SUMMARY:Kitchen reset —", "SUMMARY:Take out recycling —"},
		"routines.ics":     {"SUMMARY:Morning ready — Avery", "SUMMARY:Sunday reset — Jordan"},
		"maintenance.ics":  {"SUMMARY:Test smoke detectors", "SUMMARY:Replace HVAC filter"},
	} {
		data, err := os.ReadFile(filepath.Join(app, "calendars", rel))
		if err != nil {
			t.Fatalf("read calendar %s: %v", rel, err)
		}
		for _, marker := range markers {
			if !strings.Contains(string(data), marker) {
				t.Fatalf("calendar %s is missing fixture marker %q", rel, marker)
			}
		}
	}

	family, err := os.ReadFile(filepath.Join(app, "calendars", "family.green.ics"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(family), "DTEND;VALUE=DATE:") {
		t.Fatal("family fixture is missing explicit exclusive all-day ends for multi-day spans")
	}

	writebackBytes, err := os.ReadFile(filepath.Join(app, "config", "calendar-writeback.json"))
	if err != nil {
		t.Fatal(err)
	}
	var writeback struct {
		Version    int  `json:"version"`
		Enabled    bool `json:"enabled"`
		RequirePIN bool `json:"requirePin"`
		Calendars  []struct {
			Source     string `json:"source"`
			Collection string `json:"collection"`
			Writable   bool   `json:"writable"`
			Enabled    bool   `json:"enabled"`
			Name       string `json:"name,omitempty"`
		} `json:"calendars"`
	}
	decoder := json.NewDecoder(bytes.NewReader(writebackBytes))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&writeback); err != nil {
		t.Fatalf("parse strict calendar writeback registry: %v", err)
	}
	if writeback.Version != 2 || !writeback.Enabled || writeback.RequirePIN || len(writeback.Calendars) != 3 {
		t.Fatalf("unexpected Studio writeback registry: %#v", writeback)
	}
	wantWritable := map[string]string{
		"calendars/family.green.ics": filepath.Join(home, ".dashboard-vdirsyncer", "collections", "showcase-family.green"),
		"calendars/home.amber.ics":   filepath.Join(home, ".dashboard-vdirsyncer", "collections", "showcase-home.amber"),
		"calendars/plans.violet.ics": filepath.Join(home, ".dashboard-vdirsyncer", "collections", "showcase-plans.violet"),
	}
	for _, row := range writeback.Calendars {
		want, ok := wantWritable[row.Source]
		if !ok || !row.Writable || !row.Enabled || row.Collection != want {
			t.Fatalf("unexpected writable Studio calendar: %#v", row)
		}
		if entries, err := os.ReadDir(row.Collection); err != nil || len(entries) == 0 {
			t.Fatalf("writable Studio collection is not seeded: %s: %v", row.Collection, err)
		}
		delete(wantWritable, row.Source)
	}
	if len(wantWritable) != 0 {
		t.Fatalf("Studio writeback registry is missing: %#v", wantWritable)
	}

	sessionBytes, err := os.ReadFile(filepath.Join(app, "config", "showcase-session-calendar.json"))
	if err != nil {
		t.Fatalf("read Studio session calendar metadata: %v", err)
	}
	var sessionMeta struct {
		Schema          int      `json:"schema"`
		SessionOnly     bool     `json:"sessionOnly"`
		ResetsOnClose   bool     `json:"resetsOnClose"`
		WritableSources []string `json:"writableSources"`
	}
	if err := json.Unmarshal(sessionBytes, &sessionMeta); err != nil {
		t.Fatalf("parse Studio session calendar metadata: %v", err)
	}
	if sessionMeta.Schema != 1 || !sessionMeta.SessionOnly || !sessionMeta.ResetsOnClose || len(sessionMeta.WritableSources) != 3 {
		t.Fatalf("unexpected Studio session calendar metadata: %#v", sessionMeta)
	}

	if _, err := os.Stat(filepath.Join(home, ".dashboard-family-board.json")); err != nil {
		t.Fatal(err)
	}
}

func TestRealityLayerCalendarDatesFollowHouseholdRules(t *testing.T) {
	loc, err := time.LoadLocation("America/Chicago")
	if err != nil {
		t.Fatal(err)
	}
	today := time.Date(2026, time.July, 1, 0, 0, 0, 0, loc)
	fixtures := showcaseCalendars(DefaultScenario, today, loc, DefaultLocation())
	byFile := map[string]showcaseCalendarFixture{}
	for _, fixture := range fixtures {
		byFile[fixture.File] = fixture
	}
	for _, check := range []struct {
		file, title string
		weekday     time.Weekday
	}{
		{"plans.violet.ics", "Saturday farmers market", time.Saturday},
		{"home.amber.ics", "Set out trash and recycling", time.Monday},
		{"home.amber.ics", "Trash pickup", time.Tuesday},
		{"home.amber.ics", "Recycling pickup", time.Tuesday},
		{"plans.violet.ics", "Payday", time.Friday},
		{"family.green.ics", "Family meal plan", time.Sunday},
		{"family.green.ics", "Piano practice", time.Wednesday},
	} {
		fixture := byFile[check.file]
		var found *showcaseCalendarEvent
		for i := range fixture.Events {
			if fixture.Events[i].Title == check.title {
				found = &fixture.Events[i]
				break
			}
		}
		if found == nil {
			t.Fatalf("missing %q in %s", check.title, check.file)
		}
		if found.Start.Weekday() != check.weekday {
			t.Fatalf("%q starts on %s, want %s", check.title, found.Start.Weekday(), check.weekday)
		}
	}

	plans := byFile["plans.violet.ics"]
	var paydayFound bool
	for _, event := range plans.Events {
		if event.Title == "Saturday farmers market" && len(event.ExDates) != 1 {
			t.Fatalf("Saturday market must include one deliberate skipped occurrence: %#v", event)
		}
		if event.Title == "Payday" {
			paydayFound = true
			if event.RRULE != "FREQ=WEEKLY;INTERVAL=2;BYDAY=FR;COUNT=24" {
				t.Fatalf("unexpected payday recurrence: %#v", event)
			}
		}
	}
	if !paydayFound {
		t.Fatal("missing recurring payday event")
	}

	family := byFile["family.green.ics"]
	var moved bool
	for _, event := range family.Events {
		if event.Title == "Piano practice — moved" {
			moved = true
			if event.RecurrenceID.Weekday() != time.Wednesday || event.Start.Weekday() != time.Thursday {
				t.Fatalf("piano override does not demonstrate a Wednesday-to-Thursday occurrence move: %#v", event)
			}
		}
	}
	if !moved {
		t.Fatal("missing moved recurring piano occurrence")
	}

	// The rolling model deliberately has history and future beyond the current
	// month. A recurrence starts at least 12 weeks back and its count reaches
	// more than 20 weeks forward.
	pastCutoff := today.AddDate(0, 0, -showcasePastDays+7)
	futureCutoff := today.AddDate(0, 0, 20*7)
	var historical, future bool
	for _, event := range append(append([]showcaseCalendarEvent{}, family.Events...), append(byFile["home.amber.ics"].Events, plans.Events...)...) {
		if event.Start.Before(pastCutoff) {
			historical = true
		}
		if event.RRULE != "" && strings.Contains(event.RRULE, "COUNT=") && event.Start.Before(today) {
			future = true
		}
	}
	if !historical || !future || !futureCutoff.After(today) {
		t.Fatalf("rolling calendar coverage is incomplete: historical=%t future=%t", historical, future)
	}
}

func TestBusyCalendarAddsPlanningBlocksToPlansFeed(t *testing.T) {
	root := t.TempDir()
	app := filepath.Join(root, "app")
	home := filepath.Join(root, "home")
	if err := Seed(app, home, "busy-calendar", time.Date(2026, 6, 30, 12, 0, 0, 0, time.UTC)); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(filepath.Join(app, "calendars", "plans.violet.ics"))
	if err != nil || !strings.Contains(string(data), "SUMMARY:Planning block 7") {
		t.Fatalf("busy-calendar plans fixture is incomplete: %v", err)
	}
}

func TestLocationProfilesSeedDistinctCityFixtures(t *testing.T) {
	for _, location := range AllLocations() {
		root := t.TempDir()
		app := filepath.Join(root, "app")
		home := filepath.Join(root, "home")
		if err := SeedForLocation(app, home, DefaultScenario, location.ID, time.Date(2026, 7, 1, 12, 0, 0, 0, time.UTC)); err != nil {
			t.Fatalf("SeedForLocation(%s): %v", location.ID, err)
		}
		data, err := os.ReadFile(filepath.Join(app, "config", "config.local.js"))
		if err != nil || !strings.Contains(string(data), location.City) || !strings.Contains(string(data), location.TimeZone) {
			t.Fatalf("location settings missing for %s: %v", location.ID, err)
		}
		plans, err := os.ReadFile(filepath.Join(app, "calendars", "plans.violet.ics"))
		market := icsText(location.Market)
		volunteer := icsText(location.VolunteerSite)
		if err != nil || !strings.Contains(string(plans), market) || !strings.Contains(string(plans), volunteer) {
			t.Fatalf("map-ready public venue catalog missing for %s: %v", location.ID, err)
		}
	}
}

func TestLocationProfilesCarryTourAlertData(t *testing.T) {
	for _, location := range AllLocations() {
		if location.AlertEvent == "" || location.AlertSeverity == "" {
			t.Fatalf("location %s is missing its synthetic Tour alert metadata", location.ID)
		}
	}
}
