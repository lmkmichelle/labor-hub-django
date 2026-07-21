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
  const defaultPanelHtml = panel.innerHTML;

  let currentMetric = "scholars"; // "scholars" | "papers" — drives map colouring
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

  function setMetric(metric) {
    currentMetric = metric;
    document.querySelectorAll(".map-toggle").forEach((btn) => {
      const isActive = btn.dataset.metric === metric;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    updateMapColors();
    applyPanelMetric();
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

  // Keep the default prompt available if we ever need to reset the panel.
  panel.dataset.defaultHtml = defaultPanelHtml;

  setMetric(currentMetric);
  loadSummary();
});
