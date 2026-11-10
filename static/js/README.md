# Vendored third-party JS

Per CLAUDE.md, no runtime CDN loads — third-party scripts are vendored here and served via
`{% static %}`.

- `flowbite.min.js` — Flowbite (see `package.json` for the pinned version).
- `cropper.min.js` — [Cropper.js](https://fengyuanchen.github.io/cropperjs) v1.6.2, MIT licensed.
  Used by `avatar-editor.js` for the Edit Profile picture crop/rotate/zoom control. Its stylesheet
  is vendored alongside at `static/css/cropper.min.css`.

- `vendor/tagify.min.js` — [Tagify](https://github.com/yairEO/tagify) v4.39.0, MIT licensed, pinned (it
  used to load unpinned from a CDN). Its stylesheet is `static/css/tagify.css`. `tagify.js` here is
  the project's own code that builds on it.

Fonts: Inter is self-hosted in `static/fonts/inter/` (SIL OFL 1.1, licence file alongside).

The paper-submission Authors field's reorder-by-author-name control (`tagify.js`'s
`addAuthorReorderButtons`) is plain move up/down buttons, no vendored drag library -- two earlier
attempts (`@yaireo/dragsort`, then `SortableJS/Sortable` with `forceFallback: true`) both hit
real drag-animation bugs (see `addAuthorReorderButtons`'s own comment for the details and links),
and buttons are the accessible baseline for this kind of reorder regardless (WCAG 2.2 SC 2.5.7
requires a non-drag alternative to any drag interaction).
