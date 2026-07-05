package studiohost

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestR8ValidateSessionEventCapabilitiesRequiresPopupMetadata(t *testing.T) {
	events := []map[string]any{
		r8Event("calendars/family.green.ics", "Family meal plan", true, false),
		r8Event("calendars/school.blue.ics", "Summer learning camp", true, false),
		r8Event("calendars/home.amber.ics", "Grocery pickup", true, false),
		r8Event("calendars/plans.violet.ics", "Library pickup", true, true),
		r8Event("calendars/plans.violet.ics", "Food pantry volunteer shift", true, false),
	}
	if err := r8ValidateSessionEventCapabilities(events); err != nil {
		t.Fatalf("complete editable-event cache was rejected: %v", err)
	}
}

func TestR8ValidateSessionEventCapabilitiesRejectsMissingSingleEventCapability(t *testing.T) {
	events := []map[string]any{
		r8Event("calendars/family.green.ics", "Family meal plan", true, false),
		r8Event("calendars/school.blue.ics", "Summer learning camp", true, false),
		r8Event("calendars/home.amber.ics", "Grocery pickup", true, false),
		r8Event("calendars/plans.violet.ics", "Library pickup", true, true),
		r8Event("calendars/plans.violet.ics", "Food pantry volunteer shift", false, false),
	}
	if err := r8ValidateSessionEventCapabilities(events); err == nil || !strings.Contains(err.Error(), "Food pantry volunteer shift") {
		t.Fatalf("missing single-event capability was accepted: %v", err)
	}
}

func TestR8EventCapabilityCacheProtocol(t *testing.T) {
	events := []map[string]any{
		r8Event("calendars/family.green.ics", "Family meal plan", true, false),
		r8Event("calendars/school.blue.ics", "Summer learning camp", true, false),
		r8Event("calendars/home.amber.ics", "Grocery pickup", true, false),
		r8Event("calendars/plans.violet.ics", "Library pickup", true, true),
		r8Event("calendars/plans.violet.ics", "Food pantry volunteer shift", true, false),
	}
	var rebuilt bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/cache/rebuild":
			if r.Method != http.MethodPost {
				t.Errorf("rebuild method = %s, want POST", r.Method)
			}
			rebuilt = true
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"ok":true}`))
		case "/cache/events.cache.json":
			if !rebuilt {
				t.Error("event cache was read before rebuild")
			}
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{"events": events})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	if err := r8RebuildSessionEventCache(server.URL); err != nil {
		t.Fatalf("rebuild request failed: %v", err)
	}
	if err := r8AssertSessionEventCapabilitiesWithRetry(server.URL, 1, 0, nil); err != nil {
		t.Fatalf("event cache readiness failed: %v", err)
	}
}

func TestR8RuntimeChecksEventCapabilitiesAfterWritebackStatus(t *testing.T) {
	body, err := os.ReadFile("runtime.go")
	if err != nil {
		t.Fatal(err)
	}
	text := string(body)
	writeback := strings.Index(text, "assertSessionCalendarWritebackReady(runtime.url)")
	capabilities := strings.Index(text, "assertShowcaseSessionEventManagementReady(runtime.url)")
	if writeback < 0 || capabilities < 0 || capabilities < writeback {
		t.Fatalf("runtime does not verify popup capabilities after calendar writeback status")
	}
}

func r8Event(source, title string, canEdit, canOccurrenceEdit bool) map[string]any {
	return map[string]any{
		"title": title,
		"cal":   map[string]any{"url": source},
		"writeback": map[string]any{
			"candidate":         true,
			"canEdit":           canEdit,
			"canOccurrenceEdit": canOccurrenceEdit,
		},
	}
}
