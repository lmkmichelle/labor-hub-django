# Phase 1 Contracts: UI Component Interfaces

**Feature**: [spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

These are the **template and CSS interfaces** the cleanup exposes — the "public API" other templates
depend on. They are contracts in the sense that every listing/form/page must consume the component
through this interface rather than re-implementing it. Signatures are the intended shape; exact
parameter names may be refined during implementation as long as the contract (one source, documented
inputs, unchanged behavior) holds.

---

## Template partial contracts

### `partials/_list_item.html`
Single reusable list/card item (evolved from `_publications_list.html`).

```django
{% include "partials/_list_item.html" with
     title=<str> url=<str?> subtitle=<str?> description=<str?>
     meta=<str?> badge=<str?> image=<str?> %}
```
- **Consumers**: home lists (dict-driven), publications list, scholars directory, seminars list,
  events list, profile papers.
- **Contract**: renders Flowbite card markup only (no Bootstrap classes); optional params omitted
  render nothing (no empty labels); MUST NOT require changes to caller view context.

### `partials/_list.html` (optional wrapper)
Iterates items + renders the shared empty state and (optionally) the pagination control.

```django
{% include "partials/_list.html" with
     items=<iterable> empty_text=<str> page_obj=<Page?> is_paginated=<bool?> querystring=<str?> %}
```
- **Contract**: when `items` is empty, renders the standard styled empty-state message; when
  `is_paginated`, includes `_pagination.html`.

### `partials/_pagination.html`
Flowbite pagination for any Django-paginated list.

```django
{% include "partials/_pagination.html" with
     page_obj=<Page> is_paginated=<bool> querystring=<str?> %}
```
- **Contract**: renders nothing when `is_paginated` is false; preserves `querystring`
  (active search/filters) on every page link; no Bootstrap `page-item`/`page-link` classes.

### `partials/_search_form.html` (existing — unchanged interface)
```django
{% include "partials/_search_form.html" with action=<url?> placeholder=<str?> %}
```
- **Contract**: remains the single search-bar source; behavior unchanged.

### `partials/_form_field.html` and `partials/_select_field.html` (existing)
Rendered via the inclusion tags below; control classes reference the shared `.form-input` / select
`@apply` atoms instead of inline-duplicated strings.

---

## Inclusion-tag contracts (`core/templatetags/form_tags.py`)

### `{% render_field %}`
```django
{% render_field field %}                {# field: a Django BoundField #}
```
- **Behavior**: renders label + control + help text + errors for text/email/password/textarea/file/
  date/checkbox widgets using the shared field partial. **Sole** field-rendering path (FR-004).
- **Invariant**: field name, label, help text, and validation output identical to pre-cleanup
  (FR-014).

### `{% render_select %}`
```django
{% render_select field %}
```
- **Behavior**: renders a `<select>` (single/multi) via the shared select partial with token styling.
- **Invariant**: options, selected state, and validation identical to pre-cleanup.

**Consumer migration** (from hand-rolled markup → these tags):
`registration/login.html`, `publications/publication_form.html`, advisor `<select>` in `apply.html`.

---

## CSS component-class contract (`static/src/input.css` → `output.css`)

Declared once in a `@layer components` block; usable as normal classes in any template. Names are the
contract; the `@apply` bodies below are the current utility strings and may be tuned so long as the
rendered appearance of already-correct pages is preserved (minimal-churn).

| Class | Purpose | Replaces (Findings F) |
|-------|---------|-----------------------|
| `.form-input` | text/email/password/textarea/date control | the ~90-char input string (×~15) |
| `.form-select` | select control | duplicated select classes in `_select_field.html` |
| `.btn-primary` | primary/submit action | primary-button string on every form |
| `.btn-secondary` | secondary/cancel action | secondary/cancel-button string on every form |
| `.card-surface` | list/card container surface | card string in publications + users lists |
| `.nav-link` | navbar item | the six repeated nav-link strings in `base.html` |

- **Contract**: exactly one definition per class (SC-003); each MUST use semantic design tokens
  (FR-007), not raw palette values; templates reference the class rather than re-declaring utilities;
  shared inline `style="…"` rules from Findings G are replaced by these classes/tokens.

---

## Asset-loading contract (`base.html`)

| Asset | Contract |
|-------|----------|
| Compiled CSS | `static/src/output.css` (+ `css/base.css` for genuinely global rules) — the only stylesheets loaded |
| Flowbite JS | one `{% static %}` reference to a committed, version-locked (4.0.1) `static/js/flowbite.min.js`; no CDN (FR-011) |
| Tagify | loaded **once** on pages that need it, one source, no duplication (FR-011 / SC-009) |
| Nav dropdown | well-formed `<li>`/`<div>` nesting (FR-012) |

---

## Behavioral guarantees (apply to every contract above)

1. **No behavioral change** — forms submit/validate identically; pagination paging identical; view
   context untouched (FR-014, SC-007).
2. **One source per element** — changing a component once updates all usages (SC-003).
3. **No orphaned-stylesheet classes** — zero Bootstrap-only classes remain (SC-001).
4. **Lint/build/tests green** — `djlint`, `npm run build`, and `manage.py test` all pass (SC-008).
