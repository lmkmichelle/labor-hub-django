# Implementation Plan: Flowbite Frontend Cleanup & Consolidation

**Branch**: `001-flowbite-frontend-cleanup` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-flowbite-frontend-cleanup/spec.md`

## Summary

Finish the half-completed migration from **Bootstrap 5 + django-crispy-forms + HTMX** to
**TailwindCSS v4 + Flowbite**. Today the codebase carries two overlapping style systems, but only
the Tailwind/Flowbite stylesheet is loaded — so pages still using Bootstrap markup render unstyled,
and the same UI concepts (list cards, form fields, buttons, pagination) are re-implemented five
different ways.

Technical approach (per resolved clarifications): a **minimal-churn, presentation-only** refactor.
Pages already correct in Flowbite are preserved as-is; only broken Bootstrap pages are brought up to
the existing Flowbite design system. Duplication is removed with a **blended abstraction**:
reusable **template partials/inclusion-tags** for structural components (list/card item, pagination,
buttons, page chrome) plus a small set of **Tailwind `@apply` component classes in
`static/src/input.css`** for atomic form-control styling (compiled into the single committed
`output.css`). The dead legacy stack (crispy-forms, crispy-bootstrap5, django-htmx) and its
settings/config are removed. No data model, URL, view-behavior, form-field, or validation changes.
A constitution amendment (Principle III) reconciles governance with the new stack.

## Technical Context

**Language/Version**: Python 3 / Django 5.2.3 (local dev verified on Python 3.14.6 via `py`).

**Primary Dependencies**: Django 5.2.3; TailwindCSS v4 (`@tailwindcss/cli` ^4.1.18, CSS-first — no
`tailwind.config.js`); Flowbite ^4.0.1 (npm) + `flowbite-typography`; Tagify (tag input);
`django-compressor` (static pipeline). **Being removed**: `django-crispy-forms`,
`crispy-bootstrap5`, `django-htmx`.

**Storage**: N/A for this feature — presentation-only; no models, migrations, or queries change.

**Testing**: `djlint` (template lint gate, required); `python manage.py test` (Django suite — see
Constitution Check note: apps currently ship empty `tests.py` stubs); `npm run build` (Tailwind
build must succeed and produce `output.css`); manual visual validation via [quickstart.md](./quickstart.md).

**Target Platform**: Server-rendered Django web app; modern browsers. Eventual host: Media3 managed
Linux (no Node at runtime — CSS is prebuilt and `output.css` is committed).

**Project Type**: Web application — single Django project, multi-app (`accounts`, `publications`,
`events`, `seminars`, `core`), server-rendered templates with a shared `templates/` + `static/`
tree. Not a split frontend/backend repo.

**Performance Goals**: No change intended; preserve current behavior. Asset-loading changes (Flowbite
JS, Tagify) must not regress page weight or the `collectstatic`/compressor pipeline.

**Constraints**: Presentation-only (no data/logic/field/validation change — FR-014). Minimal-churn:
preserve appearance of already-correct Flowbite pages; fix only broken Bootstrap pages. Core flows
usable without JavaScript (Flowbite/Tagify/datepicker are progressive enhancements). Accessibility
preserved (labels, keyboard, contrast). `djlint` and the test suite must pass (FR-013, SC-008).

**Scale/Scope**: ~1 base template, 6 shared partials, ~12 app templates, 2 template-tag field
partials, 3 `forms.py`, `settings.py`, `requirements.txt`, `input.css`, `base.html` asset loads.
Consolidations: 5 list systems → 1 shared component; ~15 duplicated input-class strings → 1
`@apply` class; per-page pagination markup → 1 shared partial; hand-rolled form fields → the single
`render_field`/`render_select` path.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` **v1.0.0**.

| Principle | Assessment |
|-----------|------------|
| **I. Code Quality** | **Advanced by this feature.** Removes dead code, unused imports, commented blocks, and duplication (DRY); keeps the `djlint` gate. Fully aligned. |
| **II. Testing Standards** | **Conditional.** Apps currently have empty `tests.py` stubs, so `manage.py test` passes trivially. This is a *rendering-defect* fix; the pragmatic regression guard is lightweight **view smoke tests** (HTTP 200 + template renders) for the touched pages — recommended in research, not a spec FR. The suite MUST pass (SC-008). No behavioral/form change (FR-014) so form logic is preserved by construction. |
| **III. User Experience Consistency** | **CONFLICT (justified, resolved).** The principle *mandates* forms via `django-crispy-forms` + Bootstrap 5 pack and HTMX as progressive enhancement — the exact stack this feature removes. Resolution: **FR-015 amends the constitution** (Principle III) to codify the Tailwind/Flowbite component approach; tracked in Complexity Tracking. All other clauses of III (extend base templates, reuse partials, consistent messaging/empty states, no-JS core flows, accessibility) are *strengthened* by this work. |
| **IV. Performance Requirements** | **Neutral / aligned.** No query, pagination-behavior, or view changes. Static-asset change (Flowbite JS from build-consistent local static, Tagify loaded once) stays within the `collectstatic`/compressor pipeline the principle requires. |
| **Technology & Security Standards** | Removing unused pinned deps keeps `requirements.txt` honest; deviations recorded here and in the spec. No auto-escaping disabled; no auth/upload/secret changes. |
| **Development Workflow & Quality Gates** | Gates that apply here — `djlint` + full test suite — are enforced (FR-013, SC-008). No migrations involved. Constitution amendment ships as a reviewed change per the Amendments rule. |

**Gate result**: **PASS** with one justified, tracked deviation (Principle III conflict → resolved
by the in-scope constitution amendment, FR-015). No *unjustified* violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-flowbite-frontend-cleanup/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature specification (already authored)
├── research.md          # Phase 0 output (/speckit.plan)
├── data-model.md        # Phase 1 output — UI component/presentation contracts
├── quickstart.md        # Phase 1 output — validation/run guide
├── contracts/           # Phase 1 output — template + CSS component interfaces
│   └── ui-components.md
├── checklists/
│   └── requirements.md  # Spec quality checklist (PASS)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
nole/                         # Django project package
├── settings.py               # INSTALLED_APPS + CRISPY_* to prune (FR-008); compressor stays
└── urls.py

accounts/  events/  publications/  seminars/   # feature apps (models, views, urls, forms, tests.py)
├── forms.py                  # accounts/events: dead crispy FormHelper/Layout to remove (FR-008);
│                             # accounts: dead import + commented block (FR-010)
└── ...

core/
└── templatetags/form_tags.py # render_field / render_select — the canonical field abstraction (FR-004)

templates/                    # shared, server-rendered templates
├── base.html                 # page shell: nav (markup bug FR-012), asset loads (FR-011), nav-link dup (FR-006)
├── partials/
│   ├── _list_display.html        # Bootstrap list-group  → fold into unified list component (FR-002)
│   ├── _publications_list.html    # Flowbite card list    → basis of unified list component
│   ├── _form_field.html           # Flowbite field partial (dedupe per-widget classes, FR-005)
│   ├── _select_field.html         # Flowbite select partial
│   ├── _search_form.html          # shared search bar (keep as single source)
│   └── _pagination.html           # NEW shared pagination component (FR-003)
├── accounts/ events/ publications/ seminars/  # per-app list/detail/form templates (see page inventory)
└── registration/ (login.html)      # hand-rolled fields → render_field (FR-004)

static/
├── src/input.css             # Tailwind v4 CSS-first entry → add @layer components (@apply atoms, FR-006)
├── src/output.css            # compiled, committed CSS (rebuilt via `npm run build`)
├── css/base.css              # global non-utility CSS (world-map etc.) — not the dedup mechanism
└── js/                       # tagify.js; add version-locked flowbite.min.js served via {% static %} (FR-011)

package.json                  # build/watch scripts (Tailwind CLI)
requirements.txt              # drop django-crispy-forms, crispy-bootstrap5, django-htmx (FR-008/009)
.specify/memory/constitution.md  # amend Principle III (FR-015)
```

**Structure Decision**: Single Django project (multi-app), server-rendered. All cleanup lands in the
shared `templates/` tree, `static/src/input.css` (component classes), `core/templatetags/`
(field abstraction), and three apps' `forms.py`/`settings.py`/`requirements.txt` for dead-stack
removal. No new app, package, or split-repo structure is introduced.

## Complexity Tracking

Only one deviation requires justification — an intentional, in-scope governance change, not added
implementation complexity.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Amend Constitution Principle III (crispy+Bootstrap5+HTMX mandate) — a MAJOR governance change | The current principle mandates the exact stack the user asked to remove; leaving it makes the finished cleanup permanently non-compliant | "Keep the stack to satisfy the constitution" defeats the feature's purpose; "ignore the conflict" would knowingly ship against governance. Amending is the honest, reviewed path (per the constitution's own Amendments rule). |

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 (research.md, data-model.md, contracts/, quickstart.md).*

- **I. Code Quality** — Design consolidates every shared element to one source (data-model +
  contracts) and enumerates all dead-code removals; DRY and cleanliness are improved, not eroded. ✅
- **II. Testing Standards** — Quickstart defines the validation gates (`djlint`, `manage.py test`,
  `npm run build`) and a page-by-page render check; research recommends minimal view smoke tests as
  the regression guard for the rendering fixes. No form/logic behavior changes. ✅ (conditional item
  from the pre-gate is satisfied by the validation plan)
- **III. UX Consistency** — Design keeps all pages on the shared base + partials, one field path,
  consistent empty/error states, no-JS-safe core flows, accessibility preserved; the Principle III
  amendment (FR-015) remains the tracked, in-scope resolution. ✅ (with amendment)
- **IV. Performance** — Asset-loading design keeps Flowbite JS/Tagify within `collectstatic`; no
  query/pagination-behavior change. ✅

**Result**: No new violations introduced by the design. Gate remains **PASS** with the single tracked
Principle III amendment. Ready for `/speckit.tasks`.
