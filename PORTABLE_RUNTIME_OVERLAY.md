# Portable Showcase Runtime Overlay

The Studio Builder never modifies a Dash-Go source archive. It extracts the immutable release archive into a native Builder transaction folder, verifies the release-asset SHA-256 as provenance, and invokes `tools/apply_dashgo_compatibility.py` only against that disposable extraction.

The temporary legacy bridge accepts only Dash-Go versions in its reviewed `1.5.7 <= version < 1.6.0` window. Within that narrow window, it runs the ordered portable-runtime and session-calendar adapters as the definitive source-shape probe and writes one machine-readable compatibility report. A different archive hash alone is not treated as a source incompatibility; the archive hash remains recorded in the report and is still verified against the exact published release asset before extraction.

## Purpose

Studio needs an isolated, disposable Dash-Go runtime for its four scenario calendars, offline data, restricted actions, and presentation assets. The portable overlay provides that runtime while Dash-Go Showcase Contract v1 is being developed.

This bridge is transitional. The end state is unmodified Dash-Go source launched through a supported Showcase profile and manifest rather than a source overlay.

## Safety contract

A release archive whose supplied SHA-256 does not match its downloaded bytes fails before any extraction or adapter runs. A Dash-Go version outside the reviewed bridge window fails before adapter runs. Inside the window, every required application path must exist and each adapter must match its required source anchors exactly. An anchor mismatch, missing required path, adapter failure, formatting failure, or failed candidate self-test blocks the build.

The bridge does not use fuzzy edits, guessed source substitutions, or a broad “manifest-only” acceptance path. The version window only removes false failures caused by archive packaging/provenance differences; the actual legacy adapters remain fail-closed compatibility proof.

The guided baseline-refresh workflow first applies the same bridge to a disposable extraction of a caller-supplied Dash-Go source handoff. Only a successful preflight and full candidate verification may establish evidence for a new Dash-Go release. An upstream source change that changes a real adapter anchor remains a deliberate overlay-maintenance task until Showcase Contract v1 replaces the overlay.

## Formatting contract

The session-calendar adapter runs the selected pinned `gofmt` after its mutations. Stage packaging subsequently verifies every staged Go file is already formatted. The bridge never hides a formatting difference by regenerating or replacing an unrelated source file.

## Candidate contract

Every accepted bridge report lists:

- the selected legacy profile;
- the Dash-Go version and verified source-archive SHA-256;
- the source-policy window used for selection;
- the ordered adapters that completed;
- the required Stage/Linux and Windows candidate checks.

A Studio candidate is not promotable merely because the bridge accepted its source. It must still pass the staged Linux package/runtime self-test and the Windows installer install/uninstall smoke.