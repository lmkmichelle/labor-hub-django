
document.addEventListener("DOMContentLoaded", async function () {
  const url = "{% static 'data/jel_primary.json' %}";
  const JEL_PRIMARY_CHOICES =
    [
  "General Economics and Teaching",
  "History of Economic Thought, Methodology, and Heterodox Approaches",
  "Mathematical and Quantitative Methods",
  "Microeconomics",
  "Macroeconomics and Monetary Economics",
  "International Economics",
  "Financial Economics",
  "Public Economics",
  "Health, Education, and Welfare",
  "Labor and Demographic Economics",
  "Law and Economics",
  "Industrial Organization",
  "Business Administration and Business Economics • Marketing • Accounting • Personnel Economics",
  "Economic History",
  "Economic Development, Innovation, Technological Change, and Growth",
  "Political Economy and Comparative Economic Systems",
  "Agricultural and Natural Resource Economics • Environmental and Ecological Economics",
  "Urban, Rural, Regional, Real Estate, and Transportation Economics",
  "Miscellaneous Categories",
  "Other Special Topics"
]

  const input = document.querySelector("#keywords-input");

  const tagify = new Tagify(input, {
    whitelist: JEL_PRIMARY_CHOICES,                 // full hardcoded list
    enforceWhitelist: true,         // must pick from list
    skipInvalid: true,
    delimiters: null,               // don't split on commas inside labels
    dropdown: {
      enabled: 1,                   // show on focus / when typing
      maxItems: 100,
    },
    originalInputValueFormat: items => JSON.stringify(items.map(i => i.value)),
  });

  tagify.on("input", (e) => {
    tagify.settings.whitelist = JEL_PRIMARY_CHOICES;
    tagify.dropdown.show.call(tagify, e.target.value);
  });
});
