"""
Enhanced Bundle Optimization for TW Framework.

Provides advanced bundle analysis and optimization:
  - Smart code splitting (per-page + shared chunks)
  - Tree shaking (remove unused exports)
  - Bundle analysis (size tracking, duplicate detection)
  - Import deduplication
  - Lazy loading support
  - Source map generation

Inspired by Next.js Turbopack + @next/bundle-analyzer.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
import time
import threading
import gzip
import base64

logger = logging.getLogger(__name__)


# ── Bundle Analysis ──────────────────────────────────────────────────

@dataclass
class ChunkInfo:
    """Information about a single JS chunk."""
    name: str
    url: str = ""
    size_bytes: int = 0
    size_gzip: int = 0
    modules: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    is_shared: bool = False
    is_entry: bool = False
    is_lazy: bool = False


@dataclass
class ModuleInfo:
    """Information about a single module."""
    path: str
    size_bytes: int = 0
    imported_by: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    used_exports: List[str] = field(default_factory=list)
    is_tree_shakeable: bool = False


class BundleAnalyzer:
    """Analyzes JS bundles and provides optimization recommendations.

    Like @next/bundle-analyzer — generates a report of all chunks,
    their sizes, and recommendations for optimization.
    """

    def __init__(self, output_dir: str = ""):
        self.output_dir = output_dir or os.path.join(os.getcwd(), "dist")
        self.chunks: List[ChunkInfo] = []
        self.modules: Dict[str, ModuleInfo] = {}

    def analyze_directory(self) -> Dict[str, Any]:
        """Analyze all JS files in the output directory."""
        chunks_dir = os.path.join(self.output_dir, "_tw", "static", "chunks")
        if not os.path.isdir(chunks_dir):
            # Fallback: scan all .js files in output
            chunks_dir = self.output_dir

        total_size = 0
        total_gzip = 0

        for root, _, files in os.walk(chunks_dir):
            for fname in files:
                if not fname.endswith(".js"):
                    continue
                fpath = os.path.join(root, fname)
                size = os.path.getsize(fpath)
                rel_path = os.path.relpath(fpath, self.output_dir)
                url = "/" + rel_path.replace(os.sep, "/")

                # Estimate gzip size (rough: ~30% of original for JS)
                gzip_size = int(size * 0.3)

                chunk = ChunkInfo(
                    name=fname,
                    url=url,
                    size_bytes=size,
                    size_gzip=gzip_size,
                    is_shared="runtime" in fname or "shared" in fname,
                    is_entry="page" in fname or "entry" in fname,
                )
                self.chunks.append(chunk)
                total_size += size
                total_gzip += gzip_size

        return {
            "total_chunks": len(self.chunks),
            "total_size_bytes": total_size,
            "total_size_kb": round(total_size / 1024, 2),
            "total_gzip_kb": round(total_gzip / 1024, 2),
            "chunks": [
                {
                    "name": c.name,
                    "url": c.url,
                    "size_kb": round(c.size_bytes / 1024, 2),
                    "gzip_kb": round(c.size_gzip / 1024, 2),
                    "is_shared": c.is_shared,
                    "is_entry": c.is_entry,
                }
                for c in sorted(self.chunks, key=lambda x: -x.size_bytes)
            ],
            "recommendations": self._generate_recommendations(),
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recs = []
        total = sum(c.size_bytes for c in self.chunks)

        if total > 500 * 1024:  # > 500KB total
            recs.append("Total bundle size exceeds 500KB — consider code splitting or lazy loading")

        for chunk in self.chunks:
            if chunk.size_bytes > 200 * 1024:  # > 200KB
                recs.append(f"Chunk '{chunk.name}' is {chunk.size_bytes // 1024}KB — consider splitting")

        # Check for duplicate modules
        shared_chunks = [c for c in self.chunks if c.is_shared]
        if len(shared_chunks) > 5:
            recs.append(f"Found {len(shared_chunks)} shared chunks — consider consolidating")

        if not recs:
            recs.append("Bundle size is optimal — no recommendations")

        return recs

    def generate_report(self) -> str:
        """Generate a human-readable bundle analysis report."""
        analysis = self.analyze_directory()
        lines = [
            "=" * 60,
            "  TW Framework — Bundle Analysis Report",
            "=" * 60,
            "",
            f"  Total chunks: {analysis['total_chunks']}",
            f"  Total size: {analysis['total_size_kb']} KB ({analysis['total_gzip_kb']} KB gzip)",
            "",
            "  Chunks (by size, descending):",
            "-" * 60,
        ]

        for chunk in analysis["chunks"]:
            icon = "📦" if chunk["is_shared"] else "📄"
            lines.append(
                f"  {icon} {chunk['name']:<30} "
                f"{chunk['size_kb']:>8} KB  "
                f"({chunk['gzip_kb']:>6} KB gzip)"
            )

        lines.extend([
            "-" * 60,
            "",
            "  Recommendations:",
        ])
        for rec in analysis["recommendations"]:
            lines.append(f"    • {rec}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def save_report(self, path: str = "") -> str:
        """Save report to file and return path."""
        path = path or os.path.join(self.output_dir, "bundle-report.txt")
        report = self.generate_report()
        try:
            with open(path, "w") as f:
                f.write(report)
        except OSError:
            pass
        return path


# ── Smart Code Splitting ─────────────────────────────────────────────

class SmartCodeSplitter:
    """Advanced code splitting with shared chunk detection.

    Analyzes all pages and their JS imports to determine:
    - Which modules are shared across multiple pages → shared chunk
    - Which modules are page-specific → per-page chunk
    - Which modules can be lazy-loaded → lazy chunk
    - Optimal chunk splitting to minimize total download

    Like Turbopack's automatic chunking.
    """

    def __init__(self):
        self.page_modules: Dict[str, Set[str]] = {}  # page → set of module paths
        self.module_usage: Dict[str, Set[str]] = {}  # module → set of pages using it

    def register_page(self, page_path: str, modules: Set[str]) -> None:
        """Register a page and its JS module dependencies."""
        self.page_modules[page_path] = modules
        for mod in modules:
            self.module_usage.setdefault(mod, set()).add(page_path)

    def compute_chunks(self) -> Dict[str, Any]:
        """Compute optimal chunk splitting.

        Returns a dict with:
        - shared: modules used by 2+ pages → shared chunk
        - per_page: modules used by 1 page → page-specific chunk
        - lazy: modules that can be lazy-loaded
        """
        shared_modules: Set[str] = set()
        per_page_modules: Dict[str, Set[str]] = {}

        for mod, pages in self.module_usage.items():
            if len(pages) >= 2:
                shared_modules.add(mod)
            else:
                # Single page — page-specific
                page = next(iter(pages))
                per_page_modules.setdefault(page, set()).add(mod)

        # Identify lazy-loadable modules (heavy modules used on specific pages)
        lazy_candidates: Set[str] = set()
        for mod in shared_modules:
            # Heuristic: if module path contains "chart", "editor", "markdown", etc.
            # it's a candidate for lazy loading
            lazy_keywords = ["chart", "editor", "markdown", "pdf", "excel", "calendar"]
            if any(kw in mod.lower() for kw in lazy_keywords):
                lazy_candidates.add(mod)

        # Remove lazy candidates from shared (they'll be separate chunks)
        shared_modules -= lazy_candidates

        return {
            "shared": {
                "modules": sorted(shared_modules),
                "count": len(shared_modules),
                "chunk_name": "shared.js",
            },
            "lazy": {
                "modules": sorted(lazy_candidates),
                "count": len(lazy_candidates),
                "chunk_name": "lazy.js",
            },
            "per_page": {
                page: sorted(mods)
                for page, mods in per_page_modules.items()
            },
            "total_modules": len(self.module_usage),
            "total_pages": len(self.page_modules),
        }

    def generate_chunk_manifest(self) -> str:
        """Generate a JSON manifest of all chunks for the client runtime."""
        chunks = self.compute_chunks()
        manifest = {
            "version": 2,
            "shared_chunk": chunks["shared"]["chunk_name"],
            "lazy_chunk": chunks["lazy"]["chunk_name"],
            "page_chunks": {},
        }
        for page, modules in chunks["per_page"].items():
            manifest["page_chunks"][page] = {
                "chunk": f"page-{hashlib.md5(page.encode()).hexdigest()[:8]}.js",
                "module_count": len(modules),
            }
        return json.dumps(manifest, indent=2)


# ── Enhanced Tree Shaking ────────────────────────────────────────────

class EnhancedTreeShaker:
    """Advanced tree shaking with export tracking.

    Removes unused exports from modules, similar to esbuild/webpack tree shaking.
    Tracks which exports are actually used across the project.
    """

    def __init__(self):
        self.module_exports: Dict[str, Set[str]] = {}  # module → exported names
        self.used_exports: Dict[str, Set[str]] = {}     # module → used export names
        self.import_graph: Dict[str, Set[str]] = {}     # module → imported modules

    def register_module(self, path: str, exports: Set[str], imports: Set[str] = None) -> None:
        """Register a module with its exports and imports."""
        self.module_exports[path] = exports
        self.import_graph[path] = imports or set()
        self.used_exports[path] = set()

    def mark_used(self, module_path: str, export_name: str) -> None:
        """Mark an export as used (not shakeable)."""
        self.used_exports.setdefault(module_path, set()).add(export_name)

    def analyze_imports(self, source: str, module_path: str) -> None:
        """Scan source code for import usage and mark exports as used."""
        # Match: import { foo, bar } from "./module"
        named_import = re.compile(r'import\s+\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']')
        for match in named_import.finditer(source):
            exports_str = match.group(1)
            mod_path = match.group(2)
            for export_name in exports_str.split(","):
                export_name = export_name.strip().split(" as ")[0].strip()
                if export_name:
                    self.mark_used(mod_path, export_name)

        # Match: import Name from "./module" (default import)
        default_import = re.compile(r'import\s+(\w+)\s+from\s+["\']([^"\']+)["\']')
        for match in default_import.finditer(source):
            mod_path = match.group(2)
            self.mark_used(mod_path, "default")

        # Match: import * as Name from "./module" (namespace import)
        namespace_import = re.compile(r'import\s+\*\s+as\s+(\w+)\s+from\s+["\']([^"\']+)["\']')
        for match in namespace_import.finditer(source):
            mod_path = match.group(2)
            # Mark all exports as used (namespace import uses everything)
            if mod_path in self.module_exports:
                for export_name in self.module_exports[mod_path]:
                    self.mark_used(mod_path, export_name)

    def shake(self) -> Dict[str, Any]:
        """Perform tree shaking — identify unused exports.

        Returns a report of shakeable exports per module.
        """
        report: Dict[str, Any] = {
            "modules_analyzed": len(self.module_exports),
            "total_exports": 0,
            "used_exports": 0,
            "shakeable_exports": 0,
            "details": {},
        }

        for mod_path, exports in self.module_exports.items():
            used = self.used_exports.get(mod_path, set())
            unused = exports - used
            report["total_exports"] += len(exports)
            report["used_exports"] += len(used)
            report["shakeable_exports"] += len(unused)

            if unused:
                report["details"][mod_path] = {
                    "total": len(exports),
                    "used": len(used),
                    "shakeable": sorted(unused),
                    "savings_bytes_est": len(unused) * 50,  # Rough estimate: 50 bytes per export
                }

        return report

    def apply_shaking(self, source: str, module_path: str) -> str:
        """Remove unused exports from source code.

        This is a simplified version — a full implementation would use
        an AST parser. This regex-based version handles common patterns.
        """
        unused = self.module_exports.get(module_path, set()) - self.used_exports.get(module_path, set())
        if not unused:
            return source

        # Remove unused named exports from export statements
        # Pattern: export { foo, bar, baz } → remove unused names
        def _filter_exports(match):
            names_str = match.group(1)
            names = [n.strip().split(" as ")[0].strip() for n in names_str.split(",")]
            kept = [n for n in names if n not in unused]
            if not kept:
                return ""  # Remove entire export if nothing left
            return f"export {{ {', '.join(kept)} }}"

        result = re.sub(
            r'export\s+\{([^}]+)\}',
            _filter_exports,
            source
        )

        return result


# ── Import Deduplicator ──────────────────────────────────────────────

class ImportDeduplicator:
    """Deduplicates imports across the bundle.

    If multiple modules import the same dependency, this ensures
    the dependency is only bundled once (in a shared chunk).
    """

    def __init__(self):
        self.imports: Dict[str, Set[str]] = {}  # file → set of import paths
        self.duplicate_imports: Dict[str, List[str]] = {}  # import_path → list of files

    def scan_file(self, file_path: str, source: str) -> None:
        """Scan a file for import statements."""
        found: Set[str] = set()

        # ES imports
        for match in re.finditer(r'(?:import|export)[^"]*["\']([^"\']+)["\']', source):
            found.add(match.group(1))

        # CJS require
        for match in re.finditer(r'require\s*\(\s*["\']([^"\']+)["\']\s*\)', source):
            found.add(match.group(1))

        self.imports[file_path] = found

        for imp in found:
            self.duplicate_imports.setdefault(imp, []).append(file_path)

    def get_duplicates(self) -> Dict[str, List[str]]:
        """Return imports that appear in multiple files."""
        return {
            imp: files
            for imp, files in self.duplicate_imports.items()
            if len(set(files)) > 1
        }

    def get_shared_imports(self) -> Set[str]:
        """Return import paths used by 2+ files → candidates for shared chunk."""
        return {
            imp for imp, files in self.duplicate_imports.items()
            if len(set(files)) >= 2
        }


# ── Unified Optimizer ────────────────────────────────────────────────

class BundleOptimizer:
    """Unified bundle optimization manager.

    Combines code splitting, tree shaking, bundle analysis, and
    import deduplication into a single pipeline.
    """

    def __init__(self, output_dir: str = ""):
        self.output_dir = output_dir or os.path.join(os.getcwd(), "dist")
        self.analyzer = BundleAnalyzer(self.output_dir)
        self.splitter = SmartCodeSplitter()
        self.shaker = EnhancedTreeShaker()
        self.deduplicator = ImportDeduplicator()

    def optimize(self) -> Dict[str, Any]:
        """Run the full optimization pipeline.

        1. Analyze existing bundles
        2. Compute optimal code splitting
        3. Tree shake unused exports
        4. Deduplicate imports
        5. Generate report
        """
        # Step 1: Analyze
        analysis = self.analyzer.analyze_directory()

        # Step 2: Compute chunks
        chunks = self.splitter.compute_chunks()

        # Step 3: Tree shake
        shaking_report = self.shaker.shake()

        # Step 4: Deduplicate
        duplicates = self.deduplicator.get_duplicates()
        shared_imports = self.deduplicator.get_shared_imports()

        return {
            "analysis": analysis,
            "code_splitting": chunks,
            "tree_shaking": shaking_report,
            "import_deduplication": {
                "duplicates": {k: len(set(v)) for k, v in duplicates.items()},
                "shared_imports": sorted(shared_imports),
            },
            "report_path": self.analyzer.save_report(),
        }

    def generate_report(self) -> str:
        """Generate a human-readable optimization report."""
        return self.analyzer.generate_report()


__all__ = [
    "ChunkInfo",
    "ModuleInfo",
    "BundleAnalyzer",
    "SmartCodeSplitter",
    "EnhancedTreeShaker",
    "ImportDeduplicator",
    "BundleOptimizer",
    "ChunkDependency",
    "ChunkGraph",
    "SourceMapEntry",
    "SourceMapGenerator",
    "BuildPipelineIntegrator",
    "BundlePlugin",
    "BundlePluginManager",
    "BundleWatcher",
    "CSSRule",
    "CSSOptimizationResult",
    "CSSOptimizer",
    "AssetInfo",
    "AssetPipeline",
    "ImageVariant",
    "ImageOptimizer",
    "BudgetRule",
    "BundleBudgetEnforcer",
]


# ── Chunk Graph ─────────────────────────────────────────────────────

@dataclass
class ChunkDependency:
    """Dependency between chunks."""
    chunk_name: str
    depends_on: str
    import_type: str = "static"  # static | dynamic | lazy


class ChunkGraph:
    """Directed graph of chunk dependencies.

    Represents which chunks import which other chunks.
    Used for:
    - Determining load order
    - Detecting circular dependencies
    - Computing transitive dependencies
    - Generating preload/prefetch hints
    """

    def __init__(self):
        self._nodes: Set[str] = set()
        self._edges: Dict[str, List[ChunkDependency]] = {}

    def add_chunk(self, name: str) -> None:
        """Add a chunk to the graph."""
        self._nodes.add(name)
        self._edges.setdefault(name, [])

    def add_dependency(self, chunk_name: str, depends_on: str,
                       import_type: str = "static") -> None:
        """Add a dependency edge."""
        self.add_chunk(chunk_name)
        self.add_chunk(depends_on)
        self._edges[chunk_name].append(
            ChunkDependency(chunk_name, depends_on, import_type)
        )

    def get_dependencies(self, chunk_name: str) -> List[str]:
        """Get direct dependencies of a chunk."""
        return [dep.depends_on for dep in self._edges.get(chunk_name, [])]

    def get_transitive_dependencies(self, chunk_name: str) -> List[str]:
        """Get all transitive dependencies (BFS)."""
        visited: Set[str] = set()
        queue: List[str] = [chunk_name]
        result: List[str] = []

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for dep in self._edges.get(current, []):
                if dep.depends_on not in visited:
                    result.append(dep.depends_on)
                    queue.append(dep.depends_on)

        return result

    def get_load_order(self) -> List[str]:
        """Topological sort — chunks must load in this order."""
        in_degree: Dict[str, int] = {n: 0 for n in self._nodes}
        adj: Dict[str, List[str]] = {n: [] for n in self._nodes}

        for chunk_name, deps in self._edges.items():
            for dep in deps:
                if dep.import_type == "static":
                    adj[dep.depends_on].append(chunk_name)
                    in_degree[chunk_name] = in_degree.get(chunk_name, 0) + 1

        # Kahn's algorithm
        from collections import deque
        queue: deque = deque([n for n, d in in_degree.items() if d == 0])
        order: List[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._nodes):
            # Circular dependency — return best effort
            remaining = self._nodes - set(order)
            order.extend(remaining)

        return order

    def detect_cycles(self) -> List[List[str]]:
        """Detect circular dependencies using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in self._nodes}
        parent: Dict[str, Optional[str]] = {n: None for n in self._nodes}
        cycles: List[List[str]] = []

        def dfs(u: str):
            color[u] = GRAY
            for dep in self._edges.get(u, []):
                v = dep.depends_on
                if color.get(v, WHITE) == GRAY:
                    # Found cycle
                    cycle: List[str] = [v]
                    curr = u
                    while curr != v and curr is not None:
                        cycle.append(curr)
                        curr = parent.get(curr)
                    cycle.append(v)
                    cycle.reverse()
                    cycles.append(cycle)
                elif color.get(v, WHITE) == WHITE:
                    parent[v] = u
                    dfs(v)
            color[u] = BLACK

        for node in self._nodes:
            if color[node] == WHITE:
                dfs(node)

        return cycles

    def get_preload_hints(self, chunk_name: str) -> List[str]:
        """Get chunks that should be preloaded when this chunk loads."""
        deps = self.get_transitive_dependencies(chunk_name)
        return [d for d in deps if d in self._nodes]

    def get_lazy_chunks(self) -> List[str]:
        """Get chunks that are only loaded via dynamic import."""
        all_chunks = set(self._nodes)
        statically_loaded = set()

        for chunk_name, deps in self._edges.items():
            for dep in deps:
                if dep.import_type == "static":
                    statically_loaded.add(dep.depends_on)

        return list(all_chunks - statically_loaded)

    def to_json(self) -> str:
        """Serialize graph to JSON."""
        return json.dumps({
            "nodes": sorted(self._nodes),
            "edges": [
                {"from": e.chunk_name, "to": e.depends_on, "type": e.import_type}
                for edges in self._edges.values()
                for e in edges
            ],
        }, indent=2)

    def stats(self) -> Dict[str, Any]:
        """Return graph statistics."""
        edge_count = sum(len(edges) for edges in self._edges.values())
        static_edges = sum(1 for edges in self._edges.values()
                           for e in edges if e.import_type == "static")
        dynamic_edges = sum(1 for edges in self._edges.values()
                             for e in edges if e.import_type == "dynamic")
        lazy_edges = sum(1 for edges in self._edges.values()
                         for e in edges if e.import_type == "lazy")
        return {
            "chunks": len(self._nodes),
            "edges": edge_count,
            "static_imports": static_edges,
            "dynamic_imports": dynamic_edges,
            "lazy_imports": lazy_edges,
            "cycles": len(self.detect_cycles()),
            "lazy_chunks": len(self.get_lazy_chunks()),
        }


# ── Source Map Generator ─────────────────────────────────────────────

@dataclass
class SourceMapEntry:
    """A single source map mapping entry."""
    generated_line: int
    generated_col: int
    source_file: str
    source_line: int
    source_col: int
    name: str = ""


class SourceMapGenerator:
    """Generates source maps for bundled JavaScript.

    Creates a standard Source Map v3 format mapping from
    generated bundle output back to original source files.
    """

    def __init__(self, source_root: str = ""):
        self.source_root = source_root
        self._entries: List[SourceMapEntry] = []
        self._sources: Set[str] = set()
        self._names: Set[str] = set()

    def add_mapping(self, gen_line: int, gen_col: int,
                    source_file: str, src_line: int, src_col: int,
                    name: str = "") -> None:
        """Add a source map mapping."""
        entry = SourceMapEntry(gen_line, gen_col, source_file, src_line, src_col, name)
        self._entries.append(entry)
        self._sources.add(source_file)
        if name:
            self._names.add(name)

    def add_block(self, gen_start_line: int, source_file: str,
                  src_start_line: int, line_count: int,
                  name: str = "") -> None:
        """Add a block of mappings (line-by-line)."""
        for i in range(line_count):
            self.add_mapping(
                gen_line=gen_start_line + i,
                gen_col=0,
                source_file=source_file,
                src_line=src_start_line + i,
                src_col=0,
                name=name if i == 0 else "",
            )

    def generate(self) -> Dict[str, Any]:
        """Generate the source map object (Source Map v3 format)."""
        # Sort entries by generated position
        sorted_entries = sorted(self._entries, key=lambda e: (e.generated_line, e.generated_col))

        # Build VLQ-encoded mappings string
        mappings = self._encode_vlq_mappings(sorted_entries)

        return {
            "version": 3,
            "sourceRoot": self.source_root,
            "sources": sorted(self._sources),
            "names": sorted(self._names),
            "mappings": mappings,
        }

    def generate_json(self) -> str:
        """Generate source map as JSON string."""
        return json.dumps(self.generate(), indent=2)

    def save(self, output_path: str) -> str:
        """Save source map to file."""
        smap = self.generate_json()
        try:
            with open(output_path, "w") as f:
                f.write(smap)
        except OSError:
            pass
        return output_path

    @staticmethod
    def _encode_vlq(value: int) -> str:
        """Encode a single integer as VLQ base64."""
        BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        VLQ_BASE_SHIFT = 5
        VLQ_BASE = 1 << VLQ_BASE_SHIFT
        VLQ_MASK = VLQ_BASE - 1
        VLQ_CONTINUATION_BIT = VLQ_BASE

        if value < 0:
            value = (-value << 1) | 1
        else:
            value = value << 1

        result = ""
        while True:
            digit = value & VLQ_MASK
            value >>= VLQ_BASE_SHIFT
            if value > 0:
                digit |= VLQ_CONTINUATION_BIT
            result += BASE64_CHARS[digit]
            if value == 0:
                break

        return result

    def _encode_vlq_mappings(self, entries: List[SourceMapEntry]) -> str:
        """Encode all mappings as VLQ segments."""
        segments: List[str] = []
        prev_gen_line = 0
        prev_gen_col = 0
        prev_source_idx = 0
        prev_source_line = 0
        prev_source_col = 0
        prev_name_idx = 0

        sources_sorted = sorted(self._sources)
        names_sorted = sorted(self._names)

        current_line_segments: List[str] = []

        for entry in entries:
            # Handle line breaks
            while entry.generated_line > prev_gen_line:
                segments.append(",".join(current_line_segments))
                current_line_segments = []
                prev_gen_line += 1
                prev_gen_col = 0

            source_idx = sources_sorted.index(entry.source_file)
            gen_col_delta = entry.generated_col - prev_gen_col
            source_delta = source_idx - prev_source_idx
            src_line_delta = entry.source_line - prev_source_line
            src_col_delta = entry.source_col - prev_source_col

            segment = self._encode_vlq(gen_col_delta)
            segment += self._encode_vlq(source_delta)
            segment += self._encode_vlq(src_line_delta)
            segment += self._encode_vlq(src_col_delta)

            if entry.name:
                name_idx = names_sorted.index(entry.name)
                name_delta = name_idx - prev_name_idx
                segment += self._encode_vlq(name_delta)
                prev_name_idx = name_idx

            current_line_segments.append(segment)
            prev_gen_col = entry.generated_col
            prev_source_idx = source_idx
            prev_source_line = entry.source_line
            prev_source_col = entry.source_col

        if current_line_segments:
            segments.append(",".join(current_line_segments))

        return ";".join(segments)


# ── Build Pipeline Integration ────────────────────────────────────────

class BuildPipelineIntegrator:
    """Integrates bundle optimization into the TW build pipeline.

    Called from compiler.py's build_page_job() to:
    1. Analyze page dependencies
    2. Split into optimal chunks
    3. Tree-shake unused exports
    4. Generate source maps
    5. Minify output
    6. Write chunk manifest
    """

    def __init__(self, output_dir: str = ""):
        self.output_dir = output_dir or os.path.join(os.getcwd(), "dist")
        self.optimizer = BundleOptimizer(self.output_dir)
        self.graph = ChunkGraph()
        self.source_map_gen = SourceMapGenerator(self.output_dir)
        self._page_js: Dict[str, str] = {}

    def register_page_js(self, page_path: str, js_source: str,
                         imports: Optional[Set[str]] = None) -> None:
        """Register a page's JavaScript and its imports."""
        self._page_js[page_path] = js_source
        imports = imports or set()

        # Register with splitter
        self.optimizer.splitter.register_page(page_path, imports)

        # Register with chunk graph
        self.graph.add_chunk(f"page:{page_path}")
        for imp in imports:
            self.graph.add_chunk(imp)
            self.graph.add_dependency(f"page:{page_path}", imp, "static")

    def register_shared_module(self, module_path: str, exports: Set[str],
                                imports: Optional[Set[str]] = None) -> None:
        """Register a shared module."""
        self.optimizer.shaker.register_module(module_path, exports, imports or set())
        self.graph.add_chunk(module_path)

    def optimize(self) -> Dict[str, Any]:
        """Run the full optimization pipeline.

        Returns a comprehensive report.
        """
        # Step 1: Analyze existing bundles
        analysis = self.optimizer.analyzer.analyze_directory()

        # Step 2: Compute optimal chunks
        chunks = self.optimizer.splitter.compute_chunks()

        # Step 3: Tree shake
        shaking_report = self.optimizer.shaker.shake()

        # Step 4: Deduplicate imports
        duplicates = self.optimizer.deduplicator.get_duplicates()
        shared_imports = self.optimizer.deduplicator.get_shared_imports()

        # Step 5: Chunk graph analysis
        graph_stats = self.graph.stats()
        load_order = self.graph.get_load_order()
        cycles = self.graph.detect_cycles()
        lazy_chunks = self.graph.get_lazy_chunks()

        # Step 6: Generate chunk manifest
        chunk_manifest = self.optimizer.splitter.generate_chunk_manifest()

        # Step 7: Generate source maps
        source_map_path = os.path.join(self.output_dir, "_tw", "static", "chunks.js.map")
        try:
            os.makedirs(os.path.dirname(source_map_path), exist_ok=True)
            self.source_map_gen.save(source_map_path)
        except OSError:
            pass

        # Step 8: Generate preload hints
        preload_hints = {}
        for page in self._page_js:
            hints = self.graph.get_preload_hints(f"page:{page}")
            preload_hints[page] = [h for h in hints if h.startswith("tw:") or h.startswith("@")]

        return {
            "analysis": analysis,
            "code_splitting": chunks,
            "tree_shaking": shaking_report,
            "import_deduplication": {
                "duplicates": {k: len(set(v)) for k, v in duplicates.items()},
                "shared_imports": sorted(shared_imports),
            },
            "chunk_graph": graph_stats,
            "load_order": load_order,
            "cycles_detected": cycles,
            "lazy_chunks": lazy_chunks,
            "chunk_manifest": json.loads(chunk_manifest) if chunk_manifest else {},
            "preload_hints": preload_hints,
            "source_map": source_map_path,
            "report_path": self.optimizer.analyzer.save_report(),
        }

    def generate_html_tags(self, page_path: str) -> str:
        """Generate HTML <script> tags for a page.

        Includes:
        - Preload hints for critical chunks
        - Script tags in load order
        - Lazy loading for non-critical chunks
        - Source map reference
        """
        deps = self.graph.get_transitive_dependencies(f"page:{page_path}")
        load_order = self.graph.get_load_order()

        tags: List[str] = []

        # Preload critical chunks
        for dep in deps[:3]:  # Preload top 3
            chunk_url = f"/_tw/static/chunks/{dep.replace('/', '_')}.js"
            tags.append(f'<link rel="preload" href="{chunk_url}" as="script" crossorigin>')

        # Script tags in load order
        for chunk in load_order:
            if chunk.startswith("page:"):
                continue  # Don't pre-load the page itself
            chunk_url = f"/_tw/static/chunks/{chunk.replace('/', '_')}.js"
            is_lazy = chunk in self.graph.get_lazy_chunks()
            if is_lazy:
                tags.append(f'<script src="{chunk_url}" defer></script>')
            else:
                tags.append(f'<script src="{chunk_url}"></script>')

        # Page-specific script
        if page_path in self._page_js:
            page_chunk = f"page-{hashlib.md5(page_path.encode()).hexdigest()[:8]}.js"
            tags.append(f'<script src="/_tw/static/chunks/{page_chunk}"></script>')

        # Source map reference
        tags.append('<!--# sourceMappingURL=chunks.js.map -->')

        return "\n".join(tags)

    def get_optimization_report(self) -> str:
        """Generate a human-readable optimization report."""
        report_lines = [
            self.optimizer.generate_report(),
            "",
            "  Chunk Graph Stats:",
            "-" * 60,
        ]

        stats = self.graph.stats()
        for key, value in stats.items():
            report_lines.append(f"  {key}: {value}")

        cycles = self.graph.detect_cycles()
        if cycles:
            report_lines.append("")
            report_lines.append("  ⚠️  Circular Dependencies Detected:")
            for cycle in cycles:
                report_lines.append(f"    {' → '.join(cycle)}")
        else:
            report_lines.append("")
            report_lines.append("  ✓ No circular dependencies")

        report_lines.append("")
        report_lines.append("  Load Order:")
        for i, chunk in enumerate(self.graph.get_load_order()):
            report_lines.append(f"    {i+1}. {chunk}")

        report_lines.append("")
        report_lines.append("=" * 60)
        return "\n".join(report_lines)


# ── Plugin System for Bundle Optimization ───────────────────────────

@dataclass
class BundlePlugin:
    """A bundle optimization plugin."""
    name: str
    optimize_fn: Callable[[str], str]  # takes JS source, returns optimized JS
    priority: int = 0  # lower = runs first
    enabled: bool = True
    description: str = ""


class BundlePluginManager:
    """Manages bundle optimization plugins.

    Plugins can transform JavaScript output at various stages:
    - Before minification
    - After minification
    - Before source map generation
    - After chunk splitting

    Built-in plugins:
    - DeadCodeEliminator: removes unreachable code
    - ConsoleStripper: removes console.log in production
    - ConstantFolder: folds constant expressions
    - VariableMinifier: renames variables to shorter names
    """

    def __init__(self):
        self._plugins: List[BundlePlugin] = []
        self._register_builtin_plugins()

    def _register_builtin_plugins(self) -> None:
        """Register built-in optimization plugins."""
        self.register(BundlePlugin(
            name="console-stripper",
            optimize_fn=self._strip_console,
            priority=10,
            description="Removes console.log/warn/error in production builds",
        ))
        self.register(BundlePlugin(
            name="dead-code-eliminator",
            optimize_fn=self._eliminate_dead_code,
            priority=20,
            description="Removes unreachable code blocks (if(false){...})",
        ))
        self.register(BundlePlugin(
            name="comment-stripper",
            optimize_fn=self._strip_comments,
            priority=30,
            description="Removes JavaScript comments",
        ))
        self.register(BundlePlugin(
            name="whitespace-minifier",
            optimize_fn=self._minify_whitespace,
            priority=40,
            description="Removes unnecessary whitespace",
        ))

    def register(self, plugin: BundlePlugin) -> None:
        """Register a plugin."""
        self._plugins.append(plugin)
        self._plugins.sort(key=lambda p: p.priority)

    def enable(self, name: str) -> bool:
        """Enable a plugin by name."""
        for p in self._plugins:
            if p.name == name:
                p.enabled = True
                return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a plugin by name."""
        for p in self._plugins:
            if p.name == name:
                p.enabled = False
                return True
        return False

    def run_all(self, js_source: str) -> str:
        """Run all enabled plugins in priority order."""
        result = js_source
        for plugin in self._plugins:
            if plugin.enabled:
                try:
                    result = plugin.optimize_fn(result)
                except Exception as e:
                    logger.warning("Plugin %s failed: %s", plugin.name, e)
        return result

    def get_plugin_info(self) -> List[Dict[str, Any]]:
        """Return info about all plugins."""
        return [
            {
                "name": p.name,
                "priority": p.priority,
                "enabled": p.enabled,
                "description": p.description,
            }
            for p in self._plugins
        ]

    @staticmethod
    def _strip_console(js: str) -> str:
        """Remove console.log/warn/error/debug statements."""
        import re
        # Remove console.log(...), console.warn(...), etc.
        js = re.sub(
            r'console\.(log|warn|error|debug|info)\s*\([^)]*\)\s*;?',
            '',
            js,
        )
        return js

    @staticmethod
    def _eliminate_dead_code(js: str) -> str:
        """Remove unreachable code blocks."""
        import re
        # Remove if(false){...}
        js = re.sub(r'if\s*\(\s*false\s*\)\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}', '', js)
        # Remove if(true){...} → keep the body
        def _unwrap_true(match):
            body = match.group(1)
            return body
        js = re.sub(r'if\s*\(\s*true\s*\)\s*\{([^}]*)\}', _unwrap_true, js)
        return js

    @staticmethod
    def _strip_comments(js: str) -> str:
        """Remove JavaScript comments."""
        import re
        # Remove /* */ comments
        js = re.sub(r'/\*.*?\*/', '', js, flags=re.DOTALL)
        # Remove // comments (but not in strings — simplified)
        lines = js.split('\n')
        stripped = []
        in_string = False
        for line in lines:
            result = []
            i = 0
            while i < len(line):
                if line[i] == '"' or line[i] == "'":
                    in_string = not in_string
                    result.append(line[i])
                elif not in_string and line[i:i+2] == '//':
                    break  # Rest is comment
                else:
                    result.append(line[i])
                i += 1
            stripped.append(''.join(result))
        return '\n'.join(stripped)

    @staticmethod
    def _minify_whitespace(js: str) -> str:
        """Remove unnecessary whitespace from JavaScript."""
        import re
        # Remove leading/trailing whitespace on each line
        lines = [line.strip() for line in js.split('\n')]
        js = ' '.join(lines)
        # Collapse multiple spaces
        js = re.sub(r'\s{2,}', ' ', js)
        # Remove spaces around operators
        js = re.sub(r'\s*([=+\-*/<>!&|{};,:()])\s*', r'\1', js)
        # Restore space after keywords
        for kw in ('var', 'let', 'const', 'function', 'return', 'if', 'else',
                   'for', 'while', 'switch', 'case', 'break', 'continue',
                   'throw', 'try', 'catch', 'finally', 'new', 'delete',
                   'typeof', 'instanceof', 'void', 'this', 'class', 'extends',
                   'import', 'export', 'default', 'from', 'as'):
            js = re.sub(rf'\b{kw}([a-zA-Z_$])', f'{kw} \1', js)
        return js


# ── Bundle Watcher ──────────────────────────────────────────────────

class BundleWatcher:
    """Watches for file changes and triggers incremental re-bundling.

    Used in dev mode (--watch) to re-optimize only the affected
    chunks when a source file changes.
    """

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self._watched_files: Dict[str, float] = {}  # path → last_modified
        self._change_callbacks: List[Callable[[str], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def watch(self, path: str) -> None:
        """Add a file to watch."""
        if os.path.exists(path):
            self._watched_files[path] = os.path.getmtime(path)

    def watch_directory(self, dir_path: str, extensions: Optional[Set[str]] = None) -> None:
        """Watch all files in a directory."""
        extensions = extensions or {".js", ".ts", ".tw", ".tss"}
        if not os.path.isdir(dir_path):
            return
        for root, _, files in os.walk(dir_path):
            for fname in files:
                if any(fname.endswith(ext) for ext in extensions):
                    fpath = os.path.join(root, fname)
                    self.watch(fpath)

    def on_change(self, callback: Callable[[str], None]) -> None:
        """Register a callback for file changes."""
        self._change_callbacks.append(callback)

    def check_changes(self) -> List[str]:
        """Check for changed files (non-blocking).

        Returns list of changed file paths.
        """
        changed: List[str] = []
        for path, last_mtime in list(self._watched_files.items()):
            if not os.path.exists(path):
                changed.append(path)
                del self._watched_files[path]
                continue
            current_mtime = os.path.getmtime(path)
            if current_mtime != last_mtime:
                self._watched_files[path] = current_mtime
                changed.append(path)

        # Trigger callbacks
        for path in changed:
            for callback in self._change_callbacks:
                try:
                    callback(path)
                except Exception as e:
                    logger.warning("Bundle watcher callback failed: %s", e)

        return changed

    def start(self, interval: float = 1.0) -> None:
        """Start watching in a background thread."""
        self._running = True
        def _loop():
            while self._running:
                self.check_changes()
                time.sleep(interval)
        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()
        logger.info("Bundle watcher started (%d files)", len(self._watched_files))

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Bundle watcher stopped")

    def get_watched_files(self) -> List[str]:
        """Return list of watched files."""
        return sorted(self._watched_files.keys())


# ── Update __all__ ──────────────────────────────────────────────────


# ── CSS Optimizer ────────────────────────────────────────────────────

@dataclass
class CSSRule:
    """A single CSS rule."""
    selector: str
    properties: Dict[str, str] = field(default_factory=dict)
    media_query: str = ""
    important: bool = False


@dataclass
class CSSOptimizationResult:
    """Result of CSS optimization."""
    original_size: int = 0
    optimized_size: int = 0
    rules_before: int = 0
    rules_after: int = 0
    duplicates_removed: int = 0
    unused_removed: int = 0
    minified: bool = False


class CSSOptimizer:
    """CSS optimization and minification.

    Features:
    - Minification (remove comments, whitespace, unnecessary chars)
    - Duplicate rule detection and removal
    - Unused selector elimination (based on used class list)
    - Property sorting for better gzip compression
    - Media query grouping
    - CSS variable extraction
    - Critical CSS extraction
    """

    def __init__(self, minify: bool = True, remove_duplicates: bool = True,
                 sort_properties: bool = True):
        self.minify = minify
        self.remove_duplicates = remove_duplicates
        self.sort_properties = sort_properties
        self._used_classes: Set[str] = set()

    def set_used_classes(self, classes: Set[str]) -> None:
        """Set the set of CSS classes actually used in the HTML/JS."""
        self._used_classes = classes

    def optimize(self, css: str) -> Tuple[str, CSSOptimizationResult]:
        """Optimize CSS and return (optimized_css, result)."""
        result = CSSOptimizationResult()
        result.original_size = len(css)

        rules = self._parse_css(css)
        result.rules_before = len(rules)

        if self.remove_duplicates:
            rules, dup_count = self._remove_duplicate_rules(rules)
            result.duplicates_removed = dup_count

        if self._used_classes:
            rules, unused_count = self._remove_unused_selectors(rules)
            result.unused_removed = unused_count

        if self.sort_properties:
            for rule in rules:
                rule.properties = dict(sorted(rule.properties.items()))

        result.rules_after = len(rules)

        if self.minify:
            output = self._minify_css(rules)
        else:
            output = self._serialize_css(rules)

        result.optimized_size = len(output)
        result.minified = self.minify
        return output, result

    def _parse_css(self, css: str) -> List[CSSRule]:
        """Parse CSS text into a list of CSSRule objects."""
        rules: List[CSSRule] = []
        current_media = ""

        css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)

        media_parts = re.split(r'(@media\s+[^{]+\{)', css)

        i = 0
        while i < len(media_parts):
            part = media_parts[i].strip()
            if part.startswith('@media'):
                current_media = part.rstrip('{').strip()
                i += 1
                continue

            if part:
                for match in re.finditer(r'([^{}]+)\{([^{}]*)\}', part):
                    selector_text = match.group(1).strip()
                    props_text = match.group(2).strip()

                    if not selector_text or selector_text.startswith('@'):
                        continue

                    properties: Dict[str, str] = {}
                    for prop_match in re.finditer(r'([\w-]+)\s*:\s*([^;]+)', props_text):
                        prop_name = prop_match.group(1).strip()
                        prop_value = prop_match.group(2).strip()
                        if prop_value.endswith('!important'):
                            prop_value = prop_value.replace('!important', '').strip()
                        properties[prop_name] = prop_value

                    for sel in selector_text.split(','):
                        sel = sel.strip()
                        if sel:
                            rules.append(CSSRule(
                                selector=sel,
                                properties=properties.copy(),
                                media_query=current_media,
                            ))

            i += 1

        return rules

    def _remove_duplicate_rules(self, rules: List[CSSRule]) -> Tuple[List[CSSRule], int]:
        """Remove duplicate CSS rules (same selector + properties)."""
        seen: Set[str] = set()
        unique: List[CSSRule] = []
        dup_count = 0

        for rule in rules:
            key = f"{rule.media_query}|{rule.selector}|{tuple(sorted(rule.properties.items()))}"
            if key not in seen:
                seen.add(key)
                unique.append(rule)
            else:
                dup_count += 1

        return unique, dup_count

    def _remove_unused_selectors(self, rules: List[CSSRule]) -> Tuple[List[CSSRule], int]:
        """Remove CSS rules whose selectors are not used."""
        kept: List[CSSRule] = []
        removed = 0

        for rule in rules:
            if self._is_selector_used(rule.selector):
                kept.append(rule)
            else:
                removed += 1

        return kept, removed

    def _is_selector_used(self, selector: str) -> bool:
        """Check if a selector's classes are in the used set."""
        classes = re.findall(r'\.([\w-]+)', selector)

        if not classes:
            return True

        return any(cls in self._used_classes for cls in classes)

    def _minify_css(self, rules: List[CSSRule]) -> str:
        """Minify CSS rules."""
        parts: List[str] = []
        current_media = ""

        for rule in rules:
            if rule.media_query != current_media:
                if current_media:
                    parts.append("}")
                current_media = rule.media_query
                if current_media:
                    parts.append(current_media + "{")

            props = ";".join(f"{k}:{v}" for k, v in rule.properties.items())
            parts.append(f"{rule.selector}{{{props}}}")

        if current_media:
            parts.append("}")

        return "".join(parts)

    def _serialize_css(self, rules: List[CSSRule]) -> str:
        """Serialize CSS rules with formatting."""
        NL = chr(10)
        lines: List[str] = []
        current_media = ""

        for rule in rules:
            if rule.media_query != current_media:
                if current_media:
                    lines.append("}")
                current_media = rule.media_query
                if current_media:
                    lines.append(current_media + " {")

            props = (";" + NL + "  ").join(f"{k}: {v}" for k, v in rule.properties.items())
            lines.append(f"{rule.selector} {{")
            lines.append(f"  {props};")
            lines.append("}")

        if current_media:
            lines.append("}")

        return NL.join(lines)

    def extract_critical_css(self, css: str, above_fold_selectors: List[str]) -> str:
        """Extract critical CSS for above-the-fold rendering."""
        rules = self._parse_css(css)
        critical: List[CSSRule] = []

        above_set = set(above_fold_selectors)
        for rule in rules:
            if rule.selector in above_set or any(s in rule.selector for s in above_set):
                critical.append(rule)

        return self._minify_css(critical) if self.minify else self._serialize_css(critical)

    def extract_variables(self, css: str) -> Tuple[str, Dict[str, str]]:
        """Extract CSS custom properties (variables) into a separate block."""
        variables: Dict[str, str] = {}
        rules = self._parse_css(css)

        kept: List[CSSRule] = []
        for rule in rules:
            if rule.selector == ":root":
                for prop, value in rule.properties.items():
                    if prop.startswith("--"):
                        variables[prop] = value
                    else:
                        kept.append(CSSRule(selector=":root", properties={prop: value}))
            else:
                kept.append(rule)

        return self._serialize_css(kept), variables


# ── Asset Pipeline ───────────────────────────────────────────────────

@dataclass
class AssetInfo:
    """Information about a static asset."""
    path: str
    type: str
    size: int
    hash: str = ""
    gzip_size: int = 0
    brotli_size: int = 0
    cache_busting_url: str = ""
    preload: bool = False
    integrity: str = ""


class AssetPipeline:
    """Asset processing pipeline.

    Processes static assets (JS, CSS, images, fonts) for production:
    - Fingerprinting (content-hash based filenames)
    - Compression (gzip, brotli)
    - Cache busting URLs
    - Subresource Integrity (SRI) hashes
    - Preload hints
    - Asset manifest generation
    """

    def __init__(self, public_dir: str = "public", output_dir: str = ".tw/assets"):
        self.public_dir = public_dir
        self.output_dir = output_dir
        self._assets: Dict[str, AssetInfo] = {}
        self._manifest: Dict[str, str] = {}

    def process_asset(self, filepath: str, asset_type: str = "") -> AssetInfo:
        """Process a single asset."""
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Asset not found: {filepath}")

        if not asset_type:
            ext = os.path.splitext(filepath)[1].lower()
            asset_type = {
                ".js": "js", ".mjs": "js", ".css": "css",
                ".png": "image", ".jpg": "image", ".jpeg": "image",
                ".webp": "image", ".avif": "image", ".svg": "image", ".gif": "image",
                ".woff": "font", ".woff2": "font", ".ttf": "font", ".eot": "font",
            }.get(ext, "other")

        with open(filepath, "rb") as f:
            content = f.read()

        file_hash = hashlib.sha256(content).hexdigest()[:16]

        import gzip
        gzip_size = len(gzip.compress(content, compresslevel=9))

        brotli_size = 0
        try:
            import brotli
            brotli_size = len(brotli.compress(content))
        except ImportError:
            pass

        filename = os.path.basename(filepath)
        name, ext = os.path.splitext(filename)
        hashed_filename = f"{name}.{file_hash}{ext}"
        cache_busting_url = f"/_assets/{hashed_filename}"

        sri_hash = "sha256-" + __import__("base64").b64encode(
            hashlib.sha256(content).digest()
        ).decode("ascii")

        info = AssetInfo(
            path=filepath,
            type=asset_type,
            size=len(content),
            hash=file_hash,
            gzip_size=gzip_size,
            brotli_size=brotli_size,
            cache_busting_url=cache_busting_url,
            integrity=sri_hash,
        )

        self._assets[filepath] = info
        self._manifest[filepath] = cache_busting_url

        return info

    def process_directory(self, dir_path: str = "") -> List[AssetInfo]:
        """Process all assets in a directory."""
        dir_path = dir_path or self.public_dir
        results: List[AssetInfo] = []

        if not os.path.isdir(dir_path):
            return results

        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fname in files:
                if fname.startswith('.'):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    info = self.process_asset(fpath)
                    results.append(info)
                except Exception as e:
                    logger.warning("Failed to process asset %s: %s", fpath, e)

        return results

    def get_manifest(self) -> Dict[str, str]:
        """Return the asset manifest (original path to cache-busting URL)."""
        return dict(self._manifest)

    def get_manifest_json(self) -> str:
        """Return the asset manifest as JSON."""
        return json.dumps(self._manifest, indent=2)

    def generate_html_tags(self, asset_paths: List[str]) -> str:
        """Generate HTML tags for a list of assets."""
        NL = chr(10)
        tags: List[str] = []

        for path in asset_paths:
            info = self._assets.get(path)
            if not info:
                continue

            if info.type == "js":
                tag = f'<script src="{info.cache_busting_url}"'
                if info.integrity:
                    tag += f' integrity="{info.integrity}"'
                tag += ' defer></script>'
            elif info.type == "css":
                tag = f'<link rel="stylesheet" href="{info.cache_busting_url}"'
                if info.integrity:
                    tag += f' integrity="{info.integrity}"'
                tag += '>'
            elif info.type == "font":
                tag = f'<link rel="preload" href="{info.cache_busting_url}" as="font" crossorigin>'
            elif info.type == "image":
                tag = f'<link rel="preload" href="{info.cache_busting_url}" as="image">'
            else:
                continue

            tags.append(tag)

        return NL.join(tags)

    def get_preload_tags(self) -> str:
        """Generate preload tags for all assets marked for preload."""
        NL = chr(10)
        tags: List[str] = []
        for info in self._assets.values():
            if not info.preload:
                continue
            as_type = {"js": "script", "css": "style", "font": "font", "image": "image"}.get(info.type, "fetch")
            tags.append(
                f'<link rel="preload" href="{info.cache_busting_url}" as="{as_type}"'
                + (' crossorigin' if info.type == "font" else '')
                + '>'
            )
        return NL.join(tags)

    def mark_preload(self, filepath: str) -> None:
        """Mark an asset for preloading."""
        if filepath in self._assets:
            self._assets[filepath].preload = True

    def get_summary(self) -> Dict[str, Any]:
        """Return summary of all processed assets."""
        by_type: Dict[str, Dict[str, Any]] = {}
        total_original = 0
        total_gzip = 0
        total_brotli = 0

        for info in self._assets.values():
            t = info.type
            if t not in by_type:
                by_type[t] = {"count": 0, "total_size": 0, "total_gzip": 0, "total_brotli": 0}
            by_type[t]["count"] += 1
            by_type[t]["total_size"] += info.size
            by_type[t]["total_gzip"] += info.gzip_size
            by_type[t]["total_brotli"] += info.brotli_size
            total_original += info.size
            total_gzip += info.gzip_size
            total_brotli += info.brotli_size

        return {
            "total_assets": len(self._assets),
            "by_type": by_type,
            "total_original_bytes": total_original,
            "total_gzip_bytes": total_gzip,
            "total_brotli_bytes": total_brotli,
            "compression_ratio_pct": round((1 - total_gzip / total_original) * 100, 1) if total_original else 0,
        }

    def save_manifest(self, output_path: str = "") -> str:
        """Save the manifest to a file."""
        output_path = output_path or os.path.join(self.output_dir, "manifest.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            with open(output_path, "w") as f:
                json.dump(self._manifest, f, indent=2)
        except OSError:
            pass
        return output_path


# ── Image Optimization Integration ───────────────────────────────────

@dataclass
class ImageVariant:
    """A generated image variant."""
    width: int
    height: int
    format: str
    quality: int
    file_path: str = ""
    file_size: int = 0


class ImageOptimizer:
    """Image optimization for production.

    Generates responsive image variants:
    - Multiple sizes (320, 640, 768, 1024, 1920, 3840)
    - Modern formats (WebP, AVIF) with fallback
    - Quality-based compression
    - Lazy-loading attributes
    - srcset generation

    Uses Pillow if available, otherwise generates metadata only.
    """

    DEFAULT_SIZES = [320, 640, 768, 1024, 1920, 3840]
    DEFAULT_QUALITY = {"webp": 82, "avif": 80, "jpeg": 85, "png": 90}

    def __init__(self, output_dir: str = ".tw/images"):
        self.output_dir = output_dir
        self._variants: Dict[str, List[ImageVariant]] = {}
        self._pillow_available = False
        try:
            from PIL import Image  # noqa: F401
            self._pillow_available = True
        except ImportError:
            pass

    def optimize_image(self, image_path: str,
                        sizes: Optional[List[int]] = None,
                        formats: Optional[List[str]] = None,
                        quality: Optional[Dict[str, int]] = None) -> List[ImageVariant]:
        """Generate optimized variants of an image."""
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        sizes = sizes or self.DEFAULT_SIZES
        formats = formats or (["webp", "jpeg"] if self._pillow_available else ["webp"])
        quality = quality or self.DEFAULT_QUALITY

        variants: List[ImageVariant] = []

        if self._pillow_available:
            variants = self._generate_with_pillow(image_path, sizes, formats, quality)
        else:
            for fmt in formats:
                for width in sizes:
                    variants.append(ImageVariant(
                        width=width,
                        height=0,
                        format=fmt,
                        quality=quality.get(fmt, 85),
                    ))

        self._variants[image_path] = variants
        return variants

    def _generate_with_pillow(self, image_path: str,
                               sizes: List[int], formats: List[str],
                               quality: Dict[str, int]) -> List[ImageVariant]:
        """Generate image variants using Pillow."""
        from PIL import Image as PILImage

        variants: List[ImageVariant] = []

        try:
            img = PILImage.open(image_path)
            original_width, original_height = img.size

            for width in sizes:
                if width > original_width:
                    continue

                height = int(original_height * width / original_width)
                resized = img.resize((width, height), PILImage.LANCZOS)

                for fmt in formats:
                    basename = os.path.splitext(os.path.basename(image_path))[0]
                    out_filename = f"{basename}_{width}w.{fmt}"
                    out_path = os.path.join(self.output_dir, out_filename)

                    os.makedirs(self.output_dir, exist_ok=True)

                    save_kwargs = {}
                    if fmt in ("jpeg", "webp"):
                        save_kwargs["quality"] = quality.get(fmt, 85)
                    if fmt == "png":
                        save_kwargs["optimize"] = True

                    if fmt in ("jpeg", "webp") and img.mode == "RGBA":
                        resized = resized.convert("RGB")

                    try:
                        resized.save(out_path, format=fmt.upper() if fmt != "webp" else "WEBP",
                                      **save_kwargs)
                        file_size = os.path.getsize(out_path)
                    except Exception as e:
                        logger.warning("Failed to save %s: %s", out_path, e)
                        file_size = 0

                    variants.append(ImageVariant(
                        width=width,
                        height=height,
                        format=fmt,
                        quality=quality.get(fmt, 85),
                        file_path=out_path,
                        file_size=file_size,
                    ))
        except Exception as e:
            logger.error("Image optimization failed for %s: %s", image_path, e)

        return variants

    def generate_srcset(self, image_path: str) -> str:
        """Generate srcset attribute for responsive images."""
        variants = self._variants.get(image_path, [])
        if not variants:
            return ""

        parts: List[str] = []
        for v in variants:
            if v.file_path:
                url = f"/_images/{os.path.basename(v.file_path)}"
                parts.append(f"{url} {v.width}w")

        return ", ".join(parts)

    def generate_picture_tag(self, image_path: str, alt: str = "",
                             loading: str = "lazy", sizes: str = "100vw") -> str:
        """Generate a <picture> tag with source variants and fallback."""
        NL = chr(10)
        variants = self._variants.get(image_path, [])
        if not variants:
            return f'<img src="{image_path}" alt="{alt}" loading="{loading}">'

        by_format: Dict[str, List[ImageVariant]] = {}
        for v in variants:
            by_format.setdefault(v.format, []).append(v)

        sources: List[str] = []
        for fmt, vars_list in by_format.items():
            srcset = ", ".join(
                f"/_images/{os.path.basename(v.file_path)} {v.width}w"
                for v in vars_list if v.file_path
            )
            if srcset:
                mime_type = {"webp": "image/webp", "avif": "image/avif",
                             "jpeg": "image/jpeg", "png": "image/png"}.get(fmt, "image/*")
                sources.append(
                    f'<source type="{mime_type}" srcset="{srcset}" sizes="{sizes}">'
                )

        fallback = next(
            (v for v in variants if v.format == "jpeg" and v.file_path),
            variants[0] if variants else None
        )
        fallback_url = f"/_images/{os.path.basename(fallback.file_path)}" if fallback and fallback.file_path else image_path
        fallback_width = fallback.width if fallback else ""

        parts = [
            "<picture>",
            "  " + ("  " + NL).join(sources),
            f'  <img src="{fallback_url}" alt="{alt}" loading="{loading}"'
            + (f' width="{fallback_width}"' if fallback_width else "")
            + ">",
            "</picture>",
        ]
        return NL.join(parts)

    def get_summary(self) -> Dict[str, Any]:
        """Return summary of all optimized images."""
        total_variants = sum(len(vs) for vs in self._variants.values())
        total_size = sum(
            v.file_size
            for vs in self._variants.values()
            for v in vs
        )
        return {
            "images_processed": len(self._variants),
            "total_variants": total_variants,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "pillow_available": self._pillow_available,
        }


# ── Bundle Performance Budget ────────────────────────────────────────

@dataclass
class BudgetRule:
    """A single performance budget rule."""
    name: str
    asset_type: str
    max_size_kb: float
    max_gzip_kb: float = 0
    warning_threshold: float = 0.8


class BundleBudgetEnforcer:
    """Enforces performance budgets for bundles.

    Checks if bundles exceed size limits and provides warnings/errors:
    - Per-chunk size limits
    - Total bundle size limit
    - Gzipped size limit
    - Per-asset-type limits (JS, CSS, images)
    - Initial load size limit (critical path)
    """

    def __init__(self):
        self._rules: List[BudgetRule] = []
        self._violations: List[Dict[str, Any]] = []
        self._warnings: List[Dict[str, Any]] = []

    def add_rule(self, name: str, asset_type: str, max_size_kb: float,
                 max_gzip_kb: float = 0, warning_threshold: float = 0.8) -> None:
        """Add a budget rule."""
        self._rules.append(BudgetRule(
            name=name,
            asset_type=asset_type,
            max_size_kb=max_size_kb,
            max_gzip_kb=max_gzip_kb,
            warning_threshold=warning_threshold,
        ))

    def add_defaults(self) -> None:
        """Add sensible default budget rules."""
        defaults = [
            ("Initial JS", "js", 150, 50),
            ("Initial CSS", "css", 30, 10),
            ("Total JS", "js", 500, 150),
            ("Total CSS", "css", 100, 30),
            ("Images per page", "image", 500, 0),
            ("Total page weight", "total", 2000, 500),
        ]
        for name, atype, max_kb, max_gzip in defaults:
            self.add_rule(name, atype, max_kb, max_gzip)

    def check_bundle(self, chunks: List[Dict[str, Any]],
                      assets: Optional[List[AssetInfo]] = None) -> Dict[str, Any]:
        """Check bundles against budget rules."""
        self._violations.clear()
        self._warnings.clear()

        js_size = sum(c.get("size", 0) for c in chunks if c.get("type") == "js")
        css_size = sum(c.get("size", 0) for c in chunks if c.get("type") == "css")
        total_size = js_size + css_size

        js_gzip = sum(c.get("gzip_size", 0) for c in chunks if c.get("type") == "js")
        css_gzip = sum(c.get("gzip_size", 0) for c in chunks if c.get("type") == "css")
        total_gzip = js_gzip + css_gzip

        if assets:
            img_size = sum(a.size for a in assets if a.type == "image")
            total_size += img_size
        else:
            img_size = 0

        sizes = {
            "js": (js_size, js_gzip),
            "css": (css_size, css_gzip),
            "image": (img_size, 0),
            "total": (total_size, total_gzip),
        }

        for rule in self._rules:
            actual_bytes, actual_gzip = sizes.get(rule.asset_type, (0, 0))
            actual_kb = actual_bytes / 1024
            actual_gzip_kb = actual_gzip / 1024

            threshold_kb = rule.max_size_kb * rule.warning_threshold

            if actual_kb > rule.max_size_kb:
                self._violations.append({
                    "rule": rule.name,
                    "asset_type": rule.asset_type,
                    "actual_kb": round(actual_kb, 1),
                    "max_kb": rule.max_size_kb,
                    "over_by_kb": round(actual_kb - rule.max_size_kb, 1),
                    "level": "error",
                })
            elif actual_kb > threshold_kb:
                self._warnings.append({
                    "rule": rule.name,
                    "asset_type": rule.asset_type,
                    "actual_kb": round(actual_kb, 1),
                    "threshold_kb": round(threshold_kb, 1),
                    "max_kb": rule.max_size_kb,
                    "level": "warning",
                })

            if rule.max_gzip_kb > 0 and actual_gzip_kb > rule.max_gzip_kb:
                self._violations.append({
                    "rule": rule.name + " (gzip)",
                    "asset_type": rule.asset_type,
                    "actual_kb": round(actual_gzip_kb, 1),
                    "max_kb": rule.max_gzip_kb,
                    "over_by_kb": round(actual_gzip_kb - rule.max_gzip_kb, 1),
                    "level": "error",
                })

        return {
            "passed": len(self._violations) == 0,
            "violations": self._violations,
            "warnings": self._warnings,
            "sizes": {
                atype: {"kb": round(s[0]/1024, 1), "gzip_kb": round(s[1]/1024, 1)}
                for atype, s in sizes.items()
            },
        }

    def get_report(self) -> str:
        """Generate a human-readable budget report."""
        NL = chr(10)
        lines = [
            "=" * 60,
            "  TW Framework -- Bundle Budget Report",
            "=" * 60,
            "",
        ]

        if not self._violations and not self._warnings:
            lines.append("  All budgets passed!")
        else:
            if self._violations:
                lines.append(f"  {len(self._violations)} Budget Violations:")
                for v in self._violations:
                    lines.append(
                        f"    - {v['rule']}: {v['actual_kb']}KB / {v['max_kb']}KB "
                        f"(over by {v['over_by_kb']}KB)"
                    )
                lines.append("")

            if self._warnings:
                lines.append(f"  {len(self._warnings)} Budget Warnings:")
                for w in self._warnings:
                    pct = w['actual_kb']/w['max_kb']*100 if w['max_kb'] else 0
                    lines.append(
                        f"    - {w['rule']}: {w['actual_kb']}KB / {w['max_kb']}KB "
                        f"({pct:.0f}% of budget)"
                    )

        lines.append("")
        lines.append("=" * 60)
        return NL.join(lines)


# ── Turbopack Integration (#19) ─────────────────────────────────────
# Rust-based bundler concept — 10x faster than webpack


class TurbopackConfig:
    """Configuration for Turbopack-style bundling.

    Turbopack is a Rust-based bundler that is significantly faster
    than webpack. While TW Framework runs in Python, this module
    provides the configuration and integration layer for Turbopack:

    1. Configuration generation for Turbopack
    2. Fallback to webpack/ESBuild if Turbopack not available
    3. Performance comparison and benchmarks
    4. Incremental compilation support
    """

    def __init__(self):
        self._enabled = False
        self._config: Dict[str, Any] = {
            "mode": "development",
            "dev_server": True,
            "hmr": True,
            "incremental": True,
            "memory_cache": True,
            "persistent_cache": True,
            "max_workers": 4,
        }
        self._benchmarks: Dict[str, Dict[str, float]] = {}

    def enable(self) -> None:
        self._enabled = True
        self._config["mode"] = "production"

    def disable(self) -> None:
        self._enabled = False

    @property
    def is_available(self) -> bool:
        """Check if Turbopack binary is available."""
        # In real implementation, check for the binary
        return self._enabled

    def generate_config(self, entry: str = "", output_dir: str = "") -> Dict[str, Any]:
        """Generate Turbopack configuration."""
        return {
            "entry": entry or "./index.js",
            "output": {
                "path": output_dir or ".tw/dist",
                "filename": "[name].[contenthash].js",
                "chunkFilename": "[name].[contenthash].chunk.js",
            },
            "mode": self._config.get("mode", "development"),
            "dev_server": {
                "enabled": self._config.get("dev_server", True),
                "hmr": self._config.get("hmr", True),
                "port": 3000,
            },
            "optimization": {
                "incremental": self._config.get("incremental", True),
                "tree_shaking": True,
                "minification": True,
                "code_splitting": True,
            },
            "cache": {
                "memory": self._config.get("memory_cache", True),
                "persistent": self._config.get("persistent_cache", True),
                "path": ".tw/.turbo-cache",
            },
            "workers": self._config.get("max_workers", 4),
        }

    def benchmark(self, build_fn: Callable, name: str = "build") -> Dict[str, float]:
        """Benchmark a build function."""
        import time
        start = time.time()
        build_fn()
        duration = time.time() - start

        self._benchmarks[name] = {
            "duration_ms": duration * 1000,
            "timestamp": time.time(),
        }
        return self._benchmarks[name]

    def compare_with_webpack(self, turbo_time_ms: float, webpack_time_ms: float) -> Dict[str, Any]:
        """Compare Turbopack vs webpack performance."""
        speedup = webpack_time_ms / turbo_time_ms if turbo_time_ms > 0 else 0
        return {
            "turbopack_ms": turbo_time_ms,
            "webpack_ms": webpack_time_ms,
            "speedup": round(speedup, 2),
            "faster_by_pct": round((1 - turbo_time_ms / webpack_time_ms) * 100, 1) if webpack_time_ms > 0 else 0,
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "config": self._config,
            "benchmarks": self._benchmarks,
        }


# ── Bundle Analyzer Enhancement (#20) ────────────────────────────────

class BundleReportGenerator:
    """Generates detailed bundle analysis reports.

    Analyzes the output bundle and generates:
    - Per-module size breakdown
    - Duplicate dependency detection
    - Tree-shaking effectiveness
    - Code splitting analysis
    - Performance recommendations
    """

    def __init__(self):
        self._modules: Dict[str, dict] = {}
        self._duplicates: List[dict] = []
        self._recommendations: List[str] = []

    def add_module(self, name: str, size: int, gzip_size: int = 0,
                   chunks: Optional[List[str]] = None) -> None:
        self._modules[name] = {
            "name": name,
            "size": size,
            "gzip_size": gzip_size,
            "chunks": chunks or [],
        }

    def detect_duplicates(self) -> List[dict]:
        """Detect duplicate modules across chunks."""
        chunk_map: Dict[str, List[str]] = {}
        for name, info in self._modules.items():
            for chunk in info["chunks"]:
                chunk_map.setdefault(chunk, []).append(name)

        # Find modules in multiple chunks
        module_chunks: Dict[str, List[str]] = {}
        for chunk, modules in chunk_map.items():
            for mod in modules:
                module_chunks.setdefault(mod, []).append(chunk)

        self._duplicates = [
            {"module": mod, "chunks": chunks}
            for mod, chunks in module_chunks.items()
            if len(chunks) > 1
        ]
        return self._duplicates

    def generate_recommendations(self) -> List[str]:
        """Generate performance recommendations."""
        self._recommendations.clear()

        # Check for large modules
        for name, info in self._modules.items():
            if info["size"] > 100000:  # >100KB
                self._recommendations.append(
                    "Module '" + name + "' is " + str(info["size"] // 1024) + "KB — consider code splitting"
                )

        # Check for duplicates
        if self._duplicates:
            self._recommendations.append(
                str(len(self._duplicates)) + " duplicate modules detected — use shared chunks"
            )

        # Check total size
        total = sum(m["size"] for m in self._modules.values())
        if total > 500000:  # >500KB
            self._recommendations.append(
                "Total bundle size is " + str(total // 1024) + "KB — consider lazy loading"
            )

        return self._recommendations

    def generate_report(self) -> Dict[str, Any]:
        """Generate full analysis report."""
        self.detect_duplicates()
        self.generate_recommendations()

        total_size = sum(m["size"] for m in self._modules.values())
        total_gzip = sum(m["gzip_size"] for m in self._modules.values())

        return {
            "total_modules": len(self._modules),
            "total_size_bytes": total_size,
            "total_size_kb": round(total_size / 1024, 1),
            "total_gzip_bytes": total_gzip,
            "total_gzip_kb": round(total_gzip / 1024, 1),
            "compression_ratio": round((1 - total_gzip / total_size) * 100, 1) if total_size else 0,
            "duplicates": self._duplicates,
            "recommendations": self._recommendations,
            "modules": sorted(self._modules.values(), key=lambda x: -x["size"])[:20],
        }

    def generate_html_report(self) -> str:
        """Generate HTML visual report."""
        report = self.generate_report()
        NL = chr(10)
        lines = [
            '<!DOCTYPE html>',
            '<html><head><title>Bundle Report</title></head><body>',
            '<h1>Bundle Analysis Report</h1>',
            '<p>Total size: ' + str(report["total_size_kb"]) + 'KB (gzip: ' + str(report["total_gzip_kb"]) + 'KB)</p>',
            '<p>Compression ratio: ' + str(report["compression_ratio"]) + '%</p>',
            '<h2>Modules (top 20)</h2>',
            '<table border="1"><tr><th>Module</th><th>Size (KB)</th><th>Gzip (KB)</th><th>Chunks</th></tr>',
        ]
        for mod in report["modules"]:
            lines.append(
                '<tr><td>' + mod["name"] + '</td>'
                '<td>' + str(round(mod["size"] / 1024, 1)) + '</td>'
                '<td>' + str(round(mod["gzip_size"] / 1024, 1)) + '</td>'
                '<td>' + ", ".join(mod["chunks"]) + '</td></tr>'
            )
        lines.append('</table>')

        if report["duplicates"]:
            lines.append('<h2>Duplicates</h2><ul>')
            for dup in report["duplicates"]:
                lines.append('<li>' + dup["module"] + ' in: ' + ", ".join(dup["chunks"]) + '</li>')
            lines.append('</ul>')

        if report["recommendations"]:
            lines.append('<h2>Recommendations</h2><ul>')
            for rec in report["recommendations"]:
                lines.append('<li>' + rec + '</li>')
            lines.append('</ul>')

        lines.append('</body></html>')
        return NL.join(lines)
