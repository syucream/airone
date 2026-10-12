"""Create isolated source snapshots and generate their OpenAPI contracts."""

import hashlib
import json
import os
import re
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Any

from .common import ContractError, run_command

SETTINGS = """from airone.settings_common import Common


class DRFSpectacularExcludeCustomView(Common):
    SPECTACULAR_SETTINGS = {
        **Common.SPECTACULAR_SETTINGS,
        "PREPROCESSING_HOOKS": [
            *Common.SPECTACULAR_SETTINGS.get("PREPROCESSING_HOOKS", []),
            "airone.spectacular.exclude_customview_hook",
        ],
    }
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    DATABASE_ROUTERS = []
    ENABLED_PLUGINS = []
"""


def _git(repo: Path, *args: str) -> str:
    result = run_command(["git", *args], cwd=repo)
    if result.returncode:
        raise ContractError(f"Git command failed: {result.stderr.strip()}")
    return result.stdout


def _excluded(name: str) -> bool:
    path = Path(name)
    return any(
        part.startswith(".env") or any(word in part.lower() for word in ("credential", "secret"))
        for part in path.parts
    ) or path.suffix.lower() in {".pem", ".key", ".p12"}


def _relevant(name: str) -> bool:
    return Path(name).suffix in {".py", ".html"} and not _excluded(name)


def _digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _working_files(repo: Path) -> tuple[dict[str, bytes], list[str], list[str]]:
    tracked = set(_git(repo, "ls-files", "-z").split("\0")) - {""}
    untracked = set(_git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0")) - {
        ""
    }
    files: dict[str, bytes] = {}
    excluded = []
    included = []
    for name in sorted(tracked | untracked):
        if name == "airone/settings.py" or name.startswith("custom_view/") or not _relevant(name):
            excluded.append(name)
            continue
        path = repo / name
        if path.is_symlink() or any(
            parent.is_symlink() for parent in path.parents if parent != repo
        ):
            raise ContractError(f"Source symlink is unsupported: {name}")
        if path.is_file():
            files[name] = path.read_bytes()
            if name in untracked:
                included.append(name)
    return files, included, excluded


def prepare_snapshots(repo: Path, base_ref: str, destination: Path) -> dict[str, Any]:
    """Snapshot the merge base and working sources, rejecting concurrent changes."""
    repo = repo.resolve()
    base_commit = _git(
        repo, "rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}"
    ).strip()
    base_sha = _git(repo, "merge-base", base_commit, "HEAD").strip()
    head_sha = _git(repo, "rev-parse", "HEAD").strip()
    status = _git(repo, "status", "--porcelain", "-z")
    head_files, untracked, excluded = _working_files(repo)
    base_files: dict[str, bytes] = {}
    objects: list[tuple[str, str]] = []
    for entry in _git(repo, "ls-tree", "-r", "-z", base_sha).split("\0"):
        if not entry:
            continue
        info, name = entry.split("\t", 1)
        if name == "airone/settings.py" or name.startswith("custom_view/") or not _relevant(name):
            continue
        mode, _, object_id = info.split()
        if mode != "100644" and mode != "100755":
            raise ContractError(f"Base source symlink is unsupported: {name}")
        objects.append((name, object_id))
    if objects:
        try:
            result = subprocess.run(
                ["git", "cat-file", "--batch"],
                cwd=repo,
                input="".join(object_id + "\n" for _, object_id in objects).encode(),
                capture_output=True,
                check=False,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ContractError("Cannot read base source objects") from exc
        if result.returncode:
            raise ContractError("Cannot read base source objects")
        position = 0
        for name, object_id in objects:
            end = result.stdout.find(b"\n", position)
            header = result.stdout[position:end].split()
            if len(header) != 3 or header[0].decode() != object_id or header[1] != b"blob":
                raise ContractError("Malformed base source object response")
            size = int(header[2])
            position = end + 1
            content = result.stdout[position : position + size]
            if (
                len(content) != size
                or result.stdout[position + size : position + size + 1] != b"\n"
            ):
                raise ContractError("Truncated base source object response")
            base_files[name] = content
            position += size + 1
    for label, files in (("base", base_files), ("head", head_files)):
        target = destination / label
        target.mkdir(parents=True, exist_ok=False)
        for name, content in files.items():
            normalized_name = name.replace("custom_view_sample/", "custom_view/", 1)
            path = target / normalized_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (target / "airone").mkdir(exist_ok=True)
        (target / "airone/settings.py").write_text(SETTINGS)
    current, current_untracked, _ = _working_files(repo)
    if (
        _digest(current) != _digest(head_files)
        or current_untracked != untracked
        or _git(repo, "rev-parse", "HEAD").strip() != head_sha
        or _git(repo, "status", "--porcelain", "-z") != status
    ):
        raise ContractError("Repository changed while preparing snapshots; retry the check")
    return {
        "base_ref": base_ref,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "working_tree_dirty": bool(status),
        "base_files": {
            name: hashlib.sha256(data).hexdigest() for name, data in sorted(base_files.items())
        },
        "head_files": {
            name: hashlib.sha256(data).hexdigest() for name, data in sorted(head_files.items())
        },
        "base_source_digest": _digest(base_files),
        "head_source_digest": _digest(head_files),
        "included_untracked": untracked,
        "excluded": excluded,
        "custom_view_policy": "tracked-custom_view_sample-renamed-to-custom_view",
        "deployment_sources_policy": "ignored-files-and-custom_view-excluded",
        "python_isolation_policy": "isolated-no-site-explicit-library-paths-no-pth",
        "settings_policy": "normalized-common-exclude-customview-sqlite-memory",
        "settings_digest": hashlib.sha256(SETTINGS.encode()).hexdigest(),
    }


def _validate_schema(value: Any) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("openapi"), str):
        raise ContractError("Generated schema is not an OpenAPI document")
    if not isinstance(value.get("paths"), dict) or not value["paths"]:
        raise ContractError("Generated schema has no API paths")
    pending: list[Any] = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if "$ref" in item and (
                not isinstance(item["$ref"], str) or not item["$ref"].startswith("#/")
            ):
                raise ContractError("Generated schema contains an external reference")
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def generate_schema(source: Path, output: Path, log: Path, timeout: int = 120) -> dict[str, Any]:
    """Generate a schema with a sanitized environment and isolated SDK imports."""
    source, output, log = source.resolve(), output.resolve(), log.resolve()
    env = {
        "PATH": os.defpath,
        "PYTHONNOUSERSITE": "1",
        "DJANGO_SETTINGS_MODULE": "airone.settings",
        "DJANGO_CONFIGURATION": "DRFSpectacularExcludeCustomView",
        "PAGODA_LITE": "1",
        "AIRONE_MYSQL_MASTER_URL": "sqlite://:memory:",
        "AIRONE_ES_BACKEND": "inmemory",
        "AIRONE_RABBITMQ_URL": "memory://",
        "AIRONE_SECRET_KEY": "api-contract-isolated-generation",
        "DD_TRACE_ENABLED": "false",
        "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "false",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    libraries = sorted({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})
    bootstrap = (
        "import json, runpy, sys; "
        "source = sys.argv[1]; "
        "sys.path[:0] = [source, source + '/plugin/sdk', *json.loads(sys.argv[2])]; "
        "sys.argv = ['manage.py', *sys.argv[3:]]; "
        "runpy.run_path(source + '/manage.py', run_name='__main__')"
    )
    result = run_command(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            bootstrap,
            str(source),
            json.dumps(libraries),
            "spectacular",
            "--format",
            "openapi-json",
            "--file",
            str(output),
        ],
        cwd=source,
        env=env,
        timeout=timeout,
    )
    diagnostic = result.stdout + result.stderr
    log.write_text(diagnostic)
    if result.returncode or re.search(r"\bError(?:\s+\[[^]]*\])?:|\bErrors:\s+[1-9]", diagnostic):
        raise ContractError(f"OpenAPI generation failed; see {log}")
    try:
        schema = json.loads(output.read_text())
    except (OSError, ValueError) as exc:
        raise ContractError(f"Malformed or missing generated schema; see {log}") from exc
    _validate_schema(schema)
    return {
        "schema_digest": hashlib.sha256(output.read_bytes()).hexdigest(),
        "warning_count": len(re.findall(r"\bWarning(?:\s+\[[^]]*\])?:", diagnostic)),
        "log": str(log),
    }
