# Stable Dash-Go Release Candidate Intake

## Purpose

This source change adds a **private package-candidate** intake path from an
immutable Dash-Go stable GitHub Release to Dash-Go Showcase Studio. It does not
create a Showcase Studio tag or GitHub Release.

## Normal manual path

A manually dispatched Studio Stage Candidate keeps using the checked-in Studio
manifest and its pinned `engine/Dash-Go_<version>_source.tar.gz` baseline.

## Stable-release path

A stable-release dispatch must use `candidate_origin=dashgo-stable-release` and
supply the exact Dash-Go `vX.Y.Z` tag, version, source-asset SHA-256, tag commit,
and a correlation nonce. Stage creates a disposable detached Studio worktree and
independently verifies all of these facts against the canonical
`DashDashGoApp/Dash-Go` GitHub Release API:

- the release is published, non-prerelease, and immutable;
- the release tag equals `v<version>` and resolves to the supplied commit;
- exactly one `Dash-Go_<version>_source.tar.gz` and `SHA256SUMS` asset exists;
- both GitHub asset digests, the downloaded source bytes, and the SHA256SUMS row
  agree;
- the source archive has the expected root and embedded stable Dash-Go release
  contract.

Only after that proof does Stage replace the manifest baseline and source archive
inside its temporary worktree. The checked-in Studio baseline is never modified.

## Candidate provenance

Stage writes `candidate-provenance.json` schema 2. Its `purpose` is either
`manual package candidate only` or `stable release package candidate only`.
Stable candidates carry the canonical Dash-Go repository, version, tag, immutable
tag commit, asset names, asset IDs, SHA-256 digests, and dispatch nonce.

The Windows package workflow still requires a completed successful
`workflow_dispatch` Stage run for the exact same Studio commit. It accepts only
schema-2 provenance and validates the stable-release proof before packaging.

## Promotion boundary

This bridge produces candidate artifacts only. Human acceptance and any future
Studio release/tag promotion remain separate deliberate steps.
