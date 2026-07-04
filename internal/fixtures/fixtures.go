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
	{ID: "everyday-household", Title: "Everyday Household", Kind: "START HERE", Description: "A polished family dashboard with a full calendar gallery: multiday plans, household chores, routines, maintenance, messages, To Do, Grocery, and weather-ready settings."},
	{ID: "busy-calendar", Title: "Busy Calendar", Kind: "CALENDAR", Description: "A full calendar gallery with color-coded feeds, all-day spans, chores, routines, maintenance, locations, and a dense day-timeline exploration path."},
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
	// Studio intentionally ships several independent local calendars rather than
	// placing every event in one catch-all feed. This keeps the calendar chooser,
	// colors, and visibility controls representative of a real household setup.
	if err := seedCalendars(calendarDir, scenario.ID, today, now.Location(), profile); err != nil {
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
		map[string]any{"id": "lunches", "name": "Prepare lunches", "createdAt": now.Add(-24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "weekdays", "day": 0, "every": 1, "anchorDate": dateText(today)}, "effort": 2, "eligible": []string{"avery", "jordan", "sam"}},
		map[string]any{"id": "plants", "name": "Water plants", "createdAt": now.Add(-24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "days", "day": 0, "every": 4, "anchorDate": dateText(today.AddDate(0, 0, -4))}, "effort": 1, "eligible": []string{"jordan", "sam"}},
		map[string]any{"id": "mail", "name": "Sort mail", "createdAt": now.Add(-24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "weekly", "day": int(today.AddDate(0, 0, 3).Weekday()), "every": 1, "anchorDate": dateText(today.AddDate(0, 0, -4))}, "effort": 1, "eligible": []string{"avery", "jordan"}},
	}, "assignments": []any{
		showcaseChoreAssignment("asg-dishes-yesterday", today.AddDate(0, 0, -1), "dishes", "Dishes", "jordan", "Jordan", "completed"),
		showcaseChoreAssignment("asg-dishes-today", today, "dishes", "Dishes", "avery", "Avery", "assigned"),
		showcaseChoreAssignment("asg-recycling-today", today, "recycling", "Take out recycling", "jordan", "Jordan", "assigned"),
		showcaseChoreAssignment("asg-litter-tomorrow", today.AddDate(0, 0, 1), "litter", "Refresh litter box", "sam", "Sam", "assigned"),
		showcaseChoreAssignment("asg-floors-plus2", today.AddDate(0, 0, 2), "floors", "Vacuum main floor", "avery", "Avery", "assigned"),
		showcaseChoreAssignment("asg-mail-plus3", today.AddDate(0, 0, 3), "mail", "Sort mail", "jordan", "Jordan", "assigned"),
		showcaseChoreAssignment("asg-plants-plus4", today.AddDate(0, 0, 4), "plants", "Water plants", "sam", "Sam", "assigned"),
		showcaseChoreAssignment("asg-lunches-plus5", today.AddDate(0, 0, 5), "lunches", "Prepare lunches", "avery", "Avery", "assigned"),
		showcaseChoreAssignment("asg-dishes-plus6", today.AddDate(0, 0, 6), "dishes", "Dishes", "sam", "Sam", "assigned"),
		showcaseChoreAssignment("asg-recycling-plus7", today.AddDate(0, 0, 7), "recycling", "Take out recycling", "jordan", "Jordan", "assigned"),
		showcaseChoreAssignment("asg-litter-plus8", today.AddDate(0, 0, 8), "litter", "Refresh litter box", "sam", "Sam", "assigned"),
		showcaseChoreAssignment("asg-floors-plus10", today.AddDate(0, 0, 10), "floors", "Vacuum main floor", "avery", "Avery", "assigned"),
		showcaseChoreAssignment("asg-plants-plus12", today.AddDate(0, 0, 12), "plants", "Water plants", "jordan", "Jordan", "assigned"),
		showcaseChoreAssignment("asg-lunches-plus14", today.AddDate(0, 0, 14), "lunches", "Prepare lunches", "sam", "Sam", "assigned"),
	}, "settings": map[string]any{"horizonDays": 21, "calendarOutputEnabled": true}}
	return writeJSON(filepath.Join(config, "chore-wheel.json"), chores, 0644)
}

func showcaseChoreAssignment(id string, when time.Time, choreID, choreName, personID, personName, status string) map[string]any {
	return map[string]any{"id": id, "date": dateText(when), "choreId": choreID, "choreName": choreName, "personId": personID, "personName": personName, "status": status, "source": "showcase"}
}

func seedRoutines(config string, people []map[string]any, today time.Time, now time.Time) error {
	peopleSnap := []any{}
	for _, p := range people {
		peopleSnap = append(peopleSnap, map[string]any{"id": p["id"], "name": p["name"]})
	}
	routines := map[string]any{"schema": 1, "revision": 1, "settings": map[string]any{"calendarOutputEnabled": true, "calendarHorizonDays": 56, "defaultCalendarEnabled": true}, "people": peopleSnap, "routines": []any{
		map[string]any{"id": "morning", "title": "Morning ready", "note": "A calm before-school checklist.", "steps": []any{map[string]any{"id": "pack", "text": "Pack bag"}, map[string]any{"id": "breakfast", "text": "Breakfast"}, map[string]any{"id": "teeth", "text": "Brush teeth"}}, "assignments": []any{map[string]any{"id": "morning-avery", "personId": "avery", "personNameSnapshot": "Avery", "calendarEnabled": true, "schedule": map[string]any{"kind": "weekdays", "every": 1, "weekdays": []string{"MO", "TU", "WE", "TH", "FR"}, "startOn": dateText(today.AddDate(0, 0, -14)), "endOn": "", "month": 1, "day": 1, "time": "07:15", "allDay": false}}}},
		map[string]any{"id": "school-launch", "title": "School launch", "note": "Lunch, library item, and a quick weather check.", "steps": []any{map[string]any{"id": "lunch", "text": "Lunch check"}, map[string]any{"id": "library", "text": "Library item"}, map[string]any{"id": "weather", "text": "Weather layer"}}, "assignments": []any{map[string]any{"id": "launch-sam", "personId": "sam", "personNameSnapshot": "Sam", "calendarEnabled": true, "schedule": map[string]any{"kind": "weekdays", "every": 1, "weekdays": []string{"MO", "TU", "WE", "TH", "FR"}, "startOn": dateText(today.AddDate(0, 0, -14)), "endOn": "", "month": 1, "day": 1, "time": "07:45", "allDay": false}}}},
		map[string]any{"id": "evening", "title": "Evening reset", "note": "Close the day together.", "steps": []any{map[string]any{"id": "counter", "text": "Clear counters"}, map[string]any{"id": "laundry", "text": "Start laundry"}, map[string]any{"id": "calendar", "text": "Check tomorrow"}}, "assignments": []any{map[string]any{"id": "evening-jordan", "personId": "jordan", "personNameSnapshot": "Jordan", "calendarEnabled": true, "schedule": map[string]any{"kind": "days", "every": 1, "weekdays": []string{}, "startOn": dateText(today.AddDate(0, 0, -14)), "endOn": "", "month": 1, "day": 1, "time": "20:00", "allDay": false}}}},
		map[string]any{"id": "sunday-reset", "title": "Sunday reset", "note": "Refresh the week without over-scheduling it.", "steps": []any{map[string]any{"id": "calendar", "text": "Review calendar"}, map[string]any{"id": "grocery", "text": "Check grocery list"}, map[string]any{"id": "laundry", "text": "Start one laundry load"}}, "assignments": []any{map[string]any{"id": "reset-family", "personId": "jordan", "personNameSnapshot": "Jordan", "calendarEnabled": true, "schedule": map[string]any{"kind": "weekly", "every": 1, "weekdays": []string{"SU"}, "startOn": dateText(today.AddDate(0, 0, -21)), "endOn": "", "month": 1, "day": 1, "time": "16:30", "allDay": false}}}},
	}, "occurrences": []any{}, "history": []any{}}
	return writeJSON(filepath.Join(config, "routines.json"), routines, 0644)
}

func seedMaintenance(config string, today time.Time, now time.Time) error {
	maintenance := map[string]any{"schema": 2, "settings": map[string]any{"defaultCalendarEnabled": true, "calendarOutputEnabled": true, "dueSoonDays": 30}, "tasks": []any{
		maintenanceTask("replace-filter", "Replace HVAC filter", "Use the MERV 11 filter in the hall closet.", today.AddDate(0, 0, 1), today.AddDate(0, 0, -89), "jordan", "Jordan", now),
		maintenanceTask("test-detectors", "Test smoke detectors", "Check every bedroom and replace weak batteries.", today, today.AddDate(0, 0, -181), "avery", "Avery", now),
		maintenanceTask("clean-gutters", "Clean gutters", "Schedule before autumn leaves fall.", today.AddDate(0, 0, 16), today.AddDate(0, 0, -150), "sam", "Sam", now),
		maintenanceTask("water-filter", "Replace water filter", "Use the replacement stored with appliance manuals.", today.AddDate(0, 0, 9), today.AddDate(0, 0, -175), "avery", "Avery", now),
		maintenanceTask("camera-batteries", "Check door camera batteries", "Confirm the entry camera and mailbox sensor are charged.", today.AddDate(0, 0, 23), today.AddDate(0, 0, -340), "jordan", "Jordan", now),
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

type showcaseCalendarFixture struct {
	File   string
	Name   string
	Color  string
	Owner  string
	Tag    string
	Events []showcaseCalendarEvent
}

type showcaseCalendarEvent struct {
	UID         string
	Title       string
	Start       time.Time
	End         time.Time
	AllDay      bool
	Location    string
	Description string
}

func seedCalendars(calendarDir, scenario string, today time.Time, loc *time.Location, profile LocationProfile) error {
	fixtures := showcaseCalendars(scenario, today, loc, profile)
	manifest := make([]any, 0, len(fixtures))
	for _, fixture := range fixtures {
		if err := writeCalendar(filepath.Join(calendarDir, fixture.File), fixture.Name, today, fixture.Events); err != nil {
			return err
		}
		entry := map[string]any{
			"url":     "calendars/" + fixture.File,
			"name":    fixture.Name,
			"color":   fixture.Color,
			"enabled": true,
			"tag":     "showcase",
		}
		if fixture.Owner != "" {
			entry["owner"] = fixture.Owner
		}
		if fixture.Tag != "" {
			entry["tag"] = fixture.Tag
		}
		manifest = append(manifest, entry)
	}
	// The dashboard browser discovers local calendars through this manifest before
	// it requests their ICS files. Studio packages intentionally exclude mutable
	// runtime data, so seed both user-managed and Dash-Go-owned feed snapshots.
	return writeJSON(filepath.Join(calendarDir, "calendars.json"), manifest, 0644)
}

func showcaseCalendars(scenario string, today time.Time, loc *time.Location, profile LocationProfile) []showcaseCalendarFixture {
	base := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, loc)
	monday := weekdayOnOrAfter(base, time.Monday)
	friday := weekdayOnOrAfter(base, time.Friday)
	family := showcaseCalendarFixture{
		File: "family.green.ics", Name: "Family", Color: "#8fc4a6",
		Events: []showcaseCalendarEvent{
			timedShowcaseEvent("family-breakfast", "Breakfast together", base.Add(7*time.Hour+30*time.Minute), base.Add(8*time.Hour+15*time.Minute), "Kitchen", "A relaxed start to the day."),
			timedShowcaseEvent("family-dinner", "Dinner reservation", base.Add(18*time.Hour), base.Add(19*time.Hour+30*time.Minute), profile.City+" dinner spot", "A fictional city-shaped location supports the map preview path."),
			timedShowcaseEvent("family-picnic", "Park picnic", base.AddDate(0, 0, 2).Add(12*time.Hour), base.AddDate(0, 0, 2).Add(14*time.Hour), "Riverside park", "Bring the blue blanket and the picnic list."),
			allDayShowcaseEvent("family-birthday", "Avery’s birthday", base.AddDate(0, 0, 5)),
			timedShowcaseEvent("family-call", "Grandparent video call", base.AddDate(0, 0, 7).Add(18*time.Hour+30*time.Minute), base.AddDate(0, 0, 7).Add(19*time.Hour), "Living room", "A short family check-in."),
			allDayShowcaseEvent("family-conference", "Family-teacher conference", base.AddDate(0, 0, 9)),
			multiDayShowcaseEvent("family-trip", "Family road trip", base.AddDate(0, 0, 12), base.AddDate(0, 0, 17)),
			timedShowcaseEvent("family-return", "Unpack and reset", base.AddDate(0, 0, 17).Add(17*time.Hour), base.AddDate(0, 0, 17).Add(18*time.Hour), "Home", "Return-home checklist after the multi-day trip."),
			multiDayShowcaseEvent("family-visitors", "Cousins visiting", base.AddDate(0, 0, 24), base.AddDate(0, 0, 27)),
		},
	}
	school := showcaseCalendarFixture{
		File: "school.blue.ics", Name: "School", Color: "#8bb4d4",
		Events: []showcaseCalendarEvent{
			timedShowcaseEvent("school-showcase", "School showcase", base.Add(8*time.Hour+30*time.Minute), base.Add(9*time.Hour+30*time.Minute), profile.Venue, "Bring the blue folder."),
			timedShowcaseEvent("school-club", "Library club", base.Add(15*time.Hour+30*time.Minute), base.Add(16*time.Hour+30*time.Minute), profile.Venue, "A low-key after-school activity."),
			allDayShowcaseEvent("school-reading", "Reading challenge starts", base.AddDate(0, 0, 3)),
			timedShowcaseEvent("school-lab", "Science lab", monday.AddDate(0, 0, 1).Add(15*time.Hour+15*time.Minute), monday.AddDate(0, 0, 1).Add(16*time.Hour+30*time.Minute), profile.Venue, "Bring the completed observation sheet."),
			timedShowcaseEvent("school-workshop", "Museum workshop", friday.AddDate(0, 0, 7).Add(10*time.Hour), friday.AddDate(0, 0, 7).Add(12*time.Hour), profile.Venue, "A timed event with a location for the map preview."),
			allDayShowcaseEvent("school-supplies", "Class supply check", base.AddDate(0, 0, 15)),
			multiDayShowcaseEvent("school-camp", "Summer learning camp", base.AddDate(0, 0, 19), base.AddDate(0, 0, 23)),
		},
	}
	home := showcaseCalendarFixture{
		File: "home.amber.ics", Name: "Home", Color: "#cda76a",
		Events: []showcaseCalendarEvent{
			allDayShowcaseEvent("home-trash", "Trash pickup", base.AddDate(0, 0, 1)),
			allDayShowcaseEvent("home-recycling", "Recycling pickup", base.AddDate(0, 0, 4)),
			timedShowcaseEvent("home-prep", "Meal prep", base.Add(16*time.Hour), base.Add(17*time.Hour), "Kitchen", "Set out ingredients for tomorrow."),
			timedShowcaseEvent("home-grocery", "Grocery pickup", base.AddDate(0, 0, 2).Add(17*time.Hour), base.AddDate(0, 0, 2).Add(17*time.Hour+30*time.Minute), profile.Market, "The local Grocery list has the matching order."),
			timedShowcaseEvent("home-laundry", "Laundry reset", base.AddDate(0, 0, 6).Add(10*time.Hour), base.AddDate(0, 0, 6).Add(11*time.Hour), "Laundry room", "A small home-maintenance block."),
			multiDayShowcaseEvent("home-project", "Garage refresh", base.AddDate(0, 0, 14), base.AddDate(0, 0, 16)),
			timedShowcaseEvent("home-porch", "Porch plants", base.AddDate(0, 0, 20).Add(9*time.Hour), base.AddDate(0, 0, 20).Add(10*time.Hour), "Front porch", "A lightweight home project."),
		},
	}
	plans := showcaseCalendarFixture{
		File: "plans.violet.ics", Name: "Plans", Color: "#9a8fb0",
		Events: []showcaseCalendarEvent{
			allDayShowcaseEvent("plans-weekend", "Weekend plan", base.AddDate(0, 0, 3)),
			timedShowcaseEvent("plans-coffee", "Coffee with a friend", monday.AddDate(0, 0, 2).Add(8*time.Hour+30*time.Minute), monday.AddDate(0, 0, 2).Add(9*time.Hour+15*time.Minute), "Neighborhood cafe", "A short timed appointment."),
			timedShowcaseEvent("plans-volunteer", "Volunteer shift", base.AddDate(0, 0, 8).Add(9*time.Hour), base.AddDate(0, 0, 8).Add(11*time.Hour), profile.Venue, "An event card with location and detail."),
			timedShowcaseEvent("plans-movie", "Movie night", base.AddDate(0, 0, 10).Add(19*time.Hour), base.AddDate(0, 0, 10).Add(21*time.Hour), "Home", "A calm evening plan."),
			timedShowcaseEvent("plans-dentist", "Dentist appointment", base.AddDate(0, 0, 18).Add(14*time.Hour), base.AddDate(0, 0, 18).Add(15*time.Hour), "Downtown dental office", "A compact appointment that exercises map content."),
			timedShowcaseEvent("plans-date", "Date night", base.AddDate(0, 0, 21).Add(18*time.Hour+30*time.Minute), base.AddDate(0, 0, 21).Add(20*time.Hour+30*time.Minute), profile.City+" arts district", "A second evening plan for calendar variety."),
		},
	}
	chores := showcaseCalendarFixture{
		File: "chore-wheel.ics", Name: "Chores", Color: "#7fc4c4", Owner: "chore-wheel",
		Events: []showcaseCalendarEvent{
			allDayShowcaseEvent("chore-dishes-today", "Dishes — Avery", base),
			allDayShowcaseEvent("chore-recycling-today", "Take out recycling — Jordan", base),
			allDayShowcaseEvent("chore-litter-plus1", "Refresh litter box — Sam", base.AddDate(0, 0, 1)),
			allDayShowcaseEvent("chore-floors-plus2", "Vacuum main floor — Avery", base.AddDate(0, 0, 2)),
			allDayShowcaseEvent("chore-mail-plus3", "Sort mail — Jordan", base.AddDate(0, 0, 3)),
			allDayShowcaseEvent("chore-plants-plus4", "Water plants — Sam", base.AddDate(0, 0, 4)),
			allDayShowcaseEvent("chore-lunches-plus5", "Prepare lunches — Avery", base.AddDate(0, 0, 5)),
			allDayShowcaseEvent("chore-dishes-plus6", "Dishes — Sam", base.AddDate(0, 0, 6)),
			allDayShowcaseEvent("chore-recycling-plus7", "Take out recycling — Jordan", base.AddDate(0, 0, 7)),
			allDayShowcaseEvent("chore-litter-plus8", "Refresh litter box — Sam", base.AddDate(0, 0, 8)),
			allDayShowcaseEvent("chore-floors-plus10", "Vacuum main floor — Avery", base.AddDate(0, 0, 10)),
			allDayShowcaseEvent("chore-plants-plus12", "Water plants — Jordan", base.AddDate(0, 0, 12)),
			allDayShowcaseEvent("chore-lunches-plus14", "Prepare lunches — Sam", base.AddDate(0, 0, 14)),
		},
	}
	routines := showcaseCalendarFixture{
		File: "routines.ics", Name: "Routines", Color: "#a999d4", Owner: "routines",
		Events: showcaseRoutineCalendarEvents(base),
	}
	maintenance := showcaseCalendarFixture{
		File: "maintenance.ics", Name: "Maintenance", Color: "#d9c074", Owner: "maintenance",
		Events: []showcaseCalendarEvent{
			allDayShowcaseEvent("maintenance-detectors", "Test smoke detectors", base),
			allDayShowcaseEvent("maintenance-filter", "Replace HVAC filter", base.AddDate(0, 0, 1)),
			allDayShowcaseEvent("maintenance-water", "Replace water filter", base.AddDate(0, 0, 9)),
			allDayShowcaseEvent("maintenance-gutters", "Clean gutters", base.AddDate(0, 0, 16)),
			allDayShowcaseEvent("maintenance-camera", "Check door camera batteries", base.AddDate(0, 0, 23)),
		},
	}
	fixtures := []showcaseCalendarFixture{family, school, home, plans, chores, routines, maintenance}
	if scenario == "busy-calendar" || scenario == "capture-gallery" {
		for i := 0; i < 7; i++ {
			start := base.AddDate(0, 0, 4).Add(time.Duration(9+i) * time.Hour)
			plans.Events = append(plans.Events, timedShowcaseEvent(fmt.Sprintf("plans-busy-%d", i), fmt.Sprintf("Planning block %d", i+1), start, start.Add(75*time.Minute), profile.City+" planning room", "Dense calendar fixture."))
		}
		fixtures[3] = plans
	}
	if scenario == "family-flow" {
		family.Events = append(family.Events, timedShowcaseEvent("family-meeting", "Family meeting", base.AddDate(0, 0, 6).Add(19*time.Hour+45*time.Minute), base.AddDate(0, 0, 6).Add(20*time.Hour+20*time.Minute), profile.Venue, "Review chores, routines, and weekend plans."))
		fixtures[0] = family
	}
	return fixtures
}

func showcaseRoutineCalendarEvents(base time.Time) []showcaseCalendarEvent {
	events := []showcaseCalendarEvent{}
	for day := base.AddDate(0, 0, -1); !day.After(base.AddDate(0, 0, 24)); day = day.AddDate(0, 0, 1) {
		if day.Weekday() == time.Saturday || day.Weekday() == time.Sunday {
			events = append(events, timedShowcaseEvent("routine-weekend-"+icsDate(day), "Weekend reset — Jordan", day.Add(16*time.Hour+30*time.Minute), day.Add(17*time.Hour), "Home", "Review the calendar and grocery list."))
			continue
		}
		events = append(events,
			timedShowcaseEvent("routine-morning-"+icsDate(day), "Morning ready — Avery", day.Add(7*time.Hour+15*time.Minute), day.Add(7*time.Hour+30*time.Minute), "Home", "A weekday Routines session."),
			timedShowcaseEvent("routine-evening-"+icsDate(day), "Evening reset — Jordan", day.Add(20*time.Hour), day.Add(20*time.Hour+15*time.Minute), "Home", "Close the day together."),
		)
		if day.Weekday() == time.Monday || day.Weekday() == time.Wednesday || day.Weekday() == time.Friday {
			events = append(events, timedShowcaseEvent("routine-launch-"+icsDate(day), "School launch — Sam", day.Add(7*time.Hour+45*time.Minute), day.Add(8*time.Hour), "Home", "Lunch, library item, and weather check."))
		}
	}
	return events
}

func weekdayOnOrAfter(start time.Time, wanted time.Weekday) time.Time {
	for start.Weekday() != wanted {
		start = start.AddDate(0, 0, 1)
	}
	return start
}

func allDayShowcaseEvent(uid, title string, start time.Time) showcaseCalendarEvent {
	return showcaseCalendarEvent{UID: uid, Title: title, Start: start, End: start.AddDate(0, 0, 1), AllDay: true}
}

func multiDayShowcaseEvent(uid, title string, start, endExclusive time.Time) showcaseCalendarEvent {
	return showcaseCalendarEvent{UID: uid, Title: title, Start: start, End: endExclusive, AllDay: true}
}

func timedShowcaseEvent(uid, title string, start, end time.Time, location, description string) showcaseCalendarEvent {
	return showcaseCalendarEvent{UID: uid, Title: title, Start: start, End: end, Location: location, Description: description}
}

func writeCalendar(path, calendarName string, today time.Time, events []showcaseCalendarEvent) error {
	lines := []string{"BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Dash-Go Showcase Studio//EN", "CALSCALE:GREGORIAN", "X-WR-CALNAME:" + icsText(calendarName)}
	for _, event := range events {
		lines = append(lines, "BEGIN:VEVENT", "UID:"+event.UID, "DTSTAMP:"+icsStamp(today))
		if event.AllDay {
			end := event.End
			if end.IsZero() || !end.After(event.Start) {
				end = event.Start.AddDate(0, 0, 1)
			}
			lines = append(lines, "DTSTART;VALUE=DATE:"+icsDate(event.Start), "DTEND;VALUE=DATE:"+icsDate(end))
		} else {
			lines = append(lines, "DTSTART:"+icsStamp(event.Start), "DTEND:"+icsStamp(event.End))
		}
		lines = append(lines, "SUMMARY:"+icsText(event.Title))
		if event.Location != "" {
			lines = append(lines, "LOCATION:"+icsText(event.Location))
		}
		if event.Description != "" {
			lines = append(lines, "DESCRIPTION:"+icsText(event.Description))
		}
		lines = append(lines, "END:VEVENT")
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
