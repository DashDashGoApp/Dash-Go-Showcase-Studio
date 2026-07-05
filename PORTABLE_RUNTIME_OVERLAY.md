# Portable Showcase Runtime Overlay

The Studio Builder never modifies a Dash-Go source archive. It extracts the exact hash-pinned archive into a native Builder transaction folder and invokes `tools/apply_dashgo_compatibility.py` only there. The checked-in legacy bridge selects an exact version-and-SHA-256 profile, runs the ordered portable-runtime and session-calendar adapters, and writes one machine-readable compatibility report.

## Purpose

The overlay creates the narrow server and browser boundary needed for a disposable Windows/Linux Studio runtime:

- `DASHGO_HOME` redirects per-user Dash-Go files into the Studio workspace.
- `DASHGO_SHOWCASE=1` suppresses appliance-only background workers.
- The server rejects location commits, system actions, updates, backup/restore/import paths, external integrations, security/PIN changes, and host diagnostics with explicit Studio-only reason codes.
- `/api/geocode` returns only local synthetic preview results while Studio is active.
- POSIX locking, detached process, and disk-free helpers are split for Windows and non-Windows implementations.
- A Studio-only Tour module clears every prior app/control overlay before opening the next target, drives the temporary Lists and sample alert previews, and cleans them on every exit path.
- A Studio-only Showcase View module talks only to the private Chromium DevTools endpoint bound to `127.0.0.1`, using CSS viewport emulation rather than operating-system display changes.
- The staged overlay replaces the custom Dashboard Control summary tap toggle with native `summary` behavior so cards open reliably in desktop Chromium.

## Safety contract

An unknown version-and-SHA-256 pair is a build failure before any adapter runs. A known adapter source-anchor mismatch is also a build failure. The patcher does not attempt fuzzy edits or silently continue when the pinned baseline changes. The guided baseline refresh workflow first applies the same patcher to a disposable extraction of a caller-supplied Dash-Go source handoff. Only an exact successful preflight may update Studio manifest/archive metadata; an upstream source change remains a deliberate overlay-maintenance task.

## Formatting contract

Overlay-generated Go files are source-formatted before packaging. The Builder checks those exact files immediately after patching, then repeats `gofmt` across the full staged Dash-Go module. Formatting failures are never auto-corrected or bypassed during a release build.
