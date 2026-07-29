const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const project_root = join(__dirname, "..");

function load_list_filter(rows) {
  let input_handler;
  const input = {
    value: "",
    addEventListener(event_name, handler) {
      if (event_name === "input") {
        input_handler = handler;
      }
    },
  };
  const table = {
    hidden: false,
    querySelectorAll(selector) {
      return selector === "[data-list-filter-row]" ? rows : [];
    },
  };
  const count = { textContent: "" };
  const no_results = { hidden: true };
  const elements = new Map([
    ["[data-list-filter-input]", input],
    ["[data-list-filter-table]", table],
    ["[data-list-filter-count]", count],
    ["[data-list-filter-no-results]", no_results],
  ]);
  const list_filter = {
    querySelector(selector) {
      return elements.get(selector);
    },
  };
  const document = {
    querySelectorAll(selector) {
      return selector === "[data-list-filter]" ? [list_filter] : [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
  };
  const source = readFileSync(join(project_root, "app/static/app.js"), "utf8");
  vm.runInNewContext(source, { document });

  return { count, input, no_results, table, trigger: () => input_handler() };
}

test("list filter replaces the table only for a non-empty zero-match query", () => {
  const rows = [
    { dataset: { listFilterText: "Concrete Mix Design" }, hidden: false },
    { dataset: { listFilterText: "Steel Shop Drawings" }, hidden: false },
  ];
  const filter = load_list_filter(rows);

  filter.input.value = "missing";
  filter.trigger();
  assert.equal(filter.table.hidden, true);
  assert.equal(filter.no_results.hidden, false);
  assert.equal(filter.count.textContent, "0 of 2");

  filter.input.value = "steel";
  filter.trigger();
  assert.equal(filter.table.hidden, false);
  assert.equal(filter.no_results.hidden, true);
  assert.deepEqual(rows.map((row) => row.hidden), [true, false]);

  filter.input.value = "";
  filter.trigger();
  assert.equal(filter.table.hidden, false);
  assert.equal(filter.no_results.hidden, true);
  assert.equal(filter.count.textContent, "Showing all 2");
  assert.deepEqual(rows.map((row) => row.hidden), [false, false]);
});

test("narrow list-filter headers wrap without affecting other headers", () => {
  const css = readFileSync(join(project_root, "app/static/style.css"), "utf8");

  assert.match(
    css,
    /\.list-filter \.section-header,\n  \.list-filter \.gallery-header \{ align-items: stretch; flex-wrap: wrap; \}/,
  );
  assert.doesNotMatch(css, /^\s*\.(?:section|gallery)-header \{ align-items: stretch; flex-wrap: wrap; \}$/m);
});
