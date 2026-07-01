package studiohost

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"github.com/DashDashGoApp/Dash-Go-Showcase-Studio/internal/fixtures"
)

type App struct {
	options Options
	paths   paths

	mu      sync.Mutex
	runtime *runningRuntime
	browser *browserSession
}

func New(options Options) (*App, error) {
	normalized, err := options.normalized()
	if err != nil {
		return nil, err
	}
	// Maintenance removal actions must remain available even when a partial or
	// corrupted runtime payload cannot be started. They only act on the exact
	// private state root; all normal app actions still require a complete runtime.
	requireRuntime := normalized.Action != "clean" && normalized.Action != "purge"
	p, err := resolvePaths(normalized.StateRoot, requireRuntime)
	if err != nil {
		return nil, err
	}
	return &App{options: normalized, paths: p}, nil
}

func (a *App) Run() error {
	switch a.options.Action {
	case "diagnose":
		return a.diagnose()
	case "clean":
		return a.clean()
	case "purge":
		return a.purge()
	case "self-test":
		return a.selfTest()
	case "reset":
		scenario := a.selectedScenario()
		if err := a.prepareScenarioForLocation(scenario, a.selectedLocation()); err != nil {
			return err
		}
		fmt.Printf("RESET: %s\n", scenario)
		return nil
	case "start":
		if a.options.NoBrowser {
			if err := a.prepareScenario(a.selectedScenario()); err != nil {
				return err
			}
			runtime, err := a.startRuntime()
			if err != nil {
				return err
			}
			defer a.stopRuntime(runtime)
			fmt.Printf("READY %s\n", runtime.url)
			return nil
		}
		return a.startHub()
	default:
		return fmt.Errorf("unsupported action %q", a.options.Action)
	}
}

func (a *App) selectedLocation() string {
	if a.options.Location != "" {
		return a.options.Location
	}
	return fixtures.DefaultLocation().ID
}

func (a *App) selectedScenario() string {
	if a.options.Scenario != "" {
		return a.options.Scenario
	}
	return fixtures.DefaultScenario
}

func (a *App) diagnose() error {
	fmt.Println("Dash-Go Showcase Studio diagnostics")
	fmt.Println("Install root:", a.paths.installRoot)
	fmt.Println("Runtime app:", a.paths.runtimeApp)
	fmt.Println("Runtime server:", a.paths.runtimeServer)
	fmt.Println("State root:", a.paths.stateRoot)
	fmt.Println("Demo locations:")
	for _, location := range fixtures.AllLocations() {
		fmt.Printf("  - %s: %s (%s)\n", location.ID, location.Label, location.TimeZone)
	}
	fmt.Println("Internal fixture scenarios:")
	for _, scenario := range fixtures.AllScenarios() {
		fmt.Printf("  - %s: %s\n", scenario.ID, scenario.Title)
	}
	browser, err := findBrowser()
	if err != nil {
		fmt.Println("Browser: unavailable (", err, ")")
	} else {
		fmt.Println("Browser:", browser.path)
	}
	if info, err := os.Stat(a.paths.runtimeServer); err != nil || info.IsDir() {
		return fmt.Errorf("runtime verification failed: %s", a.paths.runtimeServer)
	}
	return nil
}

func (a *App) clean() error {
	a.mu.Lock()
	if a.runtime != nil {
		a.mu.Unlock()
		return fmt.Errorf("cannot clean while this Studio session has a running runtime")
	}
	a.mu.Unlock()
	if err := os.RemoveAll(a.paths.workspaceRoot); err != nil {
		return fmt.Errorf("remove private workspace: %w", err)
	}
	if err := os.RemoveAll(a.paths.browserRoot); err != nil {
		return fmt.Errorf("remove private browser profile: %w", err)
	}
	fmt.Println("CLEANED private Showcase workspace")
	return nil
}

func (a *App) purge() error {
	a.mu.Lock()
	active := a.runtime
	a.mu.Unlock()
	if active != nil {
		a.stopRuntime(active)
	}
	if err := validatePurgeRequest(a.paths.stateRoot, a.options.StateRoot != "", a.options.ConfirmPurge); err != nil {
		return err
	}
	if _, err := os.Stat(a.paths.stateRoot); err != nil {
		if os.IsNotExist(err) {
			fmt.Println("PURGED private Showcase Studio state (nothing existed)")
			return nil
		}
		return fmt.Errorf("inspect private Showcase state: %w", err)
	}
	if err := os.RemoveAll(a.paths.stateRoot); err != nil {
		return fmt.Errorf("purge private Showcase state: %w", err)
	}
	if _, err := os.Stat(a.paths.stateRoot); err == nil {
		return fmt.Errorf("purge private Showcase state left its root behind: %s", a.paths.stateRoot)
	} else if !os.IsNotExist(err) {
		return fmt.Errorf("verify private Showcase state purge: %w", err)
	}
	fmt.Println("PURGED private Showcase Studio state")
	return nil
}

func validatePurgeRequest(stateRoot string, customRoot bool, confirmation string) error {
	clean := filepath.Clean(stateRoot)
	if clean == "." || clean == string(filepath.Separator) || clean == filepath.VolumeName(clean)+string(filepath.Separator) {
		return fmt.Errorf("refusing to purge an unsafe state root: %q", stateRoot)
	}
	parent := filepath.Dir(clean)
	if parent == clean || parent == "." {
		return fmt.Errorf("refusing to purge an unsafe state root: %q", stateRoot)
	}
	if customRoot && confirmation != customPurgeConfirmation {
		return fmt.Errorf("purging a custom --state-root requires --confirm-purge %q", customPurgeConfirmation)
	}
	return nil
}

func (a *App) selfTest() error {
	scenario := a.selectedScenario()
	if err := a.prepareScenarioForLocation(scenario, a.selectedLocation()); err != nil {
		return err
	}
	runtime, err := a.startRuntime()
	if err != nil {
		return err
	}
	defer a.stopRuntime(runtime)
	if err := a.assertReady(runtime.url); err != nil {
		return err
	}
	fmt.Printf("PASS: Showcase self-test completed for %s\n", scenario)
	return nil
}

func (a *App) ensureStateRoot() error {
	for _, path := range []string{a.paths.stateRoot, a.paths.logsRoot} {
		if err := os.MkdirAll(path, 0755); err != nil {
			return fmt.Errorf("create Studio state directory %s: %w", filepath.Base(path), err)
		}
	}
	return nil
}
