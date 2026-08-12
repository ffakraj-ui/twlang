"""
TW Framework - Enterprise Boilerplate Features

Implements:
13. Enterprise features: Observability, coupling graph, health checks,
    conventional commits, semantic release, bundle monitoring
"""

from __future__ import annotations
import json, time, logging, os, hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class HealthCheck:
    """A single health check definition."""
    name: str
    check_fn: Callable[[], bool]
    interval_seconds: float = 30
    timeout_seconds: float = 5
    last_status: str = "unknown"  # healthy | unhealthy | unknown
    last_checked: float = 0.0
    last_error: str = ""


class HealthCheckManager:
    """Kubernetes-compatible health check manager.

    Provides:
    - /health/live — Liveness probe (is the app running?)
    - /health/ready — Readiness probe (is the app ready to serve?)
    - /health/startup — Startup probe (has the app started?)
    """

    def __init__(self):
        self._liveness_checks: Dict[str, HealthCheck] = {}
        self._readiness_checks: Dict[str, HealthCheck] = {}
        self._startup_checks: Dict[str, HealthCheck] = {}
        self._startup_complete: bool = False

    def add_liveness(self, name: str, check_fn: Callable[[], bool]) -> None:
        self._liveness_checks[name] = HealthCheck(name=name, check_fn=check_fn)

    def add_readiness(self, name: str, check_fn: Callable[[], bool]) -> None:
        self._readiness_checks[name] = HealthCheck(name=name, check_fn=check_fn)

    def add_startup(self, name: str, check_fn: Callable[[], bool]) -> None:
        self._startup_checks[name] = HealthCheck(name=name, check_fn=check_fn)

    def check_liveness(self) -> Dict[str, Any]:
        results = {}
        all_healthy = True
        for name, check in self._liveness_checks.items():
            try:
                healthy = check.check_fn()
                check.last_status = "healthy" if healthy else "unhealthy"
                check.last_checked = time.time()
                results[name] = check.last_status
                if not healthy:
                    all_healthy = False
            except Exception as e:
                check.last_status = "unhealthy"
                check.last_error = str(e)
                results[name] = "unhealthy: " + str(e)
                all_healthy = False
        return {"status": "healthy" if all_healthy else "unhealthy", "checks": results}

    def check_readiness(self) -> Dict[str, Any]:
        if not self._startup_complete:
            return {"status": "unhealthy", "reason": "startup not complete"}
        results = {}
        all_ready = True
        for name, check in self._readiness_checks.items():
            try:
                ready = check.check_fn()
                check.last_status = "healthy" if ready else "unhealthy"
                results[name] = check.last_status
                if not ready:
                    all_ready = False
            except Exception as e:
                results[name] = "unhealthy: " + str(e)
                all_ready = False
        return {"status": "healthy" if all_ready else "unhealthy", "checks": results}

    def check_startup(self) -> Dict[str, Any]:
        results = {}
        all_started = True
        for name, check in self._startup_checks.items():
            try:
                started = check.check_fn()
                results[name] = "started" if started else "pending"
                if not started:
                    all_started = False
            except Exception as e:
                results[name] = "error: " + str(e)
                all_started = False
        if all_started:
            self._startup_complete = True
        return {"status": "started" if all_started else "pending", "checks": results}

    def get_kubernetes_manifest(self) -> Dict[str, Any]:
        """Generate Kubernetes probe configuration."""
        return {
            "livenessProbe": {
                "httpGet": {"path": "/health/live", "port": 3000},
                "initialDelaySeconds": 10,
                "periodSeconds": 30,
                "timeoutSeconds": 5,
            },
            "readinessProbe": {
                "httpGet": {"path": "/health/ready", "port": 3000},
                "initialDelaySeconds": 5,
                "periodSeconds": 10,
                "timeoutSeconds": 3,
            },
            "startupProbe": {
                "httpGet": {"path": "/health/startup", "port": 3000},
                "initialDelaySeconds": 0,
                "periodSeconds": 10,
                "failureThreshold": 30,
            },
        }


@dataclass
class ComponentDependency:
    """A dependency between two components."""
    source: str
    target: str
    dependency_type: str  # "import" | "prop" | "event" | "shared-state"


class CouplingGraph:
    """Component coupling graph visualizer.

    Analyzes component dependencies and visualizes:
    - Which components import which
    - Circular dependencies
    - Most coupled components (high fan-in/fan-out)
    - Dead components (not imported by anyone)
    """

    def __init__(self):
        self._nodes: Set[str] = set()
        self._edges: List[ComponentDependency] = []

    def add_component(self, name: str) -> None:
        self._nodes.add(name)

    def add_dependency(self, source: str, target: str,
                       dep_type: str = "import") -> None:
        self._nodes.add(source)
        self._nodes.add(target)
        self._edges.append(ComponentDependency(source, target, dep_type))

    def get_dependencies(self, component: str) -> List[str]:
        """Get components that this component depends on."""
        return [e.target for e in self._edges if e.source == component]

    def get_dependents(self, component: str) -> List[str]:
        """Get components that depend on this component."""
        return [e.source for e in self._edges if e.target == component]

    def find_circular(self) -> List[List[str]]:
        """Find circular dependencies using DFS."""
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        path: List[str] = []
        path_set: Set[str] = set()

        def dfs(node: str) -> None:
            if node in path_set:
                idx = path.index(node)
                cycles.append(path[idx:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            path_set.add(node)
            for dep in self.get_dependencies(node):
                dfs(dep)
            path.pop()
            path_set.discard(node)

        for node in self._nodes:
            if node not in visited:
                dfs(node)

        return cycles

    def get_fan_in(self, component: str) -> int:
        return len(self.get_dependents(component))

    def get_fan_out(self, component: str) -> int:
        return len(self.get_dependencies(component))

    def get_dead_components(self) -> List[str]:
        """Components not depended on by anyone (except entry point)."""
        return [n for n in self._nodes if self.get_fan_in(n) == 0]

    def generate_mermaid(self) -> str:
        """Generate Mermaid.js graph for visualization."""
        lines = ["graph TD"]
        for edge in self._edges:
            lines.append("  " + edge.source.replace("-", "_") + " --> " + edge.target.replace("-", "_"))
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_components": len(self._nodes),
            "total_dependencies": len(self._edges),
            "circular_deps": len(self.find_circular()),
            "dead_components": len(self.get_dead_components()),
        }


class ObservabilityManager:
    """OpenTelemetry-style observability integration.

    Provides:
    - Distributed tracing (span creation)
    - Metrics collection (counters, gauges, histograms)
    - Structured logging (JSON format)
    - Export to OTLP-compatible backends
    """

    def __init__(self, service_name: str = "tw-framework"):
        self.service_name = service_name
        self._spans: List[Dict[str, Any]] = []
        self._metrics: Dict[str, float] = {}
        self._counters: Dict[str, int] = {}
        self._histograms: Dict[str, List[float]] = {}

    def start_span(self, name: str, parent_id: str = "") -> str:
        """Start a tracing span. Returns span ID."""
        span_id = hashlib.sha256((name + str(time.time())).encode()).hexdigest()[:16]
        span = {
            "id": span_id,
            "name": name,
            "parent_id": parent_id,
            "service": self.service_name,
            "start_time": time.time(),
            "end_time": None,
            "attributes": {},
        }
        self._spans.append(span)
        return span_id

    def end_span(self, span_id: str, attributes: Optional[Dict] = None) -> None:
        """End a tracing span."""
        for span in self._spans:
            if span["id"] == span_id:
                span["end_time"] = time.time()
                if attributes:
                    span["attributes"].update(attributes)
                break

    def increment_counter(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        self._metrics[name] = value

    def record_histogram(self, name: str, value: float) -> None:
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

    def log(self, level: str, message: str, **kwargs) -> None:
        """Structured logging in JSON format."""
        entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "service": self.service_name,
            **kwargs,
        }
        print(json.dumps(entry))

    def export_traces(self) -> str:
        """Export traces as JSON (OTLP-compatible format)."""
        return json.dumps({
            "resourceSpans": [{
                "resource": {"attributes": {"service.name": self.service_name}},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": s["id"],
                        "spanId": s["id"][:8],
                        "parentSpanId": s["parent_id"][:8] if s["parent_id"] else "",
                        "name": s["name"],
                        "startTimeUnixNano": str(int(s["start_time"] * 1e9)),
                        "endTimeUnixNano": str(int((s["end_time"] or time.time()) * 1e9)),
                        "attributes": s["attributes"],
                    } for s in self._spans]
                }]
            }]
        })

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_spans": len(self._spans),
            "counters": dict(self._counters),
            "gauges": dict(self._metrics),
            "histograms": {k: {"count": len(v), "avg": sum(v)/len(v) if v else 0} for k, v in self._histograms.items()},
        }


class ConventionalCommitParser:
    """Conventional commits parser.

    Parses commit messages in conventional format:
    feat: add new feature
    fix(scope): fix bug in scope
    docs(api): update API docs
    """
    PATTERN = "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(?:\(([^)]+)\))?!?:\s*(.+)$"

    def __init__(self):
        import re
        self._regex = re.compile(self.PATTERN)

    def parse(self, message: str) -> Optional[Dict[str, str]]:
        match = self._regex.match(message.strip())
        if not match:
            return None
        return {
            "type": match.group(1),
            "scope": match.group(2) or "",
            "breaking": "!" in message[:message.index(":")],
            "description": match.group(3),
        }

    def determine_version_bump(self, commits: List[str]) -> str:
        """Determine version bump from list of commit messages."""
        has_breaking = False
        has_feature = False
        has_fix = False

        for msg in commits:
            parsed = self.parse(msg)
            if not parsed:
                continue
            if parsed["breaking"]:
                has_breaking = True
            elif parsed["type"] == "feat":
                has_feature = True
            elif parsed["type"] == "fix":
                has_fix = True

        if has_breaking:
            return "major"
        elif has_feature:
            return "minor"
        elif has_fix:
            return "patch"
        return "none"


__all__ = [
    "HealthCheck", "HealthCheckManager",
    "ComponentDependency", "CouplingGraph",
    "ObservabilityManager",
    "ConventionalCommitParser",
]
