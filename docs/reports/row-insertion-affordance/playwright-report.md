# Pagoda row-insertion affordance rework — E2E gate

Generated: 2026-10-31T10:05:44.984Z

## Summary

- The real frontend bundle was booted in Chromium against the mock API server.
- Entry array attributes (string / number / named object), entity attributes, isolation rules, trigger conditions and trigger actions were exercised.
- Insertion bands were verified to land on the boundary they are drawn on, and the append row was verified to append at the end with focus moved into the new row.
- Every stage also checks browser console errors, page errors, failed requests, critical axe violations, horizontal overflow and off-screen controls.

## Test Results

| Result | Test case | Duration |
| --- | --- | ---: |
| PASS | @gate1 entry array attribute appends at the end and focuses the new row | 2432 ms |
| PASS | @gate1 insertion band inserts exactly on the boundary it is drawn on | 1904 ms |
| PASS | @gate1 isolation rules render a visible append row when empty | 2028 ms |
| PASS | @gate1 whole screens keep their hierarchy | 3546 ms |
| PASS | @gate2 rows no longer expose a per-row plus button | 1364 ms |
| PASS | @gate2 trigger conditions insert on the boundary | 1448 ms |
| PASS | @gate2 entity attributes insert on the boundary | 2193 ms |
| PASS | @gate2 every insertion control has an accessible name | 1224 ms |
| PASS | @gate3 trigger action values append into their own action only | 1479 ms |
| PASS | @gate3 insertion bands are keyboard operable | 1460 ms |
| PASS | @gate3 narrow viewport does not widen the layout further | 3407 ms |

## Evidence

### Append row adds at the end and focuses the new input

Entry edit / aliases (array_string). The "＋ 値を追加" control is the only place that appends; the new row is appended last and receives focus so typing continues without a second click.

![Append row adds at the end and focuses the new input](screenshots/gate1-append-row.png)

### Insertion band inserts at the drawn boundary

Two insertions via the band: one above the first row and one between row 1 and row 2. Values stay in the expected order, which proves the insertion index matches the pointer position rather than the row the control belongs to.

![Insertion band inserts at the drawn boundary](screenshots/gate1-insert-band.png)

### Isolation rules: empty state is one labelled append row

The former empty state was a lone unlabelled ＋ inside a blank table row. It is now a labelled append row, and the nested condition list shows its own append control.

![Isolation rules: empty state is one labelled append row](screenshots/gate1-isolation-empty.png)

### Entry edit — full screen

Array attributes (aliases / named_switches / ports) now read as lists with a divider-shaped insert control between rows and a labelled append row at the end.

![Entry edit — full screen](screenshots/gate1-entry-edit-full.png)

### Entity edit — full screen

The 追加 column is gone from the attribute table; the isolation-rules table and the webhook table end with labelled append rows.

![Entity edit — full screen](screenshots/gate1-entity-edit-full.png)

### Trigger edit — full screen

Conditions and actions both expose per-boundary bands plus one append row; nested action values have their own append control.

![Trigger edit — full screen](screenshots/gate1-trigger-edit-full.png)

### Row-level actions are delete-only

Each array row keeps a single, labelled delete control. The insertion affordance moved out of the row and onto the boundary, so a row no longer owns an action whose effect happens elsewhere.

![Row-level actions are delete-only](screenshots/gate2-row-actions.png)

### Trigger conditions: boundaries carry the insert affordance

A band sits between every pair of conditions and one labelled append row closes the table. The delete column no longer competes with a per-row ＋.

![Trigger conditions: boundaries carry the insert affordance](screenshots/gate2-trigger-conditions.png)

### Entity attributes: insertion band and append row

The entity attribute table lost its 追加 column. A band above each row inserts at that position and a labelled append row closes the table; the 並び替え column keeps working for reordering.

![Entity attributes: insertion band and append row](screenshots/gate2-entity-attributes.png)

### Trigger actions: outer rows and nested values are separated

Action rows use bands plus a labelled append row; the nested value lists use their own append control, so an insertion can never be confused with the scope it belongs to.

![Trigger actions: outer rows and nested values are separated](screenshots/gate3-trigger-actions.png)
