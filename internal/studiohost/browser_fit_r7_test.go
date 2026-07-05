package studiohost

import "testing"

func TestFitPreviewContentsKeepsLandscapeViewportInsideHostWorkArea(t *testing.T) {
	width, height, scale, ok := fitPreviewContents(1600, 1000, 16, 88, 1920, 1080)
	if !ok {
		t.Fatal("expected a valid fitted landscape preview")
	}
	if width+16 > 1600 || height+88 > 1000 {
		t.Fatalf("native content escaped host work area: %dx%d", width, height)
	}
	if scale <= 0 || scale >= 1 {
		t.Fatalf("expected reduced landscape scale, got %f", scale)
	}
}

func TestFitPreviewContentsKeepsPortraitViewportInsideHostWorkArea(t *testing.T) {
	width, height, scale, ok := fitPreviewContents(1600, 1000, 16, 88, 1080, 1920)
	if !ok {
		t.Fatal("expected a valid fitted portrait preview")
	}
	if width+16 > 1600 || height+88 > 1000 {
		t.Fatalf("portrait native content escaped host work area: %dx%d", width, height)
	}
	if scale <= 0 || scale >= 1 {
		t.Fatalf("expected reduced portrait scale, got %f", scale)
	}
}

func TestFitPreviewContentsRejectsInvalidWorkArea(t *testing.T) {
	if _, _, _, ok := fitPreviewContents(0, 1000, 16, 88, 1920, 1080); ok {
		t.Fatal("invalid display work area was accepted")
	}
}
