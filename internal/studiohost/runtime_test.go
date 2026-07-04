package studiohost

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"syscall"
	"testing"
	"time"
)

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
	responses := map[string]string{
		"/config/config.local.js":        "// Generated for Dash-Go Showcase Studio.\n",
		"/config/compliments.json":       `{"messages":[{"origin":"studio-normal"}]}`,
		"/calendars/calendars.json":      `[{"url":"calendars/showcase-studio.ics"}]`,
		"/calendars/showcase-studio.ics": "BEGIN:VCALENDAR\r\nSUMMARY:Breakfast together\r\nEND:VCALENDAR\r\n",
		"/api/weather":                   `{"source":"showcase-fixture","sources":[{"_source":"showcase"}]}`,
	}
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

func TestAssertClientVisibleScenarioDataRejectsFallbackContent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte("{}"))
	}))
	defer server.Close()

	if err := (&App{}).assertClientVisibleScenarioData(server.URL); err == nil {
		t.Fatal("assertClientVisibleScenarioData accepted a missing fixture marker")
	}
}
