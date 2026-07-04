package studiohost

import "testing"

func TestShowcaseViewportCatalogCoversLandscapePortraitAndFit(t *testing.T) {
	views := allShowcaseViewports()
	if len(views) != 7 {
		t.Fatalf("viewport count = %d, want 7", len(views))
	}

	want := map[string]struct {
		width, height int
		orientation   string
	}{
		"fit":                 {0, 0, "landscape"},
		"wall-landscape":      {1920, 1080, "landscape"},
		"laptop":              {1366, 768, "landscape"},
		"wide-tablet":         {1280, 800, "landscape"},
		"portrait-wall":       {1080, 1920, "portrait"},
		"portrait-tablet":     {800, 1280, "portrait"},
		"portrait-four-three": {768, 1024, "portrait"},
	}

	for id, expected := range want {
		got, ok := lookupShowcaseViewport(id)
		if !ok {
			t.Fatalf("missing viewport preset %q", id)
		}
		if got.Width != expected.width || got.Height != expected.height || got.Orientation != expected.orientation {
			t.Fatalf("preset %q = %#v, want %dx%d %s", id, got, expected.width, expected.height, expected.orientation)
		}
	}

	if wall, ok := lookupShowcaseViewport("wall-landscape"); !ok || !wall.Preview {
		t.Fatalf("wall preview must remain an explicit device emulation: %#v", wall)
	}
	if fit, ok := lookupShowcaseViewport("fit"); !ok || !fit.Fit || fit.Preview {
		t.Fatalf("fit must remain native presentation sizing: %#v", fit)
	}

	for _, removed := range []string{"compact-touch", "compact-portrait"} {
		if _, ok := lookupShowcaseViewport(removed); ok {
			t.Fatalf("removed viewport preset %q is still present", removed)
		}
	}
}

func TestParseViewportSupportsFitAndPortrait(t *testing.T) {
	fit, err := parseViewport("fit")
	if err != nil || !fit.Fit {
		t.Fatalf("fit = %#v, %v", fit, err)
	}
	portrait, err := parseViewport("600x1024")
	if err != nil {
		t.Fatal(err)
	}
	if portrait.Orientation != "portrait" || portrait.Width != 600 || portrait.Height != 1024 {
		t.Fatalf("portrait viewport = %#v", portrait)
	}
	if _, err := parseViewport("500x300"); err == nil {
		t.Fatal("unsafe small viewport was accepted")
	}
}

func TestCDPWindowID(t *testing.T) {
	windowID, err := cdpWindowID(map[string]any{
		"result": map[string]any{
			"windowId": float64(42),
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if windowID != 42 {
		t.Fatalf("window ID = %d, want 42", windowID)
	}

	for _, response := range []map[string]any{
		{},
		{"result": map[string]any{}},
		{"result": map[string]any{"windowId": float64(0)}},
		{"result": map[string]any{"windowId": float64(1.5)}},
	} {
		if _, err := cdpWindowID(response); err == nil {
			t.Fatalf("invalid window response was accepted: %#v", response)
		}
	}
}

func TestSelectStartupViewportPrefersLargestSafeLandscapePreset(t *testing.T) {
	view, ok := selectStartupViewport(2560, 1440, 16, 80)
	if !ok {
		t.Fatal("expected a startup viewport")
	}
	if view.ID != "startup-presentation-fit" || view.Width != 2340 || view.Height != 1251 || view.Preview {
		t.Fatalf("startup viewport = %#v, want native 2340x1251 presentation fit", view)
	}
}

func TestSelectStartupViewportBestFitsWhenWallDisplayCannotFitNatively(t *testing.T) {
	view, ok := selectStartupViewport(1920, 1080, 16, 80)
	if !ok {
		t.Fatal("expected a best-fit startup viewport")
	}
	if view.ID != "startup-presentation-fit" || view.Width != 1904 || view.Height != 1000 || view.Orientation != "landscape" || view.Preview {
		t.Fatalf("startup viewport = %#v, want 1904x1000 native presentation fit", view)
	}

	laptop, ok := selectStartupViewport(1366, 768, 16, 80)
	if !ok {
		t.Fatal("expected a best-fit startup viewport on a laptop display")
	}
	if laptop.ID != "startup-presentation-fit" || laptop.Width != 1350 || laptop.Height != 688 || laptop.Preview {
		t.Fatalf("laptop startup viewport = %#v, want 1350x688 native presentation fit", laptop)
	}
}

func TestSelectStartupViewportUsesHighResolutionWorkArea(t *testing.T) {
	view, ok := selectStartupViewport(3840, 2160, 16, 80)
	if !ok {
		t.Fatal("expected a startup viewport")
	}
	if view.Width != 3518 || view.Height != 1913 || view.Width <= 1920 || view.Height <= 1080 || view.Preview {
		t.Fatalf("startup viewport = %#v, want native 3518x1913 high-resolution presentation", view)
	}
}

func TestSelectStartupViewportLeavesNoFitToMaximize(t *testing.T) {
	if view, ok := selectStartupViewport(900, 600, 16, 80); ok {
		t.Fatalf("unexpected startup viewport for unsafe work area: %#v", view)
	}
	if view, ok := selectStartupViewport(0, 1080, 16, 80); ok {
		t.Fatalf("unexpected startup viewport for invalid work area: %#v", view)
	}
}
