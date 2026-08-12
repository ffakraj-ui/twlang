# Versioning and Releases

## Version History

| Version | Key Changes |
|---|---|
| v0.4.5 | LSP fixes (false positives, error positions, no auto-closing braces) |
| v0.4.4 | LSP server added, VS Code/ACode plugins, deployment docs |
| v0.4.3 | Fixed --prod HTML references, fixed multi-line CSS values, env var security |
| v0.4.2 | Code splitting, dead code detection, incremental cache |
| v0.4.1 | Middleware system, API routes, search index |
| v0.4.0 | Initial public release |

## Checking Your Version

```bash
tw --version
pip show tw-framework
```

## Upgrading

```bash
pip install --upgrade tw-framework
tw clean
tw build --prod
```

## Tagging a Release

```bash
sed -i 's/version = "0.4.5"/version = "0.4.6"/' pyproject.toml
git add pyproject.toml
git commit -m "Bump version to v0.4.6"
git push origin main
git tag -a v0.4.6 -m "Release v0.4.6"
git push origin v0.4.6
```

## Semver Guidelines

| Version Bump | When |
|---|---|
| Patch (0.4.5 -> 0.4.6) | Bug fixes |
| Minor (0.4.5 -> 0.5.0) | New features, backward compatible |
| Major (0.4.5 -> 1.0.0) | Breaking changes |

## Changelog

Maintain `CHANGELOG.md` with each release.
