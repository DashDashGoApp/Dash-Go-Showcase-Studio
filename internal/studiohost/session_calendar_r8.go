package studiohost

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strings"
	"time"
)

const (
	r8SessionEventCapabilityAttempts   = 30
	r8SessionEventCapabilityRetryDelay = 100 * time.Millisecond
)

// assertShowcaseSessionEventManagementReady proves that the browser-visible
// cache carries the same writeback capability metadata the event popup needs.
// Calendar Manager may correctly say a source is writable while a stale cache
// still lacks writeback.candidate, which would hide Manage controls.
func (a *App) assertShowcaseSessionEventManagementReady(baseURL string) error {
	if err := r8RebuildSessionEventCache(baseURL); err != nil {
		return err
	}
	return r8AssertSessionEventCapabilitiesWithRetry(
		baseURL,
		r8SessionEventCapabilityAttempts,
		r8SessionEventCapabilityRetryDelay,
		time.Sleep,
	)
}

func r8RebuildSessionEventCache(baseURL string) error {
	request, err := http.NewRequest(
		http.MethodPost,
		strings.TrimRight(baseURL, "/")+"/api/cache/rebuild",
		bytes.NewBufferString("{}"),
	)
	if err != nil {
		return fmt.Errorf("create Showcase event-cache rebuild request: %w", err)
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := (&http.Client{Timeout: 3 * time.Second}).Do(request)
	if err != nil {
		return fmt.Errorf("rebuild Showcase event cache: %w", err)
	}
	defer response.Body.Close()
	body, readErr := io.ReadAll(io.LimitReader(response.Body, 256*1024))
	if readErr != nil {
		return fmt.Errorf("read Showcase event-cache rebuild response: %w", readErr)
	}
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("Showcase event-cache rebuild returned HTTP %d: %s", response.StatusCode, strings.TrimSpace(string(body)))
	}
	return nil
}

func r8AssertSessionEventCapabilitiesWithRetry(baseURL string, attempts int, delay time.Duration, sleep func(time.Duration)) error {
	if attempts < 1 {
		attempts = 1
	}
	if sleep == nil {
		sleep = time.Sleep
	}
	var last error
	for attempt := 0; attempt < attempts; attempt++ {
		last = r8AssertSessionEventCapabilitiesOnce(baseURL)
		if last == nil {
			return nil
		}
		if attempt+1 < attempts && delay > 0 {
			sleep(delay)
		}
	}
	return fmt.Errorf("Showcase event-management capability cache did not become ready after %d attempt(s): %w", attempts, last)
}

func r8AssertSessionEventCapabilitiesOnce(baseURL string) error {
	response, err := (&http.Client{Timeout: 1500 * time.Millisecond}).Get(
		strings.TrimRight(baseURL, "/") + "/cache/events.cache.json?showcase-session-event-management=1",
	)
	if err != nil {
		return fmt.Errorf("read Showcase event cache: %w", err)
	}
	defer response.Body.Close()
	body, readErr := io.ReadAll(io.LimitReader(response.Body, 2*1024*1024))
	if readErr != nil {
		return fmt.Errorf("read Showcase event cache response: %w", readErr)
	}
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("Showcase event cache returned HTTP %d", response.StatusCode)
	}
	var cache struct {
		Events []map[string]any `json:"events"`
	}
	if err := json.Unmarshal(body, &cache); err != nil {
		return fmt.Errorf("decode Showcase event cache: %w", err)
	}
	return r8ValidateSessionEventCapabilities(cache.Events)
}

func r8ValidateSessionEventCapabilities(events []map[string]any) error {
	candidateBySource := map[string]bool{}
	libraryRecurring := false
	volunteerSingle := false
	for _, event := range events {
		calendar, _ := event["cal"].(map[string]any)
		source, _ := calendar["url"].(string)
		if _, expected := sessionCalendarWritableSources[source]; !expected {
			continue
		}
		writeback, _ := event["writeback"].(map[string]any)
		if !r8Bool(writeback["candidate"]) {
			continue
		}
		candidateBySource[source] = true
		title, _ := event["title"].(string)
		if source == "calendars/plans.violet.ics" && title == "Library pickup" && r8Bool(writeback["canOccurrenceEdit"]) {
			libraryRecurring = true
		}
		if source == "calendars/plans.violet.ics" && title == "Food pantry volunteer shift" && r8Bool(writeback["canEdit"]) {
			volunteerSingle = true
		}
	}
	missing := make([]string, 0, len(sessionCalendarWritableSources))
	for source := range sessionCalendarWritableSources {
		if !candidateBySource[source] {
			missing = append(missing, source)
		}
	}
	sort.Strings(missing)
	if len(missing) != 0 {
		return fmt.Errorf("Showcase event cache is missing writeback candidates for: %s", strings.Join(missing, ", "))
	}
	if !libraryRecurring {
		return fmt.Errorf("Showcase event cache is missing Library pickup recurring-management capability")
	}
	if !volunteerSingle {
		return fmt.Errorf("Showcase event cache is missing Food pantry volunteer shift single-event capability")
	}
	return nil
}

func r8Bool(value any) bool {
	result, _ := value.(bool)
	return result
}
