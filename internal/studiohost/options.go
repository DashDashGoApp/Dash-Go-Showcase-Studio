package studiohost

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/DashDashGoApp/Dash-Go-Showcase-Studio/internal/fixtures"
)

const customPurgeConfirmation = "PURGE SHOWCASE STUDIO"

type Options struct {
	Action       string
	Scenario     string
	Location     string
	StateRoot    string
	ConfirmPurge string
	Viewport     string
	Kiosk        bool
	NoBrowser    bool
	Trace        bool
}

func (o Options) normalized() (Options, error) {
	o.Action = strings.ToLower(strings.TrimSpace(o.Action))
	if o.Action == "" {
		o.Action = "start"
	}
	switch o.Action {
	case "start", "reset", "diagnose", "clean", "purge", "self-test":
	default:
		return Options{}, fmt.Errorf("unsupported action %q", o.Action)
	}
	o.Scenario = strings.TrimSpace(o.Scenario)
	o.Location = strings.TrimSpace(o.Location)
	if o.Location != "" {
		if _, ok := fixtures.LookupLocation(o.Location); !ok {
			return Options{}, fmt.Errorf("unknown Showcase demo location %q", o.Location)
		}
	}
	o.ConfirmPurge = strings.TrimSpace(o.ConfirmPurge)
	if o.StateRoot != "" {
		o.StateRoot = filepath.Clean(o.StateRoot)
	}
	if _, err := parseViewport(o.Viewport); err != nil {
		return Options{}, err
	}
	return o, nil
}
