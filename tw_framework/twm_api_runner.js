/* eslint-disable no-console */
// TWLang server-side `.twm` API runner.
//
// Usage:
//   node twm_api_runner.js /abs/path/to/compiled_module.cjs
//
// Reads request JSON from stdin and prints ONE JSON response to stdout.

"use strict";

const fs = require("fs");
const path = require("path");
const { createRequire } = require("module");

function findProjectRoot(startPath) {
  let current = path.resolve(startPath || process.cwd());
  if (!fs.existsSync(current)) {
    current = path.dirname(current);
  }
  if (fs.existsSync(current) && fs.statSync(current).isFile()) {
    current = path.dirname(current);
  }
  while (true) {
    if (
      fs.existsSync(path.join(current, "package.json")) ||
      fs.existsSync(path.join(current, "tw.config")) ||
      fs.existsSync(path.join(current, "[home]"))
    ) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) {
      return process.cwd();
    }
    current = parent;
  }
}

function readJsonFile(filePath, fallbackValue) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    return fallbackValue;
  }
}

function normalizeHeaderValue(headers, key) {
  if (!headers || typeof headers !== "object") return undefined;
  const target = String(key || "").toLowerCase();
  for (const [name, value] of Object.entries(headers)) {
    if (String(name).toLowerCase() === target) return value;
  }
  return undefined;
}

function createTimeoutSignal(timeoutMs) {
  const timeout = Number(timeoutMs || 0);
  if (!Number.isFinite(timeout) || timeout <= 0) return {};
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return { signal: AbortSignal.timeout(timeout) };
  }
  if (typeof AbortController === "undefined") {
    return {};
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new Error(`Request timeout after ${timeout}ms`)), timeout);
  return {
    signal: controller.signal,
    cleanup() {
      clearTimeout(timer);
    },
  };
}

function normalizeHttpData(rawText, headers) {
  const contentType = String(normalizeHeaderValue(headers, "content-type") || "").toLowerCase();
  if (contentType.includes("application/json")) {
    try {
      return JSON.parse(rawText);
    } catch (error) {
      return rawText;
    }
  }
  return rawText;
}

function buildHttpHelpers(defaultHeaders) {
  async function request(url, options = {}) {
    if (typeof fetch !== "function") {
      throw new Error("Global `fetch` is not available. Use Node.js 18+ for built-in http helpers.");
    }
    const opts = options && typeof options === "object" ? { ...options } : {};
    const method = String(opts.method || "GET").toUpperCase();
    const headers = { ...(defaultHeaders || {}), ...(opts.headers || {}) };
    let body = opts.body;
    const hasContentType = Object.keys(headers).some((name) => String(name).toLowerCase() === "content-type");
    if (
      body !== undefined &&
      body !== null &&
      typeof body === "object" &&
      !Buffer.isBuffer(body) &&
      !(body instanceof URLSearchParams) &&
      typeof body !== "string"
    ) {
      if (!hasContentType) headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    const timeoutCtl = createTimeoutSignal(opts.timeout || opts.timeoutMs || 0);
    try {
      const response = await fetch(url, {
        ...opts,
        method,
        headers,
        body,
        signal: timeoutCtl.signal || opts.signal,
      });
      const text = await response.text();
      const responseHeaders = Object.fromEntries(response.headers.entries());
      return {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        url: response.url,
        headers: responseHeaders,
        text,
        data: normalizeHttpData(text, responseHeaders),
      };
    } finally {
      if (typeof timeoutCtl.cleanup === "function") timeoutCtl.cleanup();
    }
  }

  return {
    request,
    get(url, options = {}) {
      return request(url, { ...options, method: "GET" });
    },
    post(url, body, options = {}) {
      return request(url, { ...options, method: "POST", body });
    },
    put(url, body, options = {}) {
      return request(url, { ...options, method: "PUT", body });
    },
    patch(url, body, options = {}) {
      return request(url, { ...options, method: "PATCH", body });
    },
    delete(url, options = {}) {
      return request(url, { ...options, method: "DELETE" });
    },
  };
}

function buildValueHelper(values, label) {
  const source = values && typeof values === "object" ? { ...values } : {};
  const api = {
    get(name, fallbackValue = undefined) {
      return Object.prototype.hasOwnProperty.call(source, name) ? source[name] : fallbackValue;
    },
    has(name) {
      return Object.prototype.hasOwnProperty.call(source, name);
    },
    require(name) {
      if (!Object.prototype.hasOwnProperty.call(source, name) || source[name] === "") {
        throw new Error(`Missing ${label}: ${name}`);
      }
      return source[name];
    },
    all() {
      return { ...source };
    },
  };
  return new Proxy(api, {
    get(target, prop) {
      if (prop in target) return target[prop];
      if (typeof prop === "string" && Object.prototype.hasOwnProperty.call(source, prop)) {
        return source[prop];
      }
      return undefined;
    },
    has(target, prop) {
      return prop in target || (typeof prop === "string" && Object.prototype.hasOwnProperty.call(source, prop));
    },
  });
}

function createProjectRequire(projectRoot) {
  const packageJsonPath = path.join(projectRoot, "package.json");
  if (fs.existsSync(packageJsonPath)) {
    return createRequire(packageJsonPath);
  }
  return createRequire(__filename);
}

function createPackageHelper(projectRoot) {
  const projectRequire = createProjectRequire(projectRoot);
  const packageJson = readJsonFile(path.join(projectRoot, "package.json"), {});
  return {
    json() {
      return { ...packageJson };
    },
    has(name) {
      const deps = {
        ...((packageJson && packageJson.dependencies) || {}),
        ...((packageJson && packageJson.devDependencies) || {}),
      };
      return Object.prototype.hasOwnProperty.call(deps, name);
    },
    require(name) {
      try {
        return projectRequire(name);
      } catch (error) {
        if (error && (error.code === "MODULE_NOT_FOUND" || String(error.message || "").includes("Cannot find module"))) {
          throw new Error(
            `Package \`${name}\` nahi mila. Isko project ke package.json me add karke \`npm install ${name}\` chalao.`
          );
        }
        throw error;
      }
    },
    resolve(name) {
      return projectRequire.resolve(name);
    },
  };
}

function parseServiceAccount(rawValue, projectRoot) {
  if (!rawValue) return null;
  if (typeof rawValue === "object") return rawValue;
  const text = String(rawValue).trim();
  if (!text) return null;
  if (text.startsWith("{")) {
    return JSON.parse(text);
  }
  const absolutePath = path.isAbsolute(text) ? text : path.join(projectRoot, text);
  return readJsonFile(absolutePath, null);
}

function createFirebaseHelper(projectRoot, envHelper, packageHelper) {
  function loadAdmin() {
    return packageHelper.require("firebase-admin");
  }

  function resolveCredential(admin) {
    const inlineJson =
      envHelper.get("FIREBASE_SERVICE_ACCOUNT_JSON") ||
      envHelper.get("FIREBASE_ADMIN_CREDENTIALS_JSON") ||
      envHelper.get("GOOGLE_APPLICATION_CREDENTIALS_JSON");
    const parsedInline = parseServiceAccount(inlineJson, projectRoot);
    if (parsedInline) {
      return admin.credential.cert(parsedInline);
    }
    const filePath =
      envHelper.get("FIREBASE_SERVICE_ACCOUNT_PATH") ||
      envHelper.get("FIREBASE_ADMIN_CREDENTIALS_PATH") ||
      envHelper.get("GOOGLE_APPLICATION_CREDENTIALS");
    const parsedFile = parseServiceAccount(filePath, projectRoot);
    if (parsedFile) {
      return admin.credential.cert(parsedFile);
    }
    return undefined;
  }

  function app(options = {}) {
    const admin = loadAdmin();
    if (Array.isArray(admin.apps) && admin.apps.length > 0) {
      return admin.app();
    }
    const initOptions = { ...(options || {}) };
    if (!initOptions.credential) {
      const credential = resolveCredential(admin);
      if (credential) initOptions.credential = credential;
    }
    if (!initOptions.projectId) {
      initOptions.projectId = envHelper.get("FIREBASE_PROJECT_ID") || envHelper.get("GOOGLE_CLOUD_PROJECT");
    }
    return admin.initializeApp(initOptions);
  }

  return {
    admin: loadAdmin,
    app,
    firestore() {
      return app().firestore();
    },
    auth() {
      return app().auth();
    },
    messaging() {
      return app().messaging();
    },
    storage() {
      return app().storage();
    },
  };
}

function installRuntimeHelpers(request, compiledPath) {
  const projectRoot = findProjectRoot(
    (request && request.project_root) || compiledPath || process.cwd()
  );
  const envHelper = buildValueHelper((request && request.env) || {}, "env value");
  const secretsHelper = buildValueHelper((request && request.env) || {}, "secret");
  const httpHelper = buildHttpHelpers({
    Accept: "application/json, text/plain;q=0.9, */*;q=0.8",
  });
  const packageHelper = createPackageHelper(projectRoot);
  const firebaseHelper = createFirebaseHelper(projectRoot, envHelper, packageHelper);
  globalThis.http = httpHelper;
  globalThis.env = envHelper;
  globalThis.secrets = secretsHelper;
  globalThis.pkg = packageHelper;
  globalThis.firebase = firebaseHelper;
  globalThis.helpers = {
    http: httpHelper,
    env: envHelper,
    secrets: secretsHelper,
    pkg: packageHelper,
    firebase: firebaseHelper,
    projectRoot,
  };
}

function toPairs(headers) {
  if (!headers) return [];
  if (Array.isArray(headers)) return headers;
  if (typeof headers === "object") return Object.entries(headers);
  return [];
}

function normalizeResult(result) {
  // Allowed return shapes:
  // - string
  // - object (auto JSON), or object with {json|text|html|body,status,headers,cookies}
  // - tuple-like array: [body, status] or [body, status, headers]
  let status = 200;
  let headers = [];
  let cookies = [];

  // Tuple: [body, status, headers]
  if (Array.isArray(result)) {
    const body = result[0];
    status = Number(result[1] ?? 200) || 200;
    headers = toPairs(result[2]);
    if (typeof body === "string") {
      return { status, content_type: "text/plain; charset=utf-8", body, headers, cookies };
    }
    return {
      status,
      content_type: "application/json; charset=utf-8",
      body: JSON.stringify(body),
      headers,
      cookies,
    };
  }

  if (typeof result === "string") {
    return { status: 200, content_type: "text/plain; charset=utf-8", body: result, headers: [], cookies: [] };
  }

  if (result && typeof result === "object") {
    status = Number(result.status ?? 200) || 200;
    headers = toPairs(result.headers);
    cookies = Array.isArray(result.cookies) ? result.cookies : toPairs(result.cookies);

    if (Object.prototype.hasOwnProperty.call(result, "json")) {
      const payload = result.json;
      return {
        status,
        content_type: "application/json; charset=utf-8",
        body: typeof payload === "string" ? payload : JSON.stringify(payload),
        headers,
        cookies,
      };
    }
    if (Object.prototype.hasOwnProperty.call(result, "html")) {
      return { status, content_type: "text/html; charset=utf-8", body: String(result.html ?? ""), headers, cookies };
    }
    if (Object.prototype.hasOwnProperty.call(result, "text")) {
      return { status, content_type: "text/plain; charset=utf-8", body: String(result.text ?? ""), headers, cookies };
    }
    if (Object.prototype.hasOwnProperty.call(result, "body")) {
      const bodyVal = result.body;
      const ct = String(result.content_type || result.contentType || "text/plain; charset=utf-8");
      if (bodyVal && typeof bodyVal === "object" && ct.includes("application/json")) {
        return { status, content_type: ct, body: JSON.stringify(bodyVal), headers, cookies };
      }
      return { status, content_type: ct, body: typeof bodyVal === "string" ? bodyVal : JSON.stringify(bodyVal), headers, cookies };
    }

    // Default: treat object as JSON
    return {
      status,
      content_type: "application/json; charset=utf-8",
      body: JSON.stringify(result),
      headers,
      cookies,
    };
  }

  return { status: 200, content_type: "text/plain; charset=utf-8", body: String(result ?? ""), headers: [], cookies: [] };
}

function methodList(mod) {
  const methods = ["get", "post", "put", "patch", "delete", "options"];
  return methods.filter((m) => typeof mod[m] === "function").map((m) => m.toUpperCase());
}

async function main() {
  const compiledPath = process.argv[2];
  if (!compiledPath) {
    process.stderr.write("Missing compiled module path\n");
    process.exit(2);
  }

  const mod = require(path.resolve(compiledPath));

  let input = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => (input += chunk));
  process.stdin.on("end", async () => {
    let request = {};
    try {
      request = JSON.parse(input || "{}");
    } catch (e) {
      const resp = { status: 400, content_type: "application/json; charset=utf-8", body: JSON.stringify({ error: "Invalid JSON request" }), headers: [], cookies: [] };
      process.stdout.write(JSON.stringify(resp));
      return;
    }

    const method = String(request.method || "GET").toLowerCase();
    const fn = (typeof mod[method] === "function" ? mod[method] : null) || (typeof mod.handler === "function" ? mod.handler : null);
    if (!fn) {
      const allowed = methodList(mod);
      const resp = {
        status: 405,
        content_type: "application/json; charset=utf-8",
        body: JSON.stringify({ error: "Method not allowed", allowed }),
        headers: [["Allow", allowed.join(", ")]],
        cookies: [],
      };
      process.stdout.write(JSON.stringify(resp));
      return;
    }

    try {
      installRuntimeHelpers(request, compiledPath);
      const result = await fn(request);
      const resp = normalizeResult(result);
      process.stdout.write(JSON.stringify(resp));
    } catch (e) {
      const resp = {
        status: 500,
        content_type: "application/json; charset=utf-8",
        body: JSON.stringify({ error: "TWM handler error", name: e && e.name ? e.name : "Error", message: e && e.message ? e.message : String(e) }),
        headers: [],
        cookies: [],
      };
      process.stdout.write(JSON.stringify(resp));
    }
  });

  // Important: start consuming stdin
  process.stdin.resume();
}

main().catch((e) => {
  process.stderr.write(String(e && e.stack ? e.stack : e) + "\n");
  process.exit(1);
});
