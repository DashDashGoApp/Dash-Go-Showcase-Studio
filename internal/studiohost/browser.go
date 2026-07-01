package studiohost

import (
	"bufio"
	"crypto/rand"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

type browser struct {
	path string
	name string
}

type viewportSpec struct {
	ID          string `json:"id"`
	Label       string `json:"label"`
	Width       int    `json:"width"`
	Height      int    `json:"height"`
	Orientation string `json:"orientation"`
	Fit         bool   `json:"fit"`
}

type viewportResult struct {
	ID           string `json:"id"`
	Label        string `json:"label"`
	Width        int    `json:"width"`
	Height       int    `json:"height"`
	Orientation  string `json:"orientation"`
	Fit          bool   `json:"fit"`
	Presentation string `json:"presentation"`
}

type browserSession struct {
	debugPort int
}

type cdpPageTargetInfo struct {
	ID                   string `json:"id"`
	Type                 string `json:"type"`
	WebSocketDebuggerURL string `json:"webSocketDebuggerUrl"`
}

var showcaseViewports = []viewportSpec{
	{ID: "fit", Label: "Fit Display", Orientation: "landscape", Fit: true},
	{ID: "wall-landscape", Label: "Wall Display", Width: 1920, Height: 1080, Orientation: "landscape"},
	{ID: "laptop", Label: "Common Laptop", Width: 1366, Height: 768, Orientation: "landscape"},
	{ID: "wide-tablet", Label: "16:10 Display", Width: 1280, Height: 800, Orientation: "landscape"},
	{ID: "portrait-wall", Label: "Portrait Wall", Width: 1080, Height: 1920, Orientation: "portrait"},
	{ID: "portrait-tablet", Label: "Portrait Tablet", Width: 800, Height: 1280, Orientation: "portrait"},
	{ID: "portrait-four-three", Label: "4:3 Portrait", Width: 768, Height: 1024, Orientation: "portrait"},
}

// startupShowcaseViewports intentionally includes a non-public compact fallback.
// It is only used for the first normal Studio window. The interactive Showcase
// View catalog remains the curated list above.
var startupShowcaseViewports = []viewportSpec{
	{ID: "wall-landscape", Label: "Wall Display", Width: 1920, Height: 1080, Orientation: "landscape"},
	{ID: "laptop", Label: "Common Laptop", Width: 1366, Height: 768, Orientation: "landscape"},
	{ID: "wide-tablet", Label: "16:10 Display", Width: 1280, Height: 800, Orientation: "landscape"},
	{ID: "startup-compact", Label: "Compact Startup", Width: 1024, Height: 600, Orientation: "landscape"},
}

// selectStartupViewport chooses the largest normal landscape window whose
// native outer bounds fit inside the browser-reported work area. It never
// chooses Fit because Fit is an explicit user command that maximizes later.
func selectStartupViewport(workWidth, workHeight, frameWidth, frameHeight int) (viewportSpec, bool) {
	if workWidth < 1 || workHeight < 1 || frameWidth < 0 || frameHeight < 0 {
		return viewportSpec{}, false
	}
	for _, view := range startupShowcaseViewports {
		if view.Width+frameWidth <= workWidth && view.Height+frameHeight <= workHeight {
			return view, true
		}
	}
	return viewportSpec{}, false
}

func allShowcaseViewports() []viewportSpec {
	result := make([]viewportSpec, len(showcaseViewports))
	copy(result, showcaseViewports)
	return result
}

func lookupShowcaseViewport(id string) (viewportSpec, bool) {
	for _, item := range showcaseViewports {
		if item.ID == strings.TrimSpace(strings.ToLower(id)) {
			return item, true
		}
	}
	return viewportSpec{}, false
}

func findBrowser() (browser, error) {
	if override := strings.TrimSpace(os.Getenv("DASHGO_SHOWCASE_BROWSER")); override != "" {
		if info, err := os.Stat(override); err == nil && !info.IsDir() {
			return browser{path: override, name: "configured browser"}, nil
		}
		return browser{}, fmt.Errorf("DASHGO_SHOWCASE_BROWSER does not exist: %s", override)
	}
	names := []string{"chromium", "chromium-browser", "google-chrome", "microsoft-edge"}
	if runtime.GOOS == "windows" {
		names = []string{"msedge.exe", "chrome.exe"}
	}
	for _, name := range names {
		if path, err := exec.LookPath(name); err == nil {
			return browser{path: path, name: name}, nil
		}
	}
	if runtime.GOOS == "windows" {
		roots := []string{os.Getenv("ProgramFiles"), os.Getenv("ProgramFiles(x86)"), os.Getenv("LOCALAPPDATA")}
		relatives := []string{
			filepath.Join("Microsoft", "Edge", "Application", "msedge.exe"),
			filepath.Join("Google", "Chrome", "Application", "chrome.exe"),
		}
		for _, root := range roots {
			if root == "" {
				continue
			}
			for _, relative := range relatives {
				candidate := filepath.Join(root, relative)
				if info, err := os.Stat(candidate); err == nil && !info.IsDir() {
					return browser{path: candidate, name: filepath.Base(candidate)}, nil
				}
			}
		}
	}
	return browser{}, fmt.Errorf("no supported Chromium-family browser was found")
}

func parseViewport(raw string) (viewportSpec, error) {
	value := strings.ToLower(strings.TrimSpace(raw))
	if value == "" || value == "fit" {
		preset, _ := lookupShowcaseViewport("fit")
		return preset, nil
	}
	parts := strings.Split(value, "x")
	if len(parts) != 2 {
		return viewportSpec{}, fmt.Errorf("viewport must use fit or WIDTHxHEIGHT, for example 1920x1080")
	}
	width, err := strconv.Atoi(parts[0])
	if err != nil || width < 600 || width > 7680 {
		return viewportSpec{}, fmt.Errorf("viewport width must be between 600 and 7680")
	}
	height, err := strconv.Atoi(parts[1])
	if err != nil || height < 600 || height > 4320 {
		return viewportSpec{}, fmt.Errorf("viewport height must be between 600 and 4320")
	}
	orientation := "landscape"
	if height > width {
		orientation = "portrait"
	}
	return viewportSpec{ID: "custom", Label: fmt.Sprintf("%d × %d", width, height), Width: width, Height: height, Orientation: orientation}, nil
}

func (a *App) launchBrowser(pageURL string) error {
	b, err := findBrowser()
	if err != nil {
		return err
	}
	view, err := parseViewport(a.options.Viewport)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(a.paths.browserRoot, 0700); err != nil {
		return fmt.Errorf("create private browser profile: %w", err)
	}
	debugPort, err := chooseLoopbackPort()
	if err != nil {
		return fmt.Errorf("reserve private browser debugging port: %w", err)
	}
	args := []string{
		"--no-first-run",
		"--no-default-browser-check",
		"--disable-features=Translate",
		"--force-device-scale-factor=1",
		"--new-window",
		"--user-data-dir=" + a.paths.browserRoot,
		"--remote-debugging-address=127.0.0.1",
		fmt.Sprintf("--remote-debugging-port=%d", debugPort),
		"--remote-allow-origins=http://127.0.0.1,http://localhost",
		"--app=" + pageURL,
	}
	if view.Fit && !a.options.Kiosk {
		// Start normal and inspect the work area before selecting a preset. A
		// normal bootstrap window lets the adaptive path account for title-bar
		// chrome and taskbar-safe space instead of treating Fit as maximized.
		args = append(args, "--window-size=1024,600")
	} else if !view.Fit {
		args = append(args, fmt.Sprintf("--window-size=%d,%d", view.Width, view.Height))
	}
	if a.options.Kiosk {
		args = append(args, "--kiosk")
	}
	cmd := exec.Command(b.path, args...)
	if a.options.Trace {
		fmt.Printf("Browser: %s\n", b.path)
		fmt.Printf("Browser args: %s\n", strings.Join(args, " "))
	}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("open Studio browser window: %w", err)
	}
	a.mu.Lock()
	a.browser = &browserSession{debugPort: debugPort}
	a.mu.Unlock()
	defer func() {
		a.mu.Lock()
		a.browser = nil
		a.mu.Unlock()
	}()
	effectiveView := view
	if view.Fit && !a.options.Kiosk {
		startupView, found, err := a.adaptiveStartupViewport()
		if err != nil {
			if a.options.Trace {
				fmt.Printf("Showcase adaptive startup warning: %v\n", err)
			}
		} else if found {
			effectiveView = startupView
			if a.options.Trace {
				fmt.Printf("Showcase adaptive startup viewport: %s (%dx%d)\n", effectiveView.ID, effectiveView.Width, effectiveView.Height)
			}
		} else if a.options.Trace {
			fmt.Println("Showcase adaptive startup found no safe preset; retaining the normal bootstrap window.")
		}
	}

	if !effectiveView.Fit {
		// Apply the requested native contents size and matching CSS viewport after
		// Chromium has made its private page target available. The short retry keeps
		// startup deterministic while preserving the host display configuration.
		if _, err := a.applyViewport(effectiveView); err != nil && a.options.Trace {
			fmt.Printf("Showcase viewport setup warning: %v\n", err)
		}
	}

	return cmd.Wait()
}

func (a *App) adaptiveStartupViewport() (viewportSpec, bool, error) {
	a.mu.Lock()
	session := a.browser
	a.mu.Unlock()
	if session == nil || session.debugPort < 1 {
		return viewportSpec{}, false, fmt.Errorf("the private Studio browser is not ready for adaptive startup sizing")
	}

	workWidth, workHeight, frameWidth, frameHeight, err := cdpDisplayWorkArea(session.debugPort)
	if err != nil {
		return viewportSpec{}, false, err
	}

	view, ok := selectStartupViewport(workWidth, workHeight, frameWidth, frameHeight)
	return view, ok, nil
}

func (a *App) applyViewportPreset(id string) (viewportResult, error) {
	view, ok := lookupShowcaseViewport(id)
	if !ok {
		return viewportResult{}, fmt.Errorf("unknown Showcase viewport preset %q", id)
	}
	return a.applyViewport(view)
}

func (a *App) applyViewport(view viewportSpec) (viewportResult, error) {
	a.mu.Lock()
	session := a.browser
	a.mu.Unlock()
	if session == nil || session.debugPort < 1 {
		return viewportResult{}, fmt.Errorf("the private Studio browser is not ready for a viewport change")
	}
	result := viewportResult{ID: view.ID, Label: view.Label, Width: view.Width, Height: view.Height, Orientation: view.Orientation, Fit: view.Fit}
	if err := applyChromiumViewport(session.debugPort, view, &result); err != nil {
		return viewportResult{}, err
	}
	return result, nil
}

func applyChromiumViewport(port int, view viewportSpec, result *viewportResult) error {
	deadline := time.Now().Add(8 * time.Second)
	var last error
	for time.Now().Before(deadline) {
		last = applyChromiumViewportOnce(port, view, result)
		if last == nil {
			return nil
		}
		time.Sleep(160 * time.Millisecond)
	}
	if last == nil {
		last = fmt.Errorf("Chromium DevTools endpoint did not become ready")
	}
	return fmt.Errorf("apply live Showcase viewport: %w", last)
}

func applyChromiumViewportOnce(port int, view viewportSpec, result *viewportResult) error {
	windowID, err := cdpBrowserWindowID(port)
	if err != nil {
		return fmt.Errorf("find Studio browser window: %w", err)
	}

	if view.Fit {
		if _, err := cdpCall(port, "Emulation.clearDeviceMetricsOverride", map[string]any{}); err != nil {
			return err
		}
		if _, err := cdpBrowserCall(port, "Browser.setWindowBounds", map[string]any{
			"windowId": windowID,
			"bounds": map[string]any{
				"windowState": "maximized",
			},
		}); err != nil {
			return fmt.Errorf("maximize Studio browser window: %w", err)
		}
		result.Presentation = "Fit display"
		return nil
	}

	if _, err := cdpBrowserCall(port, "Browser.setWindowBounds", map[string]any{
		"windowId": windowID,
		"bounds": map[string]any{
			"windowState": "normal",
		},
	}); err != nil {
		return fmt.Errorf("restore Studio browser window: %w", err)
	}

	if _, err := cdpBrowserCall(port, "Browser.setContentsSize", map[string]any{
		"windowId": windowID,
		"width":    view.Width,
		"height":   view.Height,
	}); err != nil {
		return fmt.Errorf("resize Studio browser contents: %w", err)
	}

	if _, err := cdpCall(port, "Emulation.setDeviceMetricsOverride", map[string]any{
		"width":             view.Width,
		"height":            view.Height,
		"deviceScaleFactor": 1,
		"mobile":            false,
	}); err != nil {
		return err
	}

	metrics, err := cdpCall(port, "Runtime.evaluate", map[string]any{
		"expression":    "JSON.stringify({innerWidth:window.innerWidth,innerHeight:window.innerHeight,outerWidth:window.outerWidth,outerHeight:window.outerHeight})",
		"returnByValue": true,
	})
	if err != nil {
		return err
	}

	innerWidth, innerHeight, outerWidth, outerHeight := cdpWindowMetrics(metrics)
	if innerWidth == view.Width && innerHeight == view.Height {
		result.Presentation = "Native window + exact CSS viewport"
	} else {
		result.Presentation = "Native window + scaled preview"
	}

	if outerWidth > 0 && outerHeight > 0 && (outerWidth < view.Width || outerHeight < view.Height) {
		result.Presentation = "Native window + scaled preview"
	}

	return nil
}

func cdpDisplayWorkArea(port int) (int, int, int, int, error) {
	metrics, err := cdpCall(port, "Runtime.evaluate", map[string]any{
		"expression":    "JSON.stringify({availWidth:screen.availWidth,availHeight:screen.availHeight,innerWidth:window.innerWidth,innerHeight:window.innerHeight,outerWidth:window.outerWidth,outerHeight:window.outerHeight})",
		"returnByValue": true,
	})
	if err != nil {
		return 0, 0, 0, 0, err
	}

	result, _ := metrics["result"].(map[string]any)
	raw, _ := result["result"].(map[string]any)
	value, _ := raw["value"].(string)
	var data struct {
		AvailWidth  int `json:"availWidth"`
		AvailHeight int `json:"availHeight"`
		InnerWidth  int `json:"innerWidth"`
		InnerHeight int `json:"innerHeight"`
		OuterWidth  int `json:"outerWidth"`
		OuterHeight int `json:"outerHeight"`
	}
	if err := json.Unmarshal([]byte(value), &data); err != nil {
		return 0, 0, 0, 0, fmt.Errorf("decode Chromium work-area metrics: %w", err)
	}
	if data.AvailWidth < 1 || data.AvailHeight < 1 || data.InnerWidth < 1 || data.InnerHeight < 1 || data.OuterWidth < data.InnerWidth || data.OuterHeight < data.InnerHeight {
		return 0, 0, 0, 0, fmt.Errorf("Chromium returned invalid work-area metrics")
	}

	return data.AvailWidth, data.AvailHeight, data.OuterWidth - data.InnerWidth, data.OuterHeight - data.InnerHeight, nil
}

func cdpWindowMetrics(response map[string]any) (int, int, int, int) {
	result, _ := response["result"].(map[string]any)
	raw, _ := result["result"].(map[string]any)
	value, _ := raw["value"].(string)
	var data struct {
		InnerWidth  int `json:"innerWidth"`
		InnerHeight int `json:"innerHeight"`
		OuterWidth  int `json:"outerWidth"`
		OuterHeight int `json:"outerHeight"`
	}
	_ = json.Unmarshal([]byte(value), &data)
	return data.InnerWidth, data.InnerHeight, data.OuterWidth, data.OuterHeight
}

func cdpCall(port int, method string, params map[string]any) (map[string]any, error) {
	wsURL, err := cdpPageWebSocketURL(port)
	if err != nil {
		return nil, err
	}
	return cdpWebSocketCall(wsURL, method, params)
}

func cdpBrowserCall(port int, method string, params map[string]any) (map[string]any, error) {
	wsURL, err := cdpBrowserWebSocketURL(port)
	if err != nil {
		return nil, err
	}
	return cdpWebSocketCall(wsURL, method, params)
}

func cdpBrowserWindowID(port int) (int, error) {
	target, err := cdpPageTarget(port)
	if err != nil {
		return 0, err
	}

	response, err := cdpBrowserCall(port, "Browser.getWindowForTarget", map[string]any{
		"targetId": target.ID,
	})
	if err != nil {
		return 0, err
	}

	return cdpWindowID(response)
}

func cdpWindowID(response map[string]any) (int, error) {
	result, ok := response["result"].(map[string]any)
	if !ok {
		return 0, fmt.Errorf("Chromium DevTools Browser.getWindowForTarget returned no result")
	}

	value, ok := result["windowId"].(float64)
	if !ok || value < 1 || value != float64(int(value)) {
		return 0, fmt.Errorf("Chromium DevTools Browser.getWindowForTarget returned an invalid window ID")
	}

	return int(value), nil
}

func cdpPageWebSocketURL(port int) (string, error) {
	target, err := cdpPageTarget(port)
	if err != nil {
		return "", err
	}

	return target.WebSocketDebuggerURL, nil
}

func cdpBrowserWebSocketURL(port int) (string, error) {
	var version struct {
		WebSocketDebuggerURL string `json:"webSocketDebuggerUrl"`
	}

	if err := cdpDevToolsGet(port, "/json/version", &version); err != nil {
		return "", err
	}

	if strings.TrimSpace(version.WebSocketDebuggerURL) == "" {
		return "", fmt.Errorf("Chromium has no browser DevTools target yet")
	}

	return version.WebSocketDebuggerURL, nil
}

func cdpPageTarget(port int) (cdpPageTargetInfo, error) {
	var targets []cdpPageTargetInfo

	if err := cdpDevToolsGet(port, "/json/list", &targets); err != nil {
		return cdpPageTargetInfo{}, err
	}

	for _, target := range targets {
		if target.Type == "page" && target.ID != "" && target.WebSocketDebuggerURL != "" {
			return target, nil
		}
	}

	return cdpPageTargetInfo{}, fmt.Errorf("Chromium has no page target yet")
}

func cdpDevToolsGet(port int, path string, destination any) error {
	if port < 1 {
		return fmt.Errorf("invalid Chromium DevTools port")
	}

	client := &http.Client{Timeout: 1200 * time.Millisecond}

	response, err := client.Get(fmt.Sprintf("http://127.0.0.1:%d%s", port, path))
	if err != nil {
		return err
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("Chromium DevTools %s returned HTTP %d", path, response.StatusCode)
	}

	return json.NewDecoder(io.LimitReader(response.Body, 1024*1024)).Decode(destination)
}

func cdpWebSocketCall(rawURL, method string, params map[string]any) (map[string]any, error) {
	parsed, err := url.Parse(rawURL)
	if err != nil || parsed.Scheme != "ws" || parsed.Host == "" {
		return nil, fmt.Errorf("invalid Chromium DevTools WebSocket URL")
	}
	conn, err := net.DialTimeout("tcp", parsed.Host, 2*time.Second)
	if err != nil {
		return nil, err
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(3 * time.Second))
	keyRaw := make([]byte, 16)
	if _, err := rand.Read(keyRaw); err != nil {
		return nil, err
	}
	key := base64.StdEncoding.EncodeToString(keyRaw)
	request, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("Connection", "Upgrade")
	request.Header.Set("Upgrade", "websocket")
	request.Header.Set("Sec-WebSocket-Version", "13")
	request.Header.Set("Sec-WebSocket-Key", key)
	request.Header.Set("Origin", "http://127.0.0.1")
	if err := request.Write(conn); err != nil {
		return nil, err
	}
	reader := bufio.NewReader(conn)
	response, err := http.ReadResponse(reader, request)
	if err != nil {
		return nil, err
	}
	if response.StatusCode != http.StatusSwitchingProtocols {
		_ = response.Body.Close()
		return nil, fmt.Errorf("Chromium DevTools WebSocket returned HTTP %d", response.StatusCode)
	}
	payload, err := json.Marshal(map[string]any{"id": 1, "method": method, "params": params})
	if err != nil {
		return nil, err
	}
	if err := writeClientWebSocketText(conn, payload); err != nil {
		return nil, err
	}
	for {
		opcode, message, err := readServerWebSocketFrame(reader)
		if err != nil {
			return nil, err
		}
		switch opcode {
		case 0x1:
			var parsedResponse map[string]any
			if err := json.Unmarshal(message, &parsedResponse); err != nil {
				continue
			}
			if id, ok := parsedResponse["id"].(float64); !ok || int(id) != 1 {
				continue
			}
			if rawErr, ok := parsedResponse["error"]; ok {
				return nil, fmt.Errorf("Chromium DevTools %s: %v", method, rawErr)
			}
			return parsedResponse, nil
		case 0x8:
			return nil, fmt.Errorf("Chromium DevTools closed the viewport connection")
		case 0x9:
			if err := writeClientWebSocketFrame(conn, 0xA, message); err != nil {
				return nil, err
			}
		}
	}
}

func writeClientWebSocketText(conn net.Conn, payload []byte) error {
	return writeClientWebSocketFrame(conn, 0x1, payload)
}

func writeClientWebSocketFrame(conn net.Conn, opcode byte, payload []byte) error {
	if len(payload) > 65535 {
		return fmt.Errorf("Chromium DevTools payload is unexpectedly large")
	}
	header := []byte{0x80 | opcode}
	if len(payload) < 126 {
		header = append(header, 0x80|byte(len(payload)))
	} else {
		header = append(header, 0x80|126, byte(len(payload)>>8), byte(len(payload)))
	}
	mask := make([]byte, 4)
	if _, err := rand.Read(mask); err != nil {
		return err
	}
	frame := append(header, mask...)
	for i, value := range payload {
		frame = append(frame, value^mask[i%len(mask)])
	}
	_, err := conn.Write(frame)
	return err
}

func readServerWebSocketFrame(reader *bufio.Reader) (byte, []byte, error) {
	first, err := reader.ReadByte()
	if err != nil {
		return 0, nil, err
	}
	second, err := reader.ReadByte()
	if err != nil {
		return 0, nil, err
	}
	length := int64(second & 0x7F)
	if length == 126 {
		var encoded uint16
		if err := binary.Read(reader, binary.BigEndian, &encoded); err != nil {
			return 0, nil, err
		}
		length = int64(encoded)
	} else if length == 127 {
		var encoded uint64
		if err := binary.Read(reader, binary.BigEndian, &encoded); err != nil {
			return 0, nil, err
		}
		if encoded > 4*1024*1024 {
			return 0, nil, fmt.Errorf("Chromium DevTools frame is unexpectedly large")
		}
		length = int64(encoded)
	}
	if length > 4*1024*1024 {
		return 0, nil, fmt.Errorf("Chromium DevTools frame is unexpectedly large")
	}
	masked := second&0x80 != 0
	var mask [4]byte
	if masked {
		if _, err := io.ReadFull(reader, mask[:]); err != nil {
			return 0, nil, err
		}
	}
	payload := make([]byte, int(length))
	if _, err := io.ReadFull(reader, payload); err != nil {
		return 0, nil, err
	}
	if masked {
		for i := range payload {
			payload[i] ^= mask[i%len(mask)]
		}
	}
	return first & 0x0F, payload, nil
}
