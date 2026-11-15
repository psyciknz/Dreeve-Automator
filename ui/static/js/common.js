"use strict";

/* Shared helpers: API client, DOM builder, toasts. */

const App = { revision: null, metaPromise: null };

class ApiError extends Error {
  constructor(status, message, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function api(method, url, body) {
  const headers = { Accept: "application/json" };
  if (method !== "GET" && App.revision) headers["X-Config-Revision"] = App.revision;
  const options = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(url, options);
  } catch (err) {
    throw new ApiError(0, "Network error: " + err.message);
  }
  let data = null;
  try { data = await response.json(); } catch (err) { /* not JSON */ }
  if (data && data.revision) App.revision = data.revision;
  if (!response.ok) {
    throw new ApiError(response.status, (data && data.error) || response.statusText, data);
  }
  return data;
}

function getMeta() {
  if (!App.metaPromise) App.metaPromise = api("GET", "/api/meta");
  return App.metaPromise;
}

function $(selector, scope = document) { return scope.querySelector(selector); }

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === false || value == null) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function toast(message, kind = "info") {
  const node = el("div", { class: "toast " + kind }, message);
  $("#toasts").append(node);
  setTimeout(() => node.remove(), kind === "error" ? 7000 : 2800);
}

function showError(container, message) {
  container.textContent = message;
  container.hidden = !message;
}

function formatTime(epochSeconds) {
  return epochSeconds ? new Date(epochSeconds * 1000).toLocaleString() : "never";
}
