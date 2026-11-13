# Browser accessibility gate

Use the Node version in `.node-version`, then run:

```sh
npm ci
npx playwright install chromium
npm run typecheck:e2e
npm run build
npm run test:a11y
```

On Linux, use `npx playwright install --with-deps chromium`. The committed
API client is sufficient; these tests do not need Python, Java, a database,
or client regeneration. Set `E2E_PORT` to an unused port when running another
checkout at the same time.

The suite serves the actual frontend bundle with fixture APIs. It checks UI
behavior, browser failures, horizontal clipping, and accessibility in Chromium.
This does not validate Django integration or production data. The separate
`live/` suite covers real API workflows.
The accessibility CI job and `typecheck:e2e` cover only the mock suite directly
under `e2e/`; the separate `live/` suite is outside this gate.

`expectAccessibility` runs every default axe rule. Critical and serious
violations block the gate; this preserves the existing severity threshold.
Every scan attaches the complete axe result to the Playwright report,
including lower-severity findings and `incomplete` checks needing manual review.
`accessibility.spec.ts` verifies that the gate rejects missing button names,
missing input labels, low contrast, and invalid lists that the old global
exclusions hid. Do not restore global `disableRules()` or exclude entire
components to make a failing scan pass.

The CI a11y job builds the bundle and runs the same suite. Reports, traces,
screenshots, and scan results are retained under `e2e/test-results/`, including
on failure. Tests must wait for the intended UI state before scanning, and
scan transient states such as open menus before closing them.
Additional scans cover search results and the bulk-update modal, both while
loading and after loading. These intermediate scans check accessibility;
the existing end-of-test layout checks remain unchanged. Finite transitions
finish before a scan so fade-in colors do not create contrast false positives;
infinite loading animations continue to run.

Automated checks are only part of accessibility assessment. Keyboard flows,
focus restoration, screen readers, zoom, input methods, and checks reported
as incomplete still need assessment. A passing gate is not a WCAG conformance
claim.

Reference: https://playwright.dev/docs/accessibility-testing
