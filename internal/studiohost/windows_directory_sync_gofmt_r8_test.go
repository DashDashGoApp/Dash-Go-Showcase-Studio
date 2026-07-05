package studiohost

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestR815WindowsDirectorySyncOverlayPreservesGofmtImportOrder(t *testing.T) {
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("locate r8.15 source contract test")
	}
	enginePath := filepath.Join(filepath.Dir(thisFile), "..", "..", "tools", "patch_dashgo_engine.py")
	body, err := os.ReadFile(enginePath)
	if err != nil {
		t.Fatalf("read base Showcase overlay: %v", err)
	}
	source := string(body)
	for _, required := range []string{
		`'\t"errors"\n\t"os"\n\t"path/filepath"\n',`,
		`'\t"errors"\n\t"os"\n\t"path/filepath"\n\t"runtime"\n',`,
		`Showcase Windows directory-sync contract`,
		`if runtime.GOOS == "windows" {`,
	} {
		if !strings.Contains(source, required) {
			t.Fatalf("r8.15 fileio overlay contract is missing %q", required)
		}
	}
	if strings.Contains(source, `'\t"errors"\n\t"os"\n\t"runtime"\n',`) {
		t.Fatal("r8.15 overlay still inserts runtime before path/filepath")
	}
}
