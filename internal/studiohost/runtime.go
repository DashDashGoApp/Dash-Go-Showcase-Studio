package studiohost

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
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

	stage := filepath.Join(a.paths.stateRoot, ".workspace-stage-"+randomSuffix())
	if err := os.RemoveAll(stage); err != nil {
		return fmt.Errorf("clear temporary Studio stage: %w", err)
	}
	defer os.RemoveAll(stage)
	stageApp := filepath.Join(stage, "app")
	stageHome := filepath.Join(stage, "home")
	if err := copyTree(a.paths.runtimeApp, stageApp); err != nil {
		return fmt.Errorf("stage pinned Dash-Go runtime: %w", err)
	}
	if err := os.MkdirAll(stageHome, 0700); err != nil {
		return fmt.Errorf("create staged Showcase home: %w", err)
	}
	// Studio fixtures own this disposable staging data. The pinned Dash-Go
	// runtime's maintenance CLI is skipped on Windows because its durable
	// parent-directory sync is denied in the GitHub-hosted staged workspace.
	if runtime.GOOS != "windows" {
		if err := a.runRuntimeCLI(stageApp, stageHome, "--setup-demo-mode", "--reset"); err != nil {
			return fmt.Errorf("seed baseline Dash-Go fixture: %w", err)
		}
	}
	if err := fixtures.SeedForLocation(stageApp, stageHome, scenario.ID, locationID, time.Now()); err != nil {
		return fmt.Errorf("seed %s: %w", scenario.Title, err)
	}
	if runtime.GOOS != "windows" {
		if err := a.runRuntimeCLI(stageApp, stageHome, "--gen-calendars"); err != nil {
			return fmt.Errorf("generate owned household calendars: %w", err)
		}
	}
	if err := fixtures.WriteRuntimeMarker(stage, scenario.ID, locationID, time.Now()); err != nil {
		return fmt.Errorf("write Showcase marker: %w", err)
	}
	if err := atomicWorkspaceSwap(a.paths.workspaceRoot, stage); err != nil {
		return fmt.Errorf("activate staged Showcase workspace: %w", err)
	}
	return nil
}

func (a *App) runRuntimeCLI(appRoot, home string, args ...string) error {
	exe := filepath.Join(appRoot, "bin", filepath.Base(a.paths.runtimeServer))
	if _, err := os.Stat(exe); err != nil {
		return fmt.Errorf("runtime command missing: %w", err)
	}
	cmd := exec.Command(exe, args...)
	prepareStudioChildCommand(cmd)
	cmd.Dir = appRoot
	cmd.Env = append(os.Environ(), "DASHGO_HOME="+home, "DASHGO_SHOWCASE=1")
	output, err := cmd.CombinedOutput()
	if err != nil {
		text := strings.TrimSpace(string(output))
		if len(text) > 4000 {
			text = text[len(text)-4000:]
		}
		if text == "" {
			return err
		}
		return fmt.Errorf("%w\n%s", err, text)
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
	if _, err := os.Stat(a.paths.workspaceApp); err != nil {
		return nil, fmt.Errorf("no prepared Showcase workspace exists; reset a scenario first")
	}
	port, err := chooseLoopbackPort()
	if err != nil {
		return nil, err
	}
	exe := filepath.Join(a.paths.workspaceApp, "bin", filepath.Base(a.paths.runtimeServer))
	logPath := filepath.Join(a.paths.logsRoot, "showcase-server.log")
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0600)
	if err != nil {
		return nil, fmt.Errorf("open Showcase runtime log: %w", err)
	}
	cmd := exec.Command(exe)
	prepareStudioChildCommand(cmd)
	cmd.Dir = a.paths.workspaceApp
	cmd.Env = append(os.Environ(),
		"DASHGO_HOME="+a.paths.workspaceHome,
		"DASHGO_SHOWCASE=1",
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

func copyTree(source, destination string) error {
	return filepath.Walk(source, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		target := filepath.Join(destination, rel)
		if info.IsDir() {
			return os.MkdirAll(target, info.Mode().Perm())
		}
		if !info.Mode().IsRegular() {
			return fmt.Errorf("runtime contains unsupported non-regular file: %s", rel)
		}
		if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
			return err
		}
		in, err := os.Open(path)
		if err != nil {
			return err
		}
		defer in.Close()
		out, err := os.OpenFile(target, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, info.Mode().Perm())
		if err != nil {
			return err
		}
		_, copyErr := io.Copy(out, in)
		closeErr := out.Close()
		if copyErr != nil {
			return copyErr
		}
		return closeErr
	})
}

const (
	workspaceRenameAttempts     = 15
	workspaceRenameInitialDelay = 50 * time.Millisecond
	workspaceRenameMaximumDelay = 500 * time.Millisecond
)

func atomicWorkspaceSwap(workspace, stage string) error {
	previous := workspace + ".previous-" + randomSuffix()
	hadWorkspace := false
	if _, err := os.Stat(workspace); err == nil {
		if err := renameWorkspacePath(workspace, previous); err != nil {
			return fmt.Errorf("move prior workspace aside: %w", err)
		}
		hadWorkspace = true
	} else if !os.IsNotExist(err) {
		return err
	}
	if err := renameWorkspacePath(stage, workspace); err != nil {
		if hadWorkspace {
			_ = renameWorkspacePath(previous, workspace)
		}
		return err
	}
	if hadWorkspace {
		_ = os.RemoveAll(previous)
	}
	return nil
}

// renameWorkspacePath keeps the scenario reset transaction atomic. Windows can
// briefly deny a directory rename immediately after an executable inside the
// staged workspace exits, for example while endpoint protection or indexing has
// an observation handle open. A bounded retry is safe because the source and
// destination stay on the same state volume and no fallback copy is used.
func renameWorkspacePath(source, destination string) error {
	return retryWorkspaceRename(os.Rename, time.Sleep, runtime.GOOS == "windows", source, destination)
}

func retryWorkspaceRename(
	rename func(string, string) error,
	sleep func(time.Duration),
	isWindows bool,
	source, destination string,
) error {
	var last error
	attempts := 0
	for attempt := 0; attempt < workspaceRenameAttempts; attempt++ {
		attempts = attempt + 1
		last = rename(source, destination)
		if last == nil {
			return nil
		}
		if !isTransientWindowsRenameError(last) || !isWindows || attempts == workspaceRenameAttempts {
			break
		}
		sleep(workspaceRenameBackoff(attempt))
	}
	return fmt.Errorf("rename %s to %s after %d attempt(s): %w", source, destination, attempts, last)
}

func isTransientWindowsRenameError(err error) bool {
	return errors.Is(err, os.ErrPermission)
}

func workspaceRenameBackoff(attempt int) time.Duration {
	delay := workspaceRenameInitialDelay
	for step := 0; step < attempt && delay < workspaceRenameMaximumDelay; step++ {
		delay *= 2
	}
	if delay > workspaceRenameMaximumDelay {
		return workspaceRenameMaximumDelay
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
