#!/usr/bin/env python3
"""Fail-closed GitHub Actions package-candidate staging engine for Dash-Go Showcase Studio."""
from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback
from pathlib import Path

sys.dont_write_bytecode = True

WINDOWS_PAYLOAD_LAYOUT = "windows-curated-v1"
WINDOWS_PAYLOAD_MANIFEST = "INSTALLER_CONTENTS.json"
WINDOWS_RUNTIME_ROOT_FILES = ("VERSION", "index.html", "themes.list")
WINDOWS_RUNTIME_TREES = ("base", "release", "ui")
WINDOWS_STAGE_REQUIRED_FILES = (
    "dash-go-showcase-studio.exe",
    "dash-go-showcase-studio.exe.manifest",
    "STUDIO_RUNTIME.json",
    WINDOWS_PAYLOAD_MANIFEST,
    "NOTICE.md",
    "LICENSE",
    "DASH-GO-THIRD-PARTY-NOTICES.md",
    "WHAT-STUDIO-DOES-LOCALLY.txt",
    "assets/branding/dash-go-showcase-studio.ico",
    "runtime/app/VERSION",
    "runtime/app/index.html",
    "runtime/app/themes.list",
    "runtime/app/bin/dash-go-showcase-server.exe",
    "runtime/app/bin/dash-go-showcase-server.exe.manifest",
)
WINDOWS_RUNTIME_PREFIXES = tuple(f"runtime/app/{name}/" for name in WINDOWS_RUNTIME_TREES)
WINDOWS_DISALLOWED_SUFFIXES = frozenset({".bat", ".cmd", ".go", ".mjs", ".ps1", ".py", ".pyc", ".sh", ".test", ".zip", ".tar", ".gz"})
WINDOWS_AS_INVOKER_MANIFEST = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<assembly xmlns=\"urn:schemas-microsoft-com:asm.v1\" manifestVersion=\"1.0\">
  <trustInfo xmlns=\"urn:schemas-microsoft-com:asm.v3\">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level=\"asInvoker\" uiAccess=\"false\"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
</assembly>
"""

SHOWCASE_OVERLAY_GO_FILES = (
    "cmd/dashboard-control-server/showcase_mode.go",
    "cmd/dashboard-control-server/portable_runtime_unix.go",
    "cmd/dashboard-control-server/portable_runtime_windows.go",
    "internal/platform/disk_free_unix.go",
    "internal/platform/disk_free_windows.go",
    "internal/platform/terminal_detach_unix.go",
    "internal/platform/terminal_detach_windows.go",
)


class BuildFailure(RuntimeError):
    def __init__(self, phase: str, kind: str, message: str, *, exit_code: int | None = None, log: Path | None = None):
        super().__init__(message)
        self.phase = phase
        self.kind = kind
        self.exit_code = exit_code
        self.log = log


@dataclasses.dataclass(frozen=True)
class PerformancePlan:
    requested: str
    effective: str
    visible_cpus: int
    visible_memory_mib: int
    cpu_budget: int
    test_p: int
    test_gomaxprocs: int
    cross_workers: int
    cross_gomaxprocs: int
    static_workers: int

    def as_json(self) -> dict[str, int | str]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class Context:
    source: Path
    kit: Path
    work: Path
    go: str
    node: str
    targets: tuple[str, ...]
    trace: bool
    manifest: dict
    events_path: Path
    logs: Path
    started: float
    build_id: str
    plan: PerformancePlan
    lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)
    timings: list[dict[str, int | str]] = dataclasses.field(default_factory=list)

    @property
    def version(self) -> str:
        return str(self.manifest["studioVersion"])

    @property
    def dashgo_version(self) -> str:
        return str(self.manifest["dashGoVersion"])

    @property
    def release_package_version(self) -> str:
        raw = self.manifest.get("releasePackageVersion", self.version)
        return str(raw)

    @property
    def dashgo_root(self) -> str:
        return f"dash-go-source-{self.dashgo_version}"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_text(text: str, maximum: int = 5000) -> str:
    text = text.replace("\x00", "")
    return text if len(text) <= maximum else "[... output truncated ...]\n" + text[-maximum:]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def event(ctx: Context, *, phase: str, status: str, step: str, detail: str = "", duration_ms: int | None = None, log: Path | None = None, exit_code: int | None = None) -> None:
    row = {"at": now_utc(), "phase": phase, "status": status, "step": step, "detail": detail, "durationMs": duration_ms, "exitCode": exit_code, "log": str(log) if log else ""}
    with ctx.lock:
        ctx.events_path.parent.mkdir(parents=True, exist_ok=True)
        with ctx.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def phase(ctx: Context, number: int, title: str):
    label = f"{number:02d} {title}"
    class Runner:
        def __enter__(self):
            self.started = time.monotonic()
            print(f"== [{label}]")
            event(ctx, phase=label, status="started", step=title)
            return label
        def __exit__(self, exc_type, exc, tb):
            elapsed = round((time.monotonic() - self.started) * 1000)
            ctx.timings.append({"phase": label, "durationMs": elapsed, "result": "PASS" if exc is None else "FAIL"})
            if exc is None:
                print(f"   PASS ({elapsed / 1000:.1f}s)")
                event(ctx, phase=label, status="passed", step=title, duration_ms=elapsed)
                return False
            if isinstance(exc, BuildFailure):
                if not exc.phase:
                    exc.phase = label
                event(ctx, phase=label, status="failed", step=title, detail=str(exc), duration_ms=elapsed, log=exc.log, exit_code=exc.exit_code)
            else:
                event(ctx, phase=label, status="failed", step=title, detail=str(exc), duration_ms=elapsed)
            return False
    return Runner()


def run(ctx: Context, phase_name: str, command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 1800) -> str:
    safe = re.sub(r"[\r\n]+", " ", " ".join(command))
    slug = re.sub(r"[^a-z0-9]+", "-", phase_name.lower()).strip("-")
    log_path = ctx.logs / f"{slug}.log"
    merged = os.environ.copy()
    merged.update({"GOTOOLCHAIN": "local", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"})
    if env:
        merged.update(env)
    started = time.monotonic()
    with ctx.lock:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="replace") as log:
            log.write(f"$ {safe}\n$ cwd: {cwd}\n\n")
    try:
        with log_path.open("a", encoding="utf-8", errors="replace") as log:
            proc = subprocess.run(command, cwd=cwd, env=merged, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise BuildFailure(phase_name, "Timeout", f"command exceeded {timeout}s: {safe}", log=log_path) from exc
    duration = round((time.monotonic() - started) * 1000)
    if ctx.trace:
        print(f"   > {safe}")
    if proc.returncode != 0:
        tail = safe_text(log_path.read_text(encoding="utf-8", errors="replace"), 4000)
        raise BuildFailure(phase_name, "Command failure", f"command failed with exit code {proc.returncode}: {safe}\n{tail}", exit_code=proc.returncode, log=log_path)
    event(ctx, phase=phase_name, status="command-passed", step=command[0], detail=safe, duration_ms=duration, log=log_path, exit_code=0)
    return log_path.read_text(encoding="utf-8", errors="replace")


def need_file(path: Path, what: str, phase_name: str) -> None:
    if not path.is_file():
        raise BuildFailure(phase_name, "Missing input", f"{what} is missing: {path}")


def prepare_work_directory(work: Path) -> None:
    if not work.exists():
        work.mkdir(parents=True, mode=0o700)
        return
    if not work.is_dir():
        raise SystemExit(f"BUILD INVOCATION ERROR: work path exists but is not a directory: {work}")
    entries = sorted(work.iterdir(), key=lambda item: item.name.lower())
    if entries:
        shown = ", ".join(entry.name for entry in entries[:8])
        suffix = "" if len(entries) <= 8 else ", ..."
        raise SystemExit(f"BUILD INVOCATION ERROR: work directory must be new or an empty caller-provisioned transaction root: {work}; found: {shown}{suffix}")


def safe_extract(source: Path, target: Path, expected_root: str, phase_name: str) -> None:
    with tarfile.open(source, "r:gz") as tar:
        members = tar.getmembers()
        roots: set[str] = set()
        for member in members:
            name = member.name.replace("\\", "/")
            if not name or name.startswith("/") or name.startswith("../") or "/../" in name:
                raise BuildFailure(phase_name, "Unsafe archive", f"unsafe source archive path: {member.name}")
            if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                raise BuildFailure(phase_name, "Unsafe archive", f"unsupported member in source archive: {member.name}")
            roots.add(name.split("/", 1)[0])
        if roots != {expected_root}:
            raise BuildFailure(phase_name, "Unsafe archive", f"unexpected Dash-Go archive roots: {sorted(roots)}; expected {expected_root}")
        try:
            tar.extractall(target, filter="fully_trusted")
        except TypeError:
            tar.extractall(target)


def remove_mutable_runtime_data(app: Path, phase_name: str) -> None:
    for relative in ("config", "calendars", "cache", "logs", "releases"):
        candidate = app / relative
        if candidate.exists():
            shutil.rmtree(candidate)
    forbidden = (".dashboard-control.env", ".dashboard-pin", ".dashboard-todo.json")
    for root, dirs, files in os.walk(app):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for name in files:
            if name in forbidden or name.endswith(".pyc"):
                raise BuildFailure(phase_name, "Payload safety", f"mutable or cache file remains in runtime payload: {Path(root, name).relative_to(app)}")


def copy_tree_clean(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=False, copy_function=shutil.copy2)


def check_payload_tree(root: Path, phase_name: str) -> None:
    banned_dirs = {".git", "config", "calendars", "cache", "logs", "releases", "__pycache__"}
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in banned_dirs for part in rel.parts):
            raise BuildFailure(phase_name, "Payload safety", f"runtime payload contains forbidden mutable/cache path: {rel}")
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise BuildFailure(phase_name, "Payload safety", f"runtime payload contains unsupported filesystem entry: {rel}")
        if path.is_file() and path.suffix in {".pyc", ".test"}:
            raise BuildFailure(phase_name, "Payload safety", f"runtime payload contains forbidden generated file: {rel}")


def parse_targets(value: str) -> tuple[str, ...]:
    rows = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    if not rows or any(item not in {"windows", "linux"} for item in rows):
        raise argparse.ArgumentTypeError("targets must be Windows, Linux, or Windows,Linux")
    return tuple(dict.fromkeys(rows))


def memory_mib() -> int:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 0


def resolve_plan(requested: str) -> PerformancePlan:
    cpu = max(1, os.cpu_count() or 1)
    memory = memory_mib()
    requested = requested.lower()
    if requested == "auto":
        effective = "desktop" if cpu >= 12 and memory >= 12 * 1024 else "safe"
    elif requested == "max" and (cpu < 12 or memory < 8 * 1024):
        effective = "desktop" if cpu >= 8 and memory >= 6 * 1024 else "safe"
    else:
        effective = requested
    if effective == "safe":
        return PerformancePlan(requested, effective, cpu, memory, min(4, cpu), min(4, cpu), min(4, cpu), 1, min(4, cpu), min(2, cpu))
    if effective == "desktop":
        workers = 4 if memory >= 16 * 1024 else 2
        return PerformancePlan(requested, effective, cpu, memory, min(16, cpu), min(12, cpu), min(12, cpu), workers, min(8, cpu), min(8, cpu))
    workers = 4 if memory >= 12 * 1024 else 2
    return PerformancePlan(requested, effective, cpu, memory, min(30, cpu), min(24, cpu), min(24, cpu), workers, min(10, cpu), min(12, cpu))


def planned_env(ctx: Context, *, cross: bool = False) -> dict[str, str]:
    return {"GOMAXPROCS": str(ctx.plan.cross_gomaxprocs if cross else ctx.plan.test_gomaxprocs)}


def go_test_network_env(ctx: Context) -> dict[str, str]:
    sink = "http://127.0.0.1:9"
    return {**planned_env(ctx), "HTTP_PROXY": sink, "HTTPS_PROXY": sink, "ALL_PROXY": sink, "http_proxy": sink, "https_proxy": sink, "all_proxy": sink, "NO_PROXY": "localhost,127.0.0.1,::1", "no_proxy": "localhost,127.0.0.1,::1"}


def validate_manifest(ctx: Context) -> None:
    required = ("schema", "studioVersion", "dashGoVersion", "dashGoSourceArchive", "dashGoSourceSha256", "goToolchain", "supportedTargets")
    for key in required:
        if key not in ctx.manifest:
            raise BuildFailure("", "Manifest", f"studio.manifest.json missing {key}")
    if ctx.manifest.get("schema") != 1:
        raise BuildFailure("", "Manifest", "studio.manifest.json schema must be 1")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-test\.\d+)?", str(ctx.manifest.get("studioVersion", ""))):
        raise BuildFailure("", "Manifest", "studioVersion must use X.Y.Z or X.Y.Z-test.N")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-beta\.\d+)?", str(ctx.manifest.get("dashGoVersion", ""))):
        raise BuildFailure("", "Manifest", "dashGoVersion must use X.Y.Z or X.Y.Z-beta.N")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-(?:test\.\d+|r[1-9]\d*))?", ctx.release_package_version):
        raise BuildFailure("", "Manifest", "releasePackageVersion must use X.Y.Z, X.Y.Z-rN, or X.Y.Z-test.N")
    if "releasePackageVersion" in ctx.manifest:
        expected = re.escape(ctx.dashgo_version)
        if not re.fullmatch(expected + r"(?:-r[1-9]\d*)?", ctx.release_package_version):
            raise BuildFailure("", "Manifest", "stable releasePackageVersion must equal dashGoVersion or dashGoVersion-rN")
    if ctx.manifest.get("goToolchain") != "1.26.4":
        raise BuildFailure("", "Manifest", "this Builder requires Go 1.26.4")
    if str(ctx.manifest.get("dashGoSourceArchive")) != f"engine/Dash-Go_{ctx.dashgo_version}_source.tar.gz":
        raise BuildFailure("", "Manifest", "Dash-Go archive path must match the pinned dashGoVersion")


def source_privacy_sanity(ctx: Context) -> None:
    forbidden = ("Pontoon Beach", "Edwardsville", "Wood River", "killersofas.com")
    for root in (ctx.source / "README.md", ctx.source / "CURRENT_STATE.md", ctx.source / "internal", ctx.source / "packaging"):
        candidates = [root] if root.is_file() else list(root.rglob("*"))
        for path in candidates:
            if not path.is_file() or path.suffix.lower() in {".tar", ".gz", ".ico", ".png"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for token in forbidden:
                if token.lower() in text.lower():
                    raise BuildFailure("", "Privacy audit", f"Studio-owned source contains prohibited private/default reference {token!r}: {path.relative_to(ctx.source)}")


def verify_showcase_overlay_formatting(ctx: Context, app: Path) -> None:
    gofmt = str(Path(ctx.go).with_name("gofmt"))
    files = [str(app / relative) for relative in SHOWCASE_OVERLAY_GO_FILES]
    for path in files:
        need_file(Path(path), f"Showcase overlay Go source {path}", "Showcase overlay formatting")
    output = run(ctx, "Showcase overlay formatting verification", [gofmt, "-l", *files], cwd=app, env=planned_env(ctx), timeout=300)
    bad = [line.strip() for line in output.splitlines() if line.strip() and not line.startswith("$")]
    if bad:
        raise BuildFailure("Showcase overlay formatting verification", "Formatting", "gofmt would change generated Showcase overlay files: " + ", ".join(bad[:20]))


def js_syntax_checks(ctx: Context, app: Path) -> None:
    files = sorted((app / "ui/js").glob("*.js"))
    if not files:
        raise BuildFailure("", "Generated assets", "Dash-Go JavaScript sources are missing")
    def check(path: Path) -> None:
        run(ctx, f"JavaScript syntax {path.name}", [ctx.node, "--check", str(path)], cwd=app, timeout=120)
    with concurrent.futures.ThreadPoolExecutor(max_workers=ctx.plan.static_workers) as pool:
        futures = [pool.submit(check, path) for path in files]
        for future in futures:
            future.result()


def showcase_tour_guard_view_contract(ctx: Context, app: Path) -> None:
    phase_name = "Showcase Tour, guard, and viewport contract"
    js_manifest = json.loads((app / "ui/js/bundle.manifest.json").read_text(encoding="utf-8"))
    app_sources = js_manifest.get("bundles", {}).get("app")
    if not isinstance(app_sources, list):
        raise BuildFailure(phase_name, "Manifest", "staged browser manifest has no app bundle list")
    expected_tail = ["family-board-footer.js", "showcase-tour.js", "showcase-view.js"]
    if app_sources[-len(expected_tail):] != expected_tail:
        raise BuildFailure(phase_name, "Manifest", f"staged app bundle tail must be {expected_tail}, found {app_sources[-len(expected_tail):]}")
    css_manifest = json.loads((app / "ui/css/bundle.manifest.json").read_text(encoding="utf-8"))
    dashboard_sources = css_manifest.get("bundles", {}).get("dashboard")
    if not isinstance(dashboard_sources, list) or dashboard_sources[-1:] != ["dashboard/showcase-studio.css"]:
        raise BuildFailure(phase_name, "Manifest", "staged dashboard CSS must end with dashboard/showcase-studio.css")
    files = {
        "tour": app / "ui/js/showcase-tour.js",
        "view": app / "ui/js/showcase-view.js",
        "style": app / "ui/css/dashboard/showcase-studio.css",
        "mode": app / "cmd/dashboard-control-server/showcase_mode.go",
        "location": app / "ui/js/control-location-lock.js",
        "navigation": app / "ui/js/control-navigation.js",
    }
    for label, path in files.items():
        need_file(path, f"staged Showcase {label} source", phase_name)
    tour = files["tour"].read_text(encoding="utf-8")
    view = files["view"].read_text(encoding="utf-8")
    mode = files["mode"].read_text(encoding="utf-8")
    location = files["location"].read_text(encoding="utf-8")
    navigation = files["navigation"].read_text(encoding="utf-8")
    for token in (
        "clearPrimarySurface", "openOnly", "dashboardListsDockEnable", "dashboardListsDockDisable",
        "Sample Weather Alert — Studio Preview", "showcaseStudioLocationLocked", "Ah ah ah, you didn’t say the magic word.",
        "/api/return-home", "pagehide",
    ):
        if token not in tour:
            raise BuildFailure(phase_name, "Tour contract", f"staged Tour is missing {token!r}")
    for token in (
        "/api/viewport",
        "Clean View",
        "Fit Display",
        "wall-landscape",
        "laptop",
        "wide-tablet",
        "portrait-wall",
        "portrait-tablet",
        "portrait-four-three",
    ):
        if token not in view:
            raise BuildFailure(phase_name, "Viewport contract", f"staged Showcase View is missing {token!r}")
    for retired in ("compact-touch", "compact-portrait"):
        if retired in view:
            raise BuildFailure(
                phase_name,
                "Viewport contract",
                f"staged Showcase View still exposes retired live preset {retired!r}",
            )
    for token in ("studio_location_locked", "studio_system_action_locked", "studio_file_import_locked", "studio_external_integration_locked", "studio_security_locked", "showcaseGeocode"):
        if token not in mode:
            raise BuildFailure(phase_name, "Studio guard", f"staged guard is missing {token!r}")
    runtime_main = (app / "cmd/dashboard-control-server/main.go").read_text(encoding="utf-8")
    for token in (
        "data := dashGoShowcaseDataRoot(dash)",
        "configDir: filepath.Join(data, \"config\")",
        "calDir: filepath.Join(data, \"calendars\")",
        "cacheDir: filepath.Join(data, \"cache\")",
        "logDir: filepath.Join(data, \"logs\")",
        "fontsDir: filepath.Join(data, \"fonts\")",
    ):
        if token not in runtime_main:
            raise BuildFailure(phase_name, "Runtime data-root contract", f"staged Showcase runtime is missing {token!r}")
    for retired in (
        "configDir: filepath.Join(dash, \"config\")",
        "calDir: filepath.Join(dash, \"calendars\")",
        "cacheDir: filepath.Join(dash, \"cache\")",
        "logDir: filepath.Join(dash, \"logs\")",
        "fontsDir: filepath.Join(dash, \"fonts\")",
    ):
        if retired in runtime_main:
            raise BuildFailure(phase_name, "Runtime data-root contract", f"staged Showcase runtime still writes mutable data under its install root: {retired}")
    for token in ("DASHGO_SHOWCASE_DATA_ROOT", "dashGoShowcaseDataRoot"):
        if token not in mode:
            raise BuildFailure(phase_name, "Runtime data-root contract", f"staged Showcase mode overlay is missing {token!r}")
    if "showcaseStudioLocationLocked" not in location:
        raise BuildFailure(phase_name, "Location lock", "staged location editor does not map Studio lock response to its modal")
    summary_start = navigation.find("function bindCtrlSummaryTaps()")
    summary_end = navigation.find("\nasync function loadCtrlSection", summary_start)
    if summary_start < 0 or summary_end < 0:
        raise BuildFailure(phase_name, "Dashboard Control", "staged native-summary contract is missing")
    summary_body = navigation[summary_start:summary_end]
    if "bindTap(" in summary_body or "d.open=!d.open" in summary_body:
        raise BuildFailure(phase_name, "Dashboard Control", "staged Dashboard Control summary still has a competing custom toggle")


def build_host(ctx: Context, target: str, output: Path, *, gui: bool = False) -> None:
    env = {**planned_env(ctx, cross=True), "GOOS": target, "GOARCH": "amd64", "CGO_ENABLED": "0"}
    command = [ctx.go, "build", "-trimpath", "-buildvcs=false"]
    label = f"Build Studio host {target}"
    if gui:
        if target != "windows":
            raise BuildFailure("Build Studio host", "Invocation", "GUI host is only valid for Windows")
        command += ["-ldflags", "-H=windowsgui"]
        label += " GUI"
    elif target == "windows":
        label += " CLI"
    command += ["-o", str(output), "./cmd/dash-go-showcase-studio"]
    run(ctx, label, command, cwd=ctx.source, env=env, timeout=900)


def pe_subsystem(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise BuildFailure("Windows launcher inspection", "Architecture", f"not a PE executable: {path}")
    offset = int.from_bytes(data[0x3C:0x40], "little")
    optional = offset + 24
    if optional + 72 > len(data) or data[offset:offset+4] != b"PE\0\0":
        raise BuildFailure("Windows launcher inspection", "Architecture", f"invalid PE headers: {path}")
    return int.from_bytes(data[optional+68:optional+70], "little")


def build_engine(ctx: Context, app: Path, target: str, output: Path) -> None:
    env = {**planned_env(ctx, cross=True), "GOOS": target, "GOARCH": "amd64", "CGO_ENABLED": "0"}
    run(ctx, f"Build Showcase server {target}", [ctx.go, "build", "-trimpath", "-buildvcs=false", "-o", str(output), "./cmd/dashboard-control-server"], cwd=app, env=env, timeout=1200)


def copy_windows_runtime_payload(staged_app: Path, runtime_app: Path, engine: Path) -> Path:
    if runtime_app.exists():
        shutil.rmtree(runtime_app)
    runtime_app.mkdir(parents=True, exist_ok=True)
    for name in WINDOWS_RUNTIME_ROOT_FILES:
        source = staged_app / name
        if not source.is_file():
            raise BuildFailure("Windows runtime package", "Missing runtime asset", f"required Windows runtime file is missing: {name}")
        shutil.copy2(source, runtime_app / name)
    for name in WINDOWS_RUNTIME_TREES:
        source = staged_app / name
        if not source.is_dir():
            raise BuildFailure("Windows runtime package", "Missing runtime asset", f"required Windows runtime tree is missing: {name}")
        shutil.copytree(source, runtime_app / name, symlinks=False, copy_function=shutil.copy2)
    target_server = runtime_app / "bin" / "dash-go-showcase-server.exe"
    target_server.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(engine, target_server)
    return target_server


def write_windows_as_invoker_manifest(executable: Path) -> Path:
    manifest = executable.with_name(executable.name + ".manifest")
    manifest.write_text(WINDOWS_AS_INVOKER_MANIFEST, encoding="utf-8")
    return manifest


def is_allowed_windows_payload_path(relative: Path) -> bool:
    value = relative.as_posix()
    return value in WINDOWS_STAGE_REQUIRED_FILES or any(value.startswith(prefix) for prefix in WINDOWS_RUNTIME_PREFIXES)


def windows_payload_inventory(root: Path, *, exclude_manifest: bool) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for path in sorted((candidate for candidate in root.rglob("*") if candidate.is_file()), key=lambda candidate: candidate.as_posix()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == WINDOWS_PAYLOAD_MANIFEST:
            continue
        rows.append({"path": relative, "sha256": sha256(path), "sizeBytes": path.stat().st_size})
    return rows


def validate_windows_runtime_payload(runtime_app: Path, phase_name: str) -> None:
    required = {
        *WINDOWS_RUNTIME_ROOT_FILES,
        "bin/dash-go-showcase-server.exe",
        "bin/dash-go-showcase-server.exe.manifest",
    }
    found_files: set[str] = set()
    for path in runtime_app.rglob("*"):
        relative = path.relative_to(runtime_app)
        value = relative.as_posix()
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise BuildFailure(phase_name, "Payload safety", f"Windows runtime payload contains unsupported filesystem entry: {value}")
        if path.is_file():
            found_files.add(value)
            if value not in required and not any(value.startswith(f"{name}/") for name in WINDOWS_RUNTIME_TREES):
                raise BuildFailure(phase_name, "Payload allowlist", f"Windows runtime payload contains unapproved file: {value}")
            if path.suffix.lower() in WINDOWS_DISALLOWED_SUFFIXES:
                raise BuildFailure(phase_name, "Payload allowlist", f"Windows runtime payload contains excluded development or script file: {value}")
    missing = sorted(required - found_files)
    if missing:
        raise BuildFailure(phase_name, "Payload allowlist", "Windows runtime payload is missing required files: " + ", ".join(missing))
    for tree in WINDOWS_RUNTIME_TREES:
        if not any(path.is_file() for path in (runtime_app / tree).rglob("*")):
            raise BuildFailure(phase_name, "Payload allowlist", f"Windows runtime payload tree is empty: {tree}")


def write_windows_payload_manifest(root: Path) -> Path:
    manifest = root / WINDOWS_PAYLOAD_MANIFEST
    write_json(manifest, {
        "schema": 1,
        "payloadLayout": WINDOWS_PAYLOAD_LAYOUT,
        "platform": "windows-amd64",
        "selfExcluded": True,
        "files": windows_payload_inventory(root, exclude_manifest=True),
    })
    return manifest


def validate_windows_stage_payload(root: Path, phase_name: str) -> None:
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        value = relative.as_posix()
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise BuildFailure(phase_name, "Payload safety", f"Windows stage contains unsupported filesystem entry: {value}")
        if path.is_file():
            if not is_allowed_windows_payload_path(relative):
                raise BuildFailure(phase_name, "Payload allowlist", f"Windows stage contains unapproved file: {value}")
            if path.suffix.lower() in WINDOWS_DISALLOWED_SUFFIXES:
                raise BuildFailure(phase_name, "Payload allowlist", f"Windows stage contains excluded development or script file: {value}")
    missing = [value for value in WINDOWS_STAGE_REQUIRED_FILES if not (root / value).is_file()]
    if missing:
        raise BuildFailure(phase_name, "Payload allowlist", "Windows stage is missing required files: " + ", ".join(missing))
    runtime_app = root / "runtime" / "app"
    validate_windows_runtime_payload(runtime_app, phase_name)
    executable_paths = sorted(path.relative_to(root).as_posix() for path in root.rglob("*.exe"))
    expected_executables = ["dash-go-showcase-studio.exe", "runtime/app/bin/dash-go-showcase-server.exe"]
    if executable_paths != expected_executables:
        raise BuildFailure(phase_name, "Payload allowlist", f"Windows stage executables must be exactly {expected_executables}, found {executable_paths}")
    for executable in expected_executables:
        manifest = root / f"{executable}.manifest"
        text = manifest.read_text(encoding="utf-8")
        if 'requestedExecutionLevel level="asInvoker" uiAccess="false"' not in text:
            raise BuildFailure(phase_name, "Windows manifest", f"Windows executable manifest is not explicit asInvoker/uiAccess=false: {manifest.relative_to(root)}")
    metadata = json.loads((root / "STUDIO_RUNTIME.json").read_text(encoding="utf-8"))
    if metadata.get("payloadLayout") != WINDOWS_PAYLOAD_LAYOUT or metadata.get("payloadManifest") != WINDOWS_PAYLOAD_MANIFEST:
        raise BuildFailure(phase_name, "Payload metadata", "STUDIO_RUNTIME.json does not identify the curated Windows payload")
    manifest = json.loads((root / WINDOWS_PAYLOAD_MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or manifest.get("payloadLayout") != WINDOWS_PAYLOAD_LAYOUT or manifest.get("platform") != "windows-amd64" or manifest.get("selfExcluded") is not True:
        raise BuildFailure(phase_name, "Payload manifest", "INSTALLER_CONTENTS.json has an invalid curated Windows payload header")
    expected = windows_payload_inventory(root, exclude_manifest=True)
    if manifest.get("files") != expected:
        raise BuildFailure(phase_name, "Payload manifest", "INSTALLER_CONTENTS.json does not exactly describe the curated Windows stage")


def package_windows_stage(ctx: Context, staged_app: Path, host: Path, engine: Path) -> Path:
    root = ctx.work / "payload" / "windows"
    if root.exists():
        shutil.rmtree(root)
    runtime_app = root / "runtime" / "app"
    target_server = copy_windows_runtime_payload(staged_app, runtime_app, engine)
    target_host = root / "dash-go-showcase-studio.exe"
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(host, target_host)
    write_windows_as_invoker_manifest(target_host)
    write_windows_as_invoker_manifest(target_server)
    windows_icon = ctx.source / "assets" / "branding" / "dash-go-showcase-studio.ico"
    if not windows_icon.is_file() or windows_icon.read_bytes()[:4] != b"\0\0\1\0":
        raise BuildFailure("Windows package", "Branding", "missing or invalid Windows Studio icon")
    icon_target = root / "assets" / "branding" / windows_icon.name
    icon_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(windows_icon, icon_target)
    for name in ("NOTICE.md", "LICENSE", "DASH-GO-THIRD-PARTY-NOTICES.md", "WHAT-STUDIO-DOES-LOCALLY.txt"):
        source = ctx.source / name
        if not source.is_file():
            raise BuildFailure("Windows package", "Documentation", f"required public Windows package document is missing: {name}")
        shutil.copy2(source, root / name)
    write_json(root / "STUDIO_RUNTIME.json", {
        "schema": 1,
        "studioVersion": ctx.version,
        "releasePackageVersion": ctx.release_package_version,
        "dashGoVersion": ctx.dashgo_version,
        "fixtureSchema": ctx.manifest["fixtureSchema"],
        "scenarioCatalog": ctx.manifest["scenarioCatalog"],
        "platform": "windows-amd64",
        "payloadLayout": WINDOWS_PAYLOAD_LAYOUT,
        "payloadManifest": WINDOWS_PAYLOAD_MANIFEST,
        "builtAt": now_utc(),
    })
    write_windows_payload_manifest(root)
    if target_server.read_bytes()[:2] != b"MZ" or target_host.read_bytes()[:2] != b"MZ":
        raise BuildFailure("Windows package", "Architecture inspection", "Windows payload does not contain the required PE executables")
    if pe_subsystem(target_host) != 2:
        raise BuildFailure("Windows launcher inspection", "PE subsystem", "user-facing Studio launcher must use the Windows GUI subsystem")
    validate_windows_stage_payload(root, "Windows package")
    return root


def native_linux_package_root() -> Path:
    base = Path("/tmp").resolve()
    if str(base).startswith("/mnt/") or str(base) == "/mnt":
        raise BuildFailure("Linux package workspace", "Unsafe workspace", f"native package workspace resolves under Windows mount: {base}")
    root = Path(tempfile.mkdtemp(prefix="dash-go-showcase-deb-", dir=str(base))).resolve()
    root.chmod(0o755)
    return root


def normalize_deb_tree_permissions(root: Path, executable: set[Path]) -> None:
    for path in sorted((item for item in root.rglob("*") if item.is_dir()), key=lambda item: len(item.parts)):
        path.chmod(0o755)
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: str(item)):
        path.chmod(0o755 if path.relative_to(root) in executable else 0o644)
    root.chmod(0o755)


def package_linux(ctx: Context, staged_app: Path, host: Path, engine: Path) -> Path:
    native = native_linux_package_root()
    try:
        root = native / "linux-root"
        app_root = root / "usr/lib/dash-go-showcase-studio"
        runtime_app = app_root / "runtime/app"
        copy_tree_clean(staged_app, runtime_app)
        remove_mutable_runtime_data(runtime_app, "Linux runtime package")
        check_payload_tree(runtime_app, "Linux runtime package")
        target_server = runtime_app / "bin/dash-go-showcase-server"
        target_server.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(engine, target_server)
        shutil.copy2(host, app_root / "dash-go-showcase-studio")
        for name in ("NOTICE.md", "LICENSE", "DASH-GO-THIRD-PARTY-NOTICES.md"):
            shutil.copy2(ctx.source / name, app_root / name)
        write_json(app_root / "STUDIO_RUNTIME.json", {"schema": 1, "studioVersion": ctx.version, "releasePackageVersion": ctx.release_package_version, "dashGoVersion": ctx.dashgo_version, "fixtureSchema": ctx.manifest["fixtureSchema"], "scenarioCatalog": ctx.manifest["scenarioCatalog"], "platform": "linux-amd64", "builtAt": now_utc()})
        bin_dir = root / "usr/bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / "dash-go-showcase-studio").write_text("#!/bin/sh\nexec /usr/lib/dash-go-showcase-studio/dash-go-showcase-studio \"$@\"\n", encoding="utf-8")
        shutil.copy2(ctx.source / "packaging/linux/dash-go-showcase-studio-uninstall", bin_dir / "dash-go-showcase-studio-uninstall")
        desktop = root / "usr/share/applications/dash-go-showcase-studio.desktop"
        desktop.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ctx.source / "packaging/linux/dash-go-showcase-studio.desktop", desktop)

        linux_icons = ctx.source / "assets" / "branding" / "linux" / "hicolor"
        if not linux_icons.is_dir():
            raise BuildFailure("Linux package", "Branding", "missing Linux Studio hicolor icon tree")
        shutil.copytree(linux_icons, root / "usr/share/icons/hicolor", dirs_exist_ok=True, copy_function=shutil.copy2)
        packaged_svg = root / "usr/share/icons/hicolor/scalable/apps/dash-go-showcase-studio.svg"
        packaged_png = root / "usr/share/icons/hicolor/48x48/apps/dash-go-showcase-studio.png"
        if not packaged_svg.is_file() or not packaged_png.is_file():
            raise BuildFailure("Linux package", "Branding", "Linux Studio icon files were not staged")
        docs = root / "usr/share/doc/dash-go-showcase-studio"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "README.Debian").write_text("Full removal: dash-go-showcase-studio-uninstall --purge\n", encoding="utf-8")
        control = root / "DEBIAN/control"
        control.parent.mkdir(parents=True, exist_ok=True)
        control.write_text("Package: dash-go-showcase-studio\n" f"Version: {ctx.release_package_version}\n" "Section: misc\nPriority: optional\nArchitecture: amd64\n" "Maintainer: DashDashGoApp <opensource@dash-go.invalid>\n" "Description: Dash-Go Showcase Studio\n A local, disposable Dash-Go product showcase with generic fixtures.\n", encoding="utf-8")
        executable = {Path("usr/lib/dash-go-showcase-studio/dash-go-showcase-studio"), Path("usr/lib/dash-go-showcase-studio/runtime/app/bin/dash-go-showcase-server"), Path("usr/bin/dash-go-showcase-studio"), Path("usr/bin/dash-go-showcase-studio-uninstall")}
        normalize_deb_tree_permissions(root, executable)
        if stat.S_IMODE((root / "DEBIAN").stat().st_mode) != 0o755:
            raise BuildFailure("Build Linux deb", "Package permissions", "DEBIAN control directory must be 0755")
        deb = native / f"Dash-Go_Showcase_Studio_{ctx.release_package_version}_Linux_amd64.deb"
        run(ctx, "Build Linux deb", ["dpkg-deb", "--build", "--root-owner-group", str(root), str(deb)], cwd=native, timeout=600)
        run(ctx, "Inspect Linux deb metadata", ["dpkg-deb", "--info", str(deb)], cwd=native, timeout=120)
        contents = run(ctx, "Inspect Linux deb contents", ["dpkg-deb", "--contents", str(deb)], cwd=native, timeout=120)
        if "dash-go-showcase-studio-uninstall" not in contents:
            raise BuildFailure("Build Linux deb", "Package contents", "Linux package omitted full-removal wrapper")
        for icon in ("usr/share/icons/hicolor/48x48/apps/dash-go-showcase-studio.png", "usr/share/icons/hicolor/scalable/apps/dash-go-showcase-studio.svg"):
            if icon not in contents:
                raise BuildFailure("Build Linux deb", "Package contents", f"Linux package omitted required Studio icon: {icon}")
        output = ctx.work / "artifacts" / deb.name
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(deb, output)
        if sha256(deb) != sha256(output):
            raise BuildFailure("Build Linux deb", "Integrity", "Linux package SHA-256 changed during native-workspace export")
        return output
    finally:
        shutil.rmtree(native, ignore_errors=True)


def linux_package_smoke(ctx: Context, deb: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="dash-go-showcase-deb-smoke-", dir="/tmp") as raw:
        root = Path(raw)
        result = subprocess.run(["dpkg-deb", "--fsys-tarfile", str(deb)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode:
            raise BuildFailure("Linux package full-removal smoke", "Package extraction", safe_text(result.stderr.decode("utf-8", "replace"), 2000))
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as tar:
            for member in tar.getmembers():
                name = member.name.replace("\\", "/")
                if name.startswith("/") or name.startswith("../") or "/../" in name or member.issym() or member.islnk():
                    raise BuildFailure("Linux package full-removal smoke", "Package extraction", f"unsafe Debian payload member: {member.name}")
            tar.extractall(root)
        host = root / "usr/lib/dash-go-showcase-studio/dash-go-showcase-studio"
        wrapper = root / "usr/bin/dash-go-showcase-studio-uninstall"
        need_file(host, "extracted Linux Studio host", "Linux package full-removal smoke")
        need_file(wrapper, "extracted Linux full-removal wrapper", "Linux package full-removal smoke")
        state = root / "private-state"
        run(ctx, "Linux package self-test", [str(host), "--action", "self-test", "--scenario", str(ctx.manifest["defaultScenario"]), "--state-root", str(state)], cwd=host.parent, timeout=180)
        if not (state / "logs").is_dir() or not (state / "workspace").is_dir():
            raise BuildFailure("Linux package full-removal smoke", "State setup", "Linux package self-test did not create the required private state")
        run(ctx, "Linux package state purge", [str(host), "--action", "purge", "--state-root", str(state), "--confirm-purge", "PURGE SHOWCASE STUDIO"], cwd=host.parent, timeout=120)
        if state.exists():
            raise BuildFailure("Linux package full-removal smoke", "State cleanup", f"Linux package state purge left private state behind: {state}")


def write_failure(ctx: Context, failure: BuildFailure | Exception) -> None:
    phase_name = failure.phase if isinstance(failure, BuildFailure) else "Unhandled builder error"
    kind = failure.kind if isinstance(failure, BuildFailure) else "Unhandled exception"
    log = failure.log if isinstance(failure, BuildFailure) else None
    exit_code = failure.exit_code if isinstance(failure, BuildFailure) else None
    message = safe_text(str(failure), 5000)
    payload = {"schema": 1, "result": "FAIL", "buildID": ctx.build_id, "studioVersion": ctx.version, "releasePackageVersion": ctx.release_package_version, "dashGoBaseline": ctx.dashgo_version, "targets": list(ctx.targets), "failedPhase": phase_name, "failureKind": kind, "exitCode": exit_code, "message": message, "events": str(ctx.events_path), "log": str(log) if log else "", "diagnostics": str(ctx.work), "performance": ctx.plan.as_json(), "timings": ctx.timings, "finishedAt": now_utc()}
    write_json(ctx.work / "failure.json", payload)
    write_json(ctx.work / "timing.json", {
        "schema": 1,
        "performance": ctx.plan.as_json(),
        "phases": ctx.timings,
        "totalDurationMs": round((time.monotonic() - ctx.started) * 1000),
        "result": "FAIL",
    })
    report = ["DASH-GO SHOWCASE STUDIO PACKAGE CANDIDATE FAILURE REPORT", "Schema: 1", "Result: FAIL", f"Build ID: {ctx.build_id}", f"Studio version: {ctx.version}", f"Release package version: {ctx.release_package_version}", f"Dash-Go baseline: {ctx.dashgo_version}", f"Targets: {', '.join(ctx.targets)}", f"Performance profile: {ctx.plan.effective}", f"Failed phase: {phase_name}", f"Failure kind: {kind}", f"Exit code: {exit_code if exit_code is not None else 'n/a'}", "", "Observed:", message, "", "Evidence:", f"- events: {ctx.events_path}"]
    if log:
        report.append(f"- detailed log: {log}")
    report += [f"- diagnostics: {ctx.work}", "", "Next safe action:", "- Do not rerun with a force or bypass switch.", "- Correct the named source, toolchain, fixture, package, or installer issue.", "- Rebuild in a new transaction; no output artifact was published by this run."]
    (ctx.work / "failure-report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--kit", type=Path, default=None, help="Optional Builder provenance root; defaults to --source for CI.")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--go", required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--targets", default="windows", type=parse_targets)
    parser.add_argument("--performance", choices=("auto", "safe", "desktop", "max"), default="auto")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    kit = (args.kit if args.kit is not None else source).resolve()
    work = args.work.resolve()
    prepare_work_directory(work)
    try:
        manifest = json.loads((source / "studio.manifest.json").read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"BUILD INVOCATION ERROR: cannot read {source / 'studio.manifest.json'}: {exc}")
    plan = resolve_plan(args.performance)
    ctx = Context(source=source, kit=kit, work=work, go=args.go, node=args.node, targets=args.targets, trace=args.trace, manifest=manifest, events_path=work / "events.jsonl", logs=work / "logs", started=time.monotonic(), build_id=work.name, plan=plan)
    ctx.logs.mkdir(parents=True, exist_ok=True)
    write_json(work / "performance.json", plan.as_json())
    write_json(work / "run.json", {"schema": 1, "buildID": ctx.build_id, "startedAt": now_utc(), "source": str(source), "kit": str(kit), "targets": list(ctx.targets), "performance": plan.as_json(), "status": "running"})
    print(f"Performance profile: requested={plan.requested}, effective={plan.effective}; CPUs={plan.visible_cpus}, RAM={plan.visible_memory_mib} MiB; cross workers={plan.cross_workers}")
    try:
        with phase(ctx, 1, "Validate source contract and manifest"):
            validate_manifest(ctx)
            run(ctx, "Studio source validation", [sys.executable, "tools/validate_studio_source.py", "--root", str(source)], cwd=source, timeout=120)
            run(ctx, "Studio branding asset validation", [sys.executable, "tools/validate_studio_branding.py", "--root", str(source)], cwd=source, timeout=120)
            source_privacy_sanity(ctx)
        with phase(ctx, 2, "Verify tools and pinned Go compiler"):
            need_file(Path(ctx.go), "selected Go compiler", "")
            if "go1.26.4" not in run(ctx, "Go compiler verification", [ctx.go, "version"], cwd=source, timeout=120):
                raise BuildFailure("", "Toolchain", "selected Go compiler is not 1.26.4")
            run(ctx, "Node verification", [ctx.node, "--version"], cwd=source, timeout=120)
            if "linux" in ctx.targets:
                run(ctx, "dpkg-deb verification", ["dpkg-deb", "--version"], cwd=source, timeout=120)
        with phase(ctx, 3, "Extract, patch, and format-check pinned Dash-Go runtime"):
            archive = source / str(ctx.manifest["dashGoSourceArchive"])
            if sha256(archive) != str(ctx.manifest["dashGoSourceSha256"]):
                raise BuildFailure("", "Input integrity", "pinned Dash-Go source archive SHA-256 mismatch")
            extract = work / "staging"
            safe_extract(archive, extract, ctx.dashgo_root, "Extract Dash-Go source")
            app = extract / ctx.dashgo_root / "app"
            need_file(app / "go.mod", "Dash-Go module", "")
            run(ctx, "Apply Showcase overlay", [sys.executable, str(source / "tools/patch_dashgo_engine.py"), "--app", str(app)], cwd=source, timeout=120)
            verify_showcase_overlay_formatting(ctx, app)
        with phase(ctx, 4, "Generate and validate browser assets"):
            run(ctx, "Generate Dash-Go browser assets", [sys.executable, str(source / "tools/generate_dashgo_assets.py"), "--app", str(app)], cwd=source, timeout=240)
            run(ctx, "Verify Dash-Go browser assets", [sys.executable, str(source / "tools/generate_dashgo_assets.py"), "--app", str(app), "--verify"], cwd=source, timeout=240)
            js_syntax_checks(ctx, app)
            showcase_tour_guard_view_contract(ctx, app)
        with phase(ctx, 5, "Test Studio host and fixture contracts"):
            run(ctx, "Studio host tests", [ctx.go, "test", "-count=1", "-p", str(ctx.plan.test_p), "./..."], cwd=source, env=go_test_network_env(ctx), timeout=900)
        with phase(ctx, 6, "Validate patched Dash-Go runtime"):
            run(ctx, "Dash-Go module verification", [ctx.go, "mod", "verify"], cwd=app, timeout=600)
            gofmt = str(Path(ctx.go).with_name("gofmt"))
            files = [str(path) for path in sorted(app.rglob("*.go")) if "vendor" not in path.parts]
            formatted = run(ctx, "Dash-Go formatting verification", [gofmt, "-l", *files], cwd=app, env=planned_env(ctx), timeout=600)
            bad = [line.strip() for line in formatted.splitlines() if line.strip() and not line.startswith("$")]
            if bad:
                raise BuildFailure("Dash-Go formatting verification", "Formatting", "gofmt would change staged Go files: " + ", ".join(bad[:20]))
            run(ctx, "Dash-Go vet", [ctx.go, "vet", "-p", str(ctx.plan.test_p), "./..."], cwd=app, env=planned_env(ctx), timeout=1500)
            print("   Go tests: outbound HTTP(S) blocked by a loopback proxy sink; localhost remains available")
            run(ctx, "Dash-Go tests", [ctx.go, "test", "-count=1", "-p", str(ctx.plan.test_p), "./..."], cwd=app, env=go_test_network_env(ctx), timeout=2400)
            run(ctx, "Dash-Go race tests", [ctx.go, "test", "-race", "-count=1", "-p", str(min(ctx.plan.test_p, 16)), "./..."], cwd=app, env=go_test_network_env(ctx), timeout=3000)
        with phase(ctx, 7, "Build target runtimes in bounded parallel"):
            binaries = work / "binaries"
            built_map: dict[str, dict[str, Path]] = {}
            jobs: list[tuple[str, str, Path]] = []
            for target in ctx.targets:
                suffix = ".exe" if target == "windows" else ""
                directory = binaries / target
                directory.mkdir(parents=True, exist_ok=True)
                built_map[target] = {
                    "engine": directory / f"dash-go-showcase-server{suffix}",
                    "host": directory / f"dash-go-showcase-studio{suffix}",
                }
                jobs.extend(((target, "engine", built_map[target]["engine"]), (target, "host", built_map[target]["host"])))
            def build_unit(item: tuple[str, str, Path]) -> None:
                target, kind, output = item
                if kind == "engine":
                    build_engine(ctx, app, target, output)
                else:
                    build_host(ctx, target, output, gui=(target == "windows"))
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(ctx.plan.cross_workers, len(jobs))) as pool:
                for future in [pool.submit(build_unit, item) for item in jobs]:
                    future.result()
            linux_entry = built_map.get("linux")
            linux_engine = linux_entry["engine"] if linux_entry else None
            linux_host = linux_entry["host"] if linux_entry else None
            if linux_engine:
                run(
                    ctx,
                    "Verify generated assets with Linux runtime",
                    [str(linux_engine), "--verify-generated-assets"],
                    cwd=app,
                    env={
                        **planned_env(ctx),
                        "DASHGO_SHOWCASE": "1",
                        "DASHGO_HOME": str(work / "runtime-home"),
                        "DASHGO_SHOWCASE_DATA_ROOT": str(work / "runtime-data"),
                    },
                    timeout=600,
                )
        with phase(ctx, 8, "Assemble target packages"):
            futures: dict[str, concurrent.futures.Future[Path]] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(2, ctx.plan.cross_workers)) as pool:
                if "windows" in ctx.targets:
                    windows_entry = built_map["windows"]
                    futures["windows"] = pool.submit(package_windows_stage, ctx, app, windows_entry["host"], windows_entry["engine"])
                if "linux" in ctx.targets:
                    linux_entry = built_map["linux"]
                    futures["linux"] = pool.submit(package_linux, ctx, app, linux_entry["host"], linux_entry["engine"])
                windows_stage = futures["windows"].result() if "windows" in futures else None
                linux_deb = futures["linux"].result() if "linux" in futures else None
        with phase(ctx, 9, "Run Showcase package self-tests and removal smoke"):
            if linux_deb:
                linux_package_smoke(ctx, linux_deb)
            if linux_host and linux_engine:
                root = work / "smoke/linux-runtime"
                copy_tree_clean(app, root / "runtime/app")
                remove_mutable_runtime_data(root / "runtime/app", "Runtime self-test")
                target = root / "runtime/app/bin/dash-go-showcase-server"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(linux_engine, target)
                target.chmod(0o755)
                shutil.copy2(linux_host, root / "dash-go-showcase-studio")
                (root / "dash-go-showcase-studio").chmod(0o755)
                run(ctx, "Showcase runtime self-test", [str(root / "dash-go-showcase-studio"), "--action", "self-test", "--scenario", str(ctx.manifest["defaultScenario"]), "--state-root", str(work / "smoke/runtime-state")], cwd=root, timeout=180)
        write_json(work / "timing.json", {"schema": 1, "performance": plan.as_json(), "phases": ctx.timings, "totalDurationMs": round((time.monotonic() - ctx.started) * 1000)})
        summary = {"schema": 1, "result": "PASS", "buildID": ctx.build_id, "studioVersion": ctx.version, "releasePackageVersion": ctx.release_package_version, "dashGoVersion": ctx.dashgo_version, "targets": list(ctx.targets), "windowsStage": str(windows_stage) if windows_stage else "", "linuxDeb": str(linux_deb) if linux_deb else "", "events": str(ctx.events_path), "work": str(ctx.work), "performance": plan.as_json(), "timing": str(work / "timing.json"), "finishedAt": now_utc()}
        write_json(work / "summary.json", summary)
        run_state = json.loads((work / "run.json").read_text(encoding="utf-8"))
        run_state.update({"status": "passed", "finishedAt": now_utc()})
        write_json(work / "run.json", run_state)
        print("== BUILD STAGING PASS")
        return 0
    except Exception as exc:
        failure = exc if isinstance(exc, BuildFailure) else BuildFailure("Unhandled builder error", "Unhandled exception", "".join(traceback.format_exception_only(type(exc), exc)).strip())
        write_failure(ctx, failure)
        state = json.loads((work / "run.json").read_text(encoding="utf-8"))
        state.update({"status": "failed", "finishedAt": now_utc()})
        write_json(work / "run.json", state)
        print((work / "failure-report.txt").read_text(encoding="utf-8"), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
