"""
Build-time execution of `.twm` lib functions.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, Optional

from .twm_parser import compile_twm_module_to_cjs

_NODE_BRIDGE_SCRIPT = r"""// TW lib function executor (build-time)
"use strict";
const path = require("path");
function main() {
  const compiledPath = process.argv[2];
  const fnName = process.argv[3];
  const argsJson = process.argv[4] || "[]";
  let args;
  try { args = JSON.parse(argsJson); } catch (e) { args = []; }
  const mod = require(path.resolve(compiledPath));
  const fn = mod[fnName];
  if (typeof fn !== "function") {
    process.stderr.write("Function '" + fnName + "' not found. Available: " + Object.keys(mod).join(", ") + "\n");
    process.exit(3);
  }
  Promise.resolve()
    .then(function () { return fn.apply(null, args); })
    .then(function (result) {
      try { process.stdout.write(JSON.stringify(result)); }
      catch (e) { process.stdout.write(JSON.stringify(String(result))); }
    })
    .catch(function (err) {
      process.stderr.write("Error: " + (err && err.stack ? err.stack : String(err)) + "\n");
      process.exit(4);
    });
}
main();
"""

class LibExecutionError(Exception):
    def __init__(self, message, *, suggestion=""):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion

_FUNC_CALL_RE = re.compile(
    r"^(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*\((?P<args>.*)\)\s*$",
    re.DOTALL,
)

def is_function_call(expr):
    if not isinstance(expr, str):
        return None
    stripped = expr.strip()
    if not stripped:
        return None
    if stripped[0] in "\"'{[" or stripped in ("true", "false", "null", "none"):
        return None
    m = _FUNC_CALL_RE.match(stripped)
    if not m:
        return None
    return {"name": m.group("name"), "raw_args": m.group("args").strip()}

def _parse_args(raw_args):
    raw = raw_args.strip()
    if not raw:
        return []
    try:
        return json.loads("[" + raw + "]")
    except json.JSONDecodeError:
        return [raw]

def _find_node():
    for candidate in ("node", "nodejs"):
        try:
            result = subprocess.run([candidate, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return ""

def execute_lib_function(twm_source, function_name, raw_args, *, module_id="", timeout=30):
    try:
        cjs_code = compile_twm_module_to_cjs(twm_source, module_id=module_id or "<lib:" + function_name + ">")
    except Exception as exc:
        raise LibExecutionError("Failed to compile lib module `" + module_id + "`: " + str(exc), suggestion="Check the .twm file for syntax errors.") from exc

    fd_mod, mod_path = tempfile.mkstemp(suffix=".cjs", prefix="tw_lib_mod_")
    try:
        with os.fdopen(fd_mod, "w") as f:
            f.write(cjs_code)
    except Exception:
        os.close(fd_mod)
        raise

    fd_bridge, bridge_path = tempfile.mkstemp(suffix=".cjs", prefix="tw_lib_exec_")
    try:
        with os.fdopen(fd_bridge, "w") as f:
            f.write(_NODE_BRIDGE_SCRIPT)
    except Exception:
        os.close(fd_bridge)
        raise

    args = _parse_args(raw_args)
    args_json = json.dumps(args, ensure_ascii=False)

    node_bin = _find_node()
    if not node_bin:
        for p in (bridge_path, mod_path):
            try: os.unlink(p)
            except OSError: pass
        raise LibExecutionError("Node.js is required to execute lib functions at build time but was not found.", suggestion="Install Node.js (v18+).")

    try:
        result = subprocess.run([node_bin, bridge_path, mod_path, function_name, args_json], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise LibExecutionError("Lib function `" + function_name + "` timed out after " + str(timeout) + "s.", suggestion="Increase the timeout.") from exc
    finally:
        for p in (bridge_path, mod_path):
            try: os.unlink(p)
            except OSError: pass

    if result.returncode != 0:
        raise LibExecutionError("Lib function `" + function_name + "` failed: " + result.stderr.strip(), suggestion="Check the .twm file.")

    stdout = result.stdout.strip()
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return stdout

__all__ = ["LibExecutionError", "execute_lib_function", "is_function_call"]
