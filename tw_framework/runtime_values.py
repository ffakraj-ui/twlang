from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RuntimeEnvironment:
    values: Dict[str, Any] = field(default_factory=dict)
    parent: Optional["RuntimeEnvironment"] = None

    def get(self, name: str, default=None):
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name, default)
        return default

    def set(self, name: str, value: Any):
        self.values[name] = value

    def to_context(self) -> Dict[str, Any]:
        data = self.parent.to_context() if self.parent is not None else {}
        data.update(self.values)
        return data

    def child(self, extra: Optional[Dict[str, Any]] = None) -> "RuntimeEnvironment":
        return RuntimeEnvironment(values=dict(extra or {}), parent=self)


__all__ = ["RuntimeEnvironment"]
