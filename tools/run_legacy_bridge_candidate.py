#!/usr/bin/env python3
"""Dispatch and prove the legacy bridge candidate on GitHub Actions.

The script is intentionally a thin orchestrator.  It validates the immutable
Dash-Go release identity, then lets the checked-in Stage and Windows workflows
perform their normal fail-closed build, runtime, installer, and uninstall tests.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPECTED_STUDIO_REPOSITORY = "DashDashGoApp/Dash-Go-Showcase-Studio"
DASHGO_REPOSITORY = "DashDashGoApp/Dash-Go"
PROFILE_ID = "legacy-bridge-v1"
STAGE_WORKFLOW = "studio-stage-candidate.yml"
WINDOWS_WORKFLOW = "studio-windows-package-candidate.yml"
VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_RE = re.compile(r"^[0-9]+$")


class CandidateError(RuntimeError):
    """A fail-closed candidate-proof error with a clear operator message."""


@dataclass(frozen=True)
class BridgePolicy:
    profile_id: str
    minimum_version: str
    maximum_version_exclusive: str


@dataclass(frozen=True)
class DashGoRelease:
    version: str
    tag: str
    source_sha256: str
    tag_commit: str


@dataclass(frozen=True)
class WorkflowRun:
    run_id: str
    status: str
    conclusion: str | None


class GitHubClient:
    def __init__(self, api_url: str, token: str) -> None:
        if not api_url.startswith("https://"):
            raise CandidateError("GITHUB_API_URL must use HTTPS")
        if not token.strip():
            raise CandidateError("GITHUB_TOKEN is required for legacy candidate dispatch")
        self.api_url = api_url.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any | None]:
        if not path.startswith("/"):
            raise CandidateError("GitHub API paths must begin with /")
        body = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Dash-Go-Showcase-Studio-Legacy-Bridge-Gate",
        }
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.api_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                if not raw:
                    return response.status, None
                try:
                    return response.status, json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise CandidateError(f"GitHub API {method} {path} returned invalid JSON") from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise CandidateError(f"GitHub API {method} {path} failed with HTTP {exc.code}: {detail[:500]}") from exc
        except urllib.error.URLError as exc:
            raise CandidateError(f"GitHub API {method} {path} could not be reached: {exc.reason}") from exc


def parse_stable_version(value: str, label: str) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise CandidateError(f"{label} must use stable X.Y.Z form")
    return int(match.group("major")), int(match.group("minor")), int(match.group("patch"))


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CandidateError(f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CandidateError(f"{label} must be a JSON object")
    return payload


def load_bridge_policy(root: Path) -> BridgePolicy:
    matrix = read_json(root / "tools" / "dashgo_compatibility.json", "compatibility matrix")
    profiles = matrix.get("profiles")
    if matrix.get("schema") != 2 or not isinstance(profiles, list):
        raise CandidateError("compatibility matrix must use schema 2 with a profiles array")
    matches = [item for item in profiles if isinstance(item, dict) and item.get("id") == PROFILE_ID]
    if len(matches) != 1:
        raise CandidateError("compatibility matrix must contain exactly one legacy-bridge-v1 profile")
    policy = matches[0].get("sourcePolicy")
    if not isinstance(policy, dict) or policy.get("selection") != "adapter-probe":
        raise CandidateError("legacy bridge profile must use the adapter-probe source policy")
    minimum = policy.get("minimumVersion")
    maximum = policy.get("maximumVersionExclusive")
    if not isinstance(minimum, str) or not isinstance(maximum, str):
        raise CandidateError("legacy bridge profile must declare a stable source-policy version window")
    if parse_stable_version(minimum, "minimumVersion") >= parse_stable_version(maximum, "maximumVersionExclusive"):
        raise CandidateError("legacy bridge source-policy version window is empty")
    checks = matches[0].get("requiredCandidateChecks")
    if not isinstance(checks, list):
        raise CandidateError("legacy bridge profile must declare required candidate checks")
    for required in (
        "staged-linux-package-and-runtime-self-test",
        "windows-installer-install-self-test-and-uninstall-smoke",
    ):
        if required not in checks:
            raise CandidateError(f"legacy bridge profile is missing required candidate check: {required}")
    return BridgePolicy(PROFILE_ID, minimum, maximum)


def assert_version_in_window(version: str, policy: BridgePolicy) -> None:
    actual = parse_stable_version(version, "Dash-Go release version")
    minimum = parse_stable_version(policy.minimum_version, "minimumVersion")
    maximum = parse_stable_version(policy.maximum_version_exclusive, "maximumVersionExclusive")
    if actual < minimum or actual >= maximum:
        raise CandidateError(
            f"Dash-Go {version} is outside reviewed legacy bridge window "
            f"{policy.minimum_version} <= version < {policy.maximum_version_exclusive}"
        )


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CandidateError(f"GitHub response is missing object: {label}")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CandidateError(f"GitHub response is missing string: {label}")
    return value.strip()


def require_run_id(value: Any, label: str) -> str:
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise CandidateError(f"GitHub response is missing numeric workflow run id: {label}")
    return value


def resolve_tag_commit(client: GitHubClient, tag: str) -> str:
    _, reference = client.request("GET", f"/repos/{DASHGO_REPOSITORY}/git/ref/tags/{urllib.parse.quote(tag, safe='')}")
    obj = require_object(require_object(reference, "tag reference").get("object"), "tag reference.object")
    while obj.get("type") == "tag":
        object_sha = require_string(obj.get("sha"), "annotated tag object SHA")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", object_sha):
            raise CandidateError("annotated Dash-Go tag has an invalid object SHA")
        _, tag_object = client.request("GET", f"/repos/{DASHGO_REPOSITORY}/git/tags/{object_sha}")
        obj = require_object(require_object(tag_object, "annotated tag").get("object"), "annotated tag.object")
    commit = require_string(obj.get("sha"), "tag commit SHA")
    if obj.get("type") != "commit" or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise CandidateError(f"Dash-Go tag {tag} does not resolve to a commit")
    return commit.lower()


def load_dashgo_release(client: GitHubClient, version: str, policy: BridgePolicy) -> DashGoRelease:
    assert_version_in_window(version, policy)
    tag = f"v{version}"
    _, release_payload = client.request("GET", f"/repos/{DASHGO_REPOSITORY}/releases/tags/{urllib.parse.quote(tag, safe='')}")
    release = require_object(release_payload, "Dash-Go release")
    if release.get("tag_name") != tag or release.get("draft") or release.get("prerelease") or release.get("immutable") is not True:
        raise CandidateError(f"Dash-Go release {tag} is not a published immutable stable release")
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise CandidateError(f"Dash-Go release {tag} has no assets list")
    source_name = f"Dash-Go_{version}_source.tar.gz"
    matches = [item for item in assets if isinstance(item, dict) and item.get("name") == source_name]
    if len(matches) != 1:
        raise CandidateError(f"Dash-Go release {tag} must contain exactly one {source_name} asset")
    digest = require_string(matches[0].get("digest"), f"{source_name} digest").lower()
    if not digest.startswith("sha256:") or not SHA256_RE.fullmatch(digest[7:]):
        raise CandidateError(f"Dash-Go release {tag} source asset must expose a SHA-256 digest")
    return DashGoRelease(version, tag, digest[7:], resolve_tag_commit(client, tag))


def run_url(repository: str, run_id: str) -> str:
    if not RUN_ID_RE.fullmatch(run_id):
        raise CandidateError(f"workflow run id is invalid: {run_id}")
    return f"https://github.com/{repository}/actions/runs/{run_id}"


def workflow_path_matches(run: dict[str, Any], workflow: str) -> bool:
    expected = f".github/workflows/{workflow}"
    path = run.get("path")
    return isinstance(path, str) and (path == expected or path.startswith(expected + "@"))


def discover_dispatched_run(
    client: GitHubClient,
    repository: str,
    workflow: str,
    branch: str,
    head_sha: str,
    title_needle: str,
) -> WorkflowRun | None:
    query = urllib.parse.urlencode({"branch": branch, "event": "workflow_dispatch", "per_page": "100"})
    _, payload = client.request("GET", f"/repos/{repository}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/runs?{query}")
    response = require_object(payload, "workflow-run list")
    runs = response.get("workflow_runs")
    if not isinstance(runs, list):
        raise CandidateError(f"GitHub did not return workflow_runs for {workflow}")
    matches: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        if run.get("head_sha") != head_sha or run.get("event") != "workflow_dispatch":
            continue
        if not workflow_path_matches(run, workflow):
            continue
        title = run.get("display_title")
        if not isinstance(title, str) or title_needle not in title:
            continue
        matches.append(run)
    if len(matches) > 1:
        raise CandidateError(f"found multiple {workflow} runs for dispatch nonce {title_needle}")
    if not matches:
        return None
    run_id = require_run_id(matches[0].get("id"), f"{workflow} run id")
    status = require_string(matches[0].get("status"), f"{workflow} run status")
    conclusion = matches[0].get("conclusion")
    if conclusion is not None and not isinstance(conclusion, str):
        raise CandidateError(f"{workflow} run conclusion is malformed")
    return WorkflowRun(run_id, status, conclusion)


def read_run(client: GitHubClient, repository: str, run_id: str) -> WorkflowRun:
    _, payload = client.request("GET", f"/repos/{repository}/actions/runs/{run_id}")
    run = require_object(payload, "workflow run")
    returned_id = require_run_id(run.get("id"), "workflow run id")
    if returned_id != run_id:
        raise CandidateError("workflow run lookup returned a different run id")
    status = require_string(run.get("status"), "workflow run status")
    conclusion = run.get("conclusion")
    if conclusion is not None and not isinstance(conclusion, str):
        raise CandidateError("workflow run conclusion is malformed")
    return WorkflowRun(returned_id, status, conclusion)


def wait_for_success(
    client: GitHubClient,
    repository: str,
    workflow: str,
    branch: str,
    head_sha: str,
    title_needle: str,
    timeout_seconds: int,
    poll_seconds: int,
) -> WorkflowRun:
    deadline = time.monotonic() + timeout_seconds
    discovered: WorkflowRun | None = None
    while time.monotonic() < deadline:
        if discovered is None:
            discovered = discover_dispatched_run(client, repository, workflow, branch, head_sha, title_needle)
            if discovered is None:
                time.sleep(poll_seconds)
                continue
            print(f"Found {workflow}: {run_url(repository, discovered.run_id)}", flush=True)
        current = read_run(client, repository, discovered.run_id)
        if current.status == "completed":
            if current.conclusion == "success":
                return current
            raise CandidateError(
                f"{workflow} did not succeed (conclusion: {current.conclusion or 'none'}). "
                f"Inspect {run_url(repository, current.run_id)}"
            )
        time.sleep(poll_seconds)
    raise CandidateError(f"timed out waiting for {workflow} dispatch nonce {title_needle}")


def dispatch_workflow(client: GitHubClient, repository: str, workflow: str, ref: str, inputs: dict[str, str]) -> None:
    if not ref or ref.startswith("refs/") or "\n" in ref:
        raise CandidateError("Studio branch name is unsafe for workflow dispatch")
    status, _ = client.request(
        "POST",
        f"/repos/{repository}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/dispatches",
        {"ref": ref, "inputs": inputs},
    )
    if status != 204:
        raise CandidateError(f"workflow dispatch for {workflow} returned HTTP {status}, expected 204")


def write_summary(lines: list[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if path:
        Path(path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise CandidateError(f"{name} is required")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=13800)
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    if args.timeout_seconds < 60 or args.poll_seconds < 3 or args.poll_seconds > 60:
        raise CandidateError("timeout and poll interval are outside safe bounds")

    root = args.root.resolve()
    policy = load_bridge_policy(root)
    repository = environment("GITHUB_REPOSITORY")
    if repository != EXPECTED_STUDIO_REPOSITORY:
        raise CandidateError(f"legacy bridge candidate may run only in {EXPECTED_STUDIO_REPOSITORY}")
    branch = environment("STUDIO_BRANCH")
    head_sha = environment("STUDIO_HEAD_SHA").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise CandidateError("STUDIO_HEAD_SHA must be a lowercase 40-character commit SHA")
    token = os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")
    client = GitHubClient(os.environ.get("GITHUB_API_URL", "https://api.github.com"), token)

    release = load_dashgo_release(client, policy.minimum_version, policy)
    deadline = time.monotonic() + args.timeout_seconds

    def remaining_seconds() -> int:
        remaining = int(deadline - time.monotonic())
        if remaining < 60:
            raise CandidateError("legacy bridge candidate proof exceeded its overall time budget")
        return remaining

    nonce = f"legacy-bridge-{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}-{head_sha[:12]}"
    print("== Legacy bridge automatic candidate proof", flush=True)
    print(f"Studio commit:   {head_sha}", flush=True)
    print(f"Bridge window:   {policy.minimum_version} <= version < {policy.maximum_version_exclusive}", flush=True)
    print(f"Dash-Go release: {release.tag}", flush=True)
    print(f"Dash-Go SHA-256: {release.source_sha256}", flush=True)
    print(f"Dispatch nonce:  {nonce}", flush=True)

    dispatch_workflow(
        client,
        repository,
        STAGE_WORKFLOW,
        branch,
        {
            "candidate_origin": "dashgo-stable-release",
            "dashgo_release_tag": release.tag,
            "dashgo_version": release.version,
            "dashgo_source_sha256": release.source_sha256,
            "dashgo_tag_commit": release.tag_commit,
            "dispatch_nonce": nonce,
            "release_package_version": release.version,
        },
    )
    stage = wait_for_success(
        client, repository, STAGE_WORKFLOW, branch, head_sha, nonce, remaining_seconds(), args.poll_seconds
    )
    dispatch_workflow(
        client,
        repository,
        WINDOWS_WORKFLOW,
        branch,
        {"stage_run_id": stage.run_id},
    )
    windows = wait_for_success(
        client,
        repository,
        WINDOWS_WORKFLOW,
        branch,
        head_sha,
        stage.run_id,
        remaining_seconds(),
        args.poll_seconds,
    )

    stage_url = run_url(repository, stage.run_id)
    windows_url = run_url(repository, windows.run_id)
    lines = [
        "## Legacy bridge candidate proof passed",
        "",
        f"- Studio commit: `{head_sha}`",
        f"- Bridge window: `{policy.minimum_version} <= version < {policy.maximum_version_exclusive}`",
        f"- Dash-Go source: `{release.tag}` / `{release.source_sha256}`",
        f"- Stage Candidate: {stage_url}",
        f"- Windows installer install/uninstall smoke: {windows_url}",
    ]
    write_summary(lines)
    write_output("stage_run_id", stage.run_id)
    write_output("stage_url", stage_url)
    write_output("windows_run_id", windows.run_id)
    write_output("windows_url", windows_url)
    print(f"PASS: Stage Candidate: {stage_url}", flush=True)
    print(f"PASS: Windows smoke:   {windows_url}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CandidateError as exc:
        print(f"LEGACY BRIDGE CANDIDATE ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
