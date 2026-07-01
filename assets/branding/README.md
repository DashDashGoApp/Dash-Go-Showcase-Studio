# Dash-Go Showcase Studio branding assets

- `dash-go-showcase-studio.svg` is the canonical scalable Studio icon supplied by the project owner.
- `dash-go-showcase-studio-small.svg` is the intentionally simplified small-size companion used for 16/20/24 px Windows icon entries. It preserves the calendar, weather, moon, status, and dark dashboard visual language without reducing the full illustration to unreadable detail.
- `dash-go-showcase-studio.ico` is the committed Windows multi-resolution package asset. It contains 16, 20, 24, 32, 48, 64, 128, and 256 px entries.
- `linux/hicolor/` contains committed Linux icon-theme PNG variants plus the scalable canonical SVG.
- `internal/studiohost/web/dash-go-showcase-studio.svg` is intentionally byte-identical to the canonical SVG. Go embeds it for the authenticated Studio Hub favicon route because `go:embed` cannot reach a file outside the package directory.

Do not convert these assets during a package build. Generated platform variants are committed so local and GitHub builds remain reproducible.
