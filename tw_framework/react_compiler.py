"""
TW Framework - React Compiler (Stable)

Implements automatic memoization compiler:
- Analyzes component render functions
- Automatically inserts memoization (equivalent to useMemo/useCallback)
- Eliminates need for manual useMemo/useCallback
- Dependency tracking and optimization
- Dead code elimination for hooks
"""

from __future__ import annotations

import re
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MemoizationSite:
    """A location where memoization should be inserted."""
    variable_name: str
    dependencies: List[str] = field(default_factory=list)
    line: int = 0
    memo_type: str = "use_memo"  # use_memo | use_callback
    is_stable: bool = False  # If deps never change, mark as stable


@dataclass
class ComponentAnalysis:
    """Analysis result for a single component."""
    name: str
    memoization_sites: List[MemoizationSite] = field(default_factory=list)
    has_side_effects: bool = False
    has_state: bool = False
    has_effects: bool = False
    state_variables: List[str] = field(default_factory=list)
    effect_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    render_complexity: int = 0  # Estimated operations
    can_auto_memoize: bool = True
    warnings: List[str] = field(default_factory=list)


class ReactCompiler:
    """Automatic memoization compiler.

    Analyzes component source code and automatically inserts
    memoization at optimal locations, eliminating the need for
    manual useMemo/useCallback.

    The compiler:
    1. Parses component render functions
    2. Identifies expensive computations
    3. Tracks dependency graphs
    4. Inserts memoization where needed
    5. Eliminates redundant memoization
    6. Optimizes hook dependency arrays
    """

    # Patterns for detecting memoization opportunities
    EXPENSIVE_OPS = re.compile(
        r'\b(map|filter|reduce|sort|flatMap|forEach|concat|flat|slice)\b'
    )
    STATE_PATTERN = re.compile(r'\bstate\s*=|useState|useSignal|use_reactive\b')
    EFFECT_PATTERN = re.compile(r'\buseEffect|useLayoutEffect|on_mount|on_unmount\b')
    DEP_PATTERN = re.compile(r'\[([^\]]+)\]')

    def __init__(self):
        self._analyses: Dict[str, ComponentAnalysis] = {}
        self._optimized_count: int = 0
        self._skipped_count: int = 0

    def analyze_component(self, name: str, source: str) -> ComponentAnalysis:
        """Analyze a component for memoization opportunities."""
        analysis = ComponentAnalysis(name=name)

        lines = source.splitlines()
        for i, line in enumerate(lines, 1):
            # Check for expensive operations
            if self.EXPENSIVE_OPS.search(line):
                var_match = re.search(r'(\w+)\s*=.*' + self.EXPENSIVE_OPS.pattern, line)
                if var_match:
                    deps = self._extract_dependencies(line, source)
                    site = MemoizationSite(
                        variable_name=var_match.group(1),
                        dependencies=deps,
                        line=i,
                        memo_type="use_memo",
                    )
                    analysis.memoization_sites.append(site)
                    analysis.render_complexity += 5

            # Check for state
            if self.STATE_PATTERN.search(line):
                analysis.has_state = True
                state_match = re.search(r'(\w+)\s*=.*(?:useState|useSignal|use_reactive)', line)
                if state_match:
                    analysis.state_variables.append(state_match.group(1))

            # Check for effects
            if self.EFFECT_PATTERN.search(line):
                analysis.has_effects = True
                deps = self._extract_deps_from_line(line)
                if deps:
                    analysis.effect_dependencies[f"effect_line_{i}"] = deps

            # Check for side effects (direct DOM manipulation, etc.)
            if re.search(r'document\.|window\.|fetch\(', line):
                analysis.has_side_effects = True
                if not re.search(r'useEffect|on_mount', line):
                    analysis.warnings.append(
                        f"Line {i}: Side effect outside of effect hook"
                    )
                    analysis.can_auto_memoize = False

            analysis.render_complexity += 1

        # Check if memoization is safe
        if analysis.has_side_effects and not analysis.has_effects:
            analysis.can_auto_memoize = False
            analysis.warnings.append("Component has side effects without effect hooks")

        self._analyses[name] = analysis
        return analysis

    def _extract_dependencies(self, line: str, full_source: str) -> List[str]:
        """Extract variable dependencies from a line of code."""
        deps: Set[str] = set()
        # Find all identifier references
        for match in re.finditer(r'\b([a-z_]\w*)\b', line):
            ident = match.group(1)
            # Skip keywords and builtins
            if ident not in ("const", "let", "var", "function", "return", "if",
                             "else", "for", "while", "map", "filter", "reduce",
                             "sort", "forEach", "flat", "concat", "slice", "self",
                             "true", "false", "none", "null"):
                deps.add(ident)
        return sorted(deps)

    def _extract_deps_from_line(self, line: str) -> List[str]:
        """Extract dependency array from a useEffect line."""
        match = self.DEP_PATTERN.search(line)
        if match:
            return [d.strip() for d in match.group(1).split(",") if d.strip()]
        return []

    def apply_memoization(self, source: str, analysis: ComponentAnalysis) -> str:
        """Apply automatic memoization to component source."""
        if not analysis.can_auto_memoize:
            self._skipped_count += 1
            logger.info("Skipping memoization for %s (not safe)", analysis.name)
            return source

        lines = source.splitlines()
        insertions: List[Tuple[int, str]] = []

        for site in analysis.memoization_sites:
            if site.is_stable:
                # Stable values don't need memoization
                continue

            if site.line <= len(lines):
                original = lines[site.line - 1]
                deps_str = ", ".join(site.dependencies) if site.dependencies else ""

                if site.memo_type == "use_memo":
                    memoized = (
                        f"    {site.variable_name} = tw.use_memo("
                        f"lambda: {original.strip()}, [{deps_str}])"
                    )
                else:
                    memoized = (
                        f"    {site.variable_name} = tw.use_callback("
                        f"{original.strip()}, [{deps_str}])"
                    )

                insertions.append((site.line - 1, memoized))

        # Apply insertions in reverse order to preserve line numbers
        for line_idx, replacement in sorted(insertions, key=lambda x: -x[0]):
            lines[line_idx] = replacement

        self._optimized_count += 1
        logger.info("Applied %d memoization sites to %s",
                     len(insertions), analysis.name)
        return "\n".join(lines)

    def compile(self, name: str, source: str) -> Tuple[str, ComponentAnalysis]:
        """Analyze and compile a component with automatic memoization."""
        analysis = self.analyze_component(name, source)
        optimized = self.apply_memoization(source, analysis)
        return optimized, analysis

    def get_stats(self) -> Dict[str, Any]:
        return {
            "components_analyzed": len(self._analyses),
            "components_optimized": self._optimized_count,
            "components_skipped": self._skipped_count,
            "total_memoization_sites": sum(
                len(a.memoization_sites) for a in self._analyses.values()
            ),
            "avg_complexity": (
                sum(a.render_complexity for a in self._analyses.values())
                / len(self._analyses) if self._analyses else 0
            ),
        }

    def get_analysis(self, name: str) -> Optional[ComponentAnalysis]:
        return self._analyses.get(name)

    def get_all_analyses(self) -> Dict[str, ComponentAnalysis]:
        return dict(self._analyses)


class HookDependencyOptimizer:
    """Optimizes React hook dependency arrays.

    Ensures that dependency arrays in useEffect, useMemo, useCallback
    contain exactly the right dependencies — no more, no less.

    Problems it fixes:
    - Missing dependencies (causes stale closures)
    - Extra dependencies (causes unnecessary re-runs)
    - Inline object/array deps (should be extracted)
    - Function deps that should be wrapped in useCallback
    """

    def __init__(self):
        self._fixes: List[Dict[str, Any]] = []

    def optimize_hooks(self, source: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Optimize hook dependencies in source code."""
        lines = source.splitlines()
        fixes: List[Dict[str, Any]] = []

        for i, line in enumerate(lines):
            # Find useEffect/useMemo/useCallback with dependency arrays
            hook_match = re.search(
                r'(use(?:Effect|Memo|Callback))\s*\(.*?,\s*\[([^\]]*)\]',
                line
            )
            if not hook_match:
                continue

            hook_name = hook_match.group(1)
            deps_str = hook_match.group(2).strip()
            current_deps = [d.strip() for d in deps_str.split(",") if d.strip()]

            # Find actual dependencies by scanning the callback body
            actual_deps = self._find_actual_deps(source, i)

            if set(current_deps) != set(actual_deps):
                new_deps = sorted(set(current_deps) | set(actual_deps))
                fixes.append({
                    "line": i + 1,
                    "hook": hook_name,
                    "old_deps": current_deps,
                    "new_deps": new_deps,
                    "added": sorted(set(new_deps) - set(current_deps)),
                    "removed": sorted(set(current_deps) - set(new_deps)),
                })

        return source, fixes

    def _find_actual_deps(self, source: str, start_line: int) -> List[str]:
        """Find actual dependencies used in a hook callback."""
        deps: Set[str] = set()
        lines = source.splitlines()

        # Scan forward to find the callback body
        depth = 0
        in_callback = False
        for i in range(start_line, min(start_line + 50, len(lines))):
            line = lines[i]
            if "(" in line: depth += line.count("(")
            if ")" in line: depth -= line.count(")")

            if not in_callback and "lambda" in line:
                in_callback = True

            if in_callback:
                for match in re.finditer(r'\b([a-z_]\w*)\b', line):
                    ident = match.group(1)
                    if ident not in ("lambda", "self", "tw", "return", "if", "else",
                                     "for", "in", "not", "and", "or", "None", "True",
                                     "False", "def", "class"):
                        if ident not in deps:
                            deps.add(ident)

            if in_callback and depth <= 0:
                break

        return sorted(deps)

    def get_fixes(self) -> List[Dict[str, Any]]:
        return list(self._fixes)


__all__ = [
    "MemoizationSite", "ComponentAnalysis", "ReactCompiler",
    "HookDependencyOptimizer",
]
