"""Compare the committed API surface with the generated current client schema."""

# CLI diagnostics are intentionally printed.
# ruff: noqa: T201

import argparse
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml

# Editable installs must not supply modules missing from the historical snapshot.
SCHEMA_BOOTSTRAP = """
import runpy
import sys
from pathlib import Path
current_root = Path(sys.argv[1]).resolve()
blocked = {current_root, current_root / "plugin/sdk"}
sys.path[:] = [entry for entry in sys.path if Path(entry).resolve() not in blocked]
sys.meta_path[:] = [
    finder for finder in sys.meta_path
    if not getattr(finder, "__module__", "").startswith("__editable___pagoda_plugin_sdk_")
]
sys.argv = ["manage.py", "spectacular"]
runpy.run_path("manage.py", run_name="__main__")
"""


class CompatibilityError(Exception):
    pass


def snapshot_sources(root: Path, base_ref: str, destination: Path) -> str:
    """Resolve once and copy Python sources only, excluding local configuration."""
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", resolved):
        raise CompatibilityError("Git did not resolve the base reference to an exact commit.")
    tracked = (
        subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "-z", resolved],
            cwd=root,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    paths = [
        name
        for name in tracked
        if name.endswith(".py")
        and not any(part.startswith(".env") for part in Path(name).parts)
        and not any(word in name.lower() for word in ("credentials", "secrets"))
    ]
    if "manage.py" not in paths:
        raise CompatibilityError("The base revision does not contain manage.py.")
    archive = subprocess.run(
        ["git", "archive", resolved, "--", *paths],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source:
            path = Path(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or ".." in path.parts
                or not path.suffix == ".py"
                or any(part.startswith(".env") for part in path.parts)
                or any(word in path.name.lower() for word in ("credentials", "secrets"))
            ):
                continue
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.extractfile(member)
            if data is None:
                raise CompatibilityError(f"Could not extract source: {member.name}")
            target.write_bytes(data.read())
    if not (destination / "manage.py").is_file():
        raise CompatibilityError("The base revision does not contain manage.py.")
    return resolved


def generate_schema(snapshot: Path, output: Path) -> None:
    """Use current installed dependencies with an isolated base source tree."""
    environment = os.environ.copy()
    environment.update(
        DJANGO_SETTINGS_MODULE="airone.settings",
        DJANGO_CONFIGURATION="DRFSpectacularExcludeCustomView",
        PAGODA_LITE="1",
        PYTHONPATH=os.pathsep.join((str(snapshot), str(snapshot / "plugin/sdk"))),
    )
    (snapshot / "logs").mkdir(exist_ok=True)
    with output.open("w") as schema:
        result = subprocess.run(
            [sys.executable, "-c", SCHEMA_BOOTSTRAP, str(Path(__file__).resolve().parents[1])],
            cwd=snapshot,
            env=environment,
            stdout=schema,
            stderr=subprocess.PIPE,
            text=True,
        )
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode or re.search(r"(^|\s)Error(:| \[)", result.stderr):
        raise CompatibilityError("Base OpenAPI schema generation failed.")
    with output.open() as generated:
        document = yaml.safe_load(generated)
    if not isinstance(document, dict) or not document.get("paths"):
        raise CompatibilityError("Base OpenAPI schema generation produced no API paths.")


def compare_schemas(base: Path, current: Path) -> int:
    return subprocess.run(
        ["oasdiff", "breaking", str(base), str(current), "--fail-on", "WARN"],
        check=False,
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--current-schema", type=Path, default=Path("spec.yaml"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    current = args.current_schema.resolve()
    try:
        if not current.is_file() or not current.stat().st_size:
            raise CompatibilityError(f"Current schema is missing or empty: {current}")
        with tempfile.TemporaryDirectory(prefix="pagoda-api-base-") as temporary:
            snapshot = Path(temporary) / "source"
            snapshot.mkdir()
            commit = snapshot_sources(root, args.base_ref, snapshot)
            print(f"Checking API compatibility against {commit}", flush=True)
            print("Base schema uses current installed dependencies and core-client settings.")
            base_schema = Path(temporary) / "base.yaml"
            generate_schema(snapshot, base_schema)
            return compare_schemas(base_schema, current)
    except (CompatibilityError, subprocess.CalledProcessError, OSError, yaml.YAMLError) as error:
        print(f"API compatibility check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
