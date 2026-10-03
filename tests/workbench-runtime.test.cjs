const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");
const { Blob } = require("node:buffer");

const APP_PATH = path.join(__dirname, "..", "docs", "workbench", "app.js");
const FIXTURE_DIR = path.join(__dirname, "..", "docs", "workbench", "fixtures");
const APP_SOURCE = fs.readFileSync(APP_PATH, "utf8");
const NativeURL = URL;

const ELEMENT_IDS = [
  "metrics-badge",
  "metrics-list",
  "metrics-meta",
  "reports",
  "specialist-count",
  "specialist-state",
  "input-badge",
  "compose",
  "guide-progress",
  "guide-hint",
  "copy-route",
  "load-demo",
  "load-failure",
  "load-adversarial",
  "record",
  "decision",
  "decision-detail",
  "integrity",
  "integrity-detail",
  "record-badge",
  "digest-comparison",
  "sealed-digest",
  "observed-digest",
  "record-foot-text",
  "record-foot-mark",
  "tamper",
  "export",
  "receipt-chips",
  "copy-receipt",
  "copy-status",
  "lab-card",
  "lab-state",
  "lab-core",
  "lab-readout",
  "lab-caption",
  "reset",
  "route-status",
];

function makeElement(id = "", tagName = "div", onClick = null) {
  const listeners = new Map();
  let textContent = "";
  const element = {
    id,
    tagName,
    innerHTML: "",
    className: "",
    disabled: false,
    hidden: false,
    value: "",
    href: "",
    download: "",
    style: {},
    dataset: {},
    attributes: {},
    removed: false,
    selected: false,
    addEventListener(type, handler) {
      listeners.set(type, handler);
    },
    dispatchEvent(event) {
      const handler = listeners.get(event.type);
      return handler ? handler.call(this, event) : true;
    },
    click() {
      if (onClick) return onClick(this);
      const handler = listeners.get("click");
      return handler ? handler.call(this, { currentTarget: this, target: this }) : undefined;
    },
    setAttribute(name, value) {
      this.attributes[name] = String(value);
    },
    getAttribute(name) {
      return this.attributes[name];
    },
    closest() {
      return this.statusCard || { dataset: {} };
    },
    select() {
      this.selected = true;
    },
    remove() {
      this.removed = true;
    },
  };
  Object.defineProperty(element, "textContent", {
    enumerable: true,
    get() {
      return textContent;
    },
    set(value) {
      textContent = String(value);
    },
  });
  return element;
}

function makeDom({ onAnchorClick } = {}) {
  const elements = new Map(ELEMENT_IDS.map((id) => [id, makeElement(id)]));
  const statusCards = new Map();
  for (const id of ["specialist-count", "decision", "integrity"]) {
    statusCards.set(id, { dataset: {} });
    elements.get(id).statusCard = statusCards.get(id);
  }
  const body = {
    children: [],
    appendChild(node) {
      this.children.push(node);
      return node;
    },
  };
  const document = {
    body,
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, makeElement(id));
      return elements.get(id);
    },
    createElement(tagName) {
      return makeElement("", tagName, tagName === "a" ? onAnchorClick : null);
    },
    execCommand() {
      return true;
    },
  };
  return { document, elements, statusCards };
}

function fixtureResponse(name) {
  const filename = path.join(FIXTURE_DIR, name);
  return {
    ok: true,
    async json() {
      return JSON.parse(fs.readFileSync(filename, "utf8"));
    },
  };
}

function makeFetch(mode = "files") {
  return async (requestUrl) => {
    if (mode === "missing") throw new Error(`fixture unavailable: ${requestUrl}`);
    const name = String(requestUrl).split("/").pop();
    return fixtureResponse(name);
  };
}

function makeUrlClass(capture) {
  class TestURL extends NativeURL {}
  TestURL.createObjectURL = (blob) => {
    capture.blob = blob;
    return "blob:workbench-test";
  };
  TestURL.revokeObjectURL = () => {};
  return TestURL;
}

function makeContext({ href = "https://workbench.test/docs/workbench/index.html", fetchMode = "files", fetchImpl = null, cryptoImpl = webcrypto } = {}) {
  let anchor;
  const dom = makeDom({
    onAnchorClick(node) {
      anchor = node;
    },
  });
  const urlCapture = {};
  const location = new NativeURL(href);
  const window = {
    location: { href, search: location.search },
    setTimeout,
  };
  const context = vm.createContext({
    console: { log() {}, warn() {}, error() {} },
    crypto: cryptoImpl,
    document: dom.document,
    fetch: fetchImpl || makeFetch(fetchMode),
    navigator: {},
    window,
    Blob,
    URL: makeUrlClass(urlCapture),
    URLSearchParams,
    TextEncoder,
    Uint8Array,
    JSON,
    Promise,
    Error,
    setTimeout,
    clearTimeout,
  });
  vm.runInContext(APP_SOURCE, context, { filename: APP_PATH });
  return { context, dom, anchor: () => anchor, urlCapture };
}

function read(context, expression) {
  return vm.runInContext(expression, context);
}

function readState(context) {
  return JSON.parse(read(context, "JSON.stringify(state)"));
}

function element(dom, id) {
  return dom.elements.get(id);
}

function tick() {
  return new Promise((resolve) => setImmediate(resolve));
}

async function settle(turns = 4) {
  for (let index = 0; index < turns; index += 1) {
    await Promise.resolve();
    await tick();
  }
}

async function waitFor(predicate, message, timeoutMs = 1500) {
  const started = Date.now();
  while (!predicate()) {
    if (Date.now() - started > timeoutMs) throw new Error(message);
    await tick();
  }
}

async function independentDigest(value) {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const hash = await webcrypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function loadAndCompose(harness, scenario = "passing") {
  await settle();
  await read(harness.context, `loadReports(${JSON.stringify(scenario)})`);
  await read(harness.context, "compose()");
  await settle();
}

test("passing compose seals the independently recomputed record and receipt text", async () => {
  const harness = makeContext();
  await loadAndCompose(harness);
  const state = readState(harness.context);
  assert.equal(state.record.status, "ready_for_review");
  assert.equal(state.originalDigest, await independentDigest(state.record));
  assert.equal(state.observedDigest, state.originalDigest);
  assert.equal(JSON.parse(element(harness.dom, "record").textContent).sha256, state.originalDigest);

  const receipt = read(harness.context, "receiptText()");
  assert.equal(receipt, `${element(harness.dom, "record").textContent}\n`);
  assert.deepEqual(JSON.parse(receipt), JSON.parse(element(harness.dom, "record").textContent));

  await read(harness.context, "exportRecord()");
  assert.ok(harness.urlCapture.blob, "export creates a blob");
  assert.equal(await harness.urlCapture.blob.text(), receipt);
  assert.equal(harness.anchor().download, "workbench-passing.json");
});

test("tamper persists the changed request and independently mismatches the sealed digest", async () => {
  const harness = makeContext();
  await loadAndCompose(harness);
  const sealed = readState(harness.context).originalDigest;

  await read(harness.context, "tamperRecord()");
  await settle();
  const state = readState(harness.context);
  assert.equal(state.record.request, "tampered request");
  assert.equal(state.observedDigest, await independentDigest(state.record));
  assert.notEqual(state.observedDigest, sealed);
  assert.equal(state.originalDigest, sealed);
  assert.equal(state.tampered, true);
  assert.match(element(harness.dom, "record").textContent, /tampered request/);
  assert.equal(element(harness.dom, "integrity").textContent, "REFUSED");
});

test("reset invalidates an in-flight compose digest so stale READY cannot return", async () => {
  let releaseDigest;
  let digestStartedResolve;
  const digestStarted = new Promise((resolve) => {
    digestStartedResolve = resolve;
  });
  const digestGate = new Promise((resolve) => {
    releaseDigest = resolve;
  });
  const cryptoImpl = {
    subtle: {
      async digest(...args) {
        digestStartedResolve();
        await digestGate;
        return webcrypto.subtle.digest(...args);
      },
    },
  };
  const harness = makeContext({ cryptoImpl });
  await settle();
  await read(harness.context, "loadReports('passing')");
  const pendingCompose = read(harness.context, "compose()");
  await digestStarted;
  await read(harness.context, "document.getElementById('reset').click()");
  releaseDigest();
  await pendingCompose;
  await settle();

  const state = readState(harness.context);
  assert.equal(state.record, null);
  assert.equal(state.reports.length, 0);
  assert.equal(element(harness.dom, "decision").textContent, "—");
  assert.equal(element(harness.dom, "integrity").textContent, "—");
  assert.equal(element(harness.dom, "record").textContent, "Load a scenario to create a bounded record.");
});

test("changing scenario during compose prevents the stale record from being installed", async () => {
  let releaseDigest;
  let digestStartedResolve;
  const digestStarted = new Promise((resolve) => {
    digestStartedResolve = resolve;
  });
  const digestGate = new Promise((resolve) => {
    releaseDigest = resolve;
  });
  const cryptoImpl = {
    subtle: {
      async digest(...args) {
        digestStartedResolve();
        await digestGate;
        return webcrypto.subtle.digest(...args);
      },
    },
  };
  const harness = makeContext({ cryptoImpl });
  await settle();
  await read(harness.context, "loadReports('passing')");
  const pendingCompose = read(harness.context, "compose()");
  await digestStarted;
  await read(harness.context, "loadReports('adversarial')");
  releaseDigest();
  await Promise.all([pendingCompose, settle()]);

  const state = readState(harness.context);
  assert.equal(state.scenario, "adversarial");
  assert.equal(state.record, null);
  assert.equal(state.originalDigest, null);
  assert.ok(state.reports.length > 0);
  assert.ok(state.reports.every((report) => report.ok === false));
  assert.equal(element(harness.dom, "decision").textContent, "—");
});

test("missing fixture fetch discloses and uses the embedded fallback", async () => {
  const harness = makeContext({ fetchMode: "missing" });
  await settle();
  await read(harness.context, "loadReports('passing')");
  await settle();
  const state = readState(harness.context);
  assert.equal(state.fixtureSource, "embedded");
  assert.deepEqual(state.reports.map((report) => report.name), ["context-integrity", "agent-proof", "atlas-receipt"]);
  assert.match(element(harness.dom, "guide-hint").textContent, /Embedded fallback fixture is active/);
  assert.equal(element(harness.dom, "specialist-count").textContent, "3");
});

test("routeUrl captures composed and tampered state, and boot replays it", async () => {
  const first = makeContext();
  await loadAndCompose(first);
  await read(first.context, "tamperRecord()");
  await settle();
  const route = read(first.context, "routeUrl()");
  const routeParams = new NativeURL(route).searchParams;
  assert.equal(routeParams.get("scenario"), "passing");
  assert.equal(routeParams.get("compose"), "1");
  assert.equal(routeParams.get("tamper"), "1");

  const replay = makeContext({ href: route });
  await waitFor(
    () => {
      const state = readState(replay.context);
      return state.record !== null && state.tampered === true;
    },
    `boot replay did not restore the composed tampered state: ${JSON.stringify(readState(replay.context))}`,
  );
  await settle();
  const replayed = readState(replay.context);
  assert.equal(replayed.scenario, "passing");
  assert.equal(replayed.record.request, "tampered request");
  assert.equal(replayed.tampered, true);
  assert.notEqual(replayed.originalDigest, replayed.observedDigest);
  assert.equal(new NativeURL(read(replay.context, "routeUrl()")).search, new NativeURL(route).search);
});

test("a user scenario change while boot is loading prevents stale route compose", async () => {
  let releaseFetch;
  let fetchCalls = 0;
  const fetchGate = new Promise((resolve) => {
    releaseFetch = resolve;
  });
  const delayedFetch = async (requestUrl) => {
    fetchCalls += 1;
    await fetchGate;
    return fixtureResponse(String(requestUrl).split("/").pop());
  };
  const harness = makeContext({
    href: "https://workbench.test/docs/workbench/index.html?scenario=passing&compose=1",
    fetchImpl: delayedFetch,
  });
  await waitFor(() => fetchCalls >= 3, "boot did not start its fixture reads");
  const userLoad = read(harness.context, "loadReports('adversarial')");
  releaseFetch();
  await userLoad;
  await settle();

  const state = readState(harness.context);
  assert.equal(state.scenario, "adversarial");
  assert.equal(state.record, null);
  assert.ok(state.reports.length > 0);
  assert.ok(state.reports.every((report) => report.ok === false));
  assert.equal(element(harness.dom, "decision").textContent, "—");
});
