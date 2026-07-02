# Studio Draft-Prepublication Candidate Intake

`studio-prepublish-candidate.yml` is the private, pre-publication Linux staging lane for a future Dash-Go stable release. It is deliberately separate from the historic post-publication Stage Candidate workflow.

## Required repository secret

Configure `DASHGO_RELEASE_READ_TOKEN` in the **Dash-Go Showcase Studio** repository before dispatching this workflow. It must be a least-privilege credential that can read the **DashDashGoApp/Dash-Go** repository and its draft release assets. The workflow rejects an empty secret before it requests the Dash-Go API.

## Required immutable inputs

The publisher must obtain and pass these values from one specific Dash-Go draft release, without recomputing or substituting values during the Studio run:

- Exact 40-character Studio source commit pinned by the Publisher. The workflow verifies that both `GITHUB_SHA` and checked-out `HEAD` equal it before reading Dash-Go.
- Draft release numeric ID.
- `vX.Y.Z` release tag and the exact tag-resolved commit.
- Draft source asset numeric ID and its SHA-256 digest.
- Draft `SHA256SUMS` asset numeric ID.
- A unique dispatch nonce.
- `release_package_version` exactly equal to `X.Y.Z`.

The materializer re-reads the draft release by its numeric ID, proves that it is draft, unpublished, non-prerelease, and mutable, validates both asset IDs and SHA-256 digests, downloads the API assets with the read token, validates `SHA256SUMS`, validates the source tarball release contract, and then stages the Studio package.

## Output and limit

A successful run uploads a short-retention `studio-prepublication-candidate-<studio-commit>` artifact with prepublication provenance schema `3` and purpose `draft prepublication package candidate only`. This workflow neither publishes the Dash-Go draft nor creates a Studio tag, release, or public package.
