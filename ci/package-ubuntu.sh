#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: package-ubuntu.sh <native-work-directory> <artifact-directory>" >&2
  exit 64
fi

work="$1"
output="$2"
source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

rm -rf "$work" "$output"
mkdir -p "$work" "$output"

export PYTHONDONTWRITEBYTECODE=1
export GOTOOLCHAIN=local

python3 "$source/ci/stage-package.py" \
  --source "$source" \
  --kit "$source" \
  --work "$work" \
  --go "$(command -v go)" \
  --node node \
  --targets windows,linux \
  --performance safe

python3 - "$source" "$work/summary.json" "$output" <<'PY'
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

source = Path(sys.argv[1]).resolve()
summary_path = Path(sys.argv[2]).resolve()
output = Path(sys.argv[3]).resolve()

summary = json.loads(summary_path.read_text(encoding="utf-8"))
if summary.get("result") != "PASS":
    raise SystemExit("staging summary did not report PASS")

windows_stage = Path(summary["windowsStage"]).resolve()
linux_deb = Path(summary["linuxDeb"]).resolve()

if not windows_stage.is_dir():
    raise SystemExit(f"Windows staging payload is missing: {windows_stage}")
if not linux_deb.is_file():
    raise SystemExit(f"Linux Debian package is missing: {linux_deb}")

output.mkdir(parents=True, exist_ok=True)

windows_archive = output / "windows-stage.tar.gz"
with tarfile.open(windows_archive, "w:gz", dereference=False) as archive:
    archive.add(windows_stage, arcname="windows", recursive=True)

linux_output = output / linux_deb.name
shutil.copy2(linux_deb, linux_output)

for name in (
    "summary.json",
    "run.json",
    "events.jsonl",
    "performance.json",
    "timing.json",
):
    candidate = summary_path.parent / name
    if candidate.is_file():
        shutil.copy2(candidate, output / name)

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

manifest = json.loads((source / "studio.manifest.json").read_text(encoding="utf-8"))
commit = subprocess.check_output(
    ["git", "-C", str(source), "rev-parse", "HEAD"],
    text=True,
).strip()

provenance = {
    "schema": 1,
    "purpose": "manual package candidate only",
    "studioVersion": summary["studioVersion"],
    "dashGoVersion": summary["dashGoVersion"],
    "studioCommit": commit,
    "dashGoSourceSha256": manifest["dashGoSourceSha256"],
    "artifacts": {
        linux_output.name: sha256(linux_output),
        windows_archive.name: sha256(windows_archive),
    },
}

(output / "candidate-provenance.json").write_text(
    json.dumps(provenance, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

print(f"PASS: staged Linux package: {linux_output.name}")
print(f"PASS: staged Windows payload: {windows_archive.name}")
PY