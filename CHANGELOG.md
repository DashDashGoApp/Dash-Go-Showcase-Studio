# Changelog

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
