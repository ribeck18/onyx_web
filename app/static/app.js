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

// Multipart sender for the file-upload modals (submit/return). The browser sets
// the multipart boundary, so no Content-Type is provided. Blank optional fields
// are dropped so an empty comments box arrives as absent, not "".
async function send_form(method, url, form) {
  const data = new FormData(form);
  for (const [name, value] of [...data.entries()]) {
    if (value === "" || (value instanceof File && value.size === 0 && value.name === "")) {
      data.delete(name);
    }
  }
  return fetch(url, { method, body: data });
}

function json_payload(form) {
  // Named, enabled fields into an object, omitting blank optional values.
  const payload = {};
  for (const field of form.querySelectorAll("[name]:not([disabled])")) {
    const value = field.value.trim();
    if (value !== "" || field.required) {
      payload[field.name] = value;
    }
  }
  return payload;
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

function clear_errors(scope) {
  const error = scope.querySelector("[data-modal-error]");
  if (error) {
    error.hidden = true;
    error.textContent = "";
  }
  for (const field_error of scope.querySelectorAll("[data-field-error]")) {
    field_error.hidden = true;
    field_error.textContent = "";
  }
}

function open_modal(overlay) {
  clear_errors(overlay);
  overlay.hidden = false;
  const first_input = overlay.querySelector("input, textarea, select");
  if (first_input) {
    first_input.focus();
  }
}

function close_modal(overlay) {
  // While a submit is in flight the modal is locked: every dismissal route
  // (Cancel/close buttons, Escape, backdrop click) funnels through here, so one
  // guard covers them all.
  const pending_form = overlay.querySelector("[data-modal-form]");
  if (pending_form && pending_form.dataset.pending === "true") {
    return;
  }
  overlay.hidden = true;
  if (overlay.dataset.tokenCreated === "true") {
    location.reload();
  }
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
  submit.hidden = false;

  const token_fields = overlay.querySelector("[data-token-fields]");
  const token_secret_box = overlay.querySelector("[data-token-secret-box]");
  const token_secret = overlay.querySelector("[data-token-secret]");
  const footer_close = overlay.querySelector(".modal-footer [data-modal-close]");
  delete overlay.dataset.tokenCreated;
  if (token_fields) {
    token_fields.hidden = false;
  }
  if (token_secret_box) {
    token_secret_box.hidden = true;
  }
  if (token_secret) {
    token_secret.textContent = "";
  }
  if (footer_close) {
    footer_close.textContent = "Cancel";
  }

  // The optional intro line adapts per trigger (e.g. Submit vs Revise copy).
  const intro = overlay.querySelector("[data-modal-intro]");
  if (intro) {
    intro.textContent = trigger.dataset.intro || "";
    intro.hidden = !trigger.dataset.intro;
  }

  // Some fields belong to create mode only (e.g. VDI notes have their own box on
  // the detail page). Hide and disable them in edit mode so they leave the form
  // entirely — disabled fields are skipped when the payload is collected.
  const is_edit = trigger.dataset.mode === "edit";
  for (const create_only of form.querySelectorAll("[data-create-only]")) {
    create_only.hidden = is_edit;
    for (const control of create_only.querySelectorAll("input, textarea, select")) {
      control.disabled = is_edit;
    }
  }

  // Reset, then pre-fill from the optional JSON payload on the trigger.
  form.reset();
  // JSA decision modal: form.reset() restores the blank Decision option but
  // not its JS-driven JSON state, so remove a previously mounted reject field.
  const jsa_decision = form.querySelector("[data-jsa-decision]");
  if (jsa_decision) {
    delete form.dataset.encoding;
    set_jsa_reject_field(form, false);
  }
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

function set_jsa_reject_field(form, is_reject) {
  const reject_field = form.querySelector("[data-jsa-reject-only]");
  if (!is_reject) {
    if (reject_field) {
      reject_field.remove();
    }
    return;
  }
  if (reject_field) {
    return;
  }
  const reject_template = form.querySelector("[data-jsa-reject-template]");
  if (!reject_template) {
    return;
  }
  reject_template.before(reject_template.content.cloneNode(true));
}

function show_modal_error(form, message) {
  const error = form.querySelector("[data-modal-error]");
  if (error) {
    error.textContent = message;
    error.hidden = false;
  }
}

// Lock or unlock the modal around an in-flight submit. The submit button is
// disabled and relabeled (its idle label is stashed for restore), the close
// controls are disabled, and the aria-live status line is shown. Form fields are
// left enabled on purpose — disabling them would drop them from FormData and the
// json_payload selector, silently breaking the request.
function set_modal_pending(form, is_pending) {
  const submit = form.querySelector("[data-modal-submit]");
  const status = form.querySelector("[data-modal-status]");
  const status_text = form.querySelector("[data-modal-status-text]");
  const progress = form.querySelector("[data-modal-progress]");
  const closers = form.querySelectorAll("[data-modal-close]");
  // Multipart file uploads show an indeterminate bar and an upload-specific
  // label; everything else just shows the status line and "Saving…".
  const is_upload = form.dataset.encoding === "multipart";
  const busy_label = is_upload ? "Uploading…" : "Saving…";
  if (is_pending) {
    form.dataset.pending = "true";
    if (submit) {
      submit.dataset.idleLabel = submit.textContent;
      submit.textContent = busy_label;
      submit.disabled = true;
    }
    for (const closer of closers) {
      closer.disabled = true;
    }
    if (status_text) {
      status_text.textContent = busy_label;
    }
    if (progress) {
      progress.hidden = !is_upload;
    }
    if (status) {
      status.hidden = false;
    }
    return;
  }
  delete form.dataset.pending;
  if (submit) {
    if (submit.dataset.idleLabel !== undefined) {
      submit.textContent = submit.dataset.idleLabel;
      delete submit.dataset.idleLabel;
    }
    submit.disabled = false;
  }
  for (const closer of closers) {
    closer.disabled = false;
  }
  if (progress) {
    progress.hidden = true;
  }
  if (status) {
    status.hidden = true;
  }
}

function missing_required(form) {
  return Array.from(form.querySelectorAll("[required]:not([disabled])")).some(
    (field) => field.value.trim() === "",
  );
}

function show_field_error(form, message) {
  // A field-level error (e.g. the duplicate item_number 409) renders inline under
  // its own field; fall back to the modal-wide error when there is no such slot.
  const field_error = form.querySelector("[data-field-error]");
  if (field_error) {
    field_error.textContent = message;
    field_error.hidden = false;
    return true;
  }
  return false;
}

async function submit_modal_form(form) {
  // Ignore re-entry (double-clicks, repeated Enter) while a submit is in flight.
  if (form.dataset.pending === "true") {
    return;
  }
  if (missing_required(form)) {
    show_modal_error(
      form,
      form.dataset.requiredMessage || "Please fill in all required fields.",
    );
    return;
  }

  clear_errors(form);
  if (form.closest('[data-modal="token-modal"]')) {
    await submit_token_form(form);
    return;
  }
  set_modal_pending(form, true);
  const response =
    form.dataset.encoding === "multipart"
      ? await send_form(form.dataset.method, form.dataset.url, form)
      : await send_json(form.dataset.method, form.dataset.url, json_payload(form));
  if (response.ok) {
    location.reload();
    return;
  }
  set_modal_pending(form, false);
  const message = await error_message_from(response);
  // A duplicate item_number is a 409 the user fixes in one field — render it
  // there; anything else is a modal-wide error.
  if (response.status === 409 && show_field_error(form, message)) {
    return;
  }
  show_modal_error(form, message);
}

async function submit_token_form(form) {
  set_modal_pending(form, true);
  const response = await send_json(form.dataset.method, form.dataset.url, json_payload(form));
  if (!response.ok) {
    set_modal_pending(form, false);
    show_modal_error(form, await error_message_from(response));
    return;
  }
  // The token modal does not reload on success, so clear pending here — before the
  // secret is revealed — to re-enable the footer close button, expose its "Done"
  // relabel, and release the modal-close guard so the user can read and close it.
  set_modal_pending(form, false);
  const body = await response.json();
  const overlay = form.closest("[data-modal]");
  const token_fields = form.querySelector("[data-token-fields]");
  const token_secret_box = form.querySelector("[data-token-secret-box]");
  const token_secret = form.querySelector("[data-token-secret]");
  const submit = form.querySelector("[data-modal-submit]");
  const footer_close = form.querySelector(".modal-footer [data-modal-close]");

  overlay.dataset.tokenCreated = "true";
  if (token_fields) {
    token_fields.hidden = true;
  }
  if (token_secret_box) {
    token_secret_box.hidden = false;
  }
  if (token_secret) {
    token_secret.textContent = body.secret;
  }
  if (submit) {
    submit.hidden = true;
  }
  if (footer_close) {
    footer_close.textContent = "Done";
  }
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

async function delete_row(row) {
  if (!window.confirm(row.dataset.deleteConfirm)) {
    return;
  }
  const response = await fetch(row.dataset.deleteUrl, { method: "DELETE" });
  if (response.ok) {
    location.reload();
  }
}

// ------------------------------------------------------------ user actions

// The admin users screen mutates with one-shot row buttons (deactivate, promote,
// delete, …) rather than a modal. Each carries its own method + URL and an
// optional confirm prompt; a 2xx reloads (or follows data-redirect when the
// page itself is being deleted), anything else surfaces the reason.
async function handle_user_action(button) {
  const confirm_message = button.dataset.confirm;
  if (confirm_message && !window.confirm(confirm_message)) {
    return;
  }
  const response = await fetch(button.dataset.url, { method: button.dataset.method });
  if (response.ok) {
    if (button.dataset.redirect) {
      location.assign(button.dataset.redirect);
    } else {
      location.reload();
    }
    return;
  }
  window.alert(await error_message_from(response));
}

// ------------------------------------------------------------------- notes

// Notes are the one in-place mutation: PATCH the notes, then update the saved
// baseline and flash "Saved" without reloading the page.
async function save_notes(button) {
  const box = button.closest("[data-notes]");
  const input = box.querySelector("[data-notes-input]");
  const response = await send_json("PATCH", box.dataset.notesUrl, {
    notes: input.value,
  });
  if (!response.ok) {
    return;
  }
  // The saved value becomes the new baseline so Save re-disables until the next
  // edit; defaultValue is what the "changed?" check compares against.
  input.defaultValue = input.value;
  button.disabled = true;
  flash_saved(box);
}

function flash_saved(box) {
  const saved = box.querySelector("[data-notes-saved]");
  if (!saved) {
    return;
  }
  saved.hidden = false;
  clearTimeout(box.saved_timer);
  box.saved_timer = setTimeout(() => {
    saved.hidden = true;
  }, 2200);
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

  // The header filename and DOWNLOAD link follow the active tab. The link
  // carries ?download=1 so the active file is saved rather than served inline.
  const filename = preview.querySelector("[data-preview-filename]");
  if (filename) {
    filename.textContent = tab.dataset.filename;
  }
  const open_link = preview.querySelector("[data-preview-open]");
  if (open_link) {
    open_link.href = `${tab.dataset.fileUrl}?download=1`;
  }
}

// --------------------------------------------------- document version panes

// Every version of a Project Document is pre-rendered as a hidden preview pane;
// clicking a timeline entry swaps the visible pane in place (no navigation).
// The header title, filename, and DOWNLOAD link follow the viewed version, and
// the accent node plus the VIEWING tag move to the clicked entry.
function switch_doc_version(entry) {
  const preview = document.querySelector("[data-doc-preview]");
  if (!preview) {
    return;
  }
  const version_id = entry.dataset.docVersion;
  for (const pane of preview.querySelectorAll("[data-doc-pane]")) {
    pane.hidden = pane.dataset.docPane !== version_id;
  }

  const is_current = entry.dataset.isCurrent === "true";
  const title = preview.querySelector("[data-preview-title]");
  if (title) {
    title.textContent = is_current
      ? "CURRENT VERSION"
      : `VERSION ${entry.dataset.versionNumber}`;
  }
  const filename = preview.querySelector("[data-preview-filename]");
  if (filename) {
    filename.textContent = entry.dataset.filename;
  }
  const open_link = preview.querySelector("[data-preview-open]");
  if (open_link) {
    open_link.href = `${entry.dataset.fileUrl}?download=1`;
  }

  // Editing metadata only makes sense against the current version, so Edit is
  // grayed out while an older version is on screen. A disabled button fires no
  // click, so the modal-open delegation needs no extra guard.
  const edit_button = document.querySelector("[data-doc-edit]");
  if (edit_button) {
    edit_button.disabled = !is_current;
  }

  // The current entry keeps its static CURRENT tag; older entries reveal their
  // VIEWING tag only while their pane is on screen.
  for (const timeline_entry of document.querySelectorAll("[data-doc-version]")) {
    const is_viewed = timeline_entry === entry;
    const node = timeline_entry.querySelector(".timeline-node");
    if (node) {
      node.classList.toggle("is-current", is_viewed);
    }
    const viewing_tag = timeline_entry.querySelector("[data-doc-viewing]");
    if (viewing_tag) {
      viewing_tag.hidden = !is_viewed;
    }
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

  const doc_version_entry = event.target.closest("[data-doc-version]");
  if (doc_version_entry) {
    switch_doc_version(doc_version_entry);
    return;
  }

  const notes_save = event.target.closest("[data-notes-save]");
  if (notes_save) {
    save_notes(notes_save);
    return;
  }

  const user_action = event.target.closest("[data-user-action]");
  if (user_action) {
    handle_user_action(user_action);
    return;
  }

  // While a grid is armed, a card click deletes instead of navigating.
  const card = event.target.closest("[data-project-card]");
  if (card && card.closest(".is-deleting")) {
    event.preventDefault();
    delete_project(card);
    return;
  }

  // A generic delete-row contract keeps VDI and RFI list delete mode on the
  // same small interaction path while preserving each row's own confirmation.
  const row_to_delete = event.target.closest("[data-delete-row]");
  if (row_to_delete && row_to_delete.closest(".is-deleting")) {
    event.preventDefault();
    delete_row(row_to_delete);
    return;
  }

  // Any row carrying data-row-href navigates as a whole; inner links and
  // buttons keep their own behavior, so only bare-row clicks fall through.
  const link_row = event.target.closest("[data-row-href]");
  if (link_row) {
    if (!event.target.closest("a, button")) {
      window.location.href = link_row.dataset.rowHref;
    }
    return;
  }

  // The whole VDI row is a link; deletion was handled by the generic contract
  // above, so this branch only keeps the normal navigation behavior.
  const vdi_row = event.target.closest("[data-vdi-row]");
  if (vdi_row) {
    event.preventDefault();
    window.location = vdi_row.dataset.href;
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-modal-form]");
  if (form) {
    event.preventDefault();
    submit_modal_form(form);
  }
});

// The JSA decision modal routes one form to two endpoints. Choosing Reject
// mounts its file field, which prevents a stale JS asset from leaving a rendered
// but permanently disabled upload control in the modal.
document.addEventListener("change", (event) => {
  const decision = event.target.closest("[data-jsa-decision]");
  if (!decision) {
    return;
  }
  const form = decision.closest("[data-modal-form]");
  const option = decision.selectedOptions[0];
  const is_reject = decision.value === "reject";

  form.dataset.url = (option && option.dataset.url) || form.dataset.url;
  if (is_reject) {
    form.dataset.encoding = "multipart";
  } else {
    delete form.dataset.encoding;
  }

  set_jsa_reject_field(form, is_reject);
});

// Save notes is enabled only while the textarea differs from the saved value.
document.addEventListener("input", (event) => {
  const notes_input = event.target.closest("[data-notes-input]");
  if (notes_input) {
    const box = notes_input.closest("[data-notes]");
    const save = box.querySelector("[data-notes-save]");
    if (save) {
      save.disabled = notes_input.value === notes_input.defaultValue;
    }
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
