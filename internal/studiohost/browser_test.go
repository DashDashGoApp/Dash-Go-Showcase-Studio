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

func TestSelectStartupViewportUsesBoundedPresentationWindow(t *testing.T) {
	view, ok := selectStartupViewport(2560, 1440, 16, 80)
	if !ok {
		t.Fatal("expected a startup viewport")
	}
	if view.ID != "startup-presentation-fit" || view.Width != 1600 || view.Height != 900 || view.Preview {
		t.Fatalf("startup viewport = %#v, want bounded native 1600x900 presentation", view)
	}
}

func TestSelectStartupViewportFitsSmallerLaptopWorkArea(t *testing.T) {
	view, ok := selectStartupViewport(1920, 1080, 16, 80)
	if !ok {
		t.Fatal("expected a startup viewport")
	}
	if view.ID != "startup-presentation-fit" || view.Width != 1600 || view.Height != 900 || view.Orientation != "landscape" || view.Preview {
		t.Fatalf("startup viewport = %#v, want 1600x900 native presentation", view)
	}

	laptop, ok := selectStartupViewport(1366, 768, 16, 80)
	if !ok {
		t.Fatal("expected a fitted startup viewport on a laptop display")
	}
	if laptop.ID != "startup-presentation-fit" || laptop.Width != 1223 || laptop.Height != 688 || laptop.Preview {
		t.Fatalf("laptop startup viewport = %#v, want 1223x688 native presentation", laptop)
	}
}

func TestSelectStartupViewportDoesNotGrowWithHighResolutionWorkArea(t *testing.T) {
	view, ok := selectStartupViewport(3840, 2160, 16, 80)
	if !ok {
		t.Fatal("expected a startup viewport")
	}
	if view.Width != 1600 || view.Height != 900 || view.Preview {
		t.Fatalf("startup viewport = %#v, want bounded 1600x900 presentation", view)
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

func TestFitPreviewContentsPreservesAspectRatio(t *testing.T) {
	width, height, scale, ok := fitPreviewContents(1366, 768, 16, 80, 1920, 1080)
	if !ok {
		t.Fatal("expected a fitted landscape preview")
	}
	if width != 1223 || height != 688 || scale < 0.636 || scale > 0.638 {
		t.Fatalf("landscape preview = %dx%d @ %.4f, want 1223x688 @ about 0.637", width, height, scale)
	}

	width, height, scale, ok = fitPreviewContents(1920, 1080, 16, 80, 1080, 1920)
	if !ok {
		t.Fatal("expected a fitted portrait preview")
	}
	if width != 563 || height != 1000 || scale < 0.520 || scale > 0.522 {
		t.Fatalf("portrait preview = %dx%d @ %.4f, want 563x1000 @ about 0.521", width, height, scale)
	}
}

func TestFitPreviewContentsNeverUpscalesExactViewport(t *testing.T) {
	width, height, scale, ok := fitPreviewContents(2560, 1440, 16, 80, 1280, 800)
	if !ok || width != 1280 || height != 800 || scale != 1 {
		t.Fatalf("exact preview = %dx%d @ %.4f, want 1280x800 @ 1", width, height, scale)
	}
}

func TestBrowserBoundIntRejectsFractionalValues(t *testing.T) {
	if got, ok := browserBoundInt(float64(1600)); !ok || got != 1600 {
		t.Fatalf("browserBoundInt(1600) = %d, %v", got, ok)
	}
	if _, ok := browserBoundInt(float64(1600.5)); ok {
		t.Fatal("fractional browser bound was accepted")
	}
}
