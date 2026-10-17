/**
 * World Map interactions.
 *
 * - Loads compact per-country counts (`/api/map/summary/`) and colours each
 *   country by the currently highlighted metric (scholars or papers).
 * - On country click, fetches a server-rendered panel fragment
 *   (`/api/map/country/<code>/`) and injects it into the side panel, so the card
 *   markup stays identical to the rest of the site.
 *
 * Endpoint URLs come from `data-*` attributes on #map-app (built with Django's
 * {% url %}), so routing stays in one place.
 */
document.addEventListener("DOMContentLoaded", () => {
  const app = document.getElementById("map-app");
  const panel = document.getElementById("map-panel");
  if (!app || !panel) {
    return;
  }

  const summaryUrl = app.dataset.summaryUrl;
  const detailUrlTemplate = app.dataset.detailUrl;
  const introText = panel.textContent.trim();
  const TOP_COUNTRIES = 8;

  // A linked-in metric (e.g. "?metric=papers" from the Scholars/Papers pages)
  // picks which toggle is active on load; otherwise default to scholars.
  const requestedMetric = new URLSearchParams(window.location.search).get("metric");
  let currentMetric = requestedMetric === "papers" ? "papers" : "scholars"; // drives map colouring
  let summary = {}; // { CODE: { scholars: n, papers: n } }
  let selectedCode = null;

  const landPaths = () => document.querySelectorAll("#map-wrap path.land");

  function updateMapColors() {
    landPaths().forEach((path) => {
      const info = summary[path.id];
      const count = info ? info[currentMetric] || 0 : 0;
      path.classList.toggle("has-data", count > 0);
      path.classList.toggle("selected", path.id === selectedCode);
    });
  }

  // Country names come from the SVG paths' title attribute.
  function countryName(code) {
    const path = document.querySelector(`#map-wrap path.land[id="${code}"]`);
    return (path && path.getAttribute("title")) || code;
  }

  // The panel's resting state: the countries with the most fellows / papers,
  // each a button that opens the country just like clicking it on the map.
  function renderCountryList() {
    const label = currentMetric === "papers" ? "papers" : "fellows";
    const rows = Object.entries(summary)
      .map(([code, info]) => [code, (info && info[currentMetric]) || 0])
      .filter(([, count]) => count > 0)
      .sort((a, b) => b[1] - a[1] || countryName(a[0]).localeCompare(countryName(b[0])))
      .slice(0, TOP_COUNTRIES);

    const heading = document.createElement("h3");
    heading.className = "text-lg font-semibold text-heading";
    heading.textContent = `Top countries by ${label}`;
    const intro = document.createElement("p");
    intro.className = "mt-1 mb-3 text-sm text-body";
    intro.textContent = introText;
    const list = document.createElement("ul");
    list.className = "m-0 flex list-none flex-col p-0";
    rows.forEach(([code, count]) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.countryCode = code;
      button.className =
        "flex w-full items-center justify-between rounded px-2 py-2 text-left text-sm hover:bg-neutral-secondary-medium";
      const name = document.createElement("span");
      name.className = "font-medium text-heading";
      name.textContent = countryName(code);
      const total = document.createElement("span");
      total.className = "text-body";
      total.textContent = String(count);
      button.append(name, total);
      item.appendChild(button);
      list.appendChild(item);
    });
    panel.replaceChildren(heading, intro, list);
  }

  function showCountryList() {
    selectedCode = null;
    updateMapColors();
    renderCountryList();
  }

  function setMetric(metric) {
    currentMetric = metric;
    document.querySelectorAll(".map-toggle").forEach((btn) => {
      const isActive = btn.dataset.metric === metric;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    updateMapColors();
    if (selectedCode) {
      applyPanelMetric();
    } else {
      renderCountryList();
    }
  }

  // The panel fragment holds both a scholars and a papers section; show only the
  // one matching the highlighted metric so the toggle drives the panel too.
  function applyPanelMetric() {
    panel.querySelectorAll(".map-panel-section").forEach((section) => {
      section.classList.toggle("hidden", section.dataset.metric !== currentMetric);
    });
  }

  function clearPanelSelection() {
    const selection = window.getSelection ? window.getSelection() : null;
    if (selection && selection.rangeCount > 0 && panel.contains(selection.anchorNode)) {
      selection.removeAllRanges();
    }
  }

  function renderPanel(html) {
    panel.innerHTML = html;
    applyPanelMetric();
    // Replacing the panel's content removes the node that held the document's
    // text caret, so the browser re-collapses the caret to the start of the new
    // content (the country name). Drop that stray selection if it landed here so
    // no blinking cursor appears in the panel. Clear again on the next frame in
    // case the live-region announcement re-places it asynchronously.
    clearPanelSelection();
    requestAnimationFrame(clearPanelSelection);
  }

  async function loadSummary() {
    try {
      const response = await fetch(summaryUrl);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      summary = await response.json();
      updateMapColors();
      if (!selectedCode) {
        renderCountryList();
      }
    } catch (err) {
      console.error("Failed to load map summary:", err);
    }
  }

  async function showCountry(code) {
    selectedCode = code;
    updateMapColors();
    panel.setAttribute("aria-busy", "true");
    try {
      const url = detailUrlTemplate.replace("__CODE__", encodeURIComponent(code));
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      renderPanel(await response.text());
    } catch (err) {
      console.error("Failed to load country details:", err);
      renderPanel(
        '<div class="rounded-base border border-default bg-neutral-primary-soft p-6 text-center text-sm text-body">' +
          "Sorry, we couldn't load details for this country. Please try again." +
          "</div>",
      );
    } finally {
      panel.removeAttribute("aria-busy");
    }
  }

  document.querySelectorAll(".map-toggle").forEach((btn) => {
    btn.addEventListener("click", () => setMetric(btn.dataset.metric));
  });

  landPaths().forEach((path) => {
    path.addEventListener("click", () => showCountry(path.id));
  });

  // One delegated listener covers the list rows and the fragment's back button.
  panel.addEventListener("click", (event) => {
    const row = event.target.closest("[data-country-code]");
    if (row) {
      showCountry(row.dataset.countryCode);
    } else if (event.target.closest("[data-map-back]")) {
      showCountryList();
    }
  });

  setMetric(currentMetric);
  loadSummary();
});
