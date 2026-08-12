import json
import os

from ..twm_parser import compile_twm_module_to_cjs


def generate_vercel_api_functions(output_dir: str, project_root: str, api_routes: list) -> None:
    """
    Generate Vercel Build Output API v3 function folders for .twm API routes.

    For each route with lang == "twm":
      - Read the .twm source file
      - Compile it to a CJS module via compile_twm_module_to_cjs()
      - Create {output_dir}/../.vercel/output/functions{route}.func/
      - Write:
          .vc-config.json
          handler.cjs   (the compiled module)
          index.js      (Vercel launcher that requires ./handler.cjs)
    """
    vercel_output = os.path.join(output_dir, "..", ".vercel", "output")
    functions_dir = os.path.join(vercel_output, "functions")

    for route_info in api_routes:
        if route_info.get("lang") != "twm":
            continue

        route_path = route_info.get("route", "")
        source_path = route_info.get("path", "")
        if not source_path or not os.path.isfile(source_path):
            continue

        # Read source
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Compile to CJS
        try:
            handler_cjs = compile_twm_module_to_cjs(source, module_id=source_path)
        except Exception as exc:
            # Log and skip
            continue

        # Build function folder path
        # route_path e.g. "/api/hello" -> "api/hello.func"
        func_rel = route_path.lstrip("/") + ".func"
        func_dir = os.path.join(functions_dir, func_rel)
        os.makedirs(func_dir, exist_ok=True)

        # .vc-config.json
        vc_config = {
            "runtime": "nodejs20.x",
            "handler": "index.js",
            "launcherType": "Nodejs",
        }
        with open(os.path.join(func_dir, ".vc-config.json"), "w", encoding="utf-8") as f:
            json.dump(vc_config, f, indent=2)

        # handler.cjs
        with open(os.path.join(func_dir, "handler.cjs"), "w", encoding="utf-8") as f:
            f.write(handler_cjs)

        # index.js – Vercel launcher
        index_js = _build_vercel_launcher()
        with open(os.path.join(func_dir, "index.js"), "w", encoding="utf-8") as f:
            f.write(index_js)


def _build_vercel_launcher() -> str:
    """
    Return the source of index.js that adapts the TWM handler to Vercel's
    request/response model.
    """
    return r'''"use strict";

const path = require("path");
const fs = require("fs");
const { createRequire } = require("module");

// ── Runtime helpers (mirror twm_api_runner.js) ──────────────────────────

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
  const secretsHelper = buildValueHelper((request && request.env) || {}, "private_action");
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
  let status = 200;
  let headers = [];
  let cookies = [];

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

// ── Vercel handler ──────────────────────────────────────────────────────

const handlerModule = require("./handler.cjs");

module.exports = async (req, res) => {
  // Build request object matching twm_api_runner.js expectations
  const method = (req.method || "GET").toLowerCase();
  const urlPath = req.url || "/";
  const headers = req.headers || {};

  // Read body
  let body = null;
  if (req.body !== undefined) {
    body = req.body;
  } else {
    // Vercel may provide raw body via req.read()? We'll rely on req.body being set by middleware.
    // For safety, try to parse if content-type indicates JSON.
    const contentType = normalizeHeaderValue(headers, "content-type") || "";
    if (contentType.includes("application/json") && typeof req.body === "string") {
      try {
        body = JSON.parse(req.body);
      } catch (e) {
        body = req.body;
      }
    } else {
      body = req.body || null;
    }
  }

  const request = {
    method: method.toUpperCase(),
    path: urlPath,
    query: Object.fromEntries(new URL(urlPath, "http://localhost").searchParams.entries()),
    body,
    headers,
    cookies: (() => {
      const cookieHeader = normalizeHeaderValue(headers, "cookie") || "";
      const cookies = {};
      if (cookieHeader) {
        for (const part of cookieHeader.split(";")) {
          const eq = part.indexOf("=");
          if (eq !== -1) {
            cookies[part.slice(0, eq).trim()] = decodeURIComponent(part.slice(eq + 1).trim());
          }
        }
      }
      return cookies;
    })(),
    env: process.env,
    project_root: findProjectRoot(__dirname),
  };

  // Install runtime helpers
  installRuntimeHelpers(request, __dirname);

  // Dispatch
  const fn = (typeof handlerModule[method] === "function" ? handlerModule[method] : null) ||
             (typeof handlerModule.handler === "function" ? handlerModule.handler : null);

  if (!fn) {
    const allowed = methodList(handlerModule);
    res.statusCode = 405;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.setHeader("Allow", allowed.join(", "));
    res.end(JSON.stringify({ error: "Method not allowed", allowed }));
    return;
  }

  try {
    const result = await fn(request);
    const normalized = normalizeResult(result);
    res.statusCode = normalized.status || 200;
    for (const [key, value] of normalized.headers || []) {
      res.setHeader(key, value);
    }
    for (const [name, value] of normalized.cookies || []) {
      res.setHeader("Set-Cookie", `${name}=${encodeURIComponent(String(value))}; Path=/; HttpOnly; SameSite=Lax`);
    }
    res.setHeader("Content-Type", normalized.content_type || "text/plain; charset=utf-8");
    res.end(normalized.body);
  } catch (err) {
    res.statusCode = 500;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.end(JSON.stringify({ error: "TWM handler error", name: err.name || "Error", message: err.message || String(err) }));
  }
};
'''
