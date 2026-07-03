# Studio Windows Runtime Boundary

## Scope

This contract applies to the Windows `1.5.6-r2` Showcase Studio package. It is a behavioral hardening change for the public Studio runtime and does not alter the published Dash-Go `1.5.6` release.

## Immutable installation files

Studio launches `runtime/app/bin/dash-go-showcase-server.exe` directly from the installed Studio directory. The Studio host never copies that executable, the Studio executable, a DLL, or a script to its state root before running it.

## Mutable per-user state

All resettable scenario data is held below the Studio state root: scenario configuration, calendars, cache, logs, user-managed font data, browser profile, and a private simulated home directory. A scenario reset atomically replaces only this data tree. No executable, DLL, script helper, or archive may be created below the state root.

## Process and network limits

Studio owns one local Dash-Go Showcase server and binds it only to `127.0.0.1` on a selected high port. The host starts the installed server with `DASHGO_SHOWCASE=1`, `DASHGO_SHOWCASE_DATA_ROOT`, and `DASHGO_HOME`; it never starts a server from a user-writable directory. Studio does not install a service, scheduled task, startup entry, firewall rule, driver, or system-wide policy.

## Release proof

Windows package smoke tests must run the installed self-test and fail if the mutable state root contains an executable or script afterward. Source and prepublication validation must fail if the old runtime-copy or mutable-workspace execution pattern returns.
