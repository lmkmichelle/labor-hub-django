document.addEventListener("DOMContentLoaded", function() {
  const input = document.querySelector("#keywords-input");
  const tagify = new Tagify(input, {
    whitelist: [],
    enforceWhitelist: false,
    dropdown: {
      enabled: 1,
      maxItems: 5,
      position: 'auto',
    }
  });
})
