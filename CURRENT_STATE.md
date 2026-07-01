# Current State

- Studio version: `2.0.0-test.10`
- Dash-Go baseline: `1.5.2` (pinned source archive)
- Supported packages: Windows amd64 and Linux amd64
- The Hub is a city picker with one **Start Tour** action. Scenario fixtures remain Builder-only data.
- The Tour drives one primary Dash-Go surface at a time and cleans temporary Lists/alert previews on every exit path.
- Studio sessions are synthetic, private, and removed when the browser window closes.
- Location search uses Studio-safe preview results; final location commits are server-side locked.
- Showcase View provides session-only live landscape and portrait CSS viewport presets through a private loopback browser connection; it never changes host display settings.
- Windows packages carry a GUI launcher for normal use and a CLI companion for Builder-only smoke/maintenance actions.
