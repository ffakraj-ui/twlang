"""
TW Framework — Build-time Runtime Compatibility Validator (v0.9.0)

Scans .twm route handler source code for API usage that requires
capabilities the selected runtime doesn't support, and raises clear
build-time errors BEFORE deployment.

Example:
    runtime = "edge"

    fn get(request) {
        data = fs.readFile("data.json")  // ← requires filesystem
    }

    → Build-time error:
      "This route is configured for Edge Runtime,
       but `fs.readFile()` requires filesystem capability.
       File: app/api/data/route.twm
       Solutions: 1. Change runtime to nodejs
                  2. Use tw.storage.read()
                  3. Move filesystem logic to a nodejs route"
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple

from .base import BaseRuntime, RuntimeCapability, CAPABILITIES
from .registry import get_runtime


# API → required capability mapping
# When TW sees these APIs in a .twm handler, it checks if the selected
# runtime supports the required capability.
API_CAPABILITY_MAP: Dict[str, str] = {
    # File system APIs
    "fs.readFile": "filesystem",
    "fs.writeFile": "filesystem",
    "fs.unlink": "filesystem",
    "fs.readdir": "filesystem",
    "fs.stat": "filesystem",
    "fs.mkdir": "filesystem",
    "fs.rmdir": "filesystem",
    "fs.createReadStream": "filesystem",
    "fs.createWriteStream": "filesystem",
    "fs.existsSync": "filesystem",
    "fs.access": "filesystem",
    "os.path.join": "filesystem",
    "open(": "filesystem",
    "path.join": "filesystem",

    # Subprocess APIs
    "child_process": "subprocess",
    "exec(": "subprocess",
    "spawn(": "subprocess",
    "execSync": "subprocess",
    "execFile": "subprocess",
    "subprocess.run": "subprocess",
    "subprocess.Popen": "subprocess",
    "os.system": "subprocess",

    # Native modules
    "require(": "native_modules",
    "import ": "native_modules",
    "dlopen": "native_modules",

    # Network (Edge supports this, but some native network APIs don't)
    "net.Socket": "network",
    "net.Server": "network",
    "net.connect": "network",
    "net.createServer": "network",
    "tls.connect": "network",
    "tls.createServer": "network",
    "dns.resolve": "network",
    "dns.lookup": "network",

    # Database (native drivers)
    "createConnection": "database",
    "createPool": "database",
    "mongoose.connect": "database",
    "pg.Client": "database",
    "pg.Pool": "database",
    "mysql.createConnection": "database",
    "mysql.createPool": "database",
    "redis.createClient": "database",
    "redis.createPool": "database",
    "sqlite3.Database": "database",
    "sqlalchemy": "database",
    "psycopg2": "database",
    "asyncpg": "database",

    # Streaming
    "createReadStream": "streaming",
    "createWriteStream": "streaming",
    "Transform": "streaming",
    "pipeline(": "streaming",
    "Readable.from": "streaming",
    "Writable": "streaming",
    "Duplex": "streaming",
}


class RuntimeValidationError(Exception):
    """Raised when a .twm route uses APIs incompatible with its selected runtime."""

    def __init__(self, message: str, file_path: str = "", line: int = 0,
                 api: str = "", capability: str = "", runtime: str = "",
                 solutions: Optional[List[str]] = None):
        self.file_path = file_path
        self.line = line
        self.api = api
        self.capability = capability
        self.runtime = runtime
        self.solutions = solutions or []
        super().__init__(message)


def _find_api_usage(source: str) -> List[Tuple[str, str, int]]:
    """Scan source code for API usage.

    v0.9.08 FIX #8/#9: Improved pattern matching + comment stripping.
    - Uses regex word boundaries instead of substring matching
    - Strips inline comments (// ... and # ...) before scanning
    - Excludes tw.* common API calls from false positives

    Returns list of (api_name, required_capability, line_number).
    """
    findings = []
    lines = source.split("\n")
    for line_num, line in enumerate(lines, 1):
        # v0.9.08 FIX #9: Strip inline comments before scanning
        # Remove // comments and # comments (but not inside strings)
        code_part = _strip_inline_comment(line)
        stripped = code_part.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue

        # v0.9.08 FIX #8: Use word-boundary matching, not substring
        # This prevents false positives like "execute(" matching "exec("
        for api, capability in API_CAPABILITY_MAP.items():
            # Build a regex pattern with word boundary before the API name
            # This prevents "openDatabase(" from matching "open("
            pattern = r'(?<![\w.])' + re.escape(api)
            if re.search(pattern, code_part):
                # Don't flag if it's inside a tw.storage.* call (common API)
                if "tw.storage" in code_part and api in ("open(", "path.join", "os.path.join"):
                    continue
                # v0.9.08 FIX #8: Don't flag "import " inside tw.* import statements
                if api == "import " and ("tw." in code_part or "from tw" in code_part):
                    continue
                findings.append((api, capability, line_num))
    return findings


def _strip_inline_comment(line: str) -> str:
    """Strip inline // or # comments from a line, respecting string literals.

    v0.9.08 FIX #9: Previously only full-line comments were skipped.
    Now handles: let x = "fs.readFile"; // safe comment
    """
    result = []
    in_string = False
    string_char = None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_string:
            result.append(ch)
            if ch == string_char and (i == 0 or line[i-1] != '\\\\'):
                in_string = False
        elif ch in ('"', "'", '`'):
            in_string = True
            string_char = ch
            result.append(ch)
        elif ch == '/' and i + 1 < len(line) and line[i+1] == '/':
            break  # Inline comment starts
        elif ch == '#':
            break  # Python-style inline comment
        else:
            result.append(ch)
        i += 1
    return ''.join(result)


def validate_runtime_compatibility(source: str, runtime_name: str,
                                    file_path: str = "") -> List[RuntimeValidationError]:
    """Validate that a .twm handler's source is compatible with its runtime.

    Args:
        source: The .twm source code
        runtime_name: The selected runtime ("edge", "nodejs", "python", "wasm")
        file_path: Path to the .twm file (for error messages)

    Returns:
        List of RuntimeValidationError objects (empty if all compatible)
    """
    runtime = get_runtime(runtime_name)
    if runtime is None:
        return [RuntimeValidationError(
            f"Unknown runtime: {runtime_name!r}. "
            f"Available: {', '.join(sorted(API_CAPABILITY_MAP.keys()[:5]))}...",
            file_path=file_path,
            runtime=runtime_name,
        )]

    capabilities = runtime.capabilities()
    errors = []
    findings = _find_api_usage(source)

    for api, capability, line_num in findings:
        if not capabilities.get(capability, False):
            solutions = _generate_solutions(api, capability, runtime_name)
            cap_desc = CAPABILITIES.get(
                RuntimeCapability(capability), capability
            )
            errors.append(RuntimeValidationError(
                message=(
                    f"This route is configured for {runtime.display_name} Runtime, "
                    f"but `{api}` requires {capability} capability ({cap_desc}).\n\n"
                    f"File: {file_path or '<unknown>'}\n"
                    f"Line: {line_num}\n\n"
                    f"Possible solutions:\n" +
                    "\n".join(f"  {i+1}. {s}" for i, s in enumerate(solutions))
                ),
                file_path=file_path,
                line=line_num,
                api=api,
                capability=capability,
                runtime=runtime_name,
                solutions=solutions,
            ))

    return errors


def validate_runtime_compatibility_or_raise(source: str, runtime_name: str,
                                                   file_path: str = "") -> None:
    """Validate and raise if incompatible.

    v0.9.08 FIX #19: Unlike validate_runtime_compatibility(), this RAISES
    the first error instead of returning a list. Use this when you want
    build to fail on incompatibility.
    """
    errors = validate_runtime_compatibility(source, runtime_name, file_path)
    if errors:
        raise errors[0]


def _generate_solutions(api: str, capability: str, runtime_name: str) -> List[str]:
    """Generate helpful solutions for a compatibility error."""
    solutions = []

    # Solution 1: Change runtime
    if runtime_name in ("edge", "wasm"):
        solutions.append('Change runtime to nodejs: add runtime = "nodejs" at top of route file')
        solutions.append('Change runtime to python: add runtime = "python" at top of route file')

    # Solution 2: Use common API
    common_api_map = {
        "filesystem": "tw.storage.read() / tw.storage.write()",
        "subprocess": "Move subprocess logic to a nodejs route",
        "native_modules": "Use tw.* common APIs instead of native modules",
        "database": "tw.db.query() (uses runtime-appropriate driver)",
        "network": "tw.http.fetch() (works on all runtimes)",
        "streaming": "Use tw.http.fetch() with streaming options",
    }
    common = common_api_map.get(capability)
    if common:
        solutions.append(f"Use {common}")

    # Solution 3: Move to different route
    if capability in ("filesystem", "subprocess", "native_modules"):
        solutions.append(f'Move {capability} logic to a separate route with runtime = "nodejs"')

    if not solutions:
        solutions.append(f"Remove the `{api}` call or use a tw.* common API equivalent")

    return solutions
