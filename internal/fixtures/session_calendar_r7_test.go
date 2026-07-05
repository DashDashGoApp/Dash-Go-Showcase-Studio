package fixtures

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestSeededSessionCalendarsIncludeSchool(t *testing.T) {
	dataRoot := t.TempDir()
	home := t.TempDir()
	if err := SeedForLocation(dataRoot, home, DefaultScenario, "chicago", time.Date(2026, time.July, 4, 12, 0, 0, 0, time.UTC)); err != nil {
		t.Fatalf("seed Studio fixtures: %v", err)
	}
	body, err := os.ReadFile(filepath.Join(dataRoot, "config", "calendar-writeback.json"))
	if err != nil {
		t.Fatalf("read session calendar registry: %v", err)
	}
	var registry struct {
		Calendars []struct {
			Source   string `json:"source"`
			Writable bool   `json:"writable"`
			Enabled  bool   `json:"enabled"`
		} `json:"calendars"`
	}
	if err := json.Unmarshal(body, &registry); err != nil {
		t.Fatalf("decode session calendar registry: %v", err)
	}
	want := map[string]bool{
		"calendars/family.green.ics": false,
		"calendars/school.blue.ics":  false,
		"calendars/home.amber.ics":   false,
		"calendars/plans.violet.ics": false,
	}
	for _, calendar := range registry.Calendars {
		if _, ok := want[calendar.Source]; ok && calendar.Writable && calendar.Enabled {
			want[calendar.Source] = true
		}
	}
	for source, found := range want {
		if !found {
			t.Fatalf("Studio session registry missing writable %s", source)
		}
	}
}
