# Live-service E2E suite

The suite in `e2e/` runs the frontend bundle against `e2e/server.mjs`, a mock
API. That is enough to check the UI, but not features whose behaviour lives in
the backend -- permissions, validation, background jobs. This suite fills that
gap by driving a real Django server, a real database and a real Celery worker.

It is separate from the mock-backed `npm run test:e2e`. These live-service
scenarios run with MySQL, Elasticsearch, RabbitMQ, a Celery worker, and the
deterministic fixture from `tools/seed_live_service_e2e.py`.

## Running it

```sh
docker compose up -d mysql elasticsearch rabbitmq

# A dedicated database, search index, and message vhost are mandatory. The
# fixture resets known users, so never point these variables at development or
# shared data.
docker exec rabbitmq rabbitmqctl add_vhost e2e
docker exec rabbitmq rabbitmqctl set_permissions -p e2e guest ".*" ".*" ".*"
export AIRONE_MYSQL_MASTER_URL="mysql://airone:password@127.0.0.1:3306/airone_e2e?charset=utf8mb4"
export AIRONE_ELASTICSEARCH_URL="elasticsearch://airone:password@127.0.0.1:9200/airone-e2e"
export AIRONE_RABBITMQ_URL="amqp://guest:guest@localhost/e2e"
export PAGODA_LIVE_SERVICE_E2E=1

uv run python manage.py migrate
uv run python manage.py shell -c 'from airone.lib.elasticsearch import ESS; ESS().recreate_index()'
uv run python tools/seed_live_service_e2e.py

npm run build
uv run python manage.py runserver 8000 &
uv run celery --app airone worker -l info &

npm run typecheck:e2e
npm run test:e2e:live-service
```

Import previews run as Celery jobs, so the worker is not optional -- without it
the dialog polls a job that never starts. The worker does **not** reload code:
restart it after changing anything under `*/tasks.py`, or it will keep running
the version it was started with.

Playwright artifacts are written to `e2e/live/test-results/`.
