# Vendored third-party JS

Per CLAUDE.md, no runtime CDN loads — third-party scripts are vendored here and served via
`{% static %}`.

- `flowbite.min.js` — Flowbite (see `package.json` for the pinned version).
- `cropper.min.js` — [Cropper.js](https://fengyuanchen.github.io/cropperjs) v1.6.2, MIT licensed.
  Used by `avatar-editor.js` for the Edit Profile picture crop/rotate/zoom control. Its stylesheet
  is vendored alongside at `static/css/cropper.min.css`.
