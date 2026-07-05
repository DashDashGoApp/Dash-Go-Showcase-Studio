package studiohost

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestR812PortabilityOverlayKeepsWindowsDirectorySyncPlatformScoped(t *testing.T) {
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("locate r8.13 source contract test")
	}
	enginePath := filepath.Join(filepath.Dir(thisFile), "..", "..", "tools", "patch_dashgo_engine.py")
	body, err := os.ReadFile(enginePath)
	if err != nil {
		t.Fatalf("read base Showcase overlay: %v", err)
	}
	source := string(body)
	for _, required := range []string{
		`fileio = app / "internal/fileio/fileio.go"`,
		`"runtime"`,
		`Showcase Windows directory-sync contract`,
		`if runtime.GOOS == "windows" {`,
		`return nil`,
	} {
		if !strings.Contains(source, required) {
			t.Fatalf("r8.13 Windows directory-sync contract is missing %q", required)
		}
	}
}
