package studiohost

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"

	"github.com/DashDashGoApp/Dash-Go-Showcase-Studio/internal/fixtures"
)

type runningRuntime struct {
	cmd  *exec.Cmd
	url  string
	done <-chan struct{}
}

func (a *App) prepareScenario(scenarioID string) error {
	return a.prepareScenarioForLocation(scenarioID, a.selectedLocation())
}

func (a *App) prepareScenarioForLocation(scenarioID, locationID string) error {
	scenario, ok := fixtures.Lookup(scenarioID)
	if !ok {
		return fmt.Errorf("unknown Showcase scenario %q", scenarioID)
	}
	if err := a.ensureStateRoot(); err != nil {
		return err
	}
	a.mu.Lock()
	active := a.runtime
	a.mu.Unlock()
	if active != nil {
		a.stopRuntime(active)
	}

	// Only disposable data is staged beneath the private state root. The Studio
	// runtime itself remains installed and is never copied or executed from here.
	stage := filepath.Join(a.paths.stateRoot, ".scenario-stage-"+randomSuffix())
	if err := os.RemoveAll(stage); err != nil {
		return fmt.Errorf("clear temporary Studio scenario data: %w", err)
	}
	defer os.RemoveAll(stage)
	stageData := filepath.Join(stage, "data")
	stageHome := filepath.Join(stage, "home")
	if err := os.MkdirAll(stageHome, 0700); err != nil {
		return fmt.Errorf("create staged Showcase home: %w", err)
	}
	if err := fixtures.SeedForLocation(stageData, stageHome, scenario.ID, locationID, time.Now()); err != nil {
		return fmt.Errorf("seed %s: %w", scenario.Title, err)
	}
	if err := fixtures.WriteRuntimeMarker(stage, scenario.ID, locationID, time.Now()); err != nil {
		return fmt.Errorf("write Showcase marker: %w", err)
	}
	if err := atomicScenarioSwap(a.paths.scenarioRoot, stage); err != nil {
		return fmt.Errorf("activate staged Showcase scenario data: %w", err)
	}
	return nil
}

func (a *App) startRuntime() (*runningRuntime, error) {
	a.mu.Lock()
	if a.runtime != nil {
		existing := a.runtime
		a.mu.Unlock()
		return existing, nil
	}
	a.mu.Unlock()
	if info, err := os.Stat(a.paths.scenarioData); err != nil || !info.IsDir() {
		return nil, fmt.Errorf("no prepared Showcase scenario data exists; reset a scenario first")
	}
	port, err := chooseLoopbackPort()
	if err != nil {
		return nil, err
	}
	exe := a.paths.runtimeServer
	logPath := filepath.Join(a.paths.logsRoot, "showcase-server.log")
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0600)
	if err != nil {
		return nil, fmt.Errorf("open Showcase runtime log: %w", err)
	}
	cmd := exec.Command(exe)
	prepareStudioChildCommand(cmd)
	cmd.Dir = a.paths.runtimeApp
	cmd.Env = append(os.Environ(),
		"DASHGO_HOME="+a.paths.scenarioHome,
		"DASHGO_SHOWCASE=1",
		"DASHGO_SHOWCASE_DATA_ROOT="+a.paths.scenarioData,
		fmt.Sprintf("DASH_CONTROL_PORT=%d", port),
	)
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	if err := cmd.Start(); err != nil {
		_ = logFile.Close()
		return nil, fmt.Errorf("start local Showcase server: %w", err)
	}
	done := make(chan struct{})
	runtime := &runningRuntime{cmd: cmd, url: fmt.Sprintf("http://127.0.0.1:%d", port), done: done}
	go func() {
		_ = cmd.Wait()
		_ = logFile.Close()
		close(done)
	}()
	if err := a.assertReady(runtime.url); err != nil {
		a.stopRuntime(runtime)
		tail, _ := tailFile(logPath, 80*1024)
		if tail != "" {
			return nil, fmt.Errorf("Showcase server did not become ready: %w\n%s", err, tail)
		}
		return nil, fmt.Errorf("Showcase server did not become ready: %w", err)
	}
	if err := a.assertClientVisibleScenarioData(runtime.url); err != nil {
		a.stopRuntime(runtime)
		tail, _ := tailFile(logPath, 80*1024)
		if tail != "" {
			return nil, fmt.Errorf("Showcase server did not expose the active scenario data; refusing to open an empty Studio session: %w\n%s", err, tail)
		}
		return nil, fmt.Errorf("Showcase server did not expose the active scenario data; refusing to open an empty Studio session: %w", err)
	}
	a.mu.Lock()
	a.runtime = runtime
	a.mu.Unlock()
	return runtime, nil
}

func (a *App) stopRuntime(runtime *runningRuntime) {
	if runtime == nil || runtime.cmd == nil || runtime.cmd.Process == nil {
		return
	}
	select {
	case <-runtime.done:
		// The runtime already exited; do not signal a recycled process handle.
	default:
		if err := runtime.cmd.Process.Signal(os.Interrupt); err != nil {
			_ = runtime.cmd.Process.Kill()
		}
		select {
		case <-runtime.done:
		case <-time.After(3 * time.Second):
			_ = runtime.cmd.Process.Kill()
			<-runtime.done
		}
	}
	a.mu.Lock()
	if a.runtime == runtime {
		a.runtime = nil
	}
	a.mu.Unlock()
	if err := a.discardSessionScenario(); err != nil {
		fmt.Fprintf(os.Stderr, "Showcase session cleanup warning: %v\n", err)
	}
}

// discardSessionScenario removes the only writable Studio data after its local
// runtime stops. A later launch reseeds a fresh scenario, so edits never cross
// session boundaries even if a previous process exits unexpectedly.
func (a *App) discardSessionScenario() error {
	if err := os.RemoveAll(a.paths.scenarioRoot); err != nil {
		return fmt.Errorf("discard Studio session data: %w", err)
	}
	return nil
}

func (a *App) stopActiveRuntime() {
	a.mu.Lock()
	active := a.runtime
	a.mu.Unlock()
	if active != nil {
		a.stopRuntime(active)
	}
}

func (a *App) assertReady(baseURL string) error {
	client := &http.Client{Timeout: 1500 * time.Millisecond}
	deadline := time.Now().Add(20 * time.Second)
	var last error
	for time.Now().Before(deadline) {
		response, err := client.Get(baseURL + "/api/ready")
		if err == nil {
			_, _ = io.Copy(io.Discard, response.Body)
			_ = response.Body.Close()
			if response.StatusCode == http.StatusOK {
				return nil
			}
			last = fmt.Errorf("/api/ready returned HTTP %d", response.StatusCode)
		} else {
			last = err
		}
		time.Sleep(200 * time.Millisecond)
	}
	if last == nil {
		last = fmt.Errorf("readiness timed out")
	}
	return last
}

type clientVisibleScenarioData struct {
	Path      string
	Contains  string
	ParseJSON bool
}

var requiredClientVisibleScenarioData = []clientVisibleScenarioData{
	{Path: "/config/config.local.js", Contains: "Generated for Dash-Go Showcase Studio"},
	{Path: "/config/compliments.json", Contains: "studio-normal", ParseJSON: true},
	{Path: "/calendars/calendars.json", Contains: "calendars/family.green.ics", ParseJSON: true},
	{Path: "/calendars/calendars.json", Contains: "calendars/school.blue.ics", ParseJSON: true},
	{Path: "/calendars/calendars.json", Contains: "calendars/home.amber.ics", ParseJSON: true},
	{Path: "/calendars/calendars.json", Contains: "calendars/plans.violet.ics", ParseJSON: true},
	{Path: "/calendars/family.green.ics", Contains: "SUMMARY:Family meal plan"},
	{Path: "/calendars/school.blue.ics", Contains: "SUMMARY:Summer learning camp"},
	{Path: "/calendars/home.amber.ics", Contains: "SUMMARY:Grocery pickup"},
	{Path: "/calendars/plans.violet.ics", Contains: "SUMMARY:Saturday farmers market"},
	{Path: "/calendars/chore-wheel.ics", Contains: "SUMMARY:Kitchen reset —"},
	{Path: "/calendars/routines.ics", Contains: "SUMMARY:Morning ready — Avery"},
	{Path: "/calendars/maintenance.ics", Contains: "SUMMARY:Test smoke detectors"},
	{Path: "/api/weather", Contains: "showcase-fixture", ParseJSON: true},
}

const (
	clientVisibleScenarioDataAttempts   = 30
	clientVisibleScenarioDataRetryDelay = 100 * time.Millisecond
)

// assertClientVisibleScenarioData verifies the exact files and local endpoint
// the browser consumes. Readiness alone only proves that the server bound its
// loopback port; it does not prove that the disposable scenario root and
// offline preview data are visible to the dashboard UI.
//
// On Windows, a just-renamed scenario directory can be visible to the child
// server before every individual fixture file is immediately openable. Do not
// open the browser on that first transient response: wait a short, bounded
// time for every browser-consumed route to become visible.
func (a *App) assertClientVisibleScenarioData(baseURL string) error {
	return assertClientVisibleScenarioDataWithRetry(
		baseURL,
		clientVisibleScenarioDataAttempts,
		clientVisibleScenarioDataRetryDelay,
		time.Sleep,
	)
}

func assertClientVisibleScenarioDataWithRetry(
	baseURL string,
	attempts int,
	delay time.Duration,
	sleep func(time.Duration),
) error {
	if attempts < 1 {
		attempts = 1
	}
	if sleep == nil {
		sleep = time.Sleep
	}

	var last error
	for attempt := 0; attempt < attempts; attempt++ {
		last = assertClientVisibleScenarioDataOnce(baseURL)
		if last == nil {
			return nil
		}
		if attempt+1 < attempts && delay > 0 {
			sleep(delay)
		}
	}
	return fmt.Errorf("Showcase scenario data did not become client-visible after %d attempt(s): %w", attempts, last)
}

func assertClientVisibleScenarioDataOnce(baseURL string) error {
	client := &http.Client{Timeout: 1500 * time.Millisecond}
	for _, probe := range requiredClientVisibleScenarioData {
		response, err := client.Get(baseURL + probe.Path)
		if err != nil {
			return fmt.Errorf("read %s: %w", probe.Path, err)
		}
		body, readErr := io.ReadAll(io.LimitReader(response.Body, 256*1024))
		_ = response.Body.Close()
		if readErr != nil {
			return fmt.Errorf("read %s response: %w", probe.Path, readErr)
		}
		if response.StatusCode != http.StatusOK {
			return fmt.Errorf("%s returned HTTP %d", probe.Path, response.StatusCode)
		}
		if probe.ParseJSON {
			var decoded any
			if err := json.Unmarshal(body, &decoded); err != nil {
				return fmt.Errorf("%s did not return JSON: %w", probe.Path, err)
			}
		}
		if !bytes.Contains(body, []byte(probe.Contains)) {
			return fmt.Errorf("%s did not contain the required Showcase fixture marker", probe.Path)
		}
	}
	return nil
}

func chooseLoopbackPort() (int, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, fmt.Errorf("reserve loopback port: %w", err)
	}
	defer listener.Close()
	address, ok := listener.Addr().(*net.TCPAddr)
	if !ok || address.Port < 1024 {
		return 0, fmt.Errorf("received invalid loopback port")
	}
	return address.Port, nil
}

func randomSuffix() string {
	var raw [8]byte
	if _, err := rand.Read(raw[:]); err == nil {
		return hex.EncodeToString(raw[:])
	}
	return fmt.Sprintf("%d", time.Now().UnixNano())
}

const (
	scenarioRenameAttempts     = 15
	scenarioRenameInitialDelay = 50 * time.Millisecond
	scenarioRenameMaximumDelay = 500 * time.Millisecond
)

func atomicScenarioSwap(active, stage string) error {
	previous := active + ".previous-" + randomSuffix()
	hadActive := false
	if _, err := os.Stat(active); err == nil {
		if err := renameScenarioPath(active, previous); err != nil {
			return fmt.Errorf("move prior scenario data aside: %w", err)
		}
		hadActive = true
	} else if !os.IsNotExist(err) {
		return err
	}
	if err := renameScenarioPath(stage, active); err != nil {
		if hadActive {
			_ = renameScenarioPath(previous, active)
		}
		return err
	}
	if hadActive {
		_ = os.RemoveAll(previous)
	}
	return nil
}

// renameScenarioPath keeps the data reset transaction atomic. Windows can
// briefly deny a directory rename after endpoint protection or indexing opens
// an observation handle. A bounded retry is safe because both paths remain on
// the same private state volume and no fallback copy is used.
func renameScenarioPath(source, destination string) error {
	return retryScenarioRename(os.Rename, time.Sleep, runtime.GOOS == "windows", source, destination)
}

func retryScenarioRename(
	rename func(string, string) error,
	sleep func(time.Duration),
	isWindows bool,
	source, destination string,
) error {
	var last error
	attempts := 0
	for attempt := 0; attempt < scenarioRenameAttempts; attempt++ {
		attempts = attempt + 1
		last = rename(source, destination)
		if last == nil {
			return nil
		}
		if !isTransientWindowsRenameError(last) || !isWindows || attempts == scenarioRenameAttempts {
			break
		}
		sleep(scenarioRenameBackoff(attempt))
	}
	return fmt.Errorf("rename %s to %s after %d attempt(s): %w", source, destination, attempts, last)
}

func isTransientWindowsRenameError(err error) bool {
	return errors.Is(err, os.ErrPermission)
}

func scenarioRenameBackoff(attempt int) time.Duration {
	delay := scenarioRenameInitialDelay
	for step := 0; step < attempt && delay < scenarioRenameMaximumDelay; step++ {
		delay *= 2
	}
	if delay > scenarioRenameMaximumDelay {
		return scenarioRenameMaximumDelay
	}
	return delay
}

func tailFile(path string, maximum int64) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return "", err
	}
	start := int64(0)
	if info.Size() > maximum {
		start = info.Size() - maximum
	}
	if _, err := file.Seek(start, io.SeekStart); err != nil {
		return "", err
	}
	var out bytes.Buffer
	if _, err := io.Copy(&out, file); err != nil {
		return "", err
	}
	return out.String(), nil
}
