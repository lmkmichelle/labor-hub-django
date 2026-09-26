document.addEventListener("DOMContentLoaded", async function () {
  const authors_input = document.querySelector("#authors-input");
  const editors_input = document.querySelector("#editors-input");
  const research_interests_input = document.querySelector("#research-interests-input");
  const topics_input = document.querySelector("#topics-input");

  function getRecommendedKeywords() {
    const el = document.getElementById("recommended-keywords-data");
    if (el) {
      try {
        return JSON.parse(el.textContent);
      } catch (e) {
        return [];
      }
    }
    return [];
  }

  const additional_keywords = getRecommendedKeywords();

  if (authors_input) {
    const authors_tag = new Tagify(authors_input, {
      whitelist: [],
      enforceWhitelist: false,
      dropdown: {
        closeOnSelect: false,
        enabled: 0,
        maxItems: 10,
        classname: "dropdown-panel",
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
  }

  if (editors_input) {
    // Same member search as authors; anyone not found is kept as a plain name.
    const editors_tag = new Tagify(editors_input, {
      whitelist: [],
      enforceWhitelist: false,
      dropdown: {
        closeOnSelect: false,
        enabled: 0,
        maxItems: 10,
        classname: "dropdown-panel",
      }
    });

    editors_tag.on('input', function (e) {
      fetch(`/api/accounts/search/?q=${encodeURIComponent(e.detail.value)}`)
        .then(res => res.json())
        .then(data => {
          editors_tag.settings.whitelist = data;
        });
    });
  }

  if (research_interests_input) {
    new Tagify(research_interests_input, {
      whitelist: additional_keywords,
      dropdown: {
        enabled: 0,
        closeOnSelect: false,
        maxItems: additional_keywords.length,
        classname: "dropdown-panel"
      }
    });
  }

  if (topics_input) {
    // Closed list: only the recommended vocabulary, no free entry. The server
    // (PublicationForm.clean_topics_input) re-checks this.
    new Tagify(topics_input, {
      whitelist: additional_keywords,
      enforceWhitelist: true,
      dropdown: {
        enabled: 0,
        closeOnSelect: false,
        maxItems: additional_keywords.length,
        classname: "dropdown-panel"
      },
      originalInputValueFormat: values =>
        JSON.stringify(values.map(v => ({value: v.value}))),
    });
  }
});
