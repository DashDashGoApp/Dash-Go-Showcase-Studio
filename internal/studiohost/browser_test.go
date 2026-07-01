package studiohost

import "testing"

func TestShowcaseViewportCatalogCoversLandscapePortraitAndFit(t *testing.T) {
	views := allShowcaseViewports()
	if len(views) != 9 {
		t.Fatalf("viewport count = %d, want 9", len(views))
	}
	want := map[string]struct {
		width, height int
		orientation   string
	}{
		"fit":                 {0, 0, "landscape"},
		"wall-landscape":      {1920, 1080, "landscape"},
		"laptop":              {1366, 768, "landscape"},
		"wide-tablet":         {1280, 800, "landscape"},
		"compact-touch":       {1024, 600, "landscape"},
		"portrait-wall":       {1080, 1920, "portrait"},
		"portrait-tablet":     {800, 1280, "portrait"},
		"portrait-four-three": {768, 1024, "portrait"},
		"compact-portrait":    {600, 1024, "portrait"},
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
