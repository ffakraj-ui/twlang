"""
TW NPM Package Manager (v0.8.1)

Lets users install, remove, and list npm packages — just like `npm install`
in Next.js. Works with the project's package.json and node_modules.

Usage:
  tw install <package>        # Install a package (alias: tw add)
  tw install                  # Install all from package.json
  tw remove <package>         # Remove a package
  tw list                     # List installed packages

Supports:
  - Version specifiers: tw install react@18.2.0
  - Dev dependencies: tw install --save-dev jest
  - Multiple packages: tw install react react-dom
  - Auto-detects npm vs pnpm vs yarn
  - Updates package.json dependencies/devDependencies
  - Integrates with tw.config server.external_packages
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from .common import log


# ─── Package Manager Detection ────────────────────────────────────────────────

def detect_package_manager(project_root: str) -> str:
    """Detect which package manager to use (npm, pnpm, yarn, bun)."""
    # Check for lockfiles in priority order
    if os.path.exists(os.path.join(project_root, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.exists(os.path.join(project_root, "yarn.lock")):
        return "yarn"
    if os.path.exists(os.path.join(project_root, "bun.lockb")):
        return "bun"
    if os.path.exists(os.path.join(project_root, "package-lock.json")):
        return "npm"
    # Check what's available on PATH
    for pm in ("npm", "pnpm", "yarn", "bun"):
        if shutil.which(pm):
            return pm
    return "npm"  # fallback


def find_node() -> Optional[str]:
    """Find Node.js binary."""
    for candidate in ("node", "nodejs"):
        if shutil.which(candidate):
            return candidate
    return None


def find_npm() -> Optional[str]:
    """Find npm binary."""
    return shutil.which("npm")


def _get_node_install_help() -> str:
    """
    Return OS-specific Node.js installation instructions with exact commands.
    Detects the operating system and suggests the most appropriate install method.
    """
    import platform

    system = platform.system().lower()
    machine = platform.machine().lower()

    # Check for Termux (Android)
    is_termux = "com.termux" in os.environ.get("PREFIX", "") or \
                os.path.exists("/data/data/com.termux/files/usr")

    if is_termux:
        return (
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  ❌ Node.js not found on your system                        ║\n"
            "║  TW Framework needs Node.js for `tw install` and API routes  ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  📱 Termux (Android) — install with:                         ║\n"
            "║                                                              ║\n"
            "║     pkg install nodejs                                       ║\n"
            "║                                                              ║\n"
            "║  After installing, verify:                                   ║\n"
            "║     node --version                                           ║\n"
            "║     npm --version                                            ║\n"
            "║                                                              ║\n"
            "║  Then run `tw install` again.                                ║\n"
            "╚══════════════════════════════════════════════════════════════╝"
        )

    if system == "linux":
        # Check for specific distros
        if shutil.which("apt"):
            return (
                "\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  ❌ Node.js not found on your system                        ║\n"
                "║  TW Framework needs Node.js for `tw install` and API routes  ║\n"
                "╠══════════════════════════════════════════════════════════════╣\n"
                "║  🐧 Debian/Ubuntu — install with:                             ║\n"
                "║                                                              ║\n"
                "║     sudo apt update && sudo apt install nodejs npm            ║\n"
                "║                                                              ║\n"
                "║  Or use nvm (recommended for version control):               ║\n"
                "║     curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash ║\n"
                "║     source ~/.bashrc                                          ║\n"
                "║     nvm install --lts                                         ║\n"
                "║                                                              ║\n"
                "║  After installing, verify:                                   ║\n"
                "║     node --version                                           ║\n"
                "║     npm --version                                            ║\n"
                "║                                                              ║\n"
                "║  Then run `tw install` again.                                ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
            )
        elif shutil.which("dnf") or shutil.which("yum"):
            return (
                "\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  ❌ Node.js not found on your system                        ║\n"
                "║  TW Framework needs Node.js for `tw install` and API routes  ║\n"
                "╠══════════════════════════════════════════════════════════════╣\n"
                "║  🐧 Fedora/RHEL/CentOS — install with:                        ║\n"
                "║                                                              ║\n"
                "║     sudo dnf install nodejs npm                              ║\n"
                "║                                                              ║\n"
                "║  Or use nvm (recommended):                                   ║\n"
                "║     curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash ║\n"
                "║     source ~/.bashrc                                          ║\n"
                "║     nvm install --lts                                         ║\n"
                "║                                                              ║\n"
                "║  After installing, verify:                                   ║\n"
                "║     node --version                                           ║\n"
                "║     npm --version                                            ║\n"
                "║                                                              ║\n"
                "║  Then run `tw install` again.                                ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
            )
        elif shutil.which("pacman"):
            return (
                "\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  ❌ Node.js not found on your system                        ║\n"
                "║  TW Framework needs Node.js for `tw install` and API routes  ║\n"
                "╠══════════════════════════════════════════════════════════════╣\n"
                "║  🐧 Arch Linux — install with:                                ║\n"
                "║                                                              ║\n"
                "║     sudo pacman -S nodejs npm                                ║\n"
                "║                                                              ║\n"
                "║  After installing, verify:                                   ║\n"
                "║     node --version                                           ║\n"
                "║     npm --version                                            ║\n"
                "║                                                              ║\n"
                "║  Then run `tw install` again.                                ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
            )
        elif shutil.which("apk"):
            return (
                "\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  ❌ Node.js not found on your system                        ║\n"
                "║  TW Framework needs Node.js for `tw install` and API routes  ║\n"
                "╠══════════════════════════════════════════════════════════════╣\n"
                "║  🐧 Alpine Linux — install with:                              ║\n"
                "║                                                              ║\n"
                "║     apk add nodejs npm                                       ║\n"
                "║                                                              ║\n"
                "║  After installing, verify:                                   ║\n"
                "║     node --version                                           ║\n"
                "║     npm --version                                            ║\n"
                "║                                                              ║\n"
                "║  Then run `tw install` again.                                ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
            )
        else:
            return (
                "\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  ❌ Node.js not found on your system                        ║\n"
                "║  TW Framework needs Node.js for `tw install` and API routes  ║\n"
                "╠══════════════════════════════════════════════════════════════╣\n"
                "║  🐧 Linux — install via nvm (recommended):                    ║\n"
                "║                                                              ║\n"
                "║     curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash ║\n"
                "║     source ~/.bashrc                                          ║\n"
                "║     nvm install --lts                                         ║\n"
                "║                                                              ║\n"
                "║  Or download from:                                           ║\n"
                "║     https://nodejs.org/en/download/                         ║\n"
                "║                                                              ║\n"
                "║  After installing, verify:                                   ║\n"
                "║     node --version                                           ║\n"
                "║     npm --version                                            ║\n"
                "║                                                              ║\n"
                "║  Then run `tw install` again.                                ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
            )

    elif system == "darwin":
        return (
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  ❌ Node.js not found on your system                        ║\n"
            "║  TW Framework needs Node.js for `tw install` and API routes  ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  🍎 macOS — install with one of:                              ║\n"
            "║                                                              ║\n"
            "║  Option A: Homebrew (recommended)                            ║\n"
            "║     brew install node                                        ║\n"
            "║                                                              ║\n"
            "║  Option B: nvm (Node Version Manager)                        ║\n"
            "║     curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash ║\n"
            "║     source ~/.zshrc                                           ║\n"
            "║     nvm install --lts                                         ║\n"
            "║                                                              ║\n"
            "║  Option C: Download from                                     ║\n"
            "║     https://nodejs.org/en/download/                         ║\n"
            "║                                                              ║\n"
            "║  After installing, verify:                                   ║\n"
            "║     node --version                                           ║\n"
            "║     npm --version                                            ║\n"
            "║                                                              ║\n"
            "║  Then run `tw install` again.                                ║\n"
            "╚══════════════════════════════════════════════════════════════╝"
        )

    elif system == "windows":
        return (
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  ❌ Node.js not found on your system                        ║\n"
            "║  TW Framework needs Node.js for `tw install` and API routes  ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  🪟 Windows — install with one of:                            ║\n"
            "║                                                              ║\n"
            "║  Option A: winget (Windows 10/11)                            ║\n"
            "║     winget install OpenJS.NodeJS                             ║\n"
            "║                                                              ║\n"
            "║  Option B: Chocolatey                                        ║\n"
            "║     choco install nodejs                                     ║\n"
            "║                                                              ║\n"
            "║  Option C: Download from                                     ║\n"
            "║     https://nodejs.org/en/download/                         ║\n"
            "║                                                              ║\n"
            "║  After installing, restart your terminal and verify:         ║\n"
            "║     node --version                                           ║\n"
            "║     npm --version                                            ║\n"
            "║                                                              ║\n"
            "║  Then run `tw install` again.                                ║\n"
            "╚══════════════════════════════════════════════════════════════╝"
        )

    else:
        return (
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  ❌ Node.js not found on your system                        ║\n"
            "║  TW Framework needs Node.js for `tw install` and API routes  ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  Download and install Node.js from:                          ║\n"
            "║     https://nodejs.org/en/download/                         ║\n"
            "║                                                              ║\n"
            "║  Or use nvm (Node Version Manager):                          ║\n"
            "║     curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash ║\n"
            "║     source ~/.bashrc                                          ║\n"
            "║     nvm install --lts                                         ║\n"
            "║                                                              ║\n"
            "║  After installing, verify:                                   ║\n"
            "║     node --version                                           ║\n"
            "║     npm --version                                            ║\n"
            "║                                                              ║\n"
            "║  Then run `tw install` again.                                ║\n"
            "╚══════════════════════════════════════════════════════════════╝"
        )


def find_package_manager(project_root: str = ".") -> Tuple[str, Optional[str]]:
    """
    Detect the project's package manager and return (pm_name, pm_binary).

    Uses detect_package_manager() to check lockfiles first, then PATH.
    Returns ("npm", "/path/to/npm") or ("pnpm", "/path/to/pnpm") etc.
    Falls back to ("npm", find_npm()) if nothing found.
    """
    pm = detect_package_manager(project_root)
    binary = shutil.which(pm)
    if binary:
        return pm, binary
    # Fallback: try npm, then node
    npm = find_npm()
    if npm:
        return "npm", npm
    return "npm", None


def _pm_install_command(pm: str, packages: List[str], dev: bool, exact: bool) -> List[str]:
    """Build the install command for the detected package manager."""
    if pm == "pnpm":
        cmd = ["pnpm", "add"]
        if dev:
            cmd.append("--save-dev")
        # pnpm saves exact by default with --save-exact
        if exact:
            cmd.append("--save-exact")
    elif pm == "yarn":
        cmd = ["yarn", "add"]
        if dev:
            cmd.append("--dev")
        if exact:
            cmd.append("--exact")
    elif pm == "bun":
        cmd = ["bun", "add"]
        if dev:
            cmd.append("--dev")
        if exact:
            cmd.append("--exact")
    else:  # npm
        cmd = ["npm", "install"]
        if dev:
            cmd.append("--save-dev")
        if exact:
            cmd.append("--save-exact")
    cmd.extend(packages)
    return cmd


def _pm_uninstall_command(pm: str, packages: List[str]) -> List[str]:
    """Build the uninstall command for the detected package manager."""
    if pm == "pnpm":
        return ["pnpm", "remove"] + packages
    elif pm == "yarn":
        return ["yarn", "remove"] + packages
    elif pm == "bun":
        return ["bun", "remove"] + packages
    else:  # npm
        return ["npm", "uninstall"] + packages


def _pm_install_all_command(pm: str) -> List[str]:
    """Build the 'install all from package.json' command for the detected PM."""
    if pm == "pnpm":
        return ["pnpm", "install"]
    elif pm == "yarn":
        return ["yarn", "install"]
    elif pm == "bun":
        return ["bun", "install"]
    else:  # npm
        return ["npm", "install"]


# ─── Package.json Helpers ─────────────────────────────────────────────────────

def read_package_json(project_root: str) -> Dict[str, Any]:
    """Read project package.json."""
    pkg_path = os.path.join(project_root, "package.json")
    if not os.path.exists(pkg_path):
        return {
            "name": "tw-site",
            "private": True,
            "version": "0.1.0",
            "dependencies": {},
            "devDependencies": {},
        }
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log(f"⚠️  Failed to read package.json: {e}", level="warning")
        return {"dependencies": {}, "devDependencies": {}}


def write_package_json(project_root: str, data: Dict[str, Any]) -> None:
    """Write project package.json."""
    pkg_path = os.path.join(project_root, "package.json")
    with open(pkg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def parse_package_spec(spec: str) -> Tuple[str, str]:
    """
    Parse a package spec like 'react@18.2.0' or 'react' or '@scope/pkg@1.0.0'.
    Returns (name, version) where version may be empty.
    """
    # Handle scoped packages: @scope/pkg@version
    if spec.startswith("@"):
        # @scope/pkg or @scope/pkg@version
        parts = spec.rsplit("@", 1)
        if len(parts) == 2 and parts[0]:
            return parts[0], parts[1]
        return spec, ""
    # Regular: pkg or pkg@version
    if "@" in spec:
        name, version = spec.split("@", 1)
        return name, version
    return spec, ""


# ─── tw.config Integration ────────────────────────────────────────────────────

def update_tw_config_packages(project_root: str, packages: List[str], remove: bool = False) -> None:
    """
    Add or remove packages from tw.config server.external_packages.
    This tells the TW build system these npm packages are allowed.
    """
    config_path = os.path.join(project_root, "tw.config")
    if not os.path.exists(config_path):
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return

    # Find the external_packages block
    # Pattern: external_packages [ "pkg1", "pkg2" ]
    pattern = re.compile(
        r'(external_packages\s*\[)([^\]]*)(\])',
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        # No external_packages block found; try to add one inside server { }
        server_pattern = re.compile(r'(server\s*\{)',)
        server_match = server_pattern.search(content)
        if server_match:
            insert_pos = server_match.end()
            # Find existing content to determine indentation
            lines = content[:insert_pos].split("\n")
            indent = "    "  # default indent
            if lines:
                last_line = lines[-1]
                leading = len(last_line) - len(last_line.lstrip())
                if leading > 0:
                    indent = " " * leading + "  "

            pkgs_str = ", ".join(f'"{p}"' for p in packages)
            new_block = f"\n{indent}external_packages [\n{indent}    {pkgs_str}\n{indent}]"
            content = content[:insert_pos] + new_block + content[insert_pos:]
        else:
            # Append server block at end
            pkgs_str = ", ".join(f'"{p}"' for p in packages)
            content += f"\n\nserver {{\n  external_packages [\n    {pkgs_str}\n  ]\n}}\n"
    else:
        # Parse existing packages from the block
        existing_str = match.group(2)
        existing = re.findall(r'"([^"]+)"', existing_str)
        if remove:
            updated = [p for p in existing if p not in packages]
        else:
            updated = list(existing)
            for p in packages:
                if p not in updated:
                    updated.append(p)

        if updated:
            pkgs_str = ", ".join(f'"{p}"' for p in updated)
            replacement = f"{match.group(1)} {pkgs_str} {match.group(3)}"
        else:
            replacement = f"{match.group(1)}{match.group(3)}"

        content = content[:match.start()] + replacement + content[match.end():]

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        log(f"⚠️  Failed to update tw.config: {e}", level="warning")


def get_tw_config_packages(project_root: str) -> List[str]:
    """Get list of external_packages from tw.config."""
    config_path = os.path.join(project_root, "tw.config")
    if not os.path.exists(config_path):
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return []

    pattern = re.compile(r'external_packages\s*\[([^\]]*)\]', re.DOTALL)
    match = pattern.search(content)
    if not match:
        return []

    return re.findall(r'"([^"]+)"', match.group(1))


# ─── Install / Remove / List ─────────────────────────────────────────────────

def install_packages(
    project_root: str,
    packages: List[str],
    dev: bool = False,
    exact: bool = False,
) -> bool:
    """
    Install npm packages and update package.json + tw.config.

    Args:
        project_root: Project root directory
        packages: List of package specs (e.g. ["react", "react-dom@18.2.0"])
        dev: Save as devDependency
        exact: Save exact version (no ^)

    Returns True on success.
    """
    node_bin = find_node()
    pm_name, pm_bin = find_package_manager(project_root)

    if not node_bin or not pm_bin:
        log(_get_node_install_help(), level="error")
        return False

    # If no packages specified, install from package.json
    if not packages:
        log(f"📦 Installing dependencies from package.json ({pm_name})...")
        return _run_pm_install(project_root, pm_name)

    # Parse package specs
    parsed = []
    for spec in packages:
        name, version = parse_package_spec(spec)
        parsed.append((name, version, spec))
        log(f"  → {name}" + (f"@{version}" if version else ""))

    # Update package.json
    pkg = read_package_json(project_root)
    dep_key = "devDependencies" if dev else "dependencies"
    if dep_key not in pkg:
        pkg[dep_key] = {}

    for name, version, _ in parsed:
        if version:
            prefix = "" if exact else "^"
            pkg[dep_key][name] = prefix + version
        else:
            # Mark as latest — npm install will resolve and update package.json
            pkg[dep_key][name] = "latest"

    write_package_json(project_root, pkg)

    # Run install via the detected package manager
    install_args = _pm_install_command(pm_name, [p for _, _, p in parsed], dev, exact)
    # Use absolute path to the binary
    install_args[0] = pm_bin

    log(f"📦 Running: {' '.join(install_args)}")
    result = subprocess.run(
        install_args,
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=300,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        log(f"✖ {pm_name} install failed: {stderr}", level="error")
        # Revert package.json changes for failed packages
        pkg = read_package_json(project_root)
        for name, _, _ in parsed:
            pkg.get(dep_key, {}).pop(name, None)
        write_package_json(project_root, pkg)
        return False

    # Now re-read package.json (npm may have updated version specs)
    pkg = read_package_json(project_root)

    # Re-read with resolved versions
    for name, _, _ in parsed:
        ver = pkg.get(dep_key, {}).get(name, "")
        if ver and ver != "latest":
            log(f"  ✔ {name}@{ver}")
        else:
            log(f"  ✔ {name} installed")

    # Update tw.config external_packages
    package_names = [name for name, _, _ in parsed]
    update_tw_config_packages(project_root, package_names, remove=False)

    log(f"✔ Installed {len(parsed)} package(s)")
    log("  Updated package.json and tw.config")

    # Check for React-specific setup
    if "react" in package_names or "react-dom" in package_names:
        log("  💡 React detected. See docs/REACT_USAGE.md for TW + React integration.")

    return True


def _run_npm_install(project_root: str) -> bool:
    """Run plain `npm install` to install all dependencies from package.json.

    Deprecated: use _run_pm_install() which auto-detects the package manager.
    Kept for backward compatibility.
    """
    return _run_pm_install(project_root)


def remove_packages(project_root: str, packages: List[str]) -> bool:
    """Remove packages via the detected package manager and update package.json + tw.config."""
    pm_name, pm_bin = find_package_manager(project_root)
    if not pm_bin:
        log(_get_node_install_help(), level="error")
        return False

    pkg = read_package_json(project_root)
    removed = []

    for name in packages:
        was_in_deps = name in pkg.get("dependencies", {})
        was_in_dev = name in pkg.get("devDependencies", {})

        if not was_in_deps and not was_in_dev:
            log(f"  ⚠️  {name} not found in package.json", level="warning")
            continue

        pkg.get("dependencies", {}).pop(name, None)
        pkg.get("devDependencies", {}).pop(name, None)
        removed.append(name)
        log(f"  → Removing {name}")

    if not removed:
        log("No packages to remove.")
        return True

    write_package_json(project_root, pkg)

    # Run uninstall via the detected package manager
    uninstall_args = _pm_uninstall_command(pm_name, removed)
    uninstall_args[0] = pm_bin
    log(f"📦 Running: {' '.join(uninstall_args)}")
    result = subprocess.run(
        uninstall_args,
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=300,
    )

    if result.returncode != 0:
        log(f"⚠️  {pm_name} uninstall warning: {result.stderr.strip()}", level="warning")

    # Update tw.config
    update_tw_config_packages(project_root, removed, remove=True)

    log(f"✔ Removed {len(removed)} package(s)")
    return True


def list_packages(project_root: str, detailed: bool = False) -> None:
    """List installed npm packages."""
    pkg = read_package_json(project_root)
    deps = pkg.get("dependencies", {})
    dev_deps = pkg.get("devDependencies", {})

    # Also show tw.config external_packages
    tw_pkgs = get_tw_config_packages(project_root)

    if not deps and not dev_deps:
        log("No dependencies found in package.json.")
        log("  Install with: tw install <package>")
        return

    if deps:
        log("Dependencies:")
        for name, version in sorted(deps.items()):
            installed = _check_installed(project_root, name)
            status = "✔" if installed else "✖ (not installed)"
            extra = ""
            if detailed and installed:
                extra = f"  → {_get_installed_version(project_root, name)}"
            log(f"  {status} {name}@{version}{extra}")

    if dev_deps:
        log("\nDev Dependencies:")
        for name, version in sorted(dev_deps.items()):
            installed = _check_installed(project_root, name)
            status = "✔" if installed else "✖ (not installed)"
            log(f"  {status} {name}@{version} (dev)")

    if tw_pkgs:
        log("\nTW Config (server.external_packages):")
        for name in tw_pkgs:
            installed = _check_installed(project_root, name)
            status = "✔" if installed else "✖ (not installed)"
            log(f"  {status} {name}")

    total = len(deps) + len(dev_deps)
    installed_count = sum(
        1 for name in list(deps.keys()) + list(dev_deps.keys())
        if _check_installed(project_root, name)
    )
    log(f"\nTotal: {total} package(s), {installed_count} installed")
    if installed_count < total:
        log("  Run `tw install` to install missing packages.")


def _run_pm_install(project_root: str, pm_name: str = None) -> bool:
    """Run the detected package manager's install-all command."""
    if pm_name is None:
        pm_name, pm_bin = find_package_manager(project_root)
    else:
        pm_bin = shutil.which(pm_name)
    if not pm_bin:
        log(_get_node_install_help(), level="error")
        return False

    cmd = _pm_install_all_command(pm_name)
    cmd[0] = pm_bin

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=300,
    )

    if result.returncode != 0:
        log(f"✖ {pm_name} install failed: {result.stderr.strip()}", level="error")
        return False

    log(f"✔ All dependencies installed ({pm_name})")
    return True


def _check_installed(project_root: str, name: str) -> bool:
    """Check if a package is installed in node_modules."""
    return os.path.exists(os.path.join(project_root, "node_modules", name, "package.json"))


def _get_installed_version(project_root: str, name: str) -> str:
    """Get installed version of a package from node_modules."""
    pkg_path = os.path.join(project_root, "node_modules", name, "package.json")
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version", "unknown")
    except (OSError, json.JSONDecodeError):
        return "unknown"


# ─── Node Modules Verification ───────────────────────────────────────────────

def verify_node_modules(project_root: str) -> Dict[str, Any]:
    """
    Verify that all dependencies in package.json are installed.
    Returns a report dict.
    """
    pkg = read_package_json(project_root)
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    installed = []
    missing = []

    for name, version in deps.items():
        if _check_installed(project_root, name):
            actual = _get_installed_version(project_root, name)
            installed.append({"name": name, "expected": version, "actual": actual})
        else:
            missing.append({"name": name, "expected": version})

    return {
        "total": len(deps),
        "installed": len(installed),
        "missing": len(missing),
        "installed_packages": installed,
        "missing_packages": missing,
        "node_modules_exists": os.path.exists(os.path.join(project_root, "node_modules")),
    }


def ensure_dependencies(project_root: str, auto_install: bool = True) -> bool:
    """
    Ensure all package.json dependencies are installed.
    If auto_install is True, run `npm install` if any are missing.
    """
    report = verify_node_modules(project_root)

    if report["missing"] == 0:
        return True

    if not auto_install:
        for pkg in report["missing_packages"]:
            log(f"  ✖ Missing: {pkg['name']}@{pkg['expected']}", level="warning")
        return False

    log(f"📦 {report['missing']} missing package(s). Running install...")
    return _run_pm_install(project_root)


__all__ = [
    "detect_package_manager",
    "find_node",
    "find_npm",
    "read_package_json",
    "write_package_json",
    "parse_package_spec",
    "update_tw_config_packages",
    "get_tw_config_packages",
    "install_packages",
    "remove_packages",
    "list_packages",
    "verify_node_modules",
    "ensure_dependencies",
]
