package studiohost

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

type paths struct {
	installRoot   string
	runtimeApp    string
	runtimeServer string
	stateRoot     string
	scenarioRoot  string
	scenarioData  string
	scenarioHome  string
	logsRoot      string
	browserRoot   string
}

func resolvePaths(stateOverride string, requireRuntime bool) (paths, error) {
	exe, err := os.Executable()
	if err != nil {
		return paths{}, fmt.Errorf("locate Studio executable: %w", err)
	}
	return resolvePathsFromInstallRoot(filepath.Dir(exe), stateOverride, requireRuntime)
}

func resolvePathsFromInstallRoot(installRoot, stateOverride string, requireRuntime bool) (paths, error) {
	installRoot = filepath.Clean(installRoot)
	runtimeApp := filepath.Join(installRoot, "runtime", "app")
	serverName := "dash-go-showcase-server"
	if runtime.GOOS == "windows" {
		serverName += ".exe"
	}
	runtimeServer := filepath.Join(runtimeApp, "bin", serverName)
	if requireRuntime {
		if info, err := os.Stat(runtimeServer); err != nil || info.IsDir() {
			return paths{}, fmt.Errorf("installed Showcase runtime is incomplete: %s", runtimeServer)
		}
	}

	stateRoot := strings.TrimSpace(stateOverride)
	if stateRoot == "" {
		stateRoot = defaultStateRoot()
	}
	if stateRoot == "" {
		return paths{}, fmt.Errorf("could not determine a private Studio state folder")
	}
	stateRoot = filepath.Clean(stateRoot)
	return paths{
		installRoot:   installRoot,
		runtimeApp:    runtimeApp,
		runtimeServer: runtimeServer,
		stateRoot:     stateRoot,
		scenarioRoot:  filepath.Join(stateRoot, "scenario"),
		scenarioData:  filepath.Join(stateRoot, "scenario", "data"),
		scenarioHome:  filepath.Join(stateRoot, "scenario", "home"),
		logsRoot:      filepath.Join(stateRoot, "logs"),
		browserRoot:   filepath.Join(stateRoot, "browser-profile"),
	}, nil
}

func defaultStateRoot() string {
	if runtime.GOOS == "windows" {
		if base := strings.TrimSpace(os.Getenv("LOCALAPPDATA")); base != "" {
			return filepath.Join(base, "Dash-Go Showcase Studio")
		}
		if base, err := os.UserConfigDir(); err == nil && base != "" {
			return filepath.Join(base, "Dash-Go Showcase Studio")
		}
		return ""
	}
	if base := strings.TrimSpace(os.Getenv("XDG_DATA_HOME")); base != "" {
		return filepath.Join(base, "dash-go-showcase-studio")
	}
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		return filepath.Join(home, ".local", "share", "dash-go-showcase-studio")
	}
	return ""
}
