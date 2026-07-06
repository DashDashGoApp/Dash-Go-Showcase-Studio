package studiohost

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
)

//go:embed dashgo_runtime_contract_matrix.json
var embeddedRuntimeContractMatrix []byte

const supportedNativeShowcaseContract = "dashgo-showcase/v1"

var runtimeContractEnvironmentName = regexp.MustCompile(`^[A-Z][A-Z0-9_]*$`)

type nativeRuntimeContractPlan struct {
	Schema               int                           `json:"schema"`
	Contract             string                        `json:"contract"`
	DeclarationPath      string                        `json:"declarationPath"`
	RequiredCapabilities []runtimeContractCapability   `json:"requiredCapabilities"`
	Activation           runtimeContractActivation     `json:"activation"`
	Readiness            runtimeContractReadiness      `json:"readiness"`
	Calendars            []runtimeContractCalendar     `json:"calendars"`
	BrowserRoutes        []runtimeContractBrowserRoute `json:"browserRoutes"`
}

type runtimeContractCapability struct {
	ID        string   `json:"id"`
	Reason    string   `json:"reason"`
	Consumers []string `json:"consumers"`
}

type runtimeContractActivation struct {
	RuntimeProfile   runtimeContractValuePath `json:"runtimeProfile"`
	ScenarioManifest runtimeContractPath      `json:"scenarioManifest"`
	DataRoot         runtimeContractPath      `json:"dataRoot"`
}

type runtimeContractValuePath struct {
	Environment string `json:"environment"`
	Value       string `json:"value"`
}

type runtimeContractPath struct {
	Environment  string `json:"environment"`
	RelativePath string `json:"relativePath"`
}

type runtimeContractReadiness struct {
	LivenessPath string `json:"livenessPath"`
	StatusPath   string `json:"statusPath"`
	Profile      string `json:"profile"`
	Cache        struct {
		Rebuilt                    bool `json:"rebuilt"`
		MinimumEvents              int  `json:"minimumEvents"`
		MinimumWritebackCandidates int  `json:"minimumWritebackCandidates"`
	} `json:"cache"`
	Problems string `json:"problems"`
}

type runtimeContractCalendar struct {
	Source                     string `json:"source"`
	Mode                       string `json:"mode"`
	ExpectedEventMarker        string `json:"expectedEventMarker"`
	MinimumWritebackCandidates int    `json:"minimumWritebackCandidates"`
}

type runtimeContractBrowserRoute struct {
	Path           string `json:"path"`
	Contains       string `json:"contains"`
	ParseJSON      bool   `json:"parseJSON"`
	Classification string `json:"classification"`
}

type embeddedRuntimeContractDocument struct {
	Schema         int                       `json:"schema"`
	NativeContract nativeRuntimeContractPlan `json:"nativeContract"`
	Assumptions    json.RawMessage           `json:"assumptions"`
	LegacyBridge   json.RawMessage           `json:"legacyBridge"`
}

var (
	nativeRuntimeContractPlanOnce sync.Once
	nativeRuntimeContractPlanData nativeRuntimeContractPlan
	nativeRuntimeContractPlanErr  error
)

// loadNativeRuntimeContractPlan turns Task 3.1's inventory into the one
// executable native launch plan. The matrix is embedded into the Studio binary
// so launcher behavior, package validation, and the documented contract share
// one checked-in declaration rather than separate string lists.
func loadNativeRuntimeContractPlan() (nativeRuntimeContractPlan, error) {
	nativeRuntimeContractPlanOnce.Do(func() {
		decoder := json.NewDecoder(bytes.NewReader(embeddedRuntimeContractMatrix))
		decoder.DisallowUnknownFields()
		var document embeddedRuntimeContractDocument
		if err := decoder.Decode(&document); err != nil {
			nativeRuntimeContractPlanErr = fmt.Errorf("decode embedded Studio runtime-contract matrix: %w", err)
			return
		}
		var trailing any
		if err := decoder.Decode(&trailing); err != io.EOF {
			if err == nil {
				nativeRuntimeContractPlanErr = errors.New("embedded Studio runtime-contract matrix contains more than one JSON value")
			} else {
				nativeRuntimeContractPlanErr = fmt.Errorf("decode embedded Studio runtime-contract matrix: %w", err)
			}
			return
		}
		if document.Schema != 1 {
			nativeRuntimeContractPlanErr = fmt.Errorf("embedded Studio runtime-contract matrix schema %d is unsupported", document.Schema)
			return
		}
		if len(document.Assumptions) == 0 || len(document.LegacyBridge) == 0 {
			nativeRuntimeContractPlanErr = errors.New("embedded Studio runtime-contract matrix is missing Task 3.1 inventory sections")
			return
		}
		if err := document.NativeContract.validate(); err != nil {
			nativeRuntimeContractPlanErr = fmt.Errorf("embedded Studio native runtime contract is invalid: %w", err)
			return
		}
		nativeRuntimeContractPlanData = document.NativeContract
	})
	if nativeRuntimeContractPlanErr != nil {
		return nativeRuntimeContractPlan{}, nativeRuntimeContractPlanErr
	}
	return nativeRuntimeContractPlanData, nil
}

func (plan nativeRuntimeContractPlan) validate() error {
	if plan.Schema != 1 {
		return fmt.Errorf("schema %d is unsupported", plan.Schema)
	}
	if plan.Contract != supportedNativeShowcaseContract {
		return fmt.Errorf("contract %q is unsupported", plan.Contract)
	}
	if _, err := cleanRuntimeContractRelativePath(plan.DeclarationPath); err != nil {
		return fmt.Errorf("declarationPath: %w", err)
	}
	if len(plan.RequiredCapabilities) == 0 {
		return errors.New("requiredCapabilities is empty")
	}
	seenCapabilities := map[string]struct{}{}
	for _, capability := range plan.RequiredCapabilities {
		if strings.TrimSpace(capability.ID) == "" || strings.TrimSpace(capability.Reason) == "" || len(capability.Consumers) == 0 {
			return fmt.Errorf("required capability is incomplete: %#v", capability)
		}
		if _, seen := seenCapabilities[capability.ID]; seen {
			return fmt.Errorf("required capability %q is duplicated", capability.ID)
		}
		seenCapabilities[capability.ID] = struct{}{}
	}
	if err := validateRuntimeContractEnvironment(plan.Activation.RuntimeProfile.Environment); err != nil {
		return fmt.Errorf("activation.runtimeProfile.environment: %w", err)
	}
	if strings.TrimSpace(plan.Activation.RuntimeProfile.Value) == "" {
		return errors.New("activation.runtimeProfile.value is empty")
	}
	for _, item := range []struct {
		name string
		path runtimeContractPath
	}{
		{name: "activation.scenarioManifest", path: plan.Activation.ScenarioManifest},
		{name: "activation.dataRoot", path: plan.Activation.DataRoot},
	} {
		if err := validateRuntimeContractEnvironment(item.path.Environment); err != nil {
			return fmt.Errorf("%s.environment: %w", item.name, err)
		}
		if _, err := cleanRuntimeContractRelativePath(item.path.RelativePath); err != nil {
			return fmt.Errorf("%s.relativePath: %w", item.name, err)
		}
	}
	if err := validateRuntimeContractURLPath(plan.Readiness.LivenessPath); err != nil {
		return fmt.Errorf("readiness.livenessPath: %w", err)
	}
	if err := validateRuntimeContractURLPath(plan.Readiness.StatusPath); err != nil {
		return fmt.Errorf("readiness.statusPath: %w", err)
	}
	if strings.TrimSpace(plan.Readiness.Profile) == "" || !plan.Readiness.Cache.Rebuilt || plan.Readiness.Cache.MinimumEvents < 1 || plan.Readiness.Cache.MinimumWritebackCandidates < 1 || strings.TrimSpace(plan.Readiness.Problems) != "must-be-empty" {
		return errors.New("readiness contract is incomplete")
	}
	if len(plan.Calendars) == 0 || len(plan.BrowserRoutes) == 0 {
		return errors.New("calendar or browser-route contract is empty")
	}
	seenCalendars := map[string]struct{}{}
	writable := 0
	for _, calendar := range plan.Calendars {
		if _, err := cleanRuntimeContractRelativePath(calendar.Source); err != nil {
			return fmt.Errorf("calendar %q: %w", calendar.Source, err)
		}
		if _, seen := seenCalendars[calendar.Source]; seen {
			return fmt.Errorf("calendar %q is duplicated", calendar.Source)
		}
		seenCalendars[calendar.Source] = struct{}{}
		if strings.TrimSpace(calendar.ExpectedEventMarker) == "" {
			return fmt.Errorf("calendar %q has no expected event marker", calendar.Source)
		}
		switch calendar.Mode {
		case "writable":
			if calendar.MinimumWritebackCandidates < 1 {
				return fmt.Errorf("writable calendar %q needs positive writeback candidates", calendar.Source)
			}
			writable++
		case "fixture-only":
			if calendar.MinimumWritebackCandidates != 0 {
				return fmt.Errorf("fixture-only calendar %q cannot require writeback candidates", calendar.Source)
			}
		default:
			return fmt.Errorf("calendar %q has unsupported mode %q", calendar.Source, calendar.Mode)
		}
	}
	if writable != plan.Readiness.Cache.MinimumWritebackCandidates {
		return fmt.Errorf("writable calendar count %d does not match required cache candidates %d", writable, plan.Readiness.Cache.MinimumWritebackCandidates)
	}
	for _, route := range plan.BrowserRoutes {
		if err := validateRuntimeContractURLPath(route.Path); err != nil {
			return fmt.Errorf("browser route %q: %w", route.Path, err)
		}
		if strings.TrimSpace(route.Contains) == "" || route.Classification != "studio-owned" {
			return fmt.Errorf("browser route %q is incomplete", route.Path)
		}
	}
	return nil
}

func validateRuntimeContractEnvironment(value string) error {
	if !runtimeContractEnvironmentName.MatchString(value) {
		return fmt.Errorf("invalid environment name %q", value)
	}
	return nil
}

func validateRuntimeContractURLPath(value string) error {
	if !strings.HasPrefix(value, "/") || strings.ContainsAny(value, "?#\\") || path.Clean(value) != value {
		return fmt.Errorf("must be a clean absolute URL path: %q", value)
	}
	return nil
}

func cleanRuntimeContractRelativePath(value string) (string, error) {
	if strings.TrimSpace(value) == "" || strings.Contains(value, "\\") {
		return "", fmt.Errorf("must be a non-empty forward-slash relative path: %q", value)
	}
	clean := path.Clean(value)
	if clean == "." || clean == ".." || strings.HasPrefix(clean, "../") || strings.HasPrefix(value, "/") || clean != value {
		return "", fmt.Errorf("must be a clean relative path: %q", value)
	}
	return clean, nil
}

func (plan nativeRuntimeContractPlan) runtimeDeclarationPath(runtimeApp string) (string, error) {
	return resolveRuntimeContractPath(runtimeApp, plan.DeclarationPath)
}

func (plan nativeRuntimeContractPlan) scenarioPaths(scenarioRoot, scenarioData string) (string, string, error) {
	dataRoot, err := resolveRuntimeContractPath(scenarioRoot, plan.Activation.DataRoot.RelativePath)
	if err != nil {
		return "", "", fmt.Errorf("resolve native data root: %w", err)
	}
	if filepath.Clean(dataRoot) != filepath.Clean(scenarioData) {
		return "", "", fmt.Errorf("runtime-contract data root %q does not match Studio scenario data root %q", dataRoot, scenarioData)
	}
	manifest, err := resolveRuntimeContractPath(scenarioRoot, plan.Activation.ScenarioManifest.RelativePath)
	if err != nil {
		return "", "", fmt.Errorf("resolve native scenario manifest: %w", err)
	}
	relative, err := filepath.Rel(dataRoot, manifest)
	if err != nil || relative == "." || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) || filepath.IsAbs(relative) {
		return "", "", fmt.Errorf("runtime-contract scenario manifest %q is outside data root %q", manifest, dataRoot)
	}
	return dataRoot, manifest, nil
}

func (plan nativeRuntimeContractPlan) stagedManifestPath(scenarioRoot, scenarioData, stagedData string) (string, error) {
	dataRoot, manifest, err := plan.scenarioPaths(scenarioRoot, scenarioData)
	if err != nil {
		return "", err
	}
	relative, err := filepath.Rel(dataRoot, manifest)
	if err != nil {
		return "", fmt.Errorf("derive staged native scenario manifest: %w", err)
	}
	if relative == "." || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) || filepath.IsAbs(relative) {
		return "", errors.New("native scenario manifest is outside the active data root")
	}
	candidate := filepath.Join(stagedData, relative)
	actualRelative, err := filepath.Rel(filepath.Clean(stagedData), candidate)
	if err != nil || actualRelative == "." || actualRelative == ".." || strings.HasPrefix(actualRelative, ".."+string(filepath.Separator)) || filepath.IsAbs(actualRelative) {
		return "", errors.New("staged native scenario manifest escapes staged data root")
	}
	info, err := os.Stat(candidate)
	if err != nil || info.IsDir() {
		if err == nil {
			err = errors.New("path is a directory")
		}
		return "", fmt.Errorf("staged native scenario manifest is unavailable: %w", err)
	}
	return candidate, nil
}

func (plan nativeRuntimeContractPlan) launchEnvironment(scenarioRoot, scenarioData string) ([]string, error) {
	dataRoot, manifest, err := plan.scenarioPaths(scenarioRoot, scenarioData)
	if err != nil {
		return nil, err
	}
	info, err := os.Stat(manifest)
	if err != nil || info.IsDir() {
		if err == nil {
			err = errors.New("path is a directory")
		}
		return nil, fmt.Errorf("native scenario manifest is unavailable: %w", err)
	}
	return []string{
		fmt.Sprintf("%s=%s", plan.Activation.RuntimeProfile.Environment, plan.Activation.RuntimeProfile.Value),
		fmt.Sprintf("%s=%s", plan.Activation.ScenarioManifest.Environment, manifest),
		fmt.Sprintf("%s=%s", plan.Activation.DataRoot.Environment, dataRoot),
	}, nil
}

func (plan nativeRuntimeContractPlan) clientVisibleScenarioData() []clientVisibleScenarioData {
	probes := make([]clientVisibleScenarioData, 0, len(plan.BrowserRoutes))
	for _, route := range plan.BrowserRoutes {
		probes = append(probes, clientVisibleScenarioData{Path: route.Path, Contains: route.Contains, ParseJSON: route.ParseJSON})
	}
	return probes
}

func (plan nativeRuntimeContractPlan) writableCalendarRequirements() map[string]int {
	requirements := map[string]int{}
	for _, calendar := range plan.Calendars {
		if calendar.Mode == "writable" {
			requirements[calendar.Source] = calendar.MinimumWritebackCandidates
		}
	}
	return requirements
}

func resolveRuntimeContractPath(root, relative string) (string, error) {
	clean, err := cleanRuntimeContractRelativePath(relative)
	if err != nil {
		return "", err
	}
	root = filepath.Clean(root)
	candidate := filepath.Join(root, filepath.FromSlash(clean))
	actualRelative, err := filepath.Rel(root, candidate)
	if err != nil || actualRelative == "." || actualRelative == ".." || strings.HasPrefix(actualRelative, ".."+string(filepath.Separator)) || filepath.IsAbs(actualRelative) {
		return "", fmt.Errorf("resolved path escapes root %q", root)
	}
	return candidate, nil
}
