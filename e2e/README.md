# E2E suite

The Playwright suite in this directory runs the real frontend bundle against the
mock API in `server.mjs`. It needs no database, so it is cheap enough to run on
every frontend change: locally, and in CI
(`.github/workflows/e2e.yml`, currently non-blocking).

The suite under `live/` is different: it drives a real Django + MySQL +
Elasticsearch stack and is run on demand. See `live/README.md`.

## Running

```sh
npm ci
npm run test:e2e:install          # downloads Chromium, once per checkout
npm run test:e2e                  # regenerate + link the client, build, run
```

Faster loop once the API client is linked and Chromium is present:

```sh
npm run build                     # only needed if frontend/ changed
npx playwright test --config=e2e/playwright.config.ts
```

Run one file, or a tagged slice:

```sh
npx playwright test --config=e2e/playwright.config.ts e2e/pagoda-smoke.spec.ts
npx playwright test --config=e2e/playwright.config.ts --grep @crud
```

## Report

Every run writes `test-results/report/report.md`: a pass/fail table for all
scenarios plus embedded full-page screenshots. **Attach it when you hand off a
UI change.** `test-results/html/index.html` is the interactive report, with
traces and videos for failures.

## Locale

The config pins `locale: "ja-JP"`. The app chooses its language from
`navigator.languages` and the scenarios assert Japanese labels, so without the
pin the suite renders English and fails on an `en-US` runner such as CI.

## Adding a scenario

1. Add a `*.spec.ts` file here; Playwright picks it up automatically.
2. Exercise real user-visible behaviour (navigate, fill, click, assert) rather
   than calling the API directly.
3. Call `captureEvidence(page, testInfo, { name, title, note })` so the screen
   appears in the report.
4. Follow the existing `beforeEach`: `POST /__e2e/reset` to reset the mock state,
   then `collectBrowserFailures` and `expectUiQualityGate` in `afterEach` so
   console errors, failed requests, axe violations, and overflow are gated.
5. If the scenario needs a new mock response, extend `server.mjs` — a missing
   route answers `500 Unhandled E2E mock`, which is usually what a failure here
   means.
