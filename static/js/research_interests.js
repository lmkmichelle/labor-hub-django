import {JEL_PRIMARY_CHOICES} from "./const";

document.addEventListener("DOMContentLoaded", async function () {
  const input = document.querySelector("#research-interests-input");
  console.log(JEL_PRIMARY_CHOICES);
  const tagify = new Tagify(input, {
    whitelist: JEL_PRIMARY_CHOICES,
    enforceWhitelist: true,
    skipInvalid: true,
    delimiters: null,
    dropdown: {
      enabled: 1,
      maxItems: 4,
    },
    originalInputValueFormat: values =>
      JSON.stringify(values.map(v => ({value: v.value})))
  });

  tagify.on("input", (e) => {
    tagify.settings.whitelist = JEL_PRIMARY_CHOICES;
    tagify.dropdown.show.call(tagify, e.target.value);
  });
})
