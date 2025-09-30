document.addEventListener("DOMContentLoaded", async function () {
  const input = document.querySelector("#keywords-input, #research-interests-input");
  const additional_keywords = [
    "Education and Human Capital",
    "Labor Supply",
    "Labor Demand",
    "Family and gender",
    "Unions and collective bargaining",
    "Active Labor Market Policies",
    "Migration",
    "AI and Technological change",
    "Macro-Labor",
    "Minimum wages",
    "Unemployment insurance",
    "Job search",
    "Labor markets and demographics",
    "Personnel economics",
    "Workers' health and well-being",
    "Contracts and Organizations",
    "Job amenities",
    "Market structure",
    "Welfare policy",
    "Applied and policy issues in labor economics",
    "Structural models of health, retirement, and savings",
    "Non-standard work",
    "Crime and Labor",
    "Geography of labor markets",
    "Intergenerational mobility",
    "Labor markets in less developed countries",
    "Econometric and data methods for labor economists",
    "Gig economy",
    "Inequality",
    "Other"
  ];


  new Tagify(input, {
    whitelist: additional_keywords,
    dropdown: {
      enabled: 0,
      closeOnSelect: false,
      maxItems: 5,
    },

    originalInputValueFormat: values =>
      JSON.stringify(values.map(v => ({value: v.value}))),
  });
});
