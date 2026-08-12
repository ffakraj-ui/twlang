# Release Checklist

Follow this checklist before publishing a new version of TW Framework.

## Pre-Release

### Code Quality

- [ ] All tests pass: `pytest`
- [ ] Code coverage >= 80%: `pytest --cov`
- [ ] No linting errors: `flake8 tw_framework/`
- [ ] Type checking passes: `mypy tw_framework/`
- [ ] No security vulnerabilities: `pip-audit`

### Documentation

- [ ] README.md updated with new features
- [ ] CHANGELOG.md updated with version notes
- [ ] New features documented in `docs/`
- [ ] API reference updated for new functions
- [ ] Migration guide written for breaking changes

### Testing

- [ ] Manual testing on sample projects
- [ ] Test `tw create` with new template
- [ ] Test `tw dev` hot reload
- [ ] Test `tw build --prod`
- [ ] Test `tw deploy` to all platforms
- [ ] Verify LSP server works in VS Code
- [ ] Test on Windows, macOS, and Linux

## Version Bump

### Semantic Versioning

| Change Type | Version Bump | Example |
|-------------|-------------|---------|
| Bug fix | Patch | 1.2.3 → 1.2.4 |
| New feature (backward compatible) | Minor | 1.2.3 → 1.3.0 |
| Breaking change | Major | 1.2.3 → 2.0.0 |

### Update Version

```python
# tw_framework/__init__.py
__version__ = "1.3.0"
```

```
# tw.config (if applicable)
version: 1.3.0
```

## Changelog Format

```markdown
## [1.3.0] - 2024-03-15

### Added
- New `render edge` mode for edge computing
- Support for custom directives
- Dark mode theme system

### Changed
- Improved build performance by 40%
- Updated default CSS reset

### Fixed
- Fixed memory leak in dev server (#42)
- Corrected error line numbers in diagnostics

### Deprecated
- `load_css` directive (use `load` instead)

### Removed
- Legacy compiler pipeline (use modular AST)

### Security
- Patched regex DoS vulnerability
```

## Git Tag

```bash
# Commit all changes
git add .
git commit -m "Release v1.3.0"

# Create signed tag
git tag -s v1.3.0 -m "Release version 1.3.0"

# Push
git push origin main
git push origin v1.3.0
```

## PyPI Release

```bash
# Build distribution
python -m build

# Upload to TestPyPI first
python -m twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ tw-framework

# Upload to PyPI
python -m twine upload dist/*
```

## GitHub Release

1. Go to Releases > Draft a new release
2. Choose tag: `v1.3.0`
3. Title: `TW Framework v1.3.0`
4. Copy changelog section into description
5. Attach built wheels
6. Publish release

## Post-Release

- [ ] Announce on Twitter/X
- [ ] Post on dev.to or Medium
- [ ] Update website documentation
- [ ] Monitor for critical issues (24h)
- [ ] Prepare hotfix branch if needed

## Hotfix Process

For critical bugs after release:

```bash
# Create hotfix branch from tag
git checkout -b hotfix/v1.3.1 v1.3.0

# Fix bug, commit
git commit -am "Fix critical bug (#45)"

# Tag and release
git tag -s v1.3.1 -m "Hotfix v1.3.1"
git push origin hotfix/v1.3.1
git push origin v1.3.1
```
