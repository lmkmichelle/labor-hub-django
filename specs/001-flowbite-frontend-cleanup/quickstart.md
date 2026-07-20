# Quickstart: Validate the Flowbite Frontend Cleanup

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

A run/validation guide proving the cleanup works end-to-end with **no visual or behavioral
regression**. It references [data-model.md](./data-model.md) and
[contracts/ui-components.md](./contracts/ui-components.md) for component details rather than
repeating them. (Implementation steps live in `tasks.md`, produced by `/speckit.tasks`.)

## Prerequisites

- Python venv active: `.\.venv\Scripts\Activate.ps1` (Windows) — Python 3 / Django 5.2.3.
- Node + npm available for the CSS build (Node not needed at runtime/host).
- Local DB configured per your `.env` (SQLite locally; see prior deployment work). No migrations are
  part of this feature.

## Setup / build

```powershell
# 1. Rebuild the Tailwind + Flowbite CSS (regenerates static/src/output.css)
npm run build

# 2. Start the app
python manage.py runserver
```

Expected: build completes with no errors and emits `static/src/output.css`; server starts and every
page loads without missing-class, missing-asset, or missing-dependency errors (FR-013).

## Automated gates (must pass)

```powershell
# Template lint gate — zero errors across all templates (FR-013 / SC-008)
djlint templates --lint

# Django test suite — must pass (SC-008). Includes any smoke tests added per research D9.
python manage.py test
```

## Visual validation — page-by-page (minimal-churn)

For each page: confirm lists/cards/buttons/fields/empty-states/pagination render in the unified
Flowbite style with correct spacing, and that **already-correct pages look unchanged**. See the page
inventory in [research.md](./research.md) (D2) for which pages are *fixed* vs *preserved*.

| # | Page | Check | Maps to |
|---|------|-------|---------|
| 1 | Home | All four lists (scholars, papers, events, seminars) render as one styled card component; each shows a styled empty state when data is absent | SC-002, US1-1 |
| 2 | Publications list + detail | Card list unchanged; detail inline `style=""` replaced by tokens/classes; no visual regression | SC-002, SC-005 |
| 3 | Scholars directory (`users_list`) | Grid look preserved; card sourced from the shared component | SC-002, SC-003 |
| 4 | Events list + detail | Normalized to the shared list component; detail preserved | SC-002 |
| 5 | Seminars list | Previously-unstyled Bootstrap list now styled Flowbite | SC-001, SC-002 |
| 6 | Any paginated list (seminars, scholars) across ≥2 pages | Pagination renders as one consistent styled control; active search/filters preserved across pages | SC-002, SC-003, US1-2 |
| 7 | Login form | Fields rendered via `render_field`; primary button = `.btn-primary`; no hand-rolled markup | SC-004 |
| 8 | Publication form | All fields via `render_field`; Tagify loads once; submit/validation identical | SC-004, SC-007, SC-009 |
| 9 | Apply / Event / Edit-profile forms | Unchanged look; advisor select via `render_select`; commented avatar block gone | SC-004, SC-005 |
| 10 | Profile page | Inline styles lifted to tokens; layout preserved | SC-002, SC-005 |
| 11 | Global nav | Dropdown well-formed and keyboard-operable; nav links styled from one class | FR-012, SC-003 |

## Behavior / non-regression checks

- **Forms**: submit each form with valid **and** invalid input; field sets, validation messages, and
  success/error outcomes are identical to before (SC-007). No form field, label, or rule changed.
- **No-JS**: with JavaScript disabled, navigation, forms, and search remain usable (Flowbite/Tagify/
  datepicker are progressive enhancements).
- **Accessibility**: labels stay associated with inputs; dropdowns keyboard-operable; contrast intact.

## Source / asset consistency checks

```powershell
# No Bootstrap-only classes remain (SC-001) — expect no matches
djlint --version   # sanity
Select-String -Path templates\**\*.html -Pattern 'list-group|page-item|page-link|\bcol-\b|d-flex|text-muted' -SimpleMatch:$false

# Flowbite JS served locally & once; no CDN (SC-009 / FR-011) — expect no cdn.jsdelivr Flowbite hit
Select-String -Path templates\**\*.html -Pattern 'cdn\.jsdelivr\.net/npm/flowbite'

# Dead deps gone (SC-006) — expect no matches
Select-String -Path requirements.txt -Pattern 'crispy|django-htmx'
```

Expected: the Bootstrap-class and CDN/dep searches return **no matches**; a change to a single
component class (e.g., `.btn-primary`) visibly updates every usage after `npm run build` (SC-003).

## Done when

- `npm run build`, `djlint`, and `python manage.py test` all pass (SC-008).
- Every row in the page table renders correctly with no regression on preserved pages (SC-002).
- Forms behave identically (SC-007); assets load once and build-consistent (SC-009); dead stack
  removed (SC-006).
- Constitution Principle III amended (FR-015).
