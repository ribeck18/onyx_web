"use strict";

// Theme toggle. Flips the data-theme attribute and persists the choice in the
// `theme` cookie (read server-side on the next load so there is no flash). The
// whole UI repaints from CSS variables, so no reload is needed.
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

function set_theme(theme) {
  document.documentElement.dataset.theme = theme;
  document.cookie = `theme=${theme}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
  update_toggle_label(theme);
}

function update_toggle_label(theme) {
  const toggle = document.querySelector("[data-theme-toggle]");
  if (!toggle) {
    return;
  }
  // The label advertises the theme it switches to.
  toggle.textContent = theme === "light" ? "☾ Dark" : "☀ Light";
}

document.addEventListener("click", (event) => {
  const toggle = event.target.closest("[data-theme-toggle]");
  if (!toggle) {
    return;
  }
  const current = document.documentElement.dataset.theme;
  set_theme(current === "light" ? "dark" : "light");
});
