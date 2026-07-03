package studiohost

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestResolvePathsSeparatesInstalledRuntimeFromMutableState(t *testing.T) {
	installRoot := filepath.Join(t.TempDir(), "installed")
	serverName := "dash-go-showcase-server"
	if filepath.Separator == '\\' {
		serverName += ".exe"
	}
	server := filepath.Join(installRoot, "runtime", "app", "bin", serverName)
	if err := os.MkdirAll(filepath.Dir(server), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(server, []byte("runtime"), 0755); err != nil {
		t.Fatal(err)
	}

	stateRoot := filepath.Join(t.TempDir(), "state")
	paths, err := resolvePathsFromInstallRoot(installRoot, stateRoot, true)
	if err != nil {
		t.Fatal(err)
	}
	if paths.runtimeServer != server {
		t.Fatalf("runtime server = %q, want %q", paths.runtimeServer, server)
	}
	if pathWithin(stateRoot, paths.runtimeServer) {
		t.Fatalf("runtime server is incorrectly located beneath mutable state: %q", paths.runtimeServer)
	}
	for label, path := range map[string]string{
		"scenario root": paths.scenarioRoot,
		"scenario data": paths.scenarioData,
		"scenario home": paths.scenarioHome,
		"logs":          paths.logsRoot,
		"browser":       paths.browserRoot,
	} {
		if !pathWithin(stateRoot, path) {
			t.Fatalf("%s escapes state root: %q", label, path)
		}
	}
}

func pathWithin(root, path string) bool {
	rel, err := filepath.Rel(filepath.Clean(root), filepath.Clean(path))
	if err != nil {
		return false
	}
	return rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator))
}
