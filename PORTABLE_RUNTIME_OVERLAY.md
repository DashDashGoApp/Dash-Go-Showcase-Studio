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

## Automatic legacy-bridge proof

A pull request that changes the legacy compatibility bridge, either adapter, its Stage/Windows candidate workflows, or the corresponding packaging path automatically runs the **Legacy Bridge Candidate Proof** workflow. The workflow uses the profile's minimum reviewed stable version, verifies the immutable Dash-Go release asset identity, dispatches the existing Stage Candidate, then dispatches the matching Windows installer install/self-test/uninstall smoke from that Stage run. The parent pull-request check succeeds only when both downstream candidates succeed.

The status check is intentionally a fast green no-op for unrelated pull requests so it can be required on `main` without blocking ordinary documentation or Hub-only changes. A bridge-affecting fork pull request fails closed because GitHub supplies a read-only token; a maintainer must bring the reviewed source into a same-repository branch before the trusted Stage and Windows candidate workflows can be dispatched.


## Native Contract v1 transition

Studio always seeds `showcase-manifest.json` with its four disposable editable calendars. When the packaged Dash-Go runtime contains a valid `release/showcase-contract.json`, Studio launches it through `DASHGO_RUNTIME_PROFILE=showcase`, `DASHGO_SHOWCASE_MANIFEST`, and `DASHGO_DATA_ROOT`, then refuses to open until `/api/showcase/status` reports the native contract, rebuilt cache, all four writable calendars, and writeback candidates.

Older packaged Dash-Go releases without that declaration continue through the checked-in legacy bridge. Studio does not guess: a malformed or incomplete native declaration fails closed, while an absent declaration is the explicit legacy-compatibility fallback until the contract-native stage path replaces the overlays.

## Runtime contract matrix (Task 3.1)

`internal/studiohost/dashgo_runtime_contract_matrix.json` makes the remaining
Studio/Dash-Go boundary explicit. It is the machine-readable inventory for
native Contract v1 capabilities, activation variables, readiness/status
expectations, calendar fixtures, browser-visible scenario routes, package
paths, and legacy-only bridge dependencies.

The immutable beta materializer and Stage selector both validate a present
`release/showcase-contract.json` against that matrix. A missing native
capability reports the exact Studio consumer and reason before package work or
Windows proof begins. The reviewed legacy bridge remains available only when
the declaration is absent. A malformed or incomplete declaration fails closed;
it never falls back to overlays.

## Executable native launch plan (Task 3.2)

The Studio host embeds that same checked-in matrix and derives the native
launch environment, disposable data-root and manifest paths, readiness/status
checks, writable-calendar policy, and browser-visible scenario probes from it.
The matrix's `scenario/data` paths are resolved relative to Studio's private
state root, never the immutable runtime application root. Before launch,
Studio requires the resolved data root to be exactly its private scenario data
path and the seeded manifest to exist. Legacy bridge environment variables and
legacy-only checks remain in their isolated fallback branch.

## Candidate runtime-plan evidence (Task 3.3)

Every native Stage Candidate now emits a compact `nativeRuntimePlan` witness in
`candidate-provenance.json`. It records the exact checked-in matrix hash, the
staged `release/showcase-contract.json` hash, the resolved activation/readiness
plan, browser probes, writable-calendar rules, and every capability that Stage
verified. The Windows candidate extracts the packaged declaration and re-derives
the witness from the checked-out matrix before packaging; a mismatch fails before
the installer smoke. Legacy candidates carry no native runtime-plan witness.

## Browser asset ownership

The legacy bridge may retain Studio's manifest-only browser-asset generator only
for a reviewed source that lacks Dash-Go's standalone
`runtime_assets.go` implementation. Whenever that implementation is present,
Studio invokes it with the pinned Go compiler and treats it as authoritative.
Studio never substitutes the legacy concatenation path after a source-owned
generator has been detected.
