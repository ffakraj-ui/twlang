import hashlib
import importlib.util
import os
from dataclasses import dataclass


HOOK_ALIASES = {
    "before_build": "beforeBuild",
    "after_build": "afterBuild",
    "before_route": "beforeRoute",
    "after_route": "afterRoute",
}


@dataclass
class LoadedExtension:
    name: str
    path: str
    module: object


class PluginAPI:
    def __init__(self, manager, extension_name):
        self.manager = manager
        self.extension_name = extension_name

    def register_hook(self, event_name, handler):
        self.manager.register_hook(event_name, handler, self.extension_name)

    def hook(self, event_name, handler):
        self.register_hook(event_name, handler)

    def get_config(self):
        return dict(self.manager.config or {})

    def get_env(self):
        return dict(self.manager.env or {})

    def get_project_root(self):
        return self.manager.project_root


class ExtensionManager:
    def __init__(self, project_root, config=None, env=None):
        self.project_root = os.path.abspath(project_root)
        self.config = dict(config or {})
        self.env = dict(env or {})
        self.extensions = []
        self.hooks = {}
        self.errors = []

    def refresh(self, config=None, env=None):
        self.config = dict(config or self.config or {})
        self.env = dict(env or self.env or {})
        self.extensions = []
        self.hooks = {}
        self.errors = []
        for path in self.discover_extension_paths():
            self._load_extension(path)
        return self

    def discover_extension_paths(self):
        paths = []
        for folder in self._extension_roots():
            if not os.path.isdir(folder):
                continue
            for dirpath, _, filenames in os.walk(folder):
                for filename in sorted(filenames):
                    if not filename.endswith(".py") or filename.startswith("_"):
                        continue
                    paths.append(os.path.join(dirpath, filename))
        return sorted(set(os.path.abspath(path) for path in paths))

    def dependency_paths(self):
        return self.discover_extension_paths()

    def emit(self, event_name, **payload):
        canonical = self._normalize_event_name(event_name)
        event_payload = dict(payload)
        event_payload.setdefault("event", canonical)
        event_payload.setdefault("project_root", self.project_root)
        event_payload.setdefault("config", dict(self.config))
        event_payload.setdefault("env", dict(self.env))
        for hook in self.hooks.get(canonical, []):
            try:
                result = hook["handler"](event_payload)
                if isinstance(result, dict):
                    event_payload.update(result)
            except Exception as err:
                self.errors.append(f"{hook['extension']}::{canonical}: {err}")
        return event_payload

    def register_hook(self, event_name, handler, extension_name):
        canonical = self._normalize_event_name(event_name)
        if not callable(handler):
            raise TypeError(f"Hook `{canonical}` from `{extension_name}` must be callable")
        self.hooks.setdefault(canonical, []).append({
            "extension": extension_name,
            "handler": handler,
        })

    def _extension_roots(self):
        home_dir = os.path.join(self.project_root, "[home]")
        return [
            os.path.join(home_dir, "plugins"),
            os.path.join(home_dir, "hooks"),
        ]

    def _normalize_event_name(self, event_name):
        raw = str(event_name or "").strip()
        return HOOK_ALIASES.get(raw, raw)

    def _load_extension(self, path):
        name = os.path.splitext(os.path.basename(path))[0]
        module_name = f"tw_ext_{name}_{hashlib.md5(path.encode('utf-8')).hexdigest()[:10]}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            self.errors.append(f"{path}: failed to create import spec")
            return
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            api = PluginAPI(self, name)
            if hasattr(module, "register") and callable(module.register):
                module.register(api)
            hooks = getattr(module, "hooks", None)
            if isinstance(hooks, dict):
                for event_name, handler in hooks.items():
                    api.register_hook(event_name, handler)
            self.extensions.append(LoadedExtension(name=name, path=path, module=module))
        except Exception as err:
            self.errors.append(f"{path}: {err}")
