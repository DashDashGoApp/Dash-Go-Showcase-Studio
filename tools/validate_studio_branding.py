#!/usr/bin/env python3
"""Validate committed Dash-Go Showcase Studio branding assets without image tool dependencies."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REQUIRED_PNG_SIZES = (16, 32, 48, 64, 128, 256)


def fail(message: str) -> None:
    raise SystemExit(f"BRANDING ASSET VALIDATION FAILED: {message}")


def need_file(path: Path) -> None:
    if not path.is_file():
        fail(f"missing required file: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    branding = root / "assets" / "branding"
    canonical = branding / "dash-go-showcase-studio.svg"
    small = branding / "dash-go-showcase-studio-small.svg"
    ico = branding / "dash-go-showcase-studio.ico"
    hub = root / "internal" / "studiohost" / "web" / "dash-go-showcase-studio.svg"

    for path in (canonical, small, ico, hub, branding / "README.md"):
        need_file(path)

    canonical_bytes = canonical.read_bytes()
    if not canonical_bytes.lstrip().startswith(b"<svg"):
        fail("canonical SVG is not an SVG document")
    if hub.read_bytes() != canonical_bytes:
        fail("embedded Studio Hub SVG must be byte-identical to canonical SVG")
    if not small.read_bytes().lstrip().startswith(b"<svg"):
        fail("small-size SVG is not an SVG document")

    data = ico.read_bytes()
    if len(data) < 6 or data[:4] != b"\0\0\1\0":
        fail("Windows ICO header is invalid")
    count = struct.unpack_from("<H", data, 4)[0]
    if count < 6:
        fail("Windows ICO must contain at least six image entries")
    if len(data) < 6 + count * 16:
        fail("Windows ICO directory is truncated")

    for size in REQUIRED_PNG_SIZES:
        png = branding / "linux" / "hicolor" / f"{size}x{size}" / "apps" / "dash-go-showcase-studio.png"
        need_file(png)
        if png.read_bytes()[:8] != PNG_SIGNATURE:
            fail(f"Linux {size}px icon is not a PNG: {png}")

    scalable = branding / "linux" / "hicolor" / "scalable" / "apps" / "dash-go-showcase-studio.svg"
    need_file(scalable)
    if scalable.read_bytes() != canonical_bytes:
        fail("Linux scalable SVG must be byte-identical to canonical SVG")

    print("Studio branding assets are complete and internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
