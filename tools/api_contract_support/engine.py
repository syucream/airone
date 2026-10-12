"""Pinned oasdiff execution and explicit, checksum-verified installation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from .common import ContractError, run_command

PINNED_VERSION = "1.33.0"
FIXED_CONFIG = b"{}\n"
ENGINE_FLAGS = ["--format", "json", "--allow-external-refs=false"]
ASSET_SHA256: dict[tuple[str, str], str] = {
    ("darwin", "all"): "2a479337c15afdcbf0b1e89c0b4d0cf0176472dbc11483358fed1f831d1e46c5",
    ("linux", "amd64"): "43a4e328e2d13ba1552d760aa68d2485c75c5621f309f6ff64ae895188345247",
    ("linux", "arm64"): "4ae3c362d6074d919aada2dea82d0ee84366591600384455d0bdc658ddf8f7ae",
}


def resolve_engine(repo: Path, override: str | None = None) -> Path:
    """Find an executable without implicitly downloading software."""
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_file():
            found = shutil.which(override)
            if found:
                candidate = Path(found)
        candidates = [candidate]
    else:
        candidates = [repo / ".cache/api-contract/bin/oasdiff"]
        found = shutil.which("oasdiff")
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise ContractError(
        "oasdiff executable not found; run "
        "uv run --locked python tools/api_contract.py install or pass --oasdiff"
    )


def install_engine(destination: Path, timeout: int = 120) -> Path:
    """Install only the executable from a release archive with a pinned digest."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    machine = {"x86_64": "amd64", "aarch64": "arm64"}.get(machine, machine)
    if system == "darwin" and machine in {"amd64", "arm64"}:
        machine = "all"
    digest = ASSET_SHA256.get((system, machine))
    if digest is None:
        raise ContractError(f"Unsupported oasdiff installation platform: {system}/{machine}")
    asset = f"oasdiff_{PINNED_VERSION}_{system}_{machine}.tar.gz"
    url = f"https://github.com/oasdiff/oasdiff/releases/download/v{PINNED_VERSION}/{asset}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=destination.parent) as scratch:
            archive_path = Path(scratch) / "release.tar.gz"
            with urllib.request.urlopen(url, timeout=timeout) as response:
                with archive_path.open("wb") as archive:
                    shutil.copyfileobj(response, archive)
            if hashlib.sha256(archive_path.read_bytes()).hexdigest() != digest:
                raise ContractError("oasdiff release archive checksum mismatch")
            with tarfile.open(archive_path, "r:gz") as archive:
                members = archive.getmembers()
                for member in members:
                    path = Path(member.name)
                    if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                        raise ContractError("Unsafe member in oasdiff release archive")
                executables = [member for member in members if member.name == "oasdiff"]
                if len(executables) != 1 or not executables[0].isfile():
                    raise ContractError("oasdiff executable missing from release archive")
                source = archive.extractfile(executables[0])
                if source is None:
                    raise ContractError("Cannot read oasdiff executable from release archive")
                temporary_binary = Path(scratch) / "oasdiff"
                with source, temporary_binary.open("wb") as target:
                    shutil.copyfileobj(source, target)
                temporary_binary.chmod(0o755)
                _check_version(temporary_binary, timeout)
                temporary_binary.replace(destination)
    except (OSError, tarfile.TarError) as exc:
        raise ContractError(f"Cannot install oasdiff: {exc}") from exc
    return destination.resolve()


def _check_version(binary: Path, timeout: int, cwd: Path | None = None) -> str:
    if cwd is None:
        with tempfile.TemporaryDirectory(prefix="pagoda-oasdiff-version-") as scratch:
            return _check_version(binary.resolve(), timeout, Path(scratch))
    config = _fixed_config(cwd)
    result = run_command(
        [str(binary), "--config", str(config), "--version"],
        cwd=cwd,
        env=_engine_env(),
        timeout=timeout,
    )
    version = result.stdout.strip()
    if result.returncode != 0 or version not in {
        f"oasdiff version {PINNED_VERSION}",
        f"oasdiff version v{PINNED_VERSION}",
    }:
        raise ContractError(f"Expected oasdiff {PINNED_VERSION}, received {version!r}")
    return version


def _json_result(
    binary: Path, command: str, base: Path, head: Path, timeout: int, cwd: Path
) -> Any:
    result = run_command(
        [
            str(binary),
            command,
            str(base),
            str(head),
            *ENGINE_FLAGS,
            "--config",
            str(_fixed_config(cwd)),
        ],
        cwd=cwd,
        env=_engine_env(),
        timeout=timeout,
    )
    if result.returncode != 0:
        raise ContractError(
            f"oasdiff {command} failed ({result.returncode}): {result.stderr.strip()}"
        )
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise ContractError(f"oasdiff {command} produced malformed JSON") from exc


def run_engine(
    binary: Path, base: Path, head: Path, output: Path, timeout: int = 120
) -> dict[str, Any]:
    """Run the pinned engine and validate both machine-readable results."""
    for spec in (base, head):
        try:
            document = json.loads(spec.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise ContractError(f"Cannot read OpenAPI snapshot: {spec}") from exc
        _reject_external_refs(document)
    binary, base, head = binary.resolve(), base.resolve(), head.resolve()
    with tempfile.TemporaryDirectory(prefix="pagoda-oasdiff-") as scratch:
        cwd = Path(scratch)
        version = _check_version(binary, timeout, cwd)
        diff = _json_result(binary, "diff", base, head, timeout, cwd)
        findings = _json_result(binary, "changelog", base, head, timeout, cwd)
    if not isinstance(diff, dict):
        raise ContractError("oasdiff diff must be a JSON object")
    if not isinstance(findings, list):
        raise ContractError("oasdiff changelog must be a JSON array")
    for finding in findings:
        if (
            not isinstance(finding, dict)
            or type(finding.get("level")) is not int
            or finding["level"] not in {1, 2, 3}
            or not isinstance(finding.get("id"), str)
            or not finding["id"]
            or not isinstance(finding.get("text"), str)
        ):
            raise ContractError("oasdiff changelog contains an unknown or malformed finding")
    output.mkdir(parents=True, exist_ok=True)
    for name, data in (("diff.json", diff), ("findings.json", findings)):
        (output / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {
        "diff": diff,
        "findings": findings,
        "version": version,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(FIXED_CONFIG).hexdigest(),
        "flags": list(ENGINE_FLAGS),
    }


def _fixed_config(cwd: Path) -> Path:
    config = cwd / "fixed-config.json"
    if not config.exists():
        config.write_bytes(FIXED_CONFIG)
        config.chmod(0o444)
    if config.read_bytes() != FIXED_CONFIG:
        raise ContractError("oasdiff fixed configuration changed during execution")
    return config.resolve()


def _engine_env() -> dict[str, str]:
    """Avoid inherited config, home lookup, and platform loader overrides."""
    return {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


def _reject_external_refs(value: Any) -> None:
    if isinstance(value, dict):
        reference = value.get("$ref")
        if "$ref" in value and (not isinstance(reference, str) or not reference.startswith("#")):
            raise ContractError("External OpenAPI references are not supported")
        for child in value.values():
            _reject_external_refs(child)
    elif isinstance(value, list):
        for child in value:
            _reject_external_refs(child)
