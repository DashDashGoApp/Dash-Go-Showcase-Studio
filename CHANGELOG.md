# Changelog

## Unreleased native-contract correction
- Restores the Studio Tour, presentation overlay, Showcase View controls, offline weather/map fixtures, location lock, server-side safety policy, and isolated session-calendar management when Dash-Go declares native `dashgo-showcase/v1`.
- Keeps native Contract v1 responsible for isolated scenario data and readiness while installing a separate, narrowly scoped Studio-owned presentation/safety extension before source-owned browser bundle generation.
- Reworks Showcase View sizing so device presets preserve their CSS aspect ratio, fit proportionally within the active display work area, center the browser window, and report the actual window size and scale.
- Replaces the fragile one-shot startup resize with bounded DevTools readiness retries and a preferred 1600 × 900 presentation window that scales down safely on smaller displays.
- Restores move, delete-series, and ordinary writeback behavior for native Studio session calendars while keeping every mutation local to the disposable scenario and suppressing remote synchronization.
- Adds hermetic native-extension, staged native-path, source-contract, and workflow gates to prevent another native release from silently omitting Studio presentation, safety, or session-calendar behavior.

## 2.0.0-test.10
- Tour transitions now clear the prior Launcher, app, Dashboard Control surface, and scrim before opening the next real Dash-Go destination.
- The Lists dock remains off in ordinary Studio sessions, appears only as a temporary Tour preview, and clears on Skip, close, Finish, Restart, reload, and session cleanup.
- Added city-specific, clearly labeled offline **Sample Weather Alert — Studio Preview** behavior during the Tour.
- Location search remains explorable with synthetic local results, but the final location commit is blocked at the staged Dash-Go server boundary and opens the “Ah ah ah, you didn’t say the magic word.” Studio modal.
- Added a deny-by-default Showcase guard for external integrations, host/system actions, updates, backups/restores/imports, diagnostics that could reveal host state, and PIN changes.
- Dashboard Control expandable cards now use native `summary` activation in the staged Studio runtime, eliminating the competing custom tap toggle that could require repeated clicks in Chromium.
- Added the live **Showcase View** switcher with Fit Display, four landscape presets, four portrait presets, a Clean View toggle, loopback-only DevTools viewport emulation, and no operating-system display changes.
- Expanded source and Builder contracts for Tour cleanup, alert/list preview lifecycle, server-side locking, viewport presets, and staged asset order.

## Earlier tests
- Previous tests focused on installer, uninstaller, city fixtures, GUI launch behavior, and Builder hardening.
