package studiohost

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHubIconRequiresTokenAndServesEmbeddedSVG(t *testing.T) {
	ctl := &controller{token: "studio-test-token"}

	denied := httptest.NewRecorder()
	ctl.handleHubIcon(denied, httptest.NewRequest(http.MethodGet, "http://studio.test/assets/dash-go-showcase-studio.svg", nil))
	if denied.Code != http.StatusForbidden {
		t.Fatalf("unauthorized icon status = %d, want %d", denied.Code, http.StatusForbidden)
	}

	request := httptest.NewRequest(http.MethodGet, "http://studio.test/assets/dash-go-showcase-studio.svg?token=studio-test-token", nil)
	allowed := httptest.NewRecorder()
	ctl.handleHubIcon(allowed, request)

	if allowed.Code != http.StatusOK {
		t.Fatalf("authorized icon status = %d, want %d", allowed.Code, http.StatusOK)
	}
	if contentType := allowed.Header().Get("Content-Type"); !strings.HasPrefix(contentType, "image/svg+xml") {
		t.Fatalf("icon content type = %q, want image/svg+xml", contentType)
	}
	if !strings.Contains(allowed.Body.String(), "<svg") {
		t.Fatal("embedded icon response does not contain an SVG document")
	}
}
