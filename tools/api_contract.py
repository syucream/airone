#!/usr/bin/env python3
"""Compare the public OpenAPI contract of a Git base and the working tree."""

import argparse
import hashlib
import importlib.metadata
import json
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Support the documented file invocation as well as ``python -m tools.api_contract``.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.api_contract_support.common import ContractError, run_command
from tools.api_contract_support.engine import install_engine, resolve_engine, run_engine
from tools.api_contract_support.snapshot import generate_schema, prepare_snapshots

SCHEMA_VERSION = 1
LIMITATIONS = [
    "Compares declared public APIv2 contracts, not runtime behavior or ACL enforcement.",
    "Uses current Python dependencies for both source revisions; not a released-contract check.",
    "Uses fixed local schema settings; deployment settings and external plugins are excluded.",
    "No TypeScript client compilation, registry verification, or real-service tests are performed.",
]


def write_json(path: Path, value: Any) -> None:
    """Write a complete, UTF-8 artifact without depending on stdout parsing."""
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def environment_info() -> dict[str, Any]:
    packages = sorted(
        (dist.metadata.get("Name", "unknown"), dist.version)
        for dist in importlib.metadata.distributions()
    )
    return {"python": sys.version.split()[0], "packages": packages, "sha256": digest(packages)}


def comparison_summary(comparison: dict[str, Any]) -> dict[str, Any]:
    """Keep the agent entrypoint concise without dropping the full evidence file."""
    base = comparison.get("base_files", {})
    head = comparison.get("head_files", {})
    return {
        **{
            key: value
            for key, value in comparison.items()
            if key not in ("base_files", "head_files", "excluded")
        },
        "base_file_count": len(base),
        "head_file_count": len(head),
        "changed_source_files": sorted(
            name for name in base.keys() | head.keys() if base.get(name) != head.get(name)
        ),
        "excluded_file_count": len(comparison.get("excluded", [])),
        "manifest": "comparison.json",
    }


def normalize_findings(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep engine evidence while exposing stable, explicitly versioned fields."""
    severities = {1: "non_breaking", 2: "review_required", 3: "breaking"}
    result: list[dict[str, Any]] = []
    for index, change in enumerate(raw):
        level = change.get("level")
        if type(level) is not int or level not in severities:
            raise ContractError("Unknown finding severity from oasdiff")
        rule = change.get("id")
        if not isinstance(rule, str) or not rule:
            raise ContractError("Missing finding rule ID from oasdiff")
        for key in ("operation", "path", "text"):
            if key in change and not isinstance(change[key], str):
                raise ContractError(f"Invalid finding {key} from oasdiff")
        # File/line coordinates can change between runs and are not diagnostic identity.
        identity = {
            key: val
            for key, val in change.items()
            if key not in ("source", "baseSource", "revisionSource", "level")
        }
        result.append(
            {
                "id": digest(identity),
                "rule_id": rule,
                "severity": severities[level],
                "method": change.get("operation", ""),
                "path": change.get("path", ""),
                "message": change.get("text", rule),
                "details": change.get("args", []),
                "section": change.get("section"),
                "raw_index": index,
            }
        )
    return sorted(result, key=lambda finding: (finding["path"], finding["method"], finding["id"]))


def classify(findings: list[dict[str, Any]]) -> tuple[str, dict[str, int], int]:
    summary = {
        level: sum(finding["severity"] == level for finding in findings)
        for level in ("breaking", "review_required", "non_breaking")
    }
    if summary["breaking"]:
        return "breaking", summary, 1
    if summary["review_required"]:
        return "review_required", summary, 0
    return "compatible", summary, 0


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_markdown(report: dict[str, Any]) -> str:
    comparison = report["comparison"]
    lines = [
        "# API contract report",
        "",
        f"Status: **{report['status']}**. Exit code: `{report['exit_code']}`.",
        "",
        f"Requested base: `{comparison.get('base_ref', 'unknown')}`.",
        f"Merge base: `{comparison.get('base_sha', 'unknown')}`.",
        f"HEAD: `{comparison.get('head_sha', 'unknown')}`.",
        f"Working tree dirty: `{comparison.get('working_tree_dirty', 'unknown')}`.",
        "",
    ]
    if report["error"]:
        lines.extend([f"Comparison failed during **{report['error']['stage']}**:", ""])
        lines.extend([markdown_cell(report["error"]["message"]), ""])
    else:
        lines.extend(
            [
                f"Breaking: {report['summary']['breaking']}; "
                f"review required: {report['summary']['review_required']}; "
                f"non-breaking: {report['summary']['non_breaking']}.",
                f"Any schema difference: `{report['has_changes']}`.",
                "",
            ]
        )
        if report["findings"]:
            lines.extend(
                [
                    "| Severity | Operation | Rule | Detail |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for finding in report["findings"]:
                detail = finding["message"]
                if finding["details"]:
                    detail += " " + json.dumps(finding["details"], ensure_ascii=False)
                cells = (
                    finding["severity"],
                    f"{finding['method']} {finding['path']}",
                    finding["rule_id"],
                    detail,
                )
                lines.append("| " + " | ".join(markdown_cell(cell) for cell in cells) + " |")
            lines.append("")
        else:
            lines.extend(
                ["No consumer-impact finding was detected; see `diff.json` for all edits.", ""]
            )
    lines.extend(["## Scope", ""])
    lines.extend(f"- {limit}" for limit in report["limitations"])
    lines.extend(["", "## Evidence", ""])
    lines.extend(f"- [{name}]({name})" for name in report["artifacts"])
    return "\n".join(lines) + "\n"


def check(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    started = time.monotonic()
    repo_result = run_command(["git", "rev-parse", "--show-toplevel"])
    if repo_result.returncode:
        raise ContractError("Run this command inside a Git working tree")
    repo = Path(repo_result.stdout.strip()).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    output = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else repo / ".cache" / "api-contract" / run_id
    )
    # Never let an unsuccessful run appear to have reused a previously successful report.
    output.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "output_dir": str(output),
        "status": "error",
        "exit_code": 2,
        "comparison": {"base_ref": args.base_ref},
        "summary": {"breaking": None, "review_required": None, "non_breaking": None},
        "has_changes": None,
        "findings": [],
        "environment": {},
        "engine": {},
        "generation": {},
        "error": None,
        "limitations": LIMITATIONS,
        "artifacts": [],
    }
    stage = "environment"
    try:
        environment = environment_info()
        write_json(output / "environment.json", environment)
        report["environment"] = {
            key: value for key, value in environment.items() if key != "packages"
        }
        report["environment"]["manifest"] = "environment.json"
        stage = "engine"
        binary = resolve_engine(repo, args.oasdiff)
        with tempfile.TemporaryDirectory(prefix="pagoda-api-contract-") as temporary:
            workspace = Path(temporary)
            stage = "snapshot"
            comparison = prepare_snapshots(repo, args.base_ref, workspace)
            write_json(output / "comparison.json", comparison)
            report["comparison"] = comparison_summary(comparison)
            for label in ("base", "head"):
                stage = f"generate_{label}"
                report["generation"][label] = generate_schema(
                    workspace / label,
                    output / f"{label}.openapi.json",
                    output / f"{label}.generation.log",
                    timeout=args.timeout,
                )
            stage = "compare"
            evidence = run_engine(
                binary,
                output / "base.openapi.json",
                output / "head.openapi.json",
                output,
                timeout=args.timeout,
            )
            report["engine"] = {
                "version": evidence["version"],
                "binary_sha256": evidence["binary_sha256"],
                "config_sha256": evidence["config_sha256"],
                "flags": evidence["flags"],
            }
            report["findings"] = normalize_findings(evidence["findings"])
            report["status"], report["summary"], report["exit_code"] = classify(report["findings"])
            report["has_changes"] = bool(evidence["diff"])
    except (ContractError, OSError, ValueError) as exc:
        report["error"] = {"stage": stage, "message": str(exc)}
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    report["artifacts"] = sorted(
        {file.name for file in output.iterdir() if file.is_file()} | {"report.json", "report.md"}
    )
    write_json(output / "report.json", report)
    (output / "report.md").write_text(render_markdown(report), encoding="utf-8")
    return report, output


def positive_timeout(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("timeout must be positive")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install", help="Download the checksum-pinned oasdiff")
    install_parser.add_argument("--timeout", type=positive_timeout, default=120)
    check_parser = commands.add_parser("check", help="Compare merge-base with working-tree sources")
    check_parser.add_argument("--base-ref", required=True)
    check_parser.add_argument(
        "--output-dir", help="New evidence directory (must not already exist)"
    )
    check_parser.add_argument("--oasdiff", help="Path to the pinned oasdiff executable")
    check_parser.add_argument("--timeout", type=positive_timeout, default=120)
    check_parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            result = run_command(["git", "rev-parse", "--show-toplevel"])
            if result.returncode:
                raise ContractError("Run this command inside a Git working tree")
            path = install_engine(
                Path(result.stdout.strip()) / ".cache" / "api-contract" / "bin" / "oasdiff",
                timeout=args.timeout,
            )
            sys.stdout.write(f"Installed pinned oasdiff: {path}\n")
            return 0
        report, output = check(args)
        if args.format == "json":
            sys.stdout.write(json.dumps(report, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(f"API contract: {report['status']} (exit {report['exit_code']})\n")
            if report["error"]:
                sys.stdout.write(f"{report['error']['stage']}: {report['error']['message']}\n")
            else:
                sys.stdout.write(json.dumps(report["summary"]) + "\n")
            sys.stdout.write(f"Report: {output / 'report.md'}\n")
            sys.stdout.write(f"JSON: {output / 'report.json'}\n")
        return int(report["exit_code"])
    except (ContractError, OSError, ValueError) as exc:
        if getattr(args, "format", None) == "json":
            sys.stdout.write(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "status": "error",
                        "exit_code": 2,
                        "summary": {
                            "breaking": None,
                            "review_required": None,
                            "non_breaking": None,
                        },
                        "has_changes": None,
                        "findings": [],
                        "error": {"stage": "setup", "message": str(exc)},
                    }
                )
                + "\n"
            )
        sys.stderr.write(f"API contract setup failed: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
