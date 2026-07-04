package fixtures

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestScenariosAreStableAndSeededLocally(t *testing.T) {
	ids := stableScenarioIDs()
	if len(ids) < 4 || ids[0] == "" {
		t.Fatalf("scenario catalog is incomplete: %#v", ids)
	}
	root := t.TempDir()
	app := filepath.Join(root, "app")
	home := filepath.Join(root, "home")
	if err := Seed(app, home, DefaultScenario, time.Date(2026, 6, 30, 12, 0, 0, 0, time.UTC)); err != nil {
		t.Fatal(err)
	}
	for _, rel := range []string{"config/household-people.json", "config/chore-wheel.json", "config/household-schedules.json", "config/todo/_lists.json", "calendars/calendars.json", "calendars/showcase-studio.ics"} {
		if _, err := os.Stat(filepath.Join(app, rel)); err != nil {
			t.Fatalf("missing %s: %v", rel, err)
		}
	}
	manifest, err := os.ReadFile(filepath.Join(app, "calendars", "calendars.json"))
	if err != nil || !contains(string(manifest), "calendars/showcase-studio.ics") {
		t.Fatalf("browser calendar manifest is missing the Showcase fixture: %v", err)
	}
	if _, err := os.Stat(filepath.Join(home, ".dashboard-family-board.json")); err != nil {
		t.Fatal(err)
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
		if err != nil || !contains(string(data), location.City) || !contains(string(data), location.TimeZone) {
			t.Fatalf("location settings missing for %s: %v", location.ID, err)
		}
		messages, err := os.ReadFile(filepath.Join(app, "config", "compliments.json"))
		if err != nil || !contains(string(messages), "studio-discovery") {
			t.Fatalf("Studio discovery messages missing for %s: %v", location.ID, err)
		}
	}
}

func contains(value, find string) bool {
	return len(find) == 0 || (len(value) >= len(find) && stringContains(value, find))
}
func stringContains(value, find string) bool {
	for i := 0; i+len(find) <= len(value); i++ {
		if value[i:i+len(find)] == find {
			return true
		}
	}
	return false
}

func TestLocationProfilesCarryTourAlertData(t *testing.T) {
	for _, location := range AllLocations() {
		if location.AlertEvent == "" || location.AlertSeverity == "" {
			t.Fatalf("location %s is missing its synthetic Tour alert metadata", location.ID)
		}
	}
}
