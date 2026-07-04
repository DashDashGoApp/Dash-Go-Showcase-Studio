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

const (
	showcasePastDays   = 84
	showcaseFutureDays = 140
)

type Scenario struct {
	ID          string `json:"id"`
	Title       string `json:"title"`
	Kind        string `json:"kind"`
	Description string `json:"description"`
}

var scenarios = []Scenario{
	{ID: "everyday-household", Title: "Everyday Household", Kind: "START HERE", Description: "A believable rolling household timeline with shared plans, recurring routines, multi-day travel, editable local calendars, maps, messages, To Do, Grocery, chores, and maintenance."},
	{ID: "busy-calendar", Title: "Busy Calendar", Kind: "CALENDAR", Description: "A fuller calendar gallery with realistic weekday and weekend timing, recurring series, exceptions, locations, notes, and dense but coherent days."},
	{ID: "family-flow", Title: "Family Flow", Kind: "HOUSEHOLD", Description: "People, private inboxes, Chore Wheel assignments, routines, maintenance, and examples that remain consistent with the visible calendar."},
	{ID: "household-schedules", Title: "Household Schedules", Kind: "SCHEDULES", Description: "Payday, trash, and recycling rules with generated occurrences, observed-date logic, and one deliberate adjustment."},
	{ID: "tasks-grocery", Title: "Tasks & Grocery", Kind: "LISTS", Description: "Local To Do and Grocery boards with open, completed, assigned, and calendar-linked household items—no cloud account required."},
	{ID: "themes-seasons", Title: "Themes & Seasons", Kind: "PRESENTATION", Description: "A stable, season-aware theme picker setup designed for exploring curated visual styles."},
	{ID: "capture-gallery", Title: "Capture Gallery", Kind: "CAPTURE", Description: "A screenshot-oriented composition with an active rolling calendar, map-ready public venues, and a calm message state."},
}

// LocationProfile defines synthetic public-city demo data. It never uses a
// user address, browser geolocation, or a live event feed. Venue fields are
// public places formatted as map-ready location strings.
type LocationProfile struct {
	ID             string  `json:"id"`
	Label          string  `json:"label"`
	City           string  `json:"city"`
	Region         string  `json:"region"`
	TimeZone       string  `json:"timeZone"`
	Latitude       float64 `json:"latitude"`
	Longitude      float64 `json:"longitude"`
	Market         string  `json:"market"`
	Library        string  `json:"library"`
	Park           string  `json:"park"`
	Museum         string  `json:"museum"`
	Cafe           string  `json:"cafe"`
	Restaurant     string  `json:"restaurant"`
	VolunteerSite  string  `json:"volunteerSite"`
	Dental         string  `json:"dental"`
	CommunityVenue string  `json:"communityVenue"`
	AlertEvent     string  `json:"alertEvent"`
	AlertSeverity  string  `json:"alertSeverity"`
}

var locationProfiles = []LocationProfile{
	{ID: "new-york", Label: "Eastern — New York, NY", City: "New York", Region: "NY", TimeZone: "America/New_York", Latitude: 40.7128, Longitude: -74.0060, Market: "Chelsea Market, 75 9th Ave, New York, NY 10011", Library: "New York Public Library, 476 5th Ave, New York, NY 10018", Park: "Riverside Park, W 72nd St and Riverside Dr, New York, NY 10023", Museum: "American Museum of Natural History, 200 Central Park W, New York, NY 10024", Cafe: "Think Coffee, 1 Bleecker St, New York, NY 10012", Restaurant: "Chelsea Market, 75 9th Ave, New York, NY 10011", VolunteerSite: "Food Bank For New York City, 39 Broadway, New York, NY 10006", Dental: "NYU College of Dentistry, 345 E 24th St, New York, NY 10010", CommunityVenue: "Hudson River Park, 353 West St, New York, NY 10036", AlertEvent: "Thunderstorm Watch", AlertSeverity: "severe"},
	{ID: "chicago", Label: "Central — Chicago, IL", City: "Chicago", Region: "IL", TimeZone: "America/Chicago", Latitude: 41.8781, Longitude: -87.6298, Market: "Whole Foods Market, 1101 S Canal St, Chicago, IL 60607", Library: "Harold Washington Library Center, 400 S State St, Chicago, IL 60605", Park: "Millennium Park, 201 E Randolph St, Chicago, IL 60602", Museum: "Chicago Children's Museum, 700 E Grand Ave, Chicago, IL 60611", Cafe: "Intelligentsia Coffee, 53 E Randolph St, Chicago, IL 60601", Restaurant: "Manny's Cafeteria and Delicatessen, 1141 S Jefferson St, Chicago, IL 60607", VolunteerSite: "Greater Chicago Food Depository, 4100 W Ann Lurie Pl, Chicago, IL 60632", Dental: "UI Health Dental Center, 801 S Paulina St, Chicago, IL 60612", CommunityVenue: "Chicago Park District, 1411 W Blackhawk St, Chicago, IL 60642", AlertEvent: "Extreme Heat Warning", AlertSeverity: "extreme"},
	{ID: "denver", Label: "Mountain — Denver, CO", City: "Denver", Region: "CO", TimeZone: "America/Denver", Latitude: 39.7392, Longitude: -104.9903, Market: "King Soopers, 1331 Speer Blvd, Denver, CO 80204", Library: "Denver Central Library, 10 W 14th Ave Pkwy, Denver, CO 80204", Park: "City Park, 2001 Colorado Blvd, Denver, CO 80205", Museum: "Denver Museum of Nature & Science, 2001 Colorado Blvd, Denver, CO 80205", Cafe: "Thump Coffee, 1201 E 13th Ave, Denver, CO 80218", Restaurant: "Denver Central Market, 2669 Larimer St, Denver, CO 80205", VolunteerSite: "Food Bank of the Rockies, 10700 E 45th Ave, Denver, CO 80239", Dental: "Denver Health Dental Clinic, 660 Bannock St, Denver, CO 80204", CommunityVenue: "Carla Madison Recreation Center, 2401 E Colfax Ave, Denver, CO 80206", AlertEvent: "High Wind Warning", AlertSeverity: "severe"},
	{ID: "los-angeles", Label: "Pacific — Los Angeles, CA", City: "Los Angeles", Region: "CA", TimeZone: "America/Los_Angeles", Latitude: 34.0522, Longitude: -118.2437, Market: "Grand Central Market, 317 S Broadway, Los Angeles, CA 90013", Library: "Los Angeles Central Library, 630 W 5th St, Los Angeles, CA 90071", Park: "Grand Park, 200 N Spring St, Los Angeles, CA 90012", Museum: "California Science Center, 700 Exposition Park Dr, Los Angeles, CA 90037", Cafe: "G&B Coffee, 200 S Grand Ave, Los Angeles, CA 90012", Restaurant: "Grand Central Market, 317 S Broadway, Los Angeles, CA 90013", VolunteerSite: "Los Angeles Regional Food Bank, 1734 E 41st St, Los Angeles, CA 90058", Dental: "USC Herman Ostrow School of Dentistry, 925 W 34th St, Los Angeles, CA 90089", CommunityVenue: "Echo Park Recreation Center, 1632 Bellevue Ave, Los Angeles, CA 90026", AlertEvent: "Heat Advisory", AlertSeverity: "moderate"},
	{ID: "anchorage", Label: "Alaska — Anchorage, AK", City: "Anchorage", Region: "AK", TimeZone: "America/Anchorage", Latitude: 61.2181, Longitude: -149.9003, Market: "New Sagaya City Market, 900 W 13th Ave, Anchorage, AK 99501", Library: "Z. J. Loussac Library, 3600 Denali St, Anchorage, AK 99503", Park: "Delaney Park, 1300 W 9th Ave, Anchorage, AK 99501", Museum: "Anchorage Museum, 625 C St, Anchorage, AK 99501", Cafe: "Kaladi Brothers Coffee, 621 W 6th Ave, Anchorage, AK 99501", Restaurant: "49th State Brewing, 717 W 3rd Ave, Anchorage, AK 99501", VolunteerSite: "Food Bank of Alaska, 2121 Spar Ave, Anchorage, AK 99501", Dental: "Alaska Native Medical Center Dental Clinic, 4315 Diplomacy Dr, Anchorage, AK 99508", CommunityVenue: "Spencer Sports Complex, 1300 E 48th Ave, Anchorage, AK 99507", AlertEvent: "Winter Weather Advisory", AlertSeverity: "moderate"},
	{ID: "honolulu", Label: "Hawaii — Honolulu, HI", City: "Honolulu", Region: "HI", TimeZone: "Pacific/Honolulu", Latitude: 21.3069, Longitude: -157.8583, Market: "Foodland Farms Ala Moana, 1450 Ala Moana Blvd, Honolulu, HI 96814", Library: "Hawaii State Library, 478 S King St, Honolulu, HI 96813", Park: "Kapiolani Park, 3840 Paki Ave, Honolulu, HI 96815", Museum: "Honolulu Museum of Art, 900 S Beretania St, Honolulu, HI 96814", Cafe: "Honolulu Coffee, 1800 Kalakaua Ave, Honolulu, HI 96815", Restaurant: "The Pig and The Lady, 83 N King St, Honolulu, HI 96817", VolunteerSite: "Hawaii Foodbank, 2611 Kilihau St, Honolulu, HI 96819", Dental: "University of Hawaii Dental Clinic, 320A Ward Ave, Honolulu, HI 96814", CommunityVenue: "Kaimuki Community Center, 1830 Wilhelmina Rise, Honolulu, HI 96816", AlertEvent: "High Surf Advisory", AlertSeverity: "moderate"},
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
	if err := seedCalendars(calendarDir, config, home, scenario.ID, today, now.Location(), profile); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(config, "chalkboard.json"), map[string]any{"version": 1, "strokes": []any{}}, 0644); err != nil {
		return err
	}
	return writeJSON(filepath.Join(config, "showcase-studio.json"), map[string]any{
		"schema": 1, "studio": "Dash-Go Showcase Studio", "scenario": scenario.ID,
		"scenarioTitle": scenario.Title, "createdAt": now.Format(time.RFC3339),
		"location": profile, "dataset": "city-household-reality-v1", "fixtureSchema": 3,
		"externalAccounts": false, "presentationMode": true,
		"calendarEditing": "session-local", "calendarRange": map[string]string{"past": "12 weeks", "future": "20 weeks"},
	}, 0644)
}

func WriteRuntimeMarker(workspaceRoot, scenario, locationID string, now time.Time) error {
	return writeJSON(filepath.Join(workspaceRoot, "SHOWCASE_RUNTIME.json"), map[string]any{
		"schema": 1, "scenario": scenario, "location": locationID, "createdAt": now.Local().Format(time.RFC3339),
		"privateWorkspace": true, "networkRequired": false, "calendarEdits": "session-local",
	}, 0600)
}

func person(id, name string, created time.Time) map[string]any {
	stamp := created.Format(time.RFC3339)
	return map[string]any{"id": id, "name": name, "state": "active", "createdAt": stamp, "updatedAt": stamp, "archivedAt": ""}
}

func seedBoard(home string, now time.Time, profile LocationProfile) error {
	board := map[string]any{"schema": 3, "settings": map[string]any{"showUrgentAlertsOnDashboard": true}, "notes": []any{
		map[string]any{"id": "board-urgent", "text": fmt.Sprintf("Weather plan: check the forecast before the park stop near %s.", profile.Park), "scope": "household", "priority": "urgent", "state": "active", "pinned": false, "createdAt": now.Add(-15 * time.Minute).Format(time.RFC3339), "updatedAt": now.Add(-15 * time.Minute).Format(time.RFC3339), "expiresAt": now.Add(48 * time.Hour).Format(time.RFC3339)},
		map[string]any{"id": "board-pinned", "text": "Calendar demo note: Family, Home, and Plans events can be added or managed in this Studio session. Those changes reset when Studio closes.", "scope": "household", "priority": "normal", "state": "active", "pinned": true, "createdAt": now.Add(-time.Hour).Format(time.RFC3339), "updatedAt": now.Add(-30 * time.Minute).Format(time.RFC3339), "expiresAt": ""},
		map[string]any{"id": "board-trip", "text": "For the next family weekend, check the packing list, charge the camera, and confirm the sitter before Friday.", "scope": "household", "priority": "normal", "state": "active", "pinned": false, "createdAt": now.Add(-2 * time.Hour).Format(time.RFC3339), "updatedAt": now.Add(-2 * time.Hour).Format(time.RFC3339), "expiresAt": now.AddDate(0, 0, 14).Format(time.RFC3339)},
		map[string]any{"id": "direct-avery-jordan", "text": "I saved the library books by the door for tomorrow.", "scope": "direct", "priority": "normal", "state": "active", "senderPersonId": "avery", "senderNameSnapshot": "Avery", "recipientPersonId": "jordan", "recipientNameSnapshot": "Jordan", "recipientReadAt": "", "createdAt": now.Add(-7 * time.Minute).Format(time.RFC3339), "updatedAt": now.Add(-7 * time.Minute).Format(time.RFC3339)},
		map[string]any{"id": "direct-sam-avery", "text": "Can we make tacos after the market this weekend?", "scope": "direct", "priority": "normal", "state": "active", "senderPersonId": "sam", "senderNameSnapshot": "Sam", "recipientPersonId": "avery", "recipientNameSnapshot": "Avery", "recipientReadAt": "", "createdAt": now.Add(-3 * time.Minute).Format(time.RFC3339), "updatedAt": now.Add(-3 * time.Minute).Format(time.RFC3339)},
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
	assignments := make([]any, 0, 40)
	for _, item := range realisticChoreAssignments(today) {
		assignments = append(assignments, item)
	}
	chores := map[string]any{"schema": 1, "revision": 2, "people": peopleSnap, "chores": []any{
		map[string]any{"id": "dishes", "name": "Kitchen reset", "createdAt": now.Add(-90 * 24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "daily", "day": 0, "every": 1, "anchorDate": dateText(today.AddDate(0, 0, -1))}, "effort": 1, "eligible": []string{"avery", "jordan", "sam"}},
		map[string]any{"id": "recycling", "name": "Take out recycling", "createdAt": now.Add(-90 * 24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "weekly", "day": int(time.Monday), "every": 1, "anchorDate": dateText(previousWeekday(today, time.Monday))}, "effort": 2, "eligible": []string{"jordan", "sam"}},
		map[string]any{"id": "litter", "name": "Refresh litter box", "createdAt": now.Add(-90 * 24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "days", "day": 0, "every": 3, "anchorDate": dateText(today.AddDate(0, 0, -3))}, "effort": 2, "eligible": []string{"sam", "jordan"}},
		map[string]any{"id": "floors", "name": "Vacuum main floor", "createdAt": now.Add(-90 * 24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "weekly", "day": int(time.Saturday), "every": 1, "anchorDate": dateText(previousWeekday(today, time.Saturday))}, "effort": 3, "eligible": []string{"avery", "sam"}},
		map[string]any{"id": "meal-plan", "name": "Set up weekday lunches", "createdAt": now.Add(-90 * 24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "weekly", "day": int(time.Sunday), "every": 1, "anchorDate": dateText(previousWeekday(today, time.Sunday))}, "effort": 2, "eligible": []string{"avery", "jordan", "sam"}},
		map[string]any{"id": "plants", "name": "Water plants", "createdAt": now.Add(-90 * 24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "weekly", "day": int(time.Sunday), "every": 1, "anchorDate": dateText(previousWeekday(today, time.Sunday))}, "effort": 1, "eligible": []string{"jordan", "sam"}},
		map[string]any{"id": "mail", "name": "Sort mail and school papers", "createdAt": now.Add(-90 * 24 * time.Hour).Format(time.RFC3339), "cadence": map[string]any{"type": "weekly", "day": int(time.Thursday), "every": 1, "anchorDate": dateText(previousWeekday(today, time.Thursday))}, "effort": 1, "eligible": []string{"avery", "jordan"}},
	}, "assignments": assignments, "settings": map[string]any{"horizonDays": 42, "calendarOutputEnabled": true}}
	return writeJSON(filepath.Join(config, "chore-wheel.json"), chores, 0644)
}

func realisticChoreAssignments(today time.Time) []map[string]any {
	out := []map[string]any{}
	start := today.AddDate(0, 0, -10)
	end := today.AddDate(0, 0, 28)
	people := []struct{ ID, Name string }{{"avery", "Avery"}, {"jordan", "Jordan"}, {"sam", "Sam"}}
	for d := start; !d.After(end); d = d.AddDate(0, 0, 1) {
		index := int(d.Sub(day(start)).Hours()/24) + len(people)*8
		person := people[index%len(people)]
		status := "assigned"
		if d.Before(today) {
			status = "completed"
		}
		out = append(out, showcaseChoreAssignment("asg-kitchen-"+icsDate(d), d, "dishes", "Kitchen reset", person.ID, person.Name, status))
		switch d.Weekday() {
		case time.Monday:
			out = append(out, showcaseChoreAssignment("asg-recycling-"+icsDate(d), d, "recycling", "Take out recycling", "jordan", "Jordan", status))
		case time.Thursday:
			out = append(out, showcaseChoreAssignment("asg-mail-"+icsDate(d), d, "mail", "Sort mail and school papers", "avery", "Avery", status))
		case time.Saturday:
			out = append(out, showcaseChoreAssignment("asg-floors-"+icsDate(d), d, "floors", "Vacuum main floor", "sam", "Sam", status))
		case time.Sunday:
			out = append(out,
				showcaseChoreAssignment("asg-lunches-"+icsDate(d), d, "meal-plan", "Set up weekday lunches", "jordan", "Jordan", status),
				showcaseChoreAssignment("asg-plants-"+icsDate(d), d, "plants", "Water plants", "sam", "Sam", status),
			)
		}
		if d.Weekday() == time.Tuesday || d.Weekday() == time.Friday {
			out = append(out, showcaseChoreAssignment("asg-litter-"+icsDate(d), d, "litter", "Refresh litter box", "sam", "Sam", status))
		}
	}
	return out
}

func showcaseChoreAssignment(id string, when time.Time, choreID, choreName, personID, personName, status string) map[string]any {
	return map[string]any{"id": id, "date": dateText(when), "choreId": choreID, "choreName": choreName, "personId": personID, "personName": personName, "status": status, "source": "showcase"}
}

func seedRoutines(config string, people []map[string]any, today time.Time, now time.Time) error {
	peopleSnap := []any{}
	for _, p := range people {
		peopleSnap = append(peopleSnap, map[string]any{"id": p["id"], "name": p["name"]})
	}
	startOn := dateText(today.AddDate(0, 0, -showcasePastDays))
	routines := map[string]any{"schema": 1, "revision": 2, "settings": map[string]any{"calendarOutputEnabled": true, "calendarHorizonDays": 140, "defaultCalendarEnabled": true}, "people": peopleSnap, "routines": []any{
		map[string]any{"id": "morning", "title": "Morning ready", "note": "Pack the bag, check breakfast, and leave with the weather layer in mind.", "steps": []any{map[string]any{"id": "pack", "text": "Pack bag"}, map[string]any{"id": "breakfast", "text": "Breakfast"}, map[string]any{"id": "teeth", "text": "Brush teeth"}}, "assignments": []any{map[string]any{"id": "morning-avery", "personId": "avery", "personNameSnapshot": "Avery", "calendarEnabled": true, "schedule": map[string]any{"kind": "weekdays", "every": 1, "weekdays": []string{"MO", "TU", "WE", "TH", "FR"}, "startOn": startOn, "endOn": "", "month": 1, "day": 1, "time": "07:15", "allDay": false}}}},
		map[string]any{"id": "school-launch", "title": "School and camp launch", "note": "Check lunch, library items, sunscreen or a rain layer, and the next pickup detail.", "steps": []any{map[string]any{"id": "lunch", "text": "Lunch check"}, map[string]any{"id": "library", "text": "Library item"}, map[string]any{"id": "weather", "text": "Weather layer"}}, "assignments": []any{map[string]any{"id": "launch-sam", "personId": "sam", "personNameSnapshot": "Sam", "calendarEnabled": true, "schedule": map[string]any{"kind": "weekdays", "every": 1, "weekdays": []string{"MO", "TU", "WE", "TH", "FR"}, "startOn": startOn, "endOn": "", "month": 1, "day": 1, "time": "07:45", "allDay": false}}}},
		map[string]any{"id": "evening", "title": "Evening reset", "note": "Clear one surface, check tomorrow, and start any needed laundry before winding down.", "steps": []any{map[string]any{"id": "counter", "text": "Clear counters"}, map[string]any{"id": "laundry", "text": "Start laundry"}, map[string]any{"id": "calendar", "text": "Check tomorrow"}}, "assignments": []any{map[string]any{"id": "evening-jordan", "personId": "jordan", "personNameSnapshot": "Jordan", "calendarEnabled": true, "schedule": map[string]any{"kind": "days", "every": 1, "weekdays": []string{}, "startOn": startOn, "endOn": "", "month": 1, "day": 1, "time": "20:00", "allDay": false}}}},
		map[string]any{"id": "sunday-reset", "title": "Sunday reset", "note": "Review the week, confirm the grocery list, and prepare one calm start for Monday.", "steps": []any{map[string]any{"id": "calendar", "text": "Review calendar"}, map[string]any{"id": "grocery", "text": "Check grocery list"}, map[string]any{"id": "laundry", "text": "Start one laundry load"}}, "assignments": []any{map[string]any{"id": "reset-family", "personId": "jordan", "personNameSnapshot": "Jordan", "calendarEnabled": true, "schedule": map[string]any{"kind": "weekly", "every": 1, "weekdays": []string{"SU"}, "startOn": startOn, "endOn": "", "month": 1, "day": 1, "time": "16:30", "allDay": false}}}},
	}, "occurrences": []any{}, "history": []any{}}
	return writeJSON(filepath.Join(config, "routines.json"), routines, 0644)
}

func seedMaintenance(config string, today time.Time, now time.Time) error {
	firstSunday := nextWeekday(today.AddDate(0, 0, 1), time.Sunday)
	maintenance := map[string]any{"schema": 2, "settings": map[string]any{"defaultCalendarEnabled": true, "calendarOutputEnabled": true, "dueSoonDays": 30}, "tasks": []any{
		maintenanceTask("replace-filter", "Replace HVAC filter", "Use the MERV 11 filter from the hall closet. Record the filter size on the Grocery list if this is the last spare.", nextWeekday(today.AddDate(0, 0, 9), time.Saturday), today.AddDate(0, 0, -88), "jordan", "Jordan", now),
		maintenanceTask("test-detectors", "Test smoke detectors", "Walk through every bedroom, replace weak batteries, and note any detector that chirps after the test.", firstSunday, today.AddDate(0, 0, -181), "avery", "Avery", now),
		maintenanceTask("clean-gutters", "Schedule gutter cleaning", "Book the service before the seasonal leaf drop and confirm the gate is unlocked on the appointment morning.", nextWeekday(today.AddDate(0, 0, 36), time.Friday), today.AddDate(0, 0, -150), "sam", "Sam", now),
		maintenanceTask("water-filter", "Replace water filter", "Use the replacement stored with the appliance manuals and run water for the recommended flush time.", nextWeekday(today.AddDate(0, 0, 18), time.Wednesday), today.AddDate(0, 0, -175), "avery", "Avery", now),
		maintenanceTask("camera-batteries", "Check door camera batteries", "Confirm the entry camera and mailbox sensor are charged before the next long weekend.", nextWeekday(today.AddDate(0, 0, 47), time.Saturday), today.AddDate(0, 0, -340), "jordan", "Jordan", now),
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
		todoTask("todo-insurance", "Bring insurance card to the dental appointment", "notStarted", "high", "jordan", "Jordan", millis),
		todoTask("todo-library", "Return the blue library bag", "notStarted", "normal", "avery", "Avery", millis),
		todoTask("todo-filter", "Check the HVAC filter size before the next grocery run", "notStarted", "normal", "sam", "Sam", millis),
		map[string]any{"id": "todo-done", "title": "Confirm this weekend's market plan", "status": "completed", "importance": "normal"},
	}, "pendingOps": []any{}}, 0644); err != nil {
		return err
	}
	return writeJSON(filepath.Join(todoDir, todoFile("local-grocery")), map[string]any{"version": 1, "listId": "local-grocery", "displayName": "Grocery", "tasks": []any{
		map[string]any{"id": "groceries-city-pickup", "title": "Confirm pickup at " + profile.Market, "status": "notStarted", "importance": "normal"},
		map[string]any{"id": "groceries-milk", "title": "Milk", "status": "notStarted", "importance": "normal"},
		map[string]any{"id": "groceries-tortillas", "title": "Tortillas", "status": "notStarted", "importance": "normal"},
		map[string]any{"id": "groceries-coffee", "title": "Coffee", "status": "notStarted", "importance": "normal"},
		map[string]any{"id": "groceries-filter", "title": "16×25×1 HVAC filter", "status": "notStarted", "importance": "normal"},
		map[string]any{"id": "groceries-apples", "title": "Apples", "status": "completed", "importance": "normal"},
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
		map[string]any{"id": 1, "text": "A shared calendar works best when daily plans, chores, and notes tell the same story.", "weight": 45, "origin": "studio-normal"},
		map[string]any{"id": 2, "text": "Small household wins add up — one helpful task and one clear plan at a time.", "weight": 45, "origin": "studio-normal"},
		map[string]any{"id": 3, "text": fmt.Sprintf("Today’s Studio household is centered on %s, %s.", profile.City, profile.Region), "weight": 20, "origin": "studio-location"},
		map[string]any{"id": 4, "text": "Try adding an event to Family, Home, or Plans. Studio saves it locally for this session only.", "weight": 10, "origin": "studio-discovery"},
		map[string]any{"id": 5, "text": "Open a location-bearing event to see its map preview and practical notes.", "weight": 10, "origin": "studio-discovery"},
		map[string]any{"id": 6, "text": "This is Dash-Go Showcase Studio. Everything here is synthetic, safe to explore, and reset automatically.", "weight": 10, "origin": "studio-discovery"},
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
window.DASHGO_SHOWCASE = true;
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
	trashStart := previousWeekday(today, time.Tuesday)
	paydayStart := showcasePaydayAnchor(today)
	schedules := map[string]any{"schema": 1, "paydays": []any{
		map[string]any{"id": "household-payday", "label": "Household payday", "enabled": true, "kind": "every-weeks", "start": dateText(paydayStart), "everyWeeks": 2, "adjustment": map[string]any{"mode": "previous-business-day", "weekends": true, "holidayLayers": []string{"civil"}}},
		map[string]any{"id": "side-payday", "label": "Side income", "enabled": true, "kind": "monthly-dates", "days": []int{14, 29}, "adjustment": map[string]any{"mode": "none"}},
	}, "pickups": []any{
		map[string]any{"id": "trash", "label": "Trash pickup", "enabled": true, "weekday": "Tuesday", "everyWeeks": 1, "start": dateText(trashStart), "adjustment": map[string]any{"mode": "shift-forward", "days": 1}},
		map[string]any{"id": "recycling", "label": "Recycling pickup", "enabled": true, "weekday": "Tuesday", "everyWeeks": 2, "start": dateText(trashStart), "adjustment": map[string]any{"mode": "none"}},
	}, "overrides": []any{map[string]any{"ruleId": "trash", "nominalDate": dateText(nextWeekday(today.AddDate(0, 0, 7), time.Tuesday)), "action": "move", "actualDate": dateText(nextWeekday(today.AddDate(0, 0, 7), time.Wednesday))}}}
	return writeJSON(filepath.Join(config, "household-schedules.json"), schedules, 0644)
}

type showcaseCalendarFixture struct {
	File     string
	Name     string
	Color    string
	Owner    string
	Tag      string
	Editable bool
	Events   []showcaseCalendarEvent
}

type showcaseCalendarEvent struct {
	UID          string
	Title        string
	Start        time.Time
	End          time.Time
	AllDay       bool
	Location     string
	Description  string
	RRULE        string
	ExDates      []time.Time
	RecurrenceID time.Time
}

func seedCalendars(calendarDir, config, home, scenario string, today time.Time, loc *time.Location, profile LocationProfile) error {
	fixtures := showcaseCalendars(scenario, today, loc, profile)
	manifest := make([]any, 0, len(fixtures))
	for _, fixture := range fixtures {
		if err := writeCalendar(filepath.Join(calendarDir, fixture.File), fixture.Name, today, fixture.Events); err != nil {
			return err
		}
		entry := map[string]any{
			"url": "calendars/" + fixture.File, "name": fixture.Name, "color": fixture.Color,
			"enabled": true, "tag": "showcase",
		}
		if fixture.Owner != "" {
			entry["owner"] = fixture.Owner
		}
		if fixture.Tag != "" {
			entry["tag"] = fixture.Tag
		}
		manifest = append(manifest, entry)
	}
	if err := writeJSON(filepath.Join(calendarDir, "calendars.json"), manifest, 0644); err != nil {
		return err
	}
	return seedSessionWriteback(config, home, today, fixtures)
}

func seedSessionWriteback(config, home string, today time.Time, fixtures []showcaseCalendarFixture) error {
	collections := filepath.Join(home, ".dashboard-vdirsyncer", "collections")
	calendars := []any{}
	for _, fixture := range fixtures {
		if !fixture.Editable {
			continue
		}
		collectionName := "showcase-" + strings.TrimSuffix(fixture.File, filepath.Ext(fixture.File))
		collection := filepath.Join(collections, collectionName)
		if err := os.MkdirAll(collection, 0700); err != nil {
			return err
		}
		byUID := map[string][]showcaseCalendarEvent{}
		for _, event := range fixture.Events {
			byUID[event.UID] = append(byUID[event.UID], event)
		}
		uids := make([]string, 0, len(byUID))
		for uid := range byUID {
			uids = append(uids, uid)
		}
		sort.Strings(uids)
		for _, uid := range uids {
			if err := writeCalendar(filepath.Join(collection, uid+".ics"), fixture.Name, today, byUID[uid]); err != nil {
				return err
			}
		}
		calendars = append(calendars, map[string]any{
			"source": "calendars/" + fixture.File, "collection": collection, "writable": true,
			"enabled": true, "name": fixture.Name,
		})
	}
	// calendar-writeback.json is parsed with DisallowUnknownFields by Dash-Go's
	// writeback registry. Keep this file strictly limited to the registry schema;
	// Studio-only session metadata lives beside it instead of making the registry
	// unreadable and silently disabling Add / Manage.
	if err := writeJSON(filepath.Join(config, "calendar-writeback.json"), map[string]any{
		"version": 2, "enabled": true, "requirePin": false, "calendars": calendars,
	}, 0600); err != nil {
		return err
	}
	return writeJSON(filepath.Join(config, "showcase-session-calendar.json"), map[string]any{
		"schema": 1, "sessionOnly": true, "resetsOnClose": true,
		"writableSources": []string{
			"calendars/family.green.ics",
			"calendars/home.amber.ics",
			"calendars/plans.violet.ics",
		},
	}, 0600)
}

func showcaseCalendars(scenario string, today time.Time, loc *time.Location, profile LocationProfile) []showcaseCalendarFixture {
	base := dayInLocation(today, loc)
	pastStart := startOfWeek(base.AddDate(0, 0, -showcasePastDays))
	futureEnd := base.AddDate(0, 0, showcaseFutureDays)
	nextFriday := nextWeekday(base, time.Friday)
	nextSaturday := nextWeekday(base, time.Saturday)
	nextTuesday := nextWeekday(base, time.Tuesday)
	firstSunday := nextWeekday(pastStart, time.Sunday)
	firstMonday := nextWeekday(pastStart, time.Monday)
	firstTuesday := nextWeekday(pastStart, time.Tuesday)
	firstWednesday := nextWeekday(pastStart, time.Wednesday)
	firstThursday := nextWeekday(pastStart, time.Thursday)
	firstFriday := showcasePaydayAnchor(base)
	firstSaturday := nextWeekday(pastStart, time.Saturday)

	family := showcaseCalendarFixture{File: "family.green.ics", Name: "Family", Color: "#8fc4a6", Editable: true, Events: []showcaseCalendarEvent{
		recurringShowcaseEvent("family-weekly-plan", "Family meal plan", at(firstSunday, 16, 30), at(firstSunday, 17, 15), "Home", "Review the coming week, check the Grocery list, and choose two low-effort dinners before the weekday rush.", "FREQ=WEEKLY;BYDAY=SU;COUNT=36"),
		recurringShowcaseEvent("family-grandparent-call", "Grandparent video call", at(firstSunday, 18, 30), at(firstSunday, 19, 0), "Home", "Set the tablet on the stand and keep a few family photos nearby for an easy Sunday check-in.", "FREQ=WEEKLY;BYDAY=SU;COUNT=36"),
		multiDayShowcaseEvent("family-past-trip", "Spring break road trip", previousWeekday(base.AddDate(0, 0, -35), time.Friday), previousWeekday(base.AddDate(0, 0, -35), time.Friday).AddDate(0, 0, 3), "", "A completed long weekend with a planned rest stop, shared packing list, and one quiet day after returning."),
		timedShowcaseEvent("family-birthday", "Avery's birthday dinner", at(nextWeekday(base.AddDate(0, 0, 16), time.Saturday), 17, 30), at(nextWeekday(base.AddDate(0, 0, 16), time.Saturday), 19, 30), profile.Restaurant, "Arrive a few minutes early for the table. The birthday card and small gift are in the hall closet.", ""),
		multiDayShowcaseEvent("family-lake-weekend", "Lake cabin weekend", nextFriday, nextFriday.AddDate(0, 0, 3), "", "Leave after the Friday workday. Pack the blue cooler, towels, charger bag, and the paper map in case cell service is limited."),
		timedShowcaseEvent("family-return-reset", "Unpack and reset", at(nextFriday.AddDate(0, 0, 3), 17, 0), at(nextFriday.AddDate(0, 0, 3), 18, 0), "Home", "Put laundry straight into the washer, refill water bottles, and check the coming school or camp schedule before dinner.", ""),
		recurringShowcaseEvent("family-piano", "Piano practice", at(firstWednesday, 17, 30), at(firstWednesday, 18, 0), profile.CommunityVenue, "Bring the music folder and leave ten minutes for setup. This recurring series includes one moved occurrence to demonstrate exceptions.", "FREQ=WEEKLY;BYDAY=WE;COUNT=34"),
		occurrenceOverride("family-piano", "Piano practice — moved", at(nextWeekday(base.AddDate(0, 0, 7), time.Wednesday), 17, 30), at(nextWeekday(base.AddDate(0, 0, 7), time.Thursday), 18, 0), at(nextWeekday(base.AddDate(0, 0, 7), time.Thursday), 18, 30), profile.CommunityVenue, "The instructor moved this one practice to Thursday. Keep the same music folder and arrive ten minutes early."),
	}}

	school := showcaseCalendarFixture{File: "school.blue.ics", Name: "School", Color: "#8bb4d4", Events: schoolCalendarEvents(base, pastStart, futureEnd, profile)}

	home := showcaseCalendarFixture{File: "home.amber.ics", Name: "Home", Color: "#cda76a", Editable: true, Events: []showcaseCalendarEvent{
		recurringShowcaseEvent("home-set-out-bins", "Set out trash and recycling", at(firstMonday, 19, 0), at(firstMonday, 19, 15), "Home", "Move the bins to the curb after dinner. Put out the blue recycling bin on the alternating collection weeks shown below.", "FREQ=WEEKLY;BYDAY=MO;COUNT=38"),
		recurringAllDayShowcaseEvent("home-trash", "Trash pickup", firstTuesday, "Bins are collected Tuesday morning. Keep the curb clear and bring the empty bin back in after work or school.", "FREQ=WEEKLY;BYDAY=TU;COUNT=38"),
		recurringAllDayShowcaseEvent("home-recycling", "Recycling pickup", firstTuesday, "Flatten cardboard, rinse containers, and set the blue bin out after dinner for Tuesday collection.", "FREQ=WEEKLY;INTERVAL=2;BYDAY=TU;COUNT=20"),
		recurringShowcaseEvent("home-grocery", "Grocery pickup", at(firstThursday, 17, 15), at(firstThursday, 17, 45), profile.Market, "Pickup window is 5:15–5:45 PM. Bring two reusable bags; the Grocery list already includes produce, coffee, and a replacement filter.", "FREQ=WEEKLY;BYDAY=TH;COUNT=34"),
		recurringShowcaseEvent("home-meal-prep", "Meal prep", at(firstSunday, 15, 0), at(firstSunday, 16, 0), "Home", "Wash produce, portion one lunch item, and thaw the first dinner before the Sunday reset is complete.", "FREQ=WEEKLY;BYDAY=SU;COUNT=36"),
		timedShowcaseEvent("home-window-service", "Window repair appointment", at(nextTuesday.AddDate(0, 0, 14), 9, 0), at(nextTuesday.AddDate(0, 0, 14), 11, 0), "Home — "+profile.City+", "+profile.Region, "The technician will call 20 minutes ahead. Clear the sill and keep the pets away from the work area.", ""),
		multiDayShowcaseEvent("home-garage-refresh", "Garage refresh", nextSaturday.AddDate(0, 0, 21), nextSaturday.AddDate(0, 0, 23), "", "Sort donation boxes, label the camping shelf, and keep one parking spot clear by Sunday evening."),
	}}

	market := recurringShowcaseEvent("plans-market", "Saturday farmers market", at(firstSaturday, 9, 0), at(firstSaturday, 10, 15), profile.Market, "Pick up seasonal produce first, then choose one treat for the weekend. Bring the tote from the entry closet.", "FREQ=WEEKLY;BYDAY=SA;COUNT=36")
	market.ExDates = []time.Time{at(nextSaturday.AddDate(0, 0, 14), 9, 0)}
	plans := showcaseCalendarFixture{File: "plans.violet.ics", Name: "Plans", Color: "#9a8fb0", Editable: true, Events: []showcaseCalendarEvent{
		recurringAllDayShowcaseEvent("plans-payday", "Payday", firstFriday, "Direct deposit posts today. Review upcoming auto-payments, move the planned savings amount, and confirm the grocery and weekend budget before the afternoon.", "FREQ=WEEKLY;INTERVAL=2;BYDAY=FR;COUNT=24"),
		market,
		recurringShowcaseEvent("plans-library", "Library pickup", at(firstThursday, 16, 30), at(firstThursday, 17, 0), profile.Library, "Return the blue bag before selecting new books. Check the holds shelf for the reading-club title.", "FREQ=WEEKLY;BYDAY=TH;COUNT=34"),
		timedShowcaseEvent("plans-volunteer", "Food pantry volunteer shift", at(nextWeekday(base.AddDate(0, 0, 10), time.Saturday), 9, 30), at(nextWeekday(base.AddDate(0, 0, 10), time.Saturday), 12, 0), profile.VolunteerSite, "Wear closed-toe shoes and arrive ten minutes early for check-in. Bring a reusable water bottle.", ""),
		timedShowcaseEvent("plans-dentist", "Dental appointment", at(nextWeekday(base.AddDate(0, 0, 18), time.Tuesday), 14, 0), at(nextWeekday(base.AddDate(0, 0, 18), time.Tuesday), 15, 0), profile.Dental, "Arrive ten minutes early with the insurance card. Keep the rest of the afternoon light for a calm return home.", ""),
		timedShowcaseEvent("plans-coffee", "Coffee catch-up", at(nextWeekday(base.AddDate(0, 0, 5), time.Wednesday), 8, 30), at(nextWeekday(base.AddDate(0, 0, 5), time.Wednesday), 9, 15), profile.Cafe, "A short weekday catch-up before the morning gets busy. Save the parking validation if one is offered.", ""),
		timedShowcaseEvent("plans-date-night", "Date night", at(nextFriday, 18, 30), at(nextFriday, 20, 30), profile.Restaurant, "Reservation is under Jordan. Confirm the sitter and leave the restaurant address in the Family Board note before heading out.", ""),
	}}

	chores := showcaseCalendarFixture{File: "chore-wheel.ics", Name: "Chores", Color: "#7fc4c4", Owner: "chore-wheel", Events: choreCalendarEvents(today)}
	routines := showcaseCalendarFixture{File: "routines.ics", Name: "Routines", Color: "#b898d0", Owner: "routines", Events: routineCalendarEvents(today)}
	maintenance := showcaseCalendarFixture{File: "maintenance.ics", Name: "Maintenance", Color: "#d68a74", Owner: "maintenance", Events: maintenanceCalendarEvents(today)}

	fixtures := []showcaseCalendarFixture{family, school, home, plans, chores, routines, maintenance}
	if scenario == "busy-calendar" {
		plans.Events = append(plans.Events, busyCalendarPlanningBlocks(base, profile)...)
		fixtures[3] = plans
	}
	return fixtures
}

func schoolCalendarEvents(base, pastStart, futureEnd time.Time, profile LocationProfile) []showcaseCalendarEvent {
	events := []showcaseCalendarEvent{}
	for monday := startOfWeek(pastStart); !monday.After(futureEnd); monday = monday.AddDate(0, 0, 7) {
		if schoolSummerWeek(monday) {
			events = append(events,
				multiDayShowcaseEvent("school-summer-camp-"+icsDate(monday), "Summer learning camp", monday, monday.AddDate(0, 0, 5), "", "A weekday summer program with outdoor time, a reading block, and a pickup window. Pack sunscreen and a labeled water bottle."),
				timedShowcaseEvent("school-library-lab-"+icsDate(monday), "Library maker lab", at(monday.AddDate(0, 0, 2), 15, 30), at(monday.AddDate(0, 0, 2), 16, 30), profile.Library, "Bring the current reading log and meet in the youth activity room after the camp pickup.", ""),
				timedShowcaseEvent("school-museum-"+icsDate(monday), "Museum discovery workshop", at(monday.AddDate(0, 0, 4), 10, 0), at(monday.AddDate(0, 0, 4), 12, 0), profile.Museum, "Check in at the family desk. Bring a small snack and save the activity sheet for the Family Board.", ""),
			)
		} else {
			events = append(events,
				timedShowcaseEvent("school-club-"+icsDate(monday), "After-school library club", at(monday.AddDate(0, 0, 1), 15, 30), at(monday.AddDate(0, 0, 1), 16, 30), profile.Library, "Return the current book first, then meet near the children's room for the group activity.", ""),
				timedShowcaseEvent("school-activity-"+icsDate(monday), "School activity workshop", at(monday.AddDate(0, 0, 3), 15, 15), at(monday.AddDate(0, 0, 3), 16, 30), profile.CommunityVenue, "Bring the signed permission slip and a water bottle. Pickup is at the main entrance.", ""),
			)
		}
	}
	conference := nextWeekday(base.AddDate(0, 0, 24), time.Thursday)
	events = append(events,
		timedShowcaseEvent("school-family-conference", "Family-teacher conference", at(conference, 16, 15), at(conference, 16, 45), profile.CommunityVenue, "Bring the reading log and two questions about the next learning goal. A short note from the meeting can go on the Family Board.", ""),
		allDayShowcaseEvent("school-supply-check", "School and camp supply check", nextWeekday(base.AddDate(0, 0, 31), time.Sunday), "Review the backpack, water bottle, and weather gear before the next Monday start."),
	)
	return events
}

func schoolSummerWeek(day time.Time) bool {
	return day.Month() >= time.June && day.Month() <= time.August
}

func choreCalendarEvents(today time.Time) []showcaseCalendarEvent {
	events := []showcaseCalendarEvent{}
	for _, assignment := range realisticChoreAssignments(today) {
		when, _ := time.ParseInLocation("2006-01-02", fmt.Sprint(assignment["date"]), today.Location())
		title := fmt.Sprintf("%s — %s", assignment["choreName"], assignment["personName"])
		desc := "Generated from the Chore Wheel assignment. Complete it in Chore Wheel so the household source of truth stays in sync."
		events = append(events, allDayShowcaseEvent(fmt.Sprint(assignment["id"]), title, when, desc))
	}
	return events
}

func routineCalendarEvents(today time.Time) []showcaseCalendarEvent {
	events := []showcaseCalendarEvent{}
	for d := today.AddDate(0, 0, -14); !d.After(today.AddDate(0, 0, 42)); d = d.AddDate(0, 0, 1) {
		if d.Weekday() == time.Saturday || d.Weekday() == time.Sunday {
			if d.Weekday() == time.Sunday {
				events = append(events, timedShowcaseEvent("routine-sunday-"+icsDate(d), "Sunday reset — Jordan", at(d, 16, 30), at(d, 17, 0), "Home", "Review the calendar, check the grocery list, and start one calm Monday preparation step.", ""))
			}
			continue
		}
		events = append(events,
			timedShowcaseEvent("routine-morning-"+icsDate(d), "Morning ready — Avery", at(d, 7, 15), at(d, 7, 30), "Home", "Pack the bag, check breakfast, and leave with the weather in mind.", ""),
			timedShowcaseEvent("routine-evening-"+icsDate(d), "Evening reset — Jordan", at(d, 20, 0), at(d, 20, 15), "Home", "Clear one surface, check tomorrow, and start any needed laundry.", ""),
		)
		if d.Weekday() == time.Monday || d.Weekday() == time.Wednesday || d.Weekday() == time.Friday {
			events = append(events, timedShowcaseEvent("routine-launch-"+icsDate(d), "School and camp launch — Sam", at(d, 7, 45), at(d, 8, 0), "Home", "Check lunch, library items, sunscreen or a rain layer, and the pickup detail.", ""))
		}
	}
	return events
}

func maintenanceCalendarEvents(today time.Time) []showcaseCalendarEvent {
	return []showcaseCalendarEvent{
		allDayShowcaseEvent("maintenance-detectors", "Test smoke detectors", nextWeekday(today.AddDate(0, 0, 1), time.Sunday), "Check every bedroom, replace weak batteries, and note any detector that chirps after the test."),
		allDayShowcaseEvent("maintenance-filter", "Replace HVAC filter", nextWeekday(today.AddDate(0, 0, 9), time.Saturday), "Use the MERV 11 filter in the hall closet and note the size on Grocery if this is the last spare."),
		allDayShowcaseEvent("maintenance-water", "Replace water filter", nextWeekday(today.AddDate(0, 0, 18), time.Wednesday), "Use the replacement stored with the appliance manuals and run water for the recommended flush time."),
		allDayShowcaseEvent("maintenance-gutters", "Schedule gutter cleaning", nextWeekday(today.AddDate(0, 0, 36), time.Friday), "Confirm the gate is unlocked on the appointment morning and keep pets indoors while work is underway."),
		allDayShowcaseEvent("maintenance-camera", "Check door camera batteries", nextWeekday(today.AddDate(0, 0, 47), time.Saturday), "Confirm the entry camera and mailbox sensor are charged before the next long weekend."),
	}
}

func busyCalendarPlanningBlocks(base time.Time, profile LocationProfile) []showcaseCalendarEvent {
	blocks := []showcaseCalendarEvent{}
	for i := 0; i < 8; i++ {
		day := nextWeekday(base.AddDate(0, 0, 3+i*2), time.Weekday((int(time.Monday)+i)%7))
		if day.Weekday() == time.Saturday || day.Weekday() == time.Sunday {
			day = nextWeekday(day.AddDate(0, 0, 1), time.Monday)
		}
		blocks = append(blocks, timedShowcaseEvent(fmt.Sprintf("plans-planning-%d", i+1), fmt.Sprintf("Planning block %d", i+1), at(day, 15+(i%3), 0), at(day, 16+(i%3), 0), profile.Library, "A focused planning block for a real household task: review the plan, take one concrete action, and leave a short note for the next person.", ""))
	}
	return blocks
}

func recurringShowcaseEvent(uid, title string, start, end time.Time, location, description, rule string) showcaseCalendarEvent {
	return showcaseCalendarEvent{UID: uid, Title: title, Start: start, End: end, Location: location, Description: description, RRULE: rule}
}

func recurringAllDayShowcaseEvent(uid, title string, start time.Time, description, rule string) showcaseCalendarEvent {
	return showcaseCalendarEvent{UID: uid, Title: title, Start: start, End: start.AddDate(0, 0, 1), AllDay: true, Description: description, RRULE: rule}
}

func occurrenceOverride(uid, title string, recurrenceID, start, end time.Time, location, description string) showcaseCalendarEvent {
	return showcaseCalendarEvent{UID: uid, Title: title, Start: start, End: end, Location: location, Description: description, RecurrenceID: recurrenceID}
}

func allDayShowcaseEvent(uid, title string, start time.Time, description string) showcaseCalendarEvent {
	return showcaseCalendarEvent{UID: uid, Title: title, Start: start, End: start.AddDate(0, 0, 1), AllDay: true, Description: description}
}

func multiDayShowcaseEvent(uid, title string, start, endExclusive time.Time, location, description string) showcaseCalendarEvent {
	return showcaseCalendarEvent{UID: uid, Title: title, Start: start, End: endExclusive, AllDay: true, Location: location, Description: description}
}

func timedShowcaseEvent(uid, title string, start, end time.Time, location, description, rule string) showcaseCalendarEvent {
	return showcaseCalendarEvent{UID: uid, Title: title, Start: start, End: end, Location: location, Description: description, RRULE: rule}
}

func writeCalendar(path, calendarName string, today time.Time, events []showcaseCalendarEvent) error {
	lines := []string{"BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Dash-Go Showcase Studio//EN", "CALSCALE:GREGORIAN", "X-WR-CALNAME:" + icsText(calendarName)}
	for _, event := range events {
		lines = append(lines, "BEGIN:VEVENT", "UID:"+event.UID, "DTSTAMP:"+icsStamp(today))
		if !event.RecurrenceID.IsZero() {
			if event.AllDay {
				lines = append(lines, "RECURRENCE-ID;VALUE=DATE:"+icsDate(event.RecurrenceID))
			} else {
				lines = append(lines, "RECURRENCE-ID:"+icsStamp(event.RecurrenceID))
			}
		}
		if event.AllDay {
			end := event.End
			if end.IsZero() || !end.After(event.Start) {
				end = event.Start.AddDate(0, 0, 1)
			}
			lines = append(lines, "DTSTART;VALUE=DATE:"+icsDate(event.Start), "DTEND;VALUE=DATE:"+icsDate(end))
		} else {
			lines = append(lines, "DTSTART:"+icsStamp(event.Start), "DTEND:"+icsStamp(event.End))
		}
		if event.RRULE != "" {
			lines = append(lines, "RRULE:"+event.RRULE)
		}
		for _, excluded := range event.ExDates {
			if event.AllDay {
				lines = append(lines, "EXDATE;VALUE=DATE:"+icsDate(excluded))
			} else {
				lines = append(lines, "EXDATE:"+icsStamp(excluded))
			}
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

func at(value time.Time, hour, minute int) time.Time {
	return time.Date(value.Year(), value.Month(), value.Day(), hour, minute, 0, 0, value.Location())
}

func dayInLocation(value time.Time, loc *time.Location) time.Time {
	value = value.In(loc)
	return time.Date(value.Year(), value.Month(), value.Day(), 0, 0, 0, 0, loc)
}

func startOfWeek(value time.Time) time.Time {
	value = day(value)
	offset := (int(value.Weekday()) + 6) % 7
	return value.AddDate(0, 0, -offset)
}

func nextWeekday(value time.Time, wanted time.Weekday) time.Time {
	value = day(value)
	for value.Weekday() != wanted {
		value = value.AddDate(0, 0, 1)
	}
	return value
}

// showcasePaydayAnchor keeps the visible Plans payday series and the Household
// Schedules payday rule on the same alternating-Friday cadence. Starting from
// the rolling fixture window guarantees useful history and future occurrences.
func showcasePaydayAnchor(today time.Time) time.Time {
	return nextWeekday(startOfWeek(day(today).AddDate(0, 0, -showcasePastDays)), time.Friday)
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
