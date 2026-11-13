# Real Celery worker fault tests

These on-demand tests run the producer and actual Celery prefork workers inside a
Linux container using the Docker host's native architecture, backed by disposable
MySQL and RabbitMQ containers. CI uses Linux amd64. The
same launcher is used locally and in CI. A native macOS trial hit a prefork pipe
error after broker reconnection; the supported test lane therefore uses Linux.

The tests establish only their asserted job status, database and filesystem
invariants. They do not establish exactly-once execution or automatic recovery
after every crash. Early acknowledgements can lose a message when a worker dies.
An import can leave partial committed effects. An export written before a crash
can remain without automatic replay. Search uses the in-memory adapter, so these
tests do not establish Elasticsearch semantics.

## Run locally

Install Docker with Compose v2 and Python 3.9 or later, and start Docker. Host Python needs
only its standard library. The image installs Python 3.14 and locked development
dependencies; a host virtualenv and existing service credentials are unnecessary.

```bash
tools/test_celery_worker.sh
# Select a class or method:
tools/test_celery_worker.sh WorkerFaultTests.test_concurrent_duplicate_and_replay
```

A fully qualified unittest name is also accepted. The initial build downloads the
base images and dependencies. Docker caches dependency layers for later runs.
Only this checkout's source is built; the Dockerfile-specific ignore excludes
credentials, environment files, keys, Git metadata, virtualenvs, artifacts, agent
configuration and generated migrations from the build context.

Each invocation uses a unique Compose project, MySQL 8.0.36 and RabbitMQ
4.1.3-management. Services publish no host ports and use container-local temporary
filesystems rather than shared data volumes. The runner mounts only its unique
artifact directory at `/artifacts`; the Docker socket is not mounted. Compose uses
`--env-file /dev/null` to avoid loading a checkout's `.env`.

If Docker reports `all predefined address pools have been fully subnetted`, choose
an unused subnet that does not overlap Docker networks, host routes or a VPN:

```bash
PAGODA_WORKER_SUBNET=198.18.250.0/28 tools/test_celery_worker.sh
```

The example is not guaranteed free on your host. This option generates an
effective Compose file with explicit IPAM under the artifact directory. Setup,
broker control and cleanup all use that file. Without the option, Docker uses its
normal automatic IPAM. Concurrent runs must use distinct subnets. Existing
networks are never pruned or modified.

## Scenarios and execution

The runner selects `tools.celery_worker.settings`, configuration `WorkerTest`,
uses database `celery_worker_test` on `mysql`, and connects to broker `rabbitmq`.
It disables eager mode, lite mode, tracing and optional plugins. It generates
migrations, migrates the disposable database, then runs standalone unittest.
Prefetch is one per process, publication retries are disabled, and connection
and barrier waits are bounded for deterministic fault injection. Production
acknowledgement defaults are retained; this is not a production timing benchmark.
The ordinary Django test suite skips this module unless launched in this lane.

- `test_concurrent_duplicate_and_replay`: concurrent delivery and later replay
  for user import, group import and export jobs.
- `test_commit_and_rollback`: publishing around transaction commit and rollback.
- `test_warm_shutdown`: completion during graceful worker shutdown.
- `test_killed_child_leaves_partial_import_visible`: partial import effects after
  a worker child is killed.
- `test_killed_export_after_write_is_not_replayed`: export writes surviving a
  child crash without an automatic replay claim.
- `test_broker_outage_surfaces_publish_failure`: publishing while the isolated
  broker application is unavailable.

Broker fault injection uses request/response files under `/artifacts/control`.
A host standard-library controller accepts only `stop_app` and `start_app`, invokes
`rabbitmqctl` on this invocation's broker, and returns the exit code. Tests have
no general Docker control capability.

The shared core wrapper claims `PREPARING` jobs with a conditional database update.
Probes make two workers pass readiness together, then count entries into the real
task body. External plugin tasks using their own readiness/update sequence must
adopt `Job.claim_for_processing()` separately; this lane does not cover the SDK
sample's independent path.

`Job.run()` publishes after an enclosing transaction commits and returns `None`
while deferred. Autocommit still returns the Celery result, and `run(False)` still
executes immediately. Publication failure after commit leaves a `PREPARING` job
and raises an error; there is no transactional outbox. A killed worker can leave
partial effects and a `PROCESSING` job. The API reports `TIMEOUT` after expiry,
but does not resume or roll back the job; redelivering that ID skips processing.
Reconcile effects before creating a replacement job. These limitations are
asserted explicitly, not treated as successful automatic recovery.

See the [Celery task guide](https://docs.celeryq.dev/en/v5.6.0/userguide/tasks.html)
and [worker guide](https://docs.celeryq.dev/en/v5.6.0/userguide/workers.html) for the
acknowledgement and shutdown semantics behind these scenarios.

## Logs, deadlines and cleanup

Logs and results remain in `.artifacts/celery-worker/<unique-run>/`, including
`setup.log`, `build.log`, `migrations.log`, `tests.log`, `control.log`,
`services.log`, `launcher-result.json`, worker logs and the suite's results.
The launcher prints the absolute directory at startup and exit. A setup or build
failure means the scenarios did not run; inspect launcher status as well as the
test results.

Service startup has a six-minute deadline with a three-minute health wait. Image
build and the container test stage each have a fifteen-minute deadline. A stage
first receives SIGTERM and has fifteen seconds to exit before SIGKILL. The
controller terminates its Docker CLI on interruption. Launcher exit, interrupt
and termination traps collect service logs and run `docker compose down --volumes
--remove-orphans`, removing the runner container and all its worker processes.
Cleanup failures make an otherwise successful invocation fail.

SIGKILL, a host crash or an unavailable Docker daemon can prevent cleanup. Use
the project name printed at startup to remove remaining containers; when explicit
IPAM was used, pass the generated `compose-with-subnet.yml` path with `-f`:

```bash
PAGODA_WORKER_SOURCE_DIR="$PWD" \
PAGODA_WORKER_TEST_DIR="$PWD/.artifacts/celery-worker/<run>" \
docker compose --env-file /dev/null --profile tests -p <project-name> \
  -f <compose-file> down --volumes --remove-orphans
```

The base Compose file requires `PAGODA_WORKER_SOURCE_DIR` and
`PAGODA_WORKER_TEST_DIR` set to the checkout and artifact absolute paths. The
launcher sets these automatically, together with `PAGODA_WORKER_COMPOSE_PROJECT`
and `PAGODA_WORKER_COMPOSE_FILE` for host control. Container paths are always
`/workspace` and `/artifacts`.

## Run in GitHub Actions

Dispatch **Celery worker fault tests** from the Actions tab on the desired branch.
GitHub exposes this manual workflow after it is present on the default branch.
There are no push or pull-request triggers. The workflow calls the same launcher
on Ubuntu and uploads artifacts even after test failure. Its forty-minute job
limit also bounds cold image builds. Local Linux-container evidence and an
actual Actions run are separate evidence; neither establishes production behavior.
