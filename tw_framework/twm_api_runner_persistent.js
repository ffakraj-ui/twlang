/* eslint-disable no-console */
// TWLang persistent .twm API runner. — v0.8.51
//
// Unlike twm_api_runner.js (which spawns, handles ONE request, then exits),
// this runner stays alive as a persistent process. Python communicates via
// stdin/stdout using newline-delimited JSON (JSON Lines protocol).
//
// Protocol:
//   Python → stdin:  {"handlerPath": "...", "method": "GET", "path": "...", ...}
//   Node   → stdout: {"status": 200, "body": "...", "content_type": "...", ...}
//
// Special commands:
//   {"__reload": true}              → clear handler cache
//   {"__ping": true}                → health check (responds {"__pong": true})
//
// This eliminates the ~100ms Node.js startup overhead per request.

"use strict";

const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { createRequire } = require("module");

// ── Handler cache: compiled modules stay in memory ──────────────────────
const handlerCache = new Map(); // compiledPath → { exports, error }

// v0.9.08 FIX #87: Cache findProjectRoot result
const _projectRootCache = new Map();

function findProjectRoot(startPath) {
    if (_projectRootCache.has(startPath)) return _projectRootCache.get(startPath);
  let current = path.resolve(startPath || process.cwd());
  if (!fs.existsSync(current)) current = path.dirname(current);
  if (fs.existsSync(current) && fs.statSync(current).isFile()) current = path.dirname(current);
  while (true) {
    if (
      fs.existsSync(path.join(current, "package.json")) ||
      fs.existsSync(path.join(current, "tw.config")) ||
      fs.existsSync(path.join(current, "[home]"))
    ) return current;
    const parent = path.dirname(current);
    if (parent === current) return process.cwd();
    _projectRootCache.set(startPath, result);
    current = parent;
  }
}

// Reuse helpers from the original runner
function normalizeHeaderValue(headers, key) {
  if (!headers || typeof headers !== "object") return undefined;
  const target = String(key || "").toLowerCase();
  for (const [name, value] of Object.entries(headers)) {
    if (String(name).toLowerCase() === target) return value;
  }
  return undefined;
}

function normalizeHttpData(rawText, headers) {
  const contentType = String(normalizeHeaderValue(headers, "content-type") || "").toLowerCase();
  // v0.9.08 FIX #90: Exact match for application/json
        if (contentType === "application/json" || contentType.startsWith("application/json+")) {
    try { return JSON.parse(rawText); } catch { return rawText; }
  }
  return rawText;
}

function createTimeoutSignal(timeoutMs) {
  const timeout = Number(timeoutMs || 0);
  if (!Number.isFinite(timeout) || timeout <= 0) return { signal: null };  // v0.9.08 FIX #89
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return { signal: AbortSignal.timeout(timeout) };
  }
  if (typeof AbortController === "undefined") return {};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new Error(`Request timeout after ${timeout}ms`)), timeout);
  return { signal: controller.signal, cleanup() { clearTimeout(timer); } };
}

// v0.9.08 FIX #88: Cache http helpers
let _cachedHttpHelpers = null;
let _cachedHttpHeaders = null;

function buildHttpHelpers(defaultHeaders) {
    if (_cachedHttpHelpers && _cachedHttpHeaders === defaultHeaders) return _cachedHttpHelpers;
    _cachedHttpHeaders = defaultHeaders;
  async function request(url, options = {}) {
    if (typeof fetch !== "function") throw new Error("Global `fetch` is not available. Use Node.js 18+.");
    const opts = options && typeof options === "object" ? { ...options } : {};
    const method = String(opts.method || "GET").toUpperCase();
    const headers = { ...(defaultHeaders || {}), ...(opts.headers || {}) };
    let body = opts.body;
    const hasContentType = Object.keys(headers).some((n) => String(n).toLowerCase() === "content-type");
    if (body !== undefined && body !== null && typeof body === "object" && !Buffer.isBuffer(body) && typeof body !== "string") {
      if (!hasContentType) headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    const timeoutCtl = createTimeoutSignal(opts.timeout || opts.timeoutMs || 0);
    try {
      const response = await fetch(url, { ...opts, method, headers, body, signal: timeoutCtl.signal || opts.signal });
      const text = await response.text();
      const responseHeaders = Object.fromEntries(response.headers.entries());
      return { ok: response.ok, status: response.status, statusText: response.statusText, url: response.url, headers: responseHeaders, text, data: normalizeHttpData(text, responseHeaders) };
    } finally {
      if (typeof timeoutCtl.cleanup === "function") timeoutCtl.cleanup();
    }
  }
  return {
    request,
    get(url, options = {}) { return request(url, { ...options, method: "GET" }); },
    post(url, body, options = {}) { return request(url, { ...options, method: "POST", body }); },
    put(url, body, options = {}) { return request(url, { ...options, method: "PUT", body }); },
    patch(url, body, options = {}) { return request(url, { ...options, method: "PATCH", body }); },
    delete(url, options = {}) { return request(url, { ...options, method: "DELETE" }); },
  };
}

// ── Load and cache a compiled handler ───────────────────────────────────
function loadHandler(compiledPath) {
  if (handlerCache.has(compiledPath)) {
    return handlerCache.get(compiledPath);
  }
  try {
    // Clear from require cache if previously loaded
    try { delete require.cache[compiledPath]; } catch (e) { console.error('Cache delete failed:', e.message); }  // v0.9.08 FIX #94
    const projectRoot = findProjectRoot(compiledPath);
    const localRequire = createRequire(path.join(projectRoot, "__twm_dummy.js"));
    const exports = localRequire(compiledPath);
    const entry = { exports, error: null };
    handlerCache.set(compiledPath, entry);
    return entry;
  } catch (err) {
    const entry = { exports: null, error: err };
    handlerCache.set(compiledPath, entry);
    return entry;
  }
}

// ── Execute one request ────────────────────────────────────────────────
async function handleRequest(req) {
  const compiledPath = req.handlerPath;
  const entry = loadHandler(compiledPath);

  if (entry.error) {
    return {
      status: 500,
      content_type: "application/json; charset=utf-8",
      body: JSON.stringify({ error: "Handler load failed", detail: entry.error.message }),
      headers: [],
      cookies: [],
    };
  }

  const mod = entry.exports || {};
  const method = String(req.method || "GET").toUpperCase();
  const fnName = method.toLowerCase();

  // Find handler function: get, post, put, patch, delete, options, or fallback "handler"
  let handler = mod[fnName] || mod.handler;
  if (typeof handler !== "function") {
    return {
      status: 405,
      content_type: "application/json; charset=utf-8",
      body: JSON.stringify({ error: `Method ${method} not allowed`, allowed: Object.keys(mod).filter((k) => typeof mod[k] === "function") }),
      headers: [],
      cookies: [],
    };
  }

  // Build request context
  const request = {
    method,
    path: req.path,
    query: req.query || {},
    body: req.body,
    headers: req.headers || {},
    cookies: req.cookies || {},
    env: req.env || {},
    project_root: req.project_root || process.cwd(),
  };

  // Attach http helpers
  const http = buildHttpHelpers(request.headers);
  request.http = http;
  request.fetch = http.request;

  // Execute
  let result;
  try {
    result = await handler(request);
  } catch (err) {
    return {
      status: 500,
      content_type: "application/json; charset=utf-8",
      body: JSON.stringify({ error: "Handler execution failed", detail: err.message, stack: process.env.NODE_ENV === "development" ? err.stack : undefined }),
      headers: [],
      cookies: [],
    };
  }

  // Normalize response
  let status = 200;
  let content_type = "application/json; charset=utf-8";
  let headers_out = [];
  let cookies_out = [];
  let body_val = result;

  if (result && typeof result === "object" && !Array.isArray(result)) {
    if (result.status !== undefined && result.status !== null) {  // v0.9.08 FIX #91
            status = parseInt(result.status, 10);
            if (isNaN(status) || status < 0) status = 200;
        }
    if (result.content_type) content_type = String(result.content_type);
    if (result.headers) {
      if (Array.isArray(result.headers)) headers_out = result.headers;
      else if (typeof result.headers === "object") headers_out = Object.entries(result.headers);
    }
    if (result.cookies) {
      if (Array.isArray(result.cookies)) cookies_out = result.cookies;
      else if (typeof result.cookies === "object") cookies_out = Object.entries(result.cookies);
    }
    if (result.body !== undefined) body_val = result.body;
  } else if (Array.isArray(result)) {
    body_val = (result[0] !== undefined && result[0] !== null) ? String(result[0]) : "";  // v0.9.08 FIX #95
    if (result[1] !== undefined && result[1] !== null) {  // v0.9.08 FIX #95
                status = parseInt(result[1], 10);
                if (isNaN(status) || status < 0) status = 200;
            }
    if (result[2]) headers_out = Object.entries(result[2]);
  }

  let body_bytes;
  if (typeof body_val === "string") {
    body_bytes = body_val;
    // v0.9.08 FIX #96: Only flip if user did NOT explicitly set content type
        if (content_type === "application/json; charset=utf-8" && !result.headers) content_type = "text/plain; charset=utf-8";
  } else if (typeof body_val === "object" && body_val !== null) {
    body_bytes = JSON.stringify(body_val);
  } else {
    body_bytes = String(body_val || "");
  }

  return { status, content_type, body: body_bytes, headers: headers_out, cookies: cookies_out };
}

// ── Main: JSON Lines protocol over stdin/stdout ────────────────────────
const rl = readline.createInterface({ input: process.stdin, terminal: false });

rl.on("line", async (line) => {
  try {
    const req = JSON.parse(line);

    // Special: health check
    if (req.__ping) {
      process.stdout.write(JSON.stringify({ __pong: true, handlers_cached: handlerCache.size }) + "\n");
      return;
    }

    // Special: reload handler cache
    if (req.__reload) {
      handlerCache.clear();
      process.stdout.write(JSON.stringify({ __reloaded: true }) + "\n");
      return;
    }

    // Normal request
    const response = await handleRequest(req);
    // v0.9.08 FIX #92: Handle backpressure
        const data = JSON.stringify(response) + "\n";
        if (!process.stdout.write(data)) {
            await new Promise(resolve => process.stdout.once("drain", resolve));
        }
  } catch (err) {
    process.stdout.write(JSON.stringify({
      status: 500,
      content_type: "application/json; charset=utf-8",
      body: JSON.stringify({ error: "Runner error", detail: err.message }),
      headers: [],
      cookies: [],
    }) + "\n");
  }
});

rl.on("close", () => {
  process.exit(0);
});

// Signal ready
process.stdout.write(JSON.stringify({ __ready: true }) + "\n");
