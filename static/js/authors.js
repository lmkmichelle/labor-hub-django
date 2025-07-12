document.addEventListener("DOMContentLoaded", function () {
  const input = document.querySelector("#authors-input");
  const tagify = new Tagify(input, {
    whitelist: [],
    enforceWhitelist: false,
    dropdown: {
      enabled: 1,
      maxItems: 10,
      position: 'auto',
    }
  });

  tagify.on('input', function (e) {
    const value = e.detail.value;
    fetch(`/api/accounts/search/?q=${encodeURIComponent(value)}`)
      .then(res => res.json())
      .then(data => {
        tagify.settings.whitelist = data;
        tagify.dropdown.show.call(tagify, value);
      });
  });
});
