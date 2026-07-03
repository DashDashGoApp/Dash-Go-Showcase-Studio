package studiohost

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestValidatePurgeRequestRejectsUnsafeRoots(t *testing.T) {
	for _, root := range []string{".", string(filepath.Separator), filepath.VolumeName(string(filepath.Separator)) + string(filepath.Separator)} {
		if err := validatePurgeRequest(root, false, ""); err == nil {
			t.Fatalf("validatePurgeRequest(%q) accepted an unsafe root", root)
		}
	}
}

func TestValidatePurgeRequestRequiresConfirmationForCustomRoot(t *testing.T) {
	root := filepath.Join(t.TempDir(), "showcase-state")
	if err := validatePurgeRequest(root, true, ""); err == nil {
		t.Fatal("custom purge did not require confirmation")
	}
	if err := validatePurgeRequest(root, true, customPurgeConfirmation); err != nil {
		t.Fatalf("custom purge confirmation rejected: %v", err)
	}
}

func TestPurgeRemovesEntireStateRoot(t *testing.T) {
	stateRoot := filepath.Join(t.TempDir(), "showcase-state")
	for _, relative := range []string{"scenario/data/marker", "browser-profile/marker", "logs/showcase-server.log"} {
		path := filepath.Join(stateRoot, relative)
		if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte("fixture"), 0600); err != nil {
			t.Fatal(err)
		}
	}
	app := &App{options: Options{StateRoot: stateRoot, ConfirmPurge: customPurgeConfirmation}, paths: paths{stateRoot: stateRoot}}
	if err := app.purge(); err != nil {
		t.Fatalf("purge failed: %v", err)
	}
	if _, err := os.Stat(stateRoot); !os.IsNotExist(err) {
		t.Fatalf("state root still exists after purge: %v", err)
	}
}

func TestNewAllowsPurgeWhenRuntimePayloadIsUnavailable(t *testing.T) {
	stateRoot := filepath.Join(t.TempDir(), "showcase-state")
	app, err := New(Options{Action: "purge", StateRoot: stateRoot, ConfirmPurge: customPurgeConfirmation, Viewport: "1920x1080"})
	if err != nil {
		t.Fatalf("purge construction should not require a runnable payload: %v", err)
	}
	if app.paths.stateRoot != stateRoot {
		t.Fatalf("purge state root = %q, want %q", app.paths.stateRoot, stateRoot)
	}
}

func TestHubIsSingleStartTourEntryPoint(t *testing.T) {
	if !strings.Contains(hubHTML, "Start Tour") || !strings.Contains(hubHTML, "Choose a demo location") {
		t.Fatal("Studio Hub no longer presents the Start Tour location entry point")
	}
	for _, forbidden := range []string{"Capture Gallery", "Scenario", "/api/launch", "Reset"} {
		if strings.Contains(hubHTML, forbidden) || strings.Contains(hubJS, forbidden) {
			t.Fatalf("Studio Hub exposes retired scenario-menu surface: %s", forbidden)
		}
	}
	if !strings.Contains(hubJS, "/api/start-tour") {
		t.Fatal("Studio Hub does not call Start Tour API")
	}
}
