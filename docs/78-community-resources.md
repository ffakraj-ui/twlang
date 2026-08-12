# Community Resources

## Official

- GitHub: https://github.com/ffakraj-ui/twlang
- PyPI: https://pypi.org/project/tw-framework/
- Issues: https://github.com/ffakraj-ui/twlang/issues

## Documentation

This docs/ folder contains 80 comprehensive documentation files covering:
- Getting started guides
- Syntax references
- CLI commands
- Deployment guides
- Troubleshooting
- Templates and examples

## Templates

- Starter project: tw create my-site
- Blog template: see docs/48-blog-template.md
- Portfolio template: see docs/49-portfolio-template.md
- E-commerce template: see docs/50-e-commerce-template.md
- SaaS landing template: see docs/52-saas-landing-template.md
- Docs site template: see docs/51-docs-template.md

## Contributing

### Report Bugs

Open an issue at https://github.com/ffakraj-ui/twlang/issues with:
1. TW Framework version (pip show tw-framework)
2. Python version
3. Minimal reproduction steps
4. Expected vs actual behavior
5. Error output

### Submit Pull Requests

```bash
git clone https://github.com/ffakraj-ui/twlang.git
cd twlang
pip install tw-framework

# Make changes...
pytest tests/
tw doctor

git checkout -b feature/my-feature
git add .
git commit -m "Add my feature"
git push origin feature/my-feature
```

## Editor Support

### VS Code

Install the vscode-tw/ extension for syntax highlighting, autocomplete, live diagnostics, hover documentation.

### ACode (Android)

Install the tw-language-acode.zip plugin for syntax highlighting and LSP integration with Termux Python.

### Other Editors

The LSP server works with any LSP-compatible editor:

```bash
python -m tw_framework.lsp_server
```

Configure your editor to launch this as a stdio LSP server for .tw and .tss files.
