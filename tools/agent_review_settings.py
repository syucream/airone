"""Django configuration overlay for a single local review attempt."""

import os
from importlib import import_module
from pathlib import Path

# django-configurations looks up the active class by name, including when a
# child command (e.g. OpenAPI generation) selects a different configuration.
name = os.environ["DJANGO_CONFIGURATION"]
original = getattr(import_module(os.environ["PAGODA_REVIEW_BASE_SETTINGS"]), name)
migration_packages = Path(os.environ["PAGODA_REVIEW_MIGRATIONS"])
globals()[name] = type(
    name,
    (original,),
    {
        "__module__": __name__,
        "MIGRATION_MODULES": {
            **getattr(original, "MIGRATION_MODULES", {}),
            **{
                directory.name: f"review_migrations.{directory.name}"
                for directory in migration_packages.iterdir()
                if (directory / "__init__.py").is_file()
            },
        },
    },
)
