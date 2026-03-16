# Investigation: Observational Data Window Width

## Bug Summary
The ObservationsModal (observational data window) is narrower than the table view. The task requests making it wider to match the table view width.

## Root Cause Analysis

The ObservationsModal is constrained by two CSS rules in `ObservationsModal.css`:

1. `.observations-overlay` has `padding: 2rem` — this creates 2rem of space on all sides, limiting the modal to `calc(100vw - 4rem)` wide.
2. `.observations-modal` has `max-width: 1400px` — this hard caps the modal at 1400px regardless of screen size.

The table view (`DataTable`) renders inside `.main-content` which is `flex: 1` filling the full viewport minus the 280px sidebar (`.sidebar`) and the `.table-container` padding of `1.5em` on each side. On large screens (>1400px + 280px sidebar), the table area is wider than 1400px, so the modal visually appears narrower.

## Affected Components
- `react-app/src/components/ObservationsModal.css` — the only file that needs to change

## Proposed Solution

Change `.observations-modal` `max-width` from `1400px` to a viewport-relative value that accounts for the overlay padding. The table view's effective width is approximately `calc(100vw - 280px - 3em)` (full vw minus sidebar minus table-container padding). To match this in the modal context (which is overlaid on top and doesn't know about the sidebar), we should maximize the modal width within the overlay padding.

**Fix**: Change `max-width: 1400px` to `max-width: calc(100vw - 4rem)` on `.observations-modal`. This makes the modal fill the full viewport width minus the overlay padding (2rem each side), matching the "feel" of the table view. Additionally reduce overlay padding from `2rem` to `1rem` to give even more horizontal space.

Alternatively, a simpler approach: set `max-width: calc(100vw - 2rem)` and keep `padding: 1rem` on the overlay, making the modal nearly full-width like the underlying table.

**Recommended fix** (minimal change):
- In `.observations-overlay`: change `padding: 2rem` to `padding: 1rem`
- In `.observations-modal`: change `max-width: 1400px` to `max-width: calc(100vw - 2rem)`

This makes the modal as wide as the viewport allows (minus 1rem each side), matching what a user sees in the table view.

## Edge Cases / Side Effects
- The `@media (max-width: 768px)` block already sets `max-width: 100%` for small screens — no change needed there.
- The `max-height: 90vh` is unchanged, vertical scroll behavior is unaffected.
- The modal already handles horizontal overflow via `overflow-x: auto` on `.observations-table-wrapper`.
