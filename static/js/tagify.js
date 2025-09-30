document.addEventListener("DOMContentLoaded", async function () {
  const authors_input = document.querySelector("#authors-input");
  const keywords_input = document.querySelector("#keywords-input");
  const research_interests_input = document.querySelector("#research-interests-input");
  const topic_input = document.querySelector("#topic-input");
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

  const authors_tag = new Tagify(authors_input, {
    whitelist: [],
    enforceWhitelist: false,
    dropdown: {
      closeOnSelect: false,
      enabled: 0,
      maxItems: 10,
    }
  });

  authors_tag.on('input', function (e) {
    const value = e.detail.value;
    fetch(`/api/accounts/search/?q=${encodeURIComponent(value)}`)
      .then(res => res.json())
      .then(data => {
        authors_tag.settings.whitelist = data;
      });
  });

  const topic_tag = new Tagify(topic_input);
  const research_interests_tag = new Tagify(research_interests_input, {
    whitelist: additional_keywords,
    dropdown: {
      enabled: 0,
      closeOnSelect: false,
      maxItems: 10,
      scroll
    }
  });

  const keywords_tag = new Tagify(keywords_input, {
    whitelist: additional_keywords,
    dropdown: {
      enabled: 0,
      closeOnSelect: false,
      maxItems: 10,
      classnames: "tags__dropdown"
    },

    originalInputValueFormat: values =>
      JSON.stringify(values.map(v => ({value: v.value}))),
  });
});
