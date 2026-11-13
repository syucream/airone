"""Best-effort application version metadata without startup dependencies."""

import logging
import subprocess

logger = logging.getLogger(__name__)


def get_version(base_dir: str) -> str:
    """Return the first application tag on HEAD, or unknown when unavailable."""
    try:
        result = subprocess.run(
            ["git", "tag", "--points-at"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("Could not determine application version from git: %s", type(error).__name__)
        return "unknown"

    for tag in result.stdout.splitlines():
        if tag.strip() and "pagoda-core-" not in tag:
            return tag.strip()

    logger.warning("Could not determine application version from git: no application tag")
    return "unknown"
