package fixtures

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	_ "time/tzdata"
)

const DefaultScenario = "everyday-household"

type Scenario struct {
	ID          string `json:"id"`
	Title       string `json:"title"`
	Kind        string `json:"kind"`
	Description string `json:"description"`
}

var scenarios = []Scenario{
	{ID: "everyday-household", Title: "Everyday Household", Kind: "START HERE", Description: "A polished family dashboard with a varied calendar, household messages, To Do, Grocery, weather-ready settings, and active routines."},
	{ID: "busy-calendar", Title: "Busy Calendar", Kind: "CALENDAR", Description: "Dense overlapping events, all-day plans, locations, multi-day travel, and a full day-timeline exploration path."},
	{ID: "family-flow", Title: "Family Flow", Kind: "HOUSEHOLD", Description: "People, private inboxes, Chore Wheel assignments, routines, maintenance, and correction-friendly completion examples."},
	{ID: "household-schedules", Title: "Household Schedules", Kind: "SCHEDULES", Description: "Payday, trash, and recycling rules with generated occurrences and a one-time adjustment example."},
	{ID: "tasks-grocery", Title: "Tasks & Grocery", Kind: "LISTS", Description: "Local To Do and Grocery boards with open, completed, and assigned household items—no cloud account required."},
	{ID: "themes-seasons", Title: "Themes & Seasons", Kind: "PRESENTATION", Description: "A stable, season-aware theme picker setup designed for exploring curated visual styles."},
	{ID: "capture-gallery", Title: "Capture Gallery", Kind: "CAPTURE", Description: "A tidy, screenshot-oriented composition with fixed local fixtures and a calm message state."},
}

// LocationProfile defines synthetic, public-city demo data. It never uses a
// user address, browser geolocation, or a live event feed.
type LocationProfile struct {
	ID            string  `json:"id"`
	Label         string  `json:"label"`
	City          string  `json:"city"`
	Region        string  `json:"region"`
	TimeZone      string  `json:"timeZone"`
	Latitude      float64 `json:"latitude"`
	Longitude     float64 `json:"longitude"`
	Market        string  `json:"market"`
	Venue         string  `json:"venue"`
	AlertEvent    string  `json:"alertEvent"`
	AlertSeverity string  `json:"alertSeverity"`
}

var locationProfiles = []LocationProfile{
	{ID: "new-york", Label: "Eastern — New York, NY", City: "New York", Region: "NY", TimeZone: "America/New_York", Latitude: 40.7128, Longitude: -74.0060, Market: "Neighborhood Market", Venue: "Riverside Community Center", AlertEvent: "Thunderstorm Watch", AlertSeverity: "severe"},
	{ID: "chicago", Label: "Central — Chicago, IL", City: "Chicago", Region: "IL", TimeZone: "America/Chicago", Latitude: 41.8781, Longitude: -87.6298, Market: "Lakeside Market", Venue: "Lakefront Community Center", AlertEvent: "Extreme Heat Warning", AlertSeverity: "extreme"},
	{ID: "denver", Label: "Mountain — Denver, CO", City: "Denver", Region: "CO", TimeZone: "America/Denver", Latitude: 39.7392, Longitude: -104.9903, Market: "Foothills Market", Venue: "Mountain View Community Center", AlertEvent: "High Wind Warning", AlertSeverity: "severe"},
	{ID: "los-angeles", Label: "Pacific — Los Angeles, CA", City: "Los Angeles", Region: "CA", TimeZone: "America/Los_Angeles", Latitude: 34.0522, Longitude: -118.2437, Market: "Sunset Neighborhood Market", Venue: "Harbor Community Center", AlertEvent: "Heat Advisory", AlertSeverity: "moderate"},
	{ID: "anchorage", Label: "Alaska — Anchorage, AK", City: "Anchorage", Region: "AK", TimeZone: "America/Anchorage", Latitude: 61.2181, Longitude: -149.9003, Market: "Northern Market", Venue: "Aurora Community Center", AlertEvent: "Winter Weather Advisory", AlertSeverity: "moderate"},
	{ID: "honolulu", Label: "Hawaii — Honolulu, HI", City: "Honolulu", Region: "HI", TimeZone: "Pacific/Honolulu", Latitude: 21.3069, Longitude: -157.8583, Market: "Island Market", Venue: "Oceanfront Community Center", AlertEvent: "High Surf Advisory", AlertSeverity: "moderate"},
}

func AllLocations() []LocationProfile {
	out := make([]LocationProfile, len(locationProfiles))
	copy(out, locationProfiles)
	return out
}

func LookupLocation(id string) (LocationProfile, bool) {
	id = strings.ToLower(strings.TrimSpace(id))
	for _, profile := range locationProfiles {
		if profile.ID == id {
			return profile, true
		}
	}
	return LocationProfile{}, false
}

func DefaultLocation() LocationProfile {
	profile, _ := LookupLocation("chicago")
	return profile
}

func AllScenarios() []Scenario {
	out := make([]Scenario, len(scenarios))
	copy(out, scenarios)
	return out
}

func Lookup(id string) (Scenario, bool) {
	id = strings.TrimSpace(id)
	for _, scenario := range scenarios {
		if scenario.ID == id {
			return scenario, true
		}
	}
	return Scenario{}, false
}

func Seed(appRoot, home, scenarioID string, now time.Time) error {
	return SeedForLocation(appRoot, home, scenarioID, DefaultLocation().ID, now)
}

func SeedForLocation(appRoot, home, scenarioID, locationID string, now time.Time) error {
	scenario, ok := Lookup(scenarioID)
	if !ok {
		return fmt.Errorf("unknown scenario %q", scenarioID)
	}
	profile, ok := LookupLocation(locationID)
	if !ok {
		return fmt.Errorf("unknown Showcase demo location %q", locationID)
	}
	loc, err := time.LoadLocation(profile.TimeZone)
	if err != nil {
		return fmt.Errorf("load Showcase demo time zone %s: %w", profile.TimeZone, err)
	}
	now = now.In(loc).Truncate(time.Second)
	today := day(now)
	config := filepath.Join(appRoot, "config")
	calendarDir := filepath.Join(appRoot, "calendars")
	if err := os.MkdirAll(config, 0755); err != nil {
		return err
	}
	if err := os.MkdirAll(calendarDir, 0755); err != nil {
		return err
	}

	people := []map[string]any{
		person("avery", "Avery", now.Add(-20*24*time.Hour)),
		person("jordan", "Jordan", now.Add(-19*24*time.Hour)),
		person("sam", "Sam", now.Add(-18*24*time.Hour)),
	}
	if err := writeJSON(filepath.Join(config, "household-people.json"), map[string]any{"schema": 1, "revision": 1, "people": people}, 0644); err != nil {
		return err
	}
	if err := seedBoard(home, now, profile); err != nil {
		return err
	}
	if err := seedChores(config, people, today, now); err != nil {
		return err
	}
	if err := seedRoutines(config, people, today, now); err != nil {
		return err
	}
	if err := seedMaintenance(config, today, now); err != nil {
		return err
	}
	if err := seedTodo(config, now, profile); err != nil {
		return err
	}
	if err := seedMessages(config, now, scenario.ID, profile); err != nil {
		return err
	}
	if err := seedSettings(config, scenario.ID, profile); err != nil {
		return err
	}
	if err := seedSchedules(config, today); err != nil {
		return err
	}
	if err := writeCalendar(filepath.Join(calendarDir, "showcase-studio.ics"), scenario.ID, today, now.Location(), profile); err != nil {
		return err
	}
	// The dashboard browser discovers local calendars through this manifest before
	// it requests the ICS file. Studio packages intentionally exclude mutable
	// runtime data, so seed the manifest with the fixture rather than relying on
	// the appliance-side calendar job to create it later.
	if err := writeJSON(filepath.Join(calendarDir, "calendars.json"), []any{
		map[string]any{
			"url":     "calendars/showcase-studio.ics",
			"name":    "Showcase Studio",
			"color":   "#7fd6a8",
			"enabled": true,
			"tag":     "showcase",
		},
	}, 0644); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(config, "chalkboard.json"), map[string]any{"version": 1, "strokes": []any{}}, 0644); err != nil {
		return err
	}
	return writeJSON(filepath.Join(config, "showcase-studio.json"), map[string]any{
		"schema": 1, "studio": "Dash-Go Showcase Studio", "scenario": scenario.ID,
		"scenarioTitle": scenario.Title, "createdAt": now.Format(time.RFC3339),
		"location": profile, "dataset": "city-household-v5", "fixtureSchema": 2,
		"externalAccounts": false, "presentationMode": true,
	}, 0644)
}

func WriteRuntimeMarker(workspaceRoot, scenario, locationID string, now time.Time) error {
	return writeJSON(filepath.Join(workspaceRoot, "SHOWCASE_RUNTIME.json"), map[string]any{
		"schema": 1, "scenario": scenario, "location": locationID, "createdAt": now.Local().Format(time.RFC3339),
		"privateWorkspace": true, "networkRequired": false,
	}, 0600)
}

func person(id, name string, created time.Time) map[string]any {
	stamp := created.Format(time.RFC3339)
	return map[string]any{"id": id, "name": name, "state": "active", "createdAt": stamp, "updatedAt": stamp, "archivedAt": ""}
}

func seedBoard(home string, now time.Time, profile LocationProfile) error {
	board := map[string]any{"schema": 3, "settings": map[string]any{"showUrgentAlertsOnDashboard": true}, "notes": []any{
		map[string]any{"id": "board-urgent", "text": fmt.Sprintf("Weather plan: check the forecast before dinner near %s.", profile.City), "scope": "household", "priority": "urgent", "state": "active", "pinned": false, "createdAt": now.Add(-15 * time.Minute).Format(time.RFC3339), "updatedAt": now.Add(-15 * time.Minute).Format(time.RFC3339), "expiresAt": now.Add(48 * time.Hour).Format(time.RFC3339)},
		map[string]any{"id": "board-pinned", "text": fmt.Sprintf("Pick up the household order from %s after school.", profile.Market), "scope": "household", "priority": "normal", "state": "active", "pinned": true, "createdAt": now.Add(-time.Hour).Format(time.RFC3339), "updatedAt": now.Add(-30 * time.Minute).Format(time.RFC3339), "expiresAt": ""},
		map[string]any{"id": "direct-avery-jordan", "text": "I saved you the seat by the window.", "scope": "direct", "priority": "normal", "state": "active", "senderPersonId": "avery", "senderNameSnapshot": "Avery", "recipientPersonId": "jordan", "recipientNameSnapshot": "Jordan", "recipientReadAt": "", "createdAt": now.Add(-7 * time.Minute).Format(time.RFC3339), "updatedAt": now.Add(-7 * time.Minute).Format(time.RFC3339)},
		map[string]any{"id": "direct-sam-avery", "text": "Can we make tacos tomorrow?", "scope": "direct", "priority": "normal", "state": "active", "senderPersonId": "sam", "senderNameSnapshot": "Sam", "recipientPersonId": "avery", "recipientNameSnapshot": "Avery", "recipientReadAt": "", "createdAt": now.Add(-3 * time.Minute).Format(time.RFC3339), "updatedAt": now.Add(-3 * time.Minute).Format(time.RFC3339)},
	}}
	if err := writeJSON(filepath.Join(home, ".dashboard-family-board.json"), board, 0600); err != nil {
		return err
	}
	return writeJSON(filepath.Join(home, ".dashboard-family-board-inbox-pins.json"), map[string]any{"schema": 1, "pins": map[string]any{}}, 0600)
}

func seedChores(config string, people []map[string]any, today time.Time, now time.Time) error {
	peopleSnap := []any{}
	for _, p := range people {
		peopleSnap = append(peopleSnap, map[string]any{"id": p["id"], "name": p["name"]})
	}
	chores := map[string]any{"schema": 1, "revision": 1, "people": peopleSnap, "chores": []any{
		map[string]any{"id": "dishes", "name": "Dishes", "createdAt": now.Add(-24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "daily", "day": 0, "every": 1, "anchorDate": dateText(today.AddDate(0, 0, -1))}, "effort": 1, "eligible": []string{"avery", "jordan", "sam"}},
		map[string]any{"id": "recycling", "name": "Take out recycling", "createdAt": now.Add(-24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "weekly", "day": int(today.Weekday()), "every": 1, "anchorDate": dateText(today.AddDate(0, 0, -7))}, "effort": 2, "eligible": []string{"avery", "jordan"}},
		map[string]any{"id": "litter", "name": "Refresh litter box", "createdAt": now.Add(-24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "days", "day": 0, "every": 3, "anchorDate": dateText(today.AddDate(0, 0, -3))}, "effort": 2, "eligible": []string{"sam", "jordan"}},
		map[string]any{"id": "floors", "name": "Vacuum main floor", "createdAt": now.Add(-24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "weekly", "day": int(today.AddDate(0, 0, 1).Weekday()), "every": 1, "anchorDate": dateText(today.AddDate(0, 0, -6))}, "effort": 3, "eligible": []string{"avery", "sam"}},
	}, "assignments": []any{
		map[string]any{"id": "asg-dishes-today", "date": dateText(today), "choreId": "dishes", "choreName": "Dishes", "personId": "avery", "personName": "Avery", "status": "assigned", "source": "showcase"},
		map[string]any{"id": "asg-recycling-today", "date": dateText(today), "choreId": "recycling", "choreName": "Take out recycling", "personId": "jordan", "personName": "Jordan", "status": "assigned", "source": "showcase"},
		map[string]any{"id": "asg-litter-tomorrow", "date": dateText(today.AddDate(0, 0, 1)), "choreId": "litter", "choreName": "Refresh litter box", "personId": "sam", "personName": "Sam", "status": "assigned", "source": "showcase"},
	}, "settings": map[string]any{"horizonDays": 14, "calendarOutputEnabled": true}}
	return writeJSON(filepath.Join(config, "chore-wheel.json"), chores, 0644)
}

func seedRoutines(config string, people []map[string]any, today time.Time, now time.Time) error {
	peopleSnap := []any{}
	for _, p := range people {
		peopleSnap = append(peopleSnap, map[string]any{"id": p["id"], "name": p["name"]})
	}
	routines := map[string]any{"schema": 1, "revision": 1, "settings": map[string]any{"calendarOutputEnabled": true, "calendarHorizonDays": 56, "defaultCalendarEnabled": true}, "people": peopleSnap, "routines": []any{
		map[string]any{"id": "morning", "title": "Morning ready", "note": "A calm before-school checklist.", "steps": []any{map[string]any{"id": "pack", "text": "Pack bag"}, map[string]any{"id": "breakfast", "text": "Breakfast"}, map[string]any{"id": "teeth", "text": "Brush teeth"}}, "assignments": []any{map[string]any{"id": "morning-avery", "personId": "avery", "personNameSnapshot": "Avery", "calendarEnabled": true, "schedule": map[string]any{"kind": "days", "every": 1, "startOn": dateText(today.AddDate(0, 0, -14)), "endOn": "", "month": 1, "day": 1, "time": "07:15", "allDay": false}}}},
		map[string]any{"id": "evening", "title": "Evening reset", "note": "Close the day together.", "steps": []any{map[string]any{"id": "counter", "text": "Clear counters"}, map[string]any{"id": "laundry", "text": "Start laundry"}, map[string]any{"id": "calendar", "text": "Check tomorrow"}}, "assignments": []any{map[string]any{"id": "evening-jordan", "personId": "jordan", "personNameSnapshot": "Jordan", "calendarEnabled": true, "schedule": map[string]any{"kind": "days", "every": 1, "startOn": dateText(today.AddDate(0, 0, -14)), "endOn": "", "month": 1, "day": 1, "time": "20:00", "allDay": false}}}},
	}, "occurrences": []any{}, "history": []any{}}
	return writeJSON(filepath.Join(config, "routines.json"), routines, 0644)
}

func seedMaintenance(config string, today time.Time, now time.Time) error {
	maintenance := map[string]any{"schema": 2, "settings": map[string]any{"defaultCalendarEnabled": true, "calendarOutputEnabled": true, "dueSoonDays": 30}, "tasks": []any{
		maintenanceTask("replace-filter", "Replace HVAC filter", "Use the MERV 11 filter in the hall closet.", today.AddDate(0, 0, 1), today.AddDate(0, 0, -89), "jordan", "Jordan", now),
		maintenanceTask("test-detectors", "Test smoke detectors", "Check every bedroom and replace weak batteries.", today, today.AddDate(0, 0, -181), "avery", "Avery", now),
		maintenanceTask("clean-gutters", "Clean gutters", "Schedule before autumn leaves fall.", today.AddDate(0, 0, 28), today.AddDate(0, 0, -150), "sam", "Sam", now),
	}, "history": []any{}}
	return writeJSON(filepath.Join(config, "maintenance-tracker.json"), maintenance, 0644)
}

func maintenanceTask(id, title, note string, due, complete time.Time, personID, personName string, now time.Time) map[string]any {
	return map[string]any{"id": id, "title": title, "note": note, "state": "active", "cadence": map[string]any{"unit": "months", "every": 3}, "lastCompletedOn": dateText(complete), "nextDueOn": dateText(due), "calendarEnabled": true, "createdAt": now.Add(-1000 * time.Hour).Format(time.RFC3339), "updatedAt": now.Add(-20 * time.Minute).Format(time.RFC3339), "archivedAt": "", "responsiblePersonId": personID, "responsiblePersonNameSnapshot": personName}
}

func seedTodo(config string, now time.Time, profile LocationProfile) error {
	todoDir := filepath.Join(config, "todo")
	if err := os.MkdirAll(todoDir, 0755); err != nil {
		return err
	}
	millis := now.UnixMilli()
	if err := writeJSON(filepath.Join(todoDir, "_lists.json"), map[string]any{"lists": []any{map[string]any{"id": "local-todo", "displayName": "To Do", "origin": "local"}, map[string]any{"id": "local-grocery", "displayName": "Grocery", "origin": "local"}}, "updatedAt": millis}, 0644); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(todoDir, todoFile("local-todo")), map[string]any{"version": 1, "listId": "local-todo", "displayName": "To Do", "tasks": []any{
		todoTask("todo-pay-bill", "Pay electricity bill", "notStarted", "high", "avery", "Avery", millis), todoTask("todo-call", "Call dentist for appointment", "notStarted", "normal", "jordan", "Jordan", millis), map[string]any{"id": "todo-done", "title": "Confirm weekend plans", "status": "completed", "importance": "normal"},
	}, "pendingOps": []any{}}, 0644); err != nil {
		return err
	}
	return writeJSON(filepath.Join(todoDir, todoFile("local-grocery")), map[string]any{"version": 1, "listId": "local-grocery", "displayName": "Grocery", "tasks": []any{
		map[string]any{"id": "groceries-city-pickup", "title": profile.Market + " pickup", "status": "notStarted", "importance": "normal"}, map[string]any{"id": "groceries-milk", "title": "Milk", "status": "notStarted", "importance": "normal"}, map[string]any{"id": "groceries-tortillas", "title": "Tortillas", "status": "notStarted", "importance": "normal"}, map[string]any{"id": "groceries-coffee", "title": "Coffee", "status": "notStarted", "importance": "normal"}, map[string]any{"id": "groceries-apples", "title": "Apples", "status": "completed", "importance": "normal"},
	}, "pendingOps": []any{}}, 0644)
}

func todoTask(id, title, status, importance, personID, personName string, millis int64) map[string]any {
	return map[string]any{"id": id, "title": title, "status": status, "importance": importance, "dashgoAssignment": map[string]any{"personId": personID, "personNameSnapshot": personName, "assignedAt": millis}}
}
func todoFile(id string) string {
	sum := sha256.Sum256([]byte(id))
	return fmt.Sprintf("%x.json", sum[:16])
}

func seedMessages(config string, now time.Time, scenario string, profile LocationProfile) error {
	_ = scenario
	messages := []any{
		map[string]any{"id": 1, "text": "A shared calendar is more useful when the whole household can see it.", "weight": 45, "origin": "studio-normal"},
		map[string]any{"id": 2, "text": "Small household wins add up — one helpful task at a time.", "weight": 45, "origin": "studio-normal"},
		map[string]any{"id": 3, "text": fmt.Sprintf("Today’s Studio household is centered on %s, %s.", profile.City, profile.Region), "weight": 20, "origin": "studio-location"},
		map[string]any{"id": 4, "text": "Groceries, chores, routines, and messages — together in one family dashboard.", "weight": 8, "origin": "studio-discovery"},
		map[string]any{"id": 5, "text": "Like this layout? Dash-Go can be configured for your own home.", "weight": 8, "origin": "studio-discovery"},
		map[string]any{"id": 6, "text": "This is Dash-Go Showcase Studio. Everything here is safe to explore and resets automatically.", "weight": 8, "origin": "studio-discovery"},
		map[string]any{"id": 7, "text": "Try the App Launcher to explore household tools built into Dash-Go.", "weight": 8, "origin": "studio-discovery"},
	}
	files := []struct {
		name  string
		value any
	}{
		{"compliments.json", map[string]any{"messages": messages, "defaultsCleared": true, "defaultsSeeded": false, "removedDefaults": []any{}, "defaultEdits": map[string]any{}, "version": 4}},
		{"message-cache.json", map[string]any{"items": []any{}, "generatedAt": now.UnixMilli(), "sources": []any{}, "enabled": []any{}, "sourceStatus": []any{}}},
		{"message-sources.json", map[string]any{"enabled": []any{}, "updatedAt": now.UnixMilli()}},
		{"message-cache-overrides.json", map[string]any{"removed": []any{}, "edits": map[string]any{}}}, {"temp-messages.json", []any{}}, {"scheduled-messages.json", []any{}},
	}
	for _, file := range files {
		if err := writeJSON(filepath.Join(config, file.name), file.value, 0644); err != nil {
			return err
		}
	}
	return nil
}

func seedSettings(config, scenario string, profile LocationProfile) error {
	local := fmt.Sprintf(`// Generated for Dash-Go Showcase Studio.
window.DASHBOARD_LOCAL = {
  demoMode: false,
  lat: %.4f,
  lon: %.4f,
  locationName: %q,
  showcaseTimeZone: %q,
  tempUnit: "fahrenheit",
  windUnit: "mph",
  theme: "basic",
  weatherProviders: ["openmeteo"],
  weatherDays: 7,
  showEventMaps: true,
  showInteractiveMaps: false
};
`, profile.Latitude, profile.Longitude, profile.City+", "+profile.Region, profile.TimeZone)
	if err := writeText(filepath.Join(config, "config.local.js"), local, 0644); err != nil {
		return err
	}
	theme := "basic"
	if scenario == "themes-seasons" {
		theme = "autumn"
	}
	if scenario == "capture-gallery" {
		theme = "midnight"
	}
	settings := map[string]any{"demoMode": false, "dashboardProfile": "enhanced", "showEventMaps": true, "showInteractiveMaps": false, "weatherDetailMode": "expanded", "showUV": true, "showAQI": true, "theme": theme, "todo": map[string]any{"syncMode": "local", "map": map[string]any{"todo": "local-todo", "grocery": "local-grocery"}, "dashboardDock": false, "dashboardDockSlots": map[string]any{"todo": true, "grocery": true}}}
	return writeJSON(filepath.Join(config, "settings.json"), settings, 0644)
}

func seedSchedules(config string, today time.Time) error {
	schedules := map[string]any{"schema": 1, "paydays": []any{
		map[string]any{"id": "household-payday", "label": "Household payday", "enabled": true, "kind": "every-weeks", "start": dateText(previousWeekday(today, time.Friday)), "everyWeeks": 2, "adjustment": map[string]any{"mode": "previous-business-day", "weekends": true, "holidayLayers": []string{"civil"}}},
		map[string]any{"id": "side-payday", "label": "Side income", "enabled": true, "kind": "monthly-dates", "days": []int{14, 29}, "adjustment": map[string]any{"mode": "none"}},
	}, "pickups": []any{
		map[string]any{"id": "trash", "label": "Trash pickup", "enabled": true, "weekday": "Tuesday", "everyWeeks": 1, "start": dateText(previousWeekday(today, time.Tuesday)), "adjustment": map[string]any{"mode": "shift-forward", "days": 1}},
		map[string]any{"id": "recycling", "label": "Recycling pickup", "enabled": true, "weekday": "Tuesday", "everyWeeks": 2, "start": dateText(previousWeekday(today, time.Tuesday)), "adjustment": map[string]any{"mode": "none"}},
	}, "overrides": []any{map[string]any{"ruleId": "trash", "nominalDate": dateText(today.AddDate(0, 0, 7)), "action": "move", "actualDate": dateText(today.AddDate(0, 0, 8))}}}
	return writeJSON(filepath.Join(config, "household-schedules.json"), schedules, 0644)
}

func writeCalendar(path, scenario string, today time.Time, loc *time.Location, profile LocationProfile) error {
	lines := []string{"BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Dash-Go Showcase Studio//EN", "CALSCALE:GREGORIAN", "X-WR-CALNAME:Showcase Studio"}
	addAllDay := func(uid, title string, start time.Time) {
		lines = append(lines, "BEGIN:VEVENT", "UID:"+uid, "DTSTAMP:"+icsStamp(today), "DTSTART;VALUE=DATE:"+icsDate(start), "SUMMARY:"+icsText(title), "END:VEVENT")
	}
	addTimed := func(uid, title string, start, end time.Time, location, desc string) {
		lines = append(lines, "BEGIN:VEVENT", "UID:"+uid, "DTSTAMP:"+icsStamp(today), "DTSTART:"+icsStamp(start), "DTEND:"+icsStamp(end), "SUMMARY:"+icsText(title))
		if location != "" {
			lines = append(lines, "LOCATION:"+icsText(location))
		}
		if desc != "" {
			lines = append(lines, "DESCRIPTION:"+icsText(desc))
		}
		lines = append(lines, "END:VEVENT")
	}
	addAllDay("showcase-birthday", "Avery’s birthday", today.AddDate(0, 0, 5))
	addAllDay("showcase-trip", "Family road trip", today.AddDate(0, 0, 12))
	base := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, loc)
	addTimed("showcase-breakfast", "Breakfast together", base.Add(7*time.Hour+30*time.Minute), base.Add(8*time.Hour+15*time.Minute), "Kitchen", "A relaxed start to the day.")
	addTimed("showcase-school", "School showcase", base.Add(8*time.Hour+30*time.Minute), base.Add(9*time.Hour+30*time.Minute), profile.Venue, "Bring the blue folder.")
	addTimed("showcase-dinner", "Dinner reservation", base.Add(18*time.Hour), base.Add(19*time.Hour+30*time.Minute), profile.City+" dinner spot", "A fictional city-shaped location supports the map preview path.")
	if scenario == "busy-calendar" || scenario == "capture-gallery" {
		for i := 0; i < 7; i++ {
			start := base.Add(time.Duration(9+i) * time.Hour)
			addTimed(fmt.Sprintf("showcase-busy-%d", i), fmt.Sprintf("Planning block %d", i+1), start, start.Add(75*time.Minute), profile.City+" planning room", "Dense calendar fixture.")
		}
	}
	if scenario == "family-flow" {
		addTimed("showcase-family", "Family meeting", base.Add(19*time.Hour+45*time.Minute), base.Add(20*time.Hour+20*time.Minute), profile.Venue, "Review chores, routines, and weekend plans.")
	}
	lines = append(lines, "END:VCALENDAR", "")
	return writeText(path, strings.Join(lines, "\r\n"), 0644)
}

func writeJSON(path string, value any, perm os.FileMode) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	return writeBytes(path, append(data, '\n'), perm)
}
func writeText(path, text string, perm os.FileMode) error {
	return writeBytes(path, []byte(text), perm)
}
func writeBytes(path string, data []byte, perm os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, perm); err != nil {
		return err
	}
	if err := os.Chmod(tmp, perm); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}
func day(value time.Time) time.Time {
	return time.Date(value.Year(), value.Month(), value.Day(), 0, 0, 0, 0, value.Location())
}
func dateText(value time.Time) string { return day(value).Format("2006-01-02") }
func previousWeekday(value time.Time, weekday time.Weekday) time.Time {
	value = day(value)
	for value.Weekday() != weekday {
		value = value.AddDate(0, 0, -1)
	}
	return value
}
func icsDate(value time.Time) string  { return day(value).Format("20060102") }
func icsStamp(value time.Time) string { return value.UTC().Format("20060102T150405Z") }
func icsText(value string) string {
	value = strings.NewReplacer("\\", "\\\\", ",", "\\,", ";", "\\;", "\n", "\\n").Replace(value)
	return value
}

// stableScenarioIDs supports compact deterministic source tests without exposing mutable globals.
func stableScenarioIDs() []string {
	ids := make([]string, 0, len(scenarios))
	for _, s := range scenarios {
		ids = append(ids, s.ID)
	}
	sort.Strings(ids)
	return ids
}
