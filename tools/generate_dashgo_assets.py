#!/usr/bin/env python3
"""Generate the four Dash-Go browser assets from manifest-owned split sources."""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import argparse, json, posixpath, stat
from pathlib import Path

class AssetError(RuntimeError): pass

def source_text(path: Path) -> str:
    value = path.read_text(encoding='utf-8')
    return value if value.endswith('\n') else value + '\n'

def manifest_files(app: Path, manifest_rel: str, root_rel: str, suffix: str, names: tuple[str, ...]) -> dict[str, list[Path]]:
    path = app / manifest_rel
    try: raw = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: raise AssetError(f'invalid {manifest_rel}: {exc}') from exc
    if not isinstance(raw, dict) or raw.get('schema') != 1 or not isinstance(raw.get('bundles'), dict):
        raise AssetError(f'invalid manifest shape: {manifest_rel}')
    bundles = raw['bundles']; out: dict[str,list[Path]] = {}; seen=set()
    if set(bundles) != set(names): raise AssetError(f'{manifest_rel} bundle names do not match {names}')
    for name in names:
        rows=bundles.get(name)
        if not isinstance(rows,list) or not rows: raise AssetError(f'{manifest_rel} {name} is empty')
        files=[]
        for item in rows:
            if not isinstance(item,str) or not item or item.strip()!=item or '\\' in item: raise AssetError(f'invalid source entry {item!r}')
            clean=posixpath.normpath(item)
            if item.startswith('/') or clean in ('.','..') or clean.startswith('../'): raise AssetError(f'unsafe source entry {item!r}')
            if clean in seen: raise AssetError(f'duplicate bundle source {clean}')
            candidate=app/root_rel/Path(*clean.split('/'))
            info=candidate.lstat()
            if candidate.suffix != suffix or stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode): raise AssetError(f'invalid source file {candidate}')
            seen.add(clean); files.append(candidate)
        out[name]=files
    return out

def build(app: Path, version: str) -> dict[Path,bytes]:
    js=manifest_files(app,'ui/js/bundle.manifest.json','ui/js','.js',('app','control'))
    css=manifest_files(app,'ui/css/bundle.manifest.json','ui/css','.css',('dashboard','control'))
    def js_bundle(name: str) -> bytes:
        control=name=='control'; target='ui/js/app.control.bundle.js' if control else 'ui/js/app.bundle.js'; kind='control bundle' if control else 'browser bundle'
        parts=[f'/* Dash-Go {version} {kind}. GENERATED as {target} from ui/js split source files; edit split files, not this bundle. */\n']
        for file in js[name]: parts.append(f'\n/* ===== {file.relative_to(app).as_posix()} ===== */\n{source_text(file)}')
        return ''.join(parts).encode()
    def css_bundle(name: str, target: str) -> bytes:
        parts=[f'/* Dash-Go {version} {target} browser bundle.\n   GENERATED from ui/css/{name} split source files; edit split files, not this bundle. */\n']
        for file in css[name]: parts.append(f'\n/* ---- {file.relative_to(app).as_posix()} ---- */\n{source_text(file)}')
        return ''.join(parts).encode()
    return {app/'ui/js/app.bundle.js':js_bundle('app'),app/'ui/js/app.control.bundle.js':js_bundle('control'),app/'ui/dashboard.css':css_bundle('dashboard','dashboard.css'),app/'ui/control-layout.css':css_bundle('control','control-layout.css')}

def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--app',type=Path,required=True);p.add_argument('--verify',action='store_true');a=p.parse_args();app=a.app.resolve();version=(app/'VERSION').read_text(encoding='utf-8').strip()
    if not version: raise AssetError('app/VERSION is empty')
    expected=build(app,version)
    for path,data in expected.items():
        if a.verify:
            if not path.is_file() or path.read_bytes()!=data: raise AssetError(f'generated asset differs: {path.relative_to(app)}')
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    print(('VERIFIED' if a.verify else 'GENERATED')+f': {len(expected)} browser assets for Dash-Go {version}')
    return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except AssetError as exc: raise SystemExit(f'ASSET ERROR: {exc}')
