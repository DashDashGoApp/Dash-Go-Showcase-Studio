package studiohost

import "testing"

func TestSessionCalendarWritableSourcesIncludeSchool(t *testing.T) {
	for _, source := range []string{
		"calendars/family.green.ics",
		"calendars/school.blue.ics",
		"calendars/home.amber.ics",
		"calendars/plans.violet.ics",
	} {
		if _, ok := sessionCalendarWritableSources[source]; !ok {
			t.Fatalf("missing Studio writable calendar source %s", source)
		}
	}
	if _, ok := sessionCalendarWritableSources["calendars/chore-wheel.ics"]; ok {
		t.Fatal("generated Chore Wheel feed must remain read-only")
	}
}
