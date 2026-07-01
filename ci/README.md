# Studio package-candidate staging engine

This directory contains the GitHub Actions-native package staging tool for Dash-Go Showcase Studio.

## Provenance

`stage-package.py` was promoted from `Dash-Go Showcase Studio Builder 0.1.0-test.22`.
It preserves the Builder staging checks for the pinned Dash-Go runtime, exact overlay anchors, generated assets, Tour/Guard/Showcase View contract, Go validation, Linux package assembly, Linux package smoke, and Windows staging payload creation.

## CI boundary

- This engine runs only on the Ubuntu GitHub Actions job.
- It produces a Linux `.deb` and a Windows staging payload.
- A separate Windows Actions job compiles and smoke-tests the Inno installer.
- This tool never creates a GitHub Release, changes `Latest`, creates `v1.0.0`, or contacts Dash-Go.

## Parity rule

Any future change to the local Builder staging contract must be reviewed for a matching update here before GitHub package candidates are trusted.
