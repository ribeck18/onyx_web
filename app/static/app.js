"use strict";

// ------------------------------------------------------------------ theme

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

// ------------------------------------------------------------ fetch helper

// One wrapper for every JSON mutation. On a 2xx the page reloads so it re-renders
// from the server; on a non-2xx the caller is handed the error message to show
// inline, with the user's input left untouched.
async function send_json(method, url, payload) {
  const options = { method, headers: { "Content-Type": "application/json" } };
  if (payload !== undefined) {
    options.body = JSON.stringify(payload);
  }
  return fetch(url, options);
}

async function error_message_from(response) {
  // FastAPI puts the reason in `detail` (a string, or a list for validation
  // errors). Fall back to a generic line if the body is not the expected shape.
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail) && body.detail.length) {
      return body.detail[0].msg || "Something went wrong. Please try again.";
    }
  } catch (parse_error) {
    // No JSON body; fall through to the generic message.
  }
  return "Something went wrong. Please try again.";
}

// ------------------------------------------------------------------ modal

function open_modal(overlay) {
  const error = overlay.querySelector("[data-modal-error]");
  if (error) {
    error.hidden = true;
    error.textContent = "";
  }
  overlay.hidden = false;
  const first_input = overlay.querySelector("input, textarea, select");
  if (first_input) {
    first_input.focus();
  }
}

function close_modal(overlay) {
  overlay.hidden = true;
}

function configure_modal(overlay, trigger) {
  // Same markup, two modes: the trigger's data-* attributes set the title,
  // submit label, target URL/method, and (edit) pre-filled values.
  const form = overlay.querySelector("[data-modal-form]");
  const title = overlay.querySelector("[data-modal-title]");
  const submit = overlay.querySelector("[data-modal-submit]");

  form.dataset.method = trigger.dataset.method || "POST";
  form.dataset.url = trigger.dataset.url || "";
  if (title && trigger.dataset.title) {
    title.textContent = trigger.dataset.title;
  }
  if (submit && trigger.dataset.submitLabel) {
    submit.textContent = trigger.dataset.submitLabel;
  }

  // Reset, then pre-fill from the optional JSON payload on the trigger.
  form.reset();
  if (trigger.dataset.prefill) {
    const values = JSON.parse(trigger.dataset.prefill);
    for (const [name, value] of Object.entries(values)) {
      const field = form.elements.namedItem(name);
      if (field) {
        field.value = value === null ? "" : value;
      }
    }
  }
}

function show_modal_error(form, message) {
  const error = form.querySelector("[data-modal-error]");
  if (error) {
    error.textContent = message;
    error.hidden = false;
  }
}

function missing_required(form) {
  return Array.from(form.querySelectorAll("[required]")).some(
    (field) => field.value.trim() === "",
  );
}

async function submit_modal_form(form) {
  if (missing_required(form)) {
    show_modal_error(
      form,
      form.dataset.requiredMessage || "Please fill in all required fields.",
    );
    return;
  }

  // Collect named fields into a JSON payload, omitting blank optional values.
  const payload = {};
  for (const field of form.querySelectorAll("[name]")) {
    const value = field.value.trim();
    if (value !== "" || field.required) {
      payload[field.name] = value;
    }
  }

  const response = await send_json(form.dataset.method, form.dataset.url, payload);
  if (response.ok) {
    location.reload();
    return;
  }
  show_modal_error(form, await error_message_from(response));
}

// -------------------------------------------------------------- delete mode

function delete_grid_for(toggle) {
  return document.getElementById(toggle.dataset.deleteToggle);
}

function toggle_delete_mode(toggle) {
  const grid = delete_grid_for(toggle);
  if (!grid) {
    return;
  }
  const arming = !grid.classList.contains("is-deleting");
  grid.classList.toggle("is-deleting", arming);
  toggle.classList.toggle("is-active", arming);
  toggle.textContent = arming ? "Done" : "Delete";
}

async function delete_project(card) {
  const number = card.dataset.projectNumber;
  const name = card.dataset.projectName;
  const confirmed = window.confirm(
    `Delete project ${number} — ${name}? This removes all its vendor data items.`,
  );
  if (!confirmed) {
    return;
  }
  const response = await fetch(`/api/projects/${card.dataset.projectId}`, {
    method: "DELETE",
  });
  if (response.ok) {
    location.reload();
  }
}

// ----------------------------------------------------------- preview tabs

function switch_preview_tab(tab) {
  const preview = tab.closest(".preview");
  if (!preview) {
    return;
  }
  const target = tab.dataset.previewTab;

  for (const button of preview.querySelectorAll("[data-preview-tab]")) {
    button.classList.toggle("is-active", button === tab);
  }
  for (const panel of preview.querySelectorAll("[data-preview-panel]")) {
    panel.hidden = panel.dataset.previewPanel !== target;
  }

  // The header filename and OPEN link follow the active tab.
  const filename = preview.querySelector("[data-preview-filename]");
  if (filename) {
    filename.textContent = tab.dataset.filename;
  }
  const open_link = preview.querySelector("[data-preview-open]");
  if (open_link) {
    open_link.href = tab.dataset.fileUrl;
  }
}

// --------------------------------------------------------- event delegation

document.addEventListener("click", (event) => {
  const theme_toggle = event.target.closest("[data-theme-toggle]");
  if (theme_toggle) {
    const current = document.documentElement.dataset.theme;
    set_theme(current === "light" ? "dark" : "light");
    return;
  }

  const open_trigger = event.target.closest("[data-modal-open]");
  if (open_trigger) {
    const overlay = document.querySelector(
      `[data-modal="${open_trigger.dataset.modalOpen}"]`,
    );
    if (overlay) {
      configure_modal(overlay, open_trigger);
      open_modal(overlay);
    }
    return;
  }

  const close_trigger = event.target.closest("[data-modal-close]");
  if (close_trigger) {
    close_modal(close_trigger.closest("[data-modal]"));
    return;
  }

  // A click on the overlay backdrop (but not the panel) closes the modal.
  if (event.target.matches("[data-modal]")) {
    close_modal(event.target);
    return;
  }

  const delete_toggle = event.target.closest("[data-delete-toggle]");
  if (delete_toggle) {
    toggle_delete_mode(delete_toggle);
    return;
  }

  const preview_tab = event.target.closest("[data-preview-tab]");
  if (preview_tab) {
    switch_preview_tab(preview_tab);
    return;
  }

  // While a grid is armed, a card click deletes instead of navigating.
  const card = event.target.closest("[data-project-card]");
  if (card && card.closest(".is-deleting")) {
    event.preventDefault();
    delete_project(card);
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-modal-form]");
  if (form) {
    event.preventDefault();
    submit_modal_form(form);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    const open_overlay = document.querySelector("[data-modal]:not([hidden])");
    if (open_overlay) {
      close_modal(open_overlay);
    }
  }
});
