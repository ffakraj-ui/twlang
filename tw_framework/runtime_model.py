from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CompilerArtifacts:
    source_path: str = ""
    tokens: List[Dict[str, Any]] = field(default_factory=list)
    ast: Optional[Dict[str, Any]] = None
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    ir: Optional[Dict[str, Any]] = None
    html: Optional[str] = None
    program: Any = None
    runtime_context: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    route_path: str = "/"
    pipeline: str = "modular"
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = ["CompilerArtifacts"]
