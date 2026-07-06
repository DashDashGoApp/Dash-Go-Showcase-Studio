# Dash-Go Showcase Studio Contract

Studio packages a pinned, staged Dash-Go baseline with fictional local fixtures. It has no real update capability, does not use real calendar/account data, and runs only on loopback.

- **Hub:** city selector plus Start Tour; no scenario grid is exposed to the user.
- **Tour:** opens one real Dash-Go destination at a time: App Launcher, Grocery, Chore Wheel, Routines, Family Message Board, and Dashboard Control.
- **Tour previews:** Lists dock and sample weather alert are temporary, Studio-labeled, and removed on any Tour exit. Normal dashboard settings stay unchanged.
- **Fixtures:** six major U.S. demo cities; synthetic location data only.
- **Messages:** ordinary household messages plus Studio-only discovery messages.
- **Location:** search/preview is allowed with synthetic results; all final location writes are rejected by the server with `studio_location_locked`.
- **Guardrails:** host/system actions, updates, live external setup, imports/restores, external notifications, security/PIN changes, and host diagnostics are denied at the staged server boundary.
- **Showcase View:** Fit Display plus three landscape and three portrait private browser-window and matching CSS viewport presets, all session-only to the Studio browser. It never alters the OS display or a real Dash-Go setting.
- **Lifecycle:** a Start/Restart Tour creates fresh data; normal Studio close removes session workspace and browser profile.
- **Windows:** GUI launcher for users; console companion reserved for Builder validation and support actions.

## Runtime contract matrix (Task 3.1)

`internal/studiohost/dashgo_runtime_contract_matrix.json` is Studio's
machine-readable inventory of every remaining Dash-Go runtime assumption. It
classifies each assumption as one of:

- **contract-owned** — a native `dashgo-showcase/v1` capability or readiness
  guarantee that Dash-Go must declare and satisfy;
- **legacy-only** — a compatibility-bridge behavior allowed only for reviewed
  older releases that do not declare a native contract;
- **studio-owned** — Studio package layout, fictional fixtures, browser-marker
  expectations, and the exact scenario presentation corpus.

The matrix inventories the relevant application/data paths, source and packaged
server binaries, all seven calendar fixtures and the four writable candidates,
synthetic configuration/weather data, readiness endpoints, and every
browser-visible route that must resolve before Studio opens a browser.

The immutable beta materializer reads this matrix while inspecting
`release/showcase-contract.json`. A native beta with a missing capability stops
in the materialization step with a deterministic report that names the missing
capability, its consuming Studio assumption, and its reason. Stage loads the
same matrix again before selecting native mode, so a malformed or incomplete
native declaration never reaches browser generation, package assembly, or the
Windows installer proof.

The matrix does not turn Studio-owned fixture names or package filenames into
Dash-Go public API. It makes those dependencies explicit and testable while
keeping Contract v1 narrow. An absent declaration may still use the reviewed
legacy bridge; a malformed or incomplete declaration is never silently
reinterpreted as legacy.

## Executable native launch plan (Task 3.2)

Studio embeds the same matrix into its host binary and compiles the native
portion into one launch plan. When a packaged Dash-Go release declares native
Contract v1, Studio derives the declaration path, activation environment names
and values, disposable `scenario/data` root, manifest path, readiness/status
routes, writable-calendar requirements, and browser route probes from that
plan. It verifies that the matrix data root resolves beneath Studio's private
state root and that the seeded manifest exists before it starts Dash-Go.

The native status and browser checks also consume the plan directly. This
removes duplicate hard-coded native capability, route, and calendar lists from
the launcher while keeping legacy-only adapters explicitly separate. A bad
embedded matrix, missing manifest, mismatched private data root, malformed
native declaration, or incomplete status remains a fail-closed startup error.
