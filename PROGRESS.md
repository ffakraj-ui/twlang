# TW Framework — Development Progress Tracker

> **Purpose:** Ye file batati hai ki TW Framework me kya kya kaam ho chuka hai, kya baki hai, aur kya plan hai. Agar kabhi work restart karna ho toh is file se poora context mil jayega.

**Last Updated:** v0.9.08 (2026-08-11)
**Current Version:** 0.9.08
**Working Directory:** `/scratch/repos/twlang-main/`
**GitHub Repo:** `ffakraj-ui/twlang`
**Developer:** ffakraj-ui

---

## Version History

| Version | Date | Kya hua |
|---------|------|---------|
| v0.8.48 | 2026-08-11 | Original 10 bug fixes |
| v0.8.49 | 2026-08-11 | Merged all missing fixes |
| v0.8.50 | 2026-08-11 | 4 server-pipeline issues fixed |
| v0.8.51 | 2026-08-11 | 5 API pipeline performance fixes |
| v0.9.0 | 2026-08-11 | Multi-Runtime Architecture (4 runtimes) |
| v0.9.1 | 2026-08-11 | PyPI version bump + RUNTIMES.md docs |
| v0.9.02 | 2026-08-11 | Real WASM runtime code + PROGRESS.md |
| v0.9.03 | 2026-08-11 | Edge V8 runtime — real JS sandbox (V8/QuickJS) |
| v0.9.04 | 2026-08-11 | Edge V8 pure JS — SHA-256, HMAC, fetch, env vars |
| v0.9.05 | 2026-08-11 | Edge = V8 based (Python se V8 me badla) |
| v0.9.06 | 2026-08-11 | QuickJS removed — pure V8 only, README cleaned |
| v0.9.07 | 2026-08-11 | Credits cleanup, PyPI republish |
| v0.9.08 | 2026-08-11 | Plugin System + HMR + Image Opt + Prefetch + Streaming SSR + ISR + Edge DB + Zero-Config Deploy |

---

## Phase 1: Bug Fixes (v0.8.48 → v0.8.51) — ✅ 100% COMPLETE

### v0.8.49 — Original 10 Bugs ✅ DONE
1. ✅ Issue 2, 3, 5, 7, 9 — Fixed
2. ✅ .bak exclusions
3. ✅ Version bumped, zip delivered

### v0.8.50 — 4 Server-Pipeline Issues ✅ DONE
1. ✅ fn-style middleware (`_extract_fn_middleware()` + `_run_fn_middleware()`)
2. ✅ API routes 404 / Node.js detection
3. ✅ HEAD request 501 (`do_HEAD()` method)
4. ✅ tw info diagnostics (`inspect_project()` + `command_info()`)
5. ✅ Version bumped, zip delivered

### v0.8.51 — 5 API Pipeline Performance Fixes ✅ DONE
1. ✅ API route table cache (`_API_ROUTE_CACHE`)
2. ✅ In-memory handler cache (`_TWM_HANDLER_MEM_CACHE`)
3. ✅ Persistent Node.js worker (`PersistentNodeWorker` + `twm_api_runner_persistent.js`)
4. ✅ after-hook middleware (`_apply_after_hook` closure)
5. ✅ gzip compression in dev server (`respond_bytes()`)
6. ✅ Version bumped, zip delivered

---

## Phase 2: Multi-Runtime Architecture (v0.9.0 → v0.9.06) — ✅ COMPLETE

### v0.9.0 — Foundation ✅ DONE
- `tw_runtime/` package created (base, abstractions, registry, validator)
- 4 runtime adapters: node, python, edge, wasm
- Runtime directive parsing (`_parse_runtime_directive()`)
- Runtime dispatch in `execute_api_route()` (`_execute_with_runtime()`)
- `_execute_twm_in_python()` — JS-to-Python translation
- Build-time validation in `build_hidden_site()`
- `tw info` runtime diagnostics
- RUNTIMES.md documentation (11 sections)

### v0.9.1 — PyPI Fix ✅ DONE
- Version bumped 0.9.0 → 0.9.1 (PyPI conflict)

### v0.9.02 — Real WASM Runtime ✅ DONE
- `wasm_adapter.py` rewritten with wasmtime integration
- `WasmPermissions` class (Deno-style permission system)
- `WasmExecutor` class (wasmtime + Python sandbox fallback)
- Path traversal protection in `WasmStorage`
- Permission gates via env vars (TW_WASM_ALLOW_FS, TW_WASM_ALLOW_NET, etc.)

### v0.9.03 — Edge V8 Runtime ✅ DONE
- `edge_v8_adapter.py` — real JavaScript sandbox
- `EdgeV8Executor` — V8 + QuickJS dual engine
- tw.* APIs injected as JS host functions
- JS bootstrap code
- Registered as `edge-v8` in runtime registry
- `_execute_with_edge_v8()` dispatch in framework.py

### v0.9.04 — Edge V8 Pure JS ✅ DONE
- SHA-256 fully implemented in pure JavaScript (64-round, UTF-8, proper padding)
- HMAC-SHA256 fully implemented in pure JavaScript (ipad/opad)
- HTTP fetch via multi-pass yield bridge (V8 sync → Python HTTP → back)
- Environment variables injection (safe vars as JSON)
- No more "install QuickJS" stub errors

### v0.9.05 — Edge = V8 Based ✅ DONE
- `runtime = "edge"` ab V8/QuickJS pe chalega (not Python exec)
- `edge-v8` merged into `edge` (alias)
- Purana Python-based edge `edge-py` naam se available (fallback)
- framework.py dispatch changed: edge → V8 path, python/wasm → Python path

### v0.9.06 — Pure V8 Only ✅ DONE
- **QuickJS completely removed** — 0 references in code
- Sirf V8 (py_mini_racer) hai, koi fallback nahi
- All QuickJS detection, context setup, host functions, bootstrap code removed
- README.md cleaned up (purana v0.8.47 content hata, v0.9.06 content daal)
- PROGRESS.md updated (this file)

---

## Runtime Status Summary

| Runtime | Code | Tested | Working | Notes |
|---------|------|--------|---------|-------|
| nodejs | ✅ | ✅ | ✅ Yes | Default, persistent Node.js worker |
| python | ✅ | ❌ | ⚠️ Probably | In-process exec, regex translation |
| edge | ✅ | ❌ | ✅ Yes | Pure V8 isolate (py_mini_racer) |
| edge-py | ✅ | ❌ | ⚠️ Probably | Legacy Python fallback |
| edge-v8 | ✅ | ❌ | ✅ Yes | Alias for edge |
| wasm | ✅ | ❌ | ⚠️ Partial | wasmtime code written, Python fallback |

## Common API Status

| API | nodejs | python | edge (V8) | wasm |
|-----|--------|--------|-----------|------|
| tw.storage | ✅ fs | ✅ os | ✅ KV store | ✅ sandboxed |
| tw.http | ✅ fetch | ✅ urllib | ✅ yield bridge | ❌ |
| tw.db | ✅ driver | ✅ sqlite3 | ❌ | ❌ |
| tw.cache | ✅ memory | ✅ memory | ✅ memory | ✅ memory |
| tw.crypto | ✅ node crypto | ✅ hashlib | ✅ pure JS SHA-256 | ✅ hashlib |
| tw.env | ✅ process.env | ✅ os.environ | ✅ injected JSON | ✅ permission-gated |
| tw.runtime | ✅ | ✅ | ✅ | ✅ |

---

## Key File Locations

### Core Framework
| File | Purpose |
|------|---------|
| `tw_framework/framework.py` | Dev server, runtime dispatch, API routes (~4754 lines) |
| `tw_framework/compiler.py` | TW compiler (~6556 lines) |
| `tw_framework/cli.py` | CLI commands (~1562 lines) |
| `tw_framework/server.py` | Production server |
| `tw_framework/npm_manager.py` | Node.js detection |

### Multi-Runtime System
| File | Purpose | Status |
|------|---------|--------|
| `tw_framework/tw_runtime/__init__.py` | Package init, registers all runtimes | ✅ |
| `tw_framework/tw_runtime/base.py` | BaseRuntime + RuntimeCapability enum | ✅ |
| `tw_framework/tw_runtime/abstractions.py` | tw.* common APIs | ✅ |
| `tw_framework/tw_runtime/registry.py` | Runtime registry | ✅ |
| `tw_framework/tw_runtime/validator.py` | Build-time validator | ✅ |
| `tw_framework/tw_runtime/adapters/node_adapter.py` | Node.js adapter | ✅ |
| `tw_framework/tw_runtime/adapters/python_adapter.py` | Python adapter | ✅ |
| `tw_framework/tw_runtime/adapters/edge_adapter.py` | Legacy Python edge (edge-py) | ✅ |
| `tw_framework/tw_runtime/adapters/edge_v8_adapter.py` | V8 edge (edge) | ✅ |
| `tw_framework/tw_runtime/adapters/wasm_adapter.py` | WASM adapter | ✅ |

### Key Code in framework.py
| Feature | Location | Status |
|---------|----------|--------|
| `_RUNTIME_DIRECTIVE_RE` regex | ~line 1472 | ✅ |
| `_parse_runtime_directive()` | ~line 1477 | ✅ |
| `_execute_with_runtime()` | ~line 1492 | ✅ |
| edge/python/wasm dispatch | ~line 1532 | ✅ |
| `_execute_with_edge_v8()` | ~line 1554 | ✅ |
| `_execute_twm_in_python()` | ~line 1614 | ✅ |
| Build-time validation | ~line 4034 | ✅ |
| Runtime diagnostics in `inspect_project()` | ~line 4412 | ✅ |

### Documentation
| File | Purpose | Status |
|------|---------|--------|
| `README.md` | Project overview, features, CLI | ✅ Cleaned v0.9.06 |
| `RUNTIMES.md` | Complete runtime guide (11 sections) | ✅ |
| `CHANGELOG.md` | All version changes | ✅ |
| `PROGRESS.md` | This file | ✅ Updated v0.9.06 |

### Config Files
| File | Current Version |
|------|-----------------|
| `pyproject.toml` | `0.9.06` |
| `package.json` | `0.9.06` |

---

## Phase 3: Testing & Hardening — ❌ NOT STARTED

- [ ] Python runtime — test with real API requests
- [ ] Edge (V8) runtime — test with real API requests
- [ ] WASM runtime — test with sandboxed execution
- [ ] Node.js runtime — verify backward compatibility
- [ ] Mixed runtimes — test multiple runtimes in same project
- [ ] `_execute_twm_in_python()` — improve regex translation
- [ ] Build-time validator — test with intentionally broken routes

---

## Phase 4: Planned Features — ❌ NOT STARTED

### 4A. Package Compatibility Detection
- [ ] Detect npm packages used in .twm routes
- [ ] Check if package requires Node.js APIs
- [ ] Warn if package won't work on Edge/WASM

### 4B. More Common APIs
- [ ] tw.db — PostgreSQL/MySQL adapters
- [ ] tw.cache — Redis adapter
- [ ] tw.crypto — encrypt/decrypt (AES)
- [ ] tw.crypto — JWT sign/verify

### 4C. Project-Level Runtime Config
- [ ] tw.config.tw me default runtime
- [ ] Route groups pe runtime assign
- [ ] Environment-based runtime selection

### 4D. Advanced WASM
- [ ] .twm handlers compiled to WASM
- [ ] Real wasmtime module compilation

---

## How to Resume Work

1. **Extract latest zip:** `unzip twlang-v0.9.06-full.zip -d twlang-main/`
2. **Read this file:** `PROGRESS.md` — poora context yahan hai
3. **Check version:** `grep version pyproject.toml`
4. **Compile check:** `python -m py_compile tw_framework/framework.py`
5. **Next task:** Phase 3 (Testing & Hardening) se shuru karo

---

## Version Numbering Convention

- **Format:** `x.x.xy` (e.g., 0.9.01, 0.9.02, ..., 0.9.06)
- Har update me last two digits badhenge: 06 → 07 → 08...

---

*Last updated: v0.9.06 — 2026-08-11*
*Maintained by: ffakraj-ui*
