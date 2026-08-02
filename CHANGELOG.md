# Changelog

## Unreleased

### Reliability and build safety

- kept plugin/extension execution visible at startup, and added optional `plugin_allowlist` filtering in `tw.config`
- hardened component-name validation to reject `..`, null bytes, and absolute paths before resolution
- restricted deploy token storage more tightly by applying `0o700` on the global config directory and `0o600` on the config file
- centralized MD5-based content hashing behind `tw_framework.common.content_hash()`
- moved core CLI/server/build status output onto a shared `log()` helper to reduce ad-hoc `print()` usage

### Project hygiene

- added repository `.gitignore` defaults for `dist/`, `.tw/`, and `.tw-cache/`
- updated `tw create` scaffolding so generated projects ignore the same build/cache directories

### Documentation

- expanded the TW grammar spec with directive syntax, layout chaining, and dynamic-route filename conventions
- documented the legacy-AST to new-AST bridge for contributors
- documented `TW_WARN_LITERAL_PARSE` and `TW_STRICT_EVAL` debug flags in the README
