# GitHub Actions CI/CD

## Auto-Deploy on Push

```yaml
name: Build and Deploy
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install tw-framework
      - run: python -m tw_framework.cli build --prod
      - uses: actions/upload-artifact@v4
        with: { name: dist, path: dist/ }
```

## GitHub Pages Deploy

```yaml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
permissions:
  contents: read
  pages: write
  id-token: write
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: |
          pip install tw-framework
          python -m tw_framework.cli export
      - uses: actions/upload-pages-artifact@v3
        with: { path: dist/ }
      - uses: actions/deploy-pages@v4
```

## Testing in CI

```yaml
- run: tw doctor
- run: python -m tw_framework.cli build --prod
- run: pytest tests/ -v
```

## Environment Variables in CI

```yaml
- name: Build
  env:
    API_URL: ${{ secrets.API_URL }}
    JWT_SECRET: ${{ secrets.JWT_SECRET }}
  run: python -m tw_framework.cli build --prod
```
