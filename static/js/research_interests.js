document.addEventListener("DOMContentLoaded", function() {
  const input = document.querySelector("#research-interests-input");
  const tagify = new Tagify(input, {
    whitelist: [],
    enforceWhitelist: false,
    dropdown: {
      enabled: 1,
      maxItems: 4,
      position: 'auto',
    }
  });
})
