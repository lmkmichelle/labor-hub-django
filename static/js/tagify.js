document.addEventListener("DOMContentLoaded", async function () {
  const authors_input = document.querySelector("#authors-input");
  const keywords_input = document.querySelector("#keywords-input");
  const research_interests_input = document.querySelector("#research-interests-input");
  const topic_input = document.querySelector("#topic-input");

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
