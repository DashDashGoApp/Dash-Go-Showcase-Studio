# Dash-Go Showcase Studio Contract

Studio packages a pinned, staged Dash-Go baseline with fictional local fixtures. It has no real update capability, does not use real calendar/account data, and runs only on loopback.

- **Hub:** city selector plus Start Tour; no scenario grid is exposed to the user.
- **Tour:** opens one real Dash-Go destination at a time: App Launcher, Grocery, Chore Wheel, Routines, Family Message Board, and Dashboard Control.
- **Tour previews:** Lists dock and sample weather alert are temporary, Studio-labeled, and removed on any Tour exit. Normal dashboard settings stay unchanged.
- **Fixtures:** six major U.S. demo cities; synthetic location data only.
- **Messages:** ordinary household messages plus Studio-only discovery messages.
- **Location:** search/preview is allowed with synthetic results; all final location writes are rejected by the server with `studio_location_locked`.
- **Guardrails:** host/system actions, updates, live external setup, imports/restores, external notifications, security/PIN changes, and host diagnostics are denied at the staged server boundary.
- **Showcase View:** Fit Display plus four landscape and four portrait CSS viewport presets, all private to the Studio browser session. It never alters the OS display or a real Dash-Go setting.
- **Lifecycle:** a Start/Restart Tour creates fresh data; normal Studio close removes session workspace and browser profile.
- **Windows:** GUI launcher for users; console companion reserved for Builder validation and support actions.
