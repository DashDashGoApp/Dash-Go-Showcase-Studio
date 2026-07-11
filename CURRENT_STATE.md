# Current State

- Studio version: `2.0.0-test.10`
- Dash-Go baseline: `1.5.2` (pinned source archive)
- Supported packages: Windows amd64 and Linux amd64
- The Hub is a city picker with one **Start Tour** action. Scenario fixtures remain Builder-only data.
- The Tour drives one primary Dash-Go surface at a time and cleans temporary Lists/alert previews on every exit path.
- Studio sessions are synthetic, private, and removed when the browser window closes.
- Location search uses Studio-safe preview results; final location commits are server-side locked.
- Showcase View provides session-only native browser-window sizing with matching live landscape and portrait CSS viewport presets through a private loopback browser connection; device previews preserve aspect ratio, fit within the active display work area, and never change host display settings.
- Native `dashgo-showcase/v1` candidates receive a checked Studio-owned presentation/safety/session-calendar extension before Dash-Go’s source-owned browser bundles are generated; Contract v1 continues to own isolated data, calendar allowlists, and readiness rather than Studio UI or mutation presentation.
- Native Studio calendar edits, moves, and series deletions are limited to enabled writable calendars declared by the disposable scenario manifest, return `sync: session`, and never queue provider synchronization.
- Normal startup prefers a centered 1600 × 900 presentation window and proportionally fits down on smaller displays after Chromium’s private DevTools endpoint becomes ready.
- Windows packages carry a GUI launcher for normal use and a CLI companion for Builder-only smoke/maintenance actions.
