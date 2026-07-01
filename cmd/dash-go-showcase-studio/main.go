package main

import (
	"flag"
	"os"

	"github.com/DashDashGoApp/Dash-Go-Showcase-Studio/internal/studiohost"
)

func main() {
	var options studiohost.Options
	flag.StringVar(&options.Action, "action", "start", "start, reset, diagnose, clean, purge, or self-test")
	flag.StringVar(&options.Scenario, "scenario", "", "internal fixture scenario ID to prepare")
	flag.StringVar(&options.Location, "location", "", "demo location ID, for example chicago")
	flag.StringVar(&options.StateRoot, "state-root", "", "override the private Studio state folder")
	flag.StringVar(&options.ConfirmPurge, "confirm-purge", "", "required phrase for purging a custom --state-root")
	flag.StringVar(&options.Viewport, "viewport", "fit", "initial window size: fit or WIDTHxHEIGHT")
	flag.BoolVar(&options.Kiosk, "kiosk", false, "open the browser in kiosk mode")
	flag.BoolVar(&options.NoBrowser, "no-browser", false, "prepare and start the local runtime without opening a browser")
	flag.BoolVar(&options.Trace, "trace", false, "print detailed host diagnostics")
	flag.Parse()

	app, err := studiohost.New(options)
	if err != nil {
		studiohost.ReportStartupError("Dash-Go Showcase Studio could not start", err)
		os.Exit(1)
	}
	if err := app.Run(); err != nil {
		studiohost.ReportStartupError("Dash-Go Showcase Studio failed", err)
		os.Exit(1)
	}
}
