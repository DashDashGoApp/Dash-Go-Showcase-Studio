# Third-Party Notices

Dash-Go includes or installs third-party software and font assets. This file identifies those components, their pinned versions where applicable, and the licenses or notices that apply.

This notice file covers software and assets distributed with Dash-Go or installed by Dash-Go. Optional online services, APIs, and user-configured providers are described separately in `INTEGRATIONS.md`.

The complete license texts named below are provided in `third_party_licenses/`.

## Included Go software

| Component | Version | License | Purpose |
|---|---:|---|---|
| `github.com/unraid/apprise-go` | `v0.2.6` | BSD 2-Clause | Optional household notification delivery |
| `github.com/gomarkdown/markdown` | `v0.0.0-20260417124207-7d523f7318df` | BSD 2-Clause | Markdown conversion used by Apprise-Go |
| `golang.org/x/crypto` | `v0.53.0` | BSD 3-Clause | Cryptographic support used by Apprise-Go |
| `golang.org/x/mod` | `v0.36.0` | BSD 3-Clause | Go module metadata support in the resolved Go module graph |
| `golang.org/x/net` | `v0.56.0` | BSD 3-Clause | HTML-processing support used by Apprise-Go |
| `golang.org/x/sync` | `v0.21.0` | BSD 3-Clause | Concurrency support in the resolved Go module graph |
| `golang.org/x/sys` | `v0.46.0` | BSD 3-Clause | Low-level operating-system support in the resolved Go module graph |
| `golang.org/x/term` | `v0.44.0` | BSD 3-Clause | Terminal support in the resolved Go module graph |
| `golang.org/x/text` | `v0.38.0` | BSD 3-Clause | International text processing support in the resolved Go module graph |
| `golang.org/x/tools` | `v0.45.0` | BSD 3-Clause | Go tooling support in the resolved Go module graph |
| `gopkg.in/yaml.v3` | `v3.0.1` | MIT AND Apache-2.0 | YAML configuration parsing used by Apprise-Go |

### Apprise-Go

Copyright (c) 2025, Chris Caron `<lead2gold@gmail.com>`

Apprise-Go is used as an optional Go notification-routing library. It is licensed under the BSD 2-Clause License.

Apprise-Go is a Go port of Apprise by Chris Caron. Its upstream notice identifies certain default notification icon assets as based on Heroicons under the MIT License. Dash-Go does not package those Apprise-Go icon assets; this attribution is retained to preserve the upstream notice context.

### Gomarkdown

Copyright © 2011 Russ Ross
Copyright © 2018 Krzysztof Kowalczyk
Copyright © 2018 Authors

Gomarkdown is licensed under the BSD 2-Clause License.

### Go supplementary libraries

Copyright 2009 The Go Authors.

`golang.org/x/crypto`, `golang.org/x/mod`, `golang.org/x/net`, `golang.org/x/sync`, `golang.org/x/sys`, `golang.org/x/term`, `golang.org/x/text`, and `golang.org/x/tools` are licensed under the BSD 3-Clause License.

### YAML v3

`gopkg.in/yaml.v3` `v3.0.1` includes Go ports of libyaml files under the MIT License (Copyright 2006–2011 Kirill Simonov) and remaining project files under Apache License 2.0 (Copyright 2011–2019 Canonical Ltd). Its source tree is therefore recorded as `MIT AND Apache-2.0`; complete texts are provided in `third_party_licenses/MIT.txt` and `third_party_licenses/Apache-2.0.txt`.

## Font software

Dash-Go installs these application fonts during normal setup or downloads them only when a user explicitly enables the corresponding optional font choice.

| Font | Use | License | Copyright / attribution |
|---|---|---|---|
| Libre Franklin | Standard Dash-Go interface font | SIL Open Font License 1.1 | Copyright (c) 2015, Impallari Type |
| DM Mono | Standard Dash-Go monospace font | SIL Open Font License 1.1 | Copyright 2020 The DM Mono Project Authors |
| Nunito | Optional Rounded typography choice | SIL Open Font License 1.1 | Copyright 2014 The Nunito Project Authors |
| Atkinson Hyperlegible | Optional Readable typography choice | SIL Open Font License 1.1 | Copyright 2020 Braille Institute of America, Inc. |

## Included license texts

The following complete license texts must be distributed with Dash-Go:

```text
third_party_licenses/
  Apache-2.0.txt
  BSD-2-Clause.txt
  BSD-3-Clause.txt
  MIT.txt
  OFL-1.1.txt
```

## Scope and maintenance

- This file records Dash-Go runtime software and font assets.
- It does not list Raspberry Pi OS packages, browser packages, or other components installed and maintained by the operating-system distribution.
- It does not grant rights in the names, logos, trademarks, hosted services, or brands of third parties.
- When a Dash-Go release changes the resolved runtime dependency graph or distributed font inventory, update this file and the corresponding license-text directory in the same change.
- The local release builder must verify that this inventory matches the resolved release dependency graph and installed asset set.
