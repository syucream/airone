"""Isolated settings for the disposable MySQL/RabbitMQ fault-test stack."""

import os
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

# Common normally loads a developer's .env. This lane must use only the
# disposable endpoints supplied by its launcher, never local credentials.
with patch("environ.Env.read_env"):
    from airone.settings_common import Common

if os.environ.get("PAGODA_WORKER_TEST") != "1":
    raise RuntimeError("Use tools/test_celery_worker.sh to run these tests")

for key, scheme, host in (
    ("AIRONE_MYSQL_MASTER_URL", "mysql", "mysql"),
    ("AIRONE_RABBITMQ_URL", "amqp", "rabbitmq"),
):
    endpoint = urlparse(os.environ[key])
    if endpoint.scheme != scheme or endpoint.hostname != host:
        raise RuntimeError(f"{key} must address the disposable Compose test stack")
    if key == "AIRONE_MYSQL_MASTER_URL" and endpoint.path != "/celery_worker_test":
        raise RuntimeError("Refusing to use a non-test database")


class WorkerTest(Common):
    DEBUG = False
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_DEFAULT_QUEUE = "worker-fault-tests"
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1
    CELERY_BROKER_CONNECTION_TIMEOUT = 3
    CELERY_TASK_PUBLISH_RETRY = False
    # Keep production acknowledgement defaults. Changing them would test a
    # different delivery contract and conceal the current crash limitation.
    DATABASE_ROUTERS: list[str] = []
    REPLICA_DATABASES = ["default"]
    DATABASES = {"default": deepcopy(Common.DATABASES["default"])}
    MEDIA_ROOT = str(Path(os.environ["PAGODA_WORKER_TEST_DIR"]) / "media")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    AIRONE = deepcopy(Common.AIRONE)
    AIRONE["EXTENSIONS"] = []
    AIRONE["PLUGINS"] = {"ENABLED": False}
    # Selected tasks do not access search; prevent accidental access to a
    # developer's Elasticsearch. This is not search-integration evidence.
    ES_CONFIG = {**Common.ES_CONFIG, "BACKEND": "inmemory", "PERSIST_PATH": None}
