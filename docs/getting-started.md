# Getting Started

## Install

```bash
pip install tw-framework
```

Requires Python 3.9+.

## Create a project

```bash
tw create my-site
cd my-site
```

This scaffolds a starter project with a home page, an about page, a reactive counter demo, a protected dashboard, search, and a couple of API routes — so you can see most of TW's features working immediately.

## Run the dev server

```bash
tw dev
```

Open `http://127.0.0.1:3000`. Edit any `.tw`, `.tss`, or `.ts` file and the browser reloads automatically.

## Project structure

```
my-site/
  tw.config              # project settings
  middleware.tw           # route middleware (auth, headers, rate limits...)
  [home]/
    pages/                 # routes — one file per page
      index.tw              # /
      about.tw               # /about
      blog/
        [slug].tw             # /blog/:slug (dynamic route)
        [slug].json            # list of valid slugs for the dynamic route
    layouts/
      main.tw                # shared page shell (<html>, <head>, {slot})
    components/             # reusable .tw components
    style/
      site.tss              # stylesheets
    api/
      contact/
        route.twm             # POST /api/contact
```

## Build for production

```bash
tw build
```

Output goes to `dist/`. Preview it locally with:

```bash
tw preview
```

## Deploy

**Vercel** — push to GitHub, import the repo on vercel.com. A `vercel.json` in your project root tells Vercel how to build it:

```json
{
  "buildCommand": "pip install tw-framework && tw build --adapter vercel",
  "outputDirectory": "dist"
}
```

**GitHub Pages** — enable Pages in your repo (Settings → Pages → Source → GitHub Actions), then add a workflow that runs `tw build` and uploads `dist/` as the Pages artifact.

## Next steps

- [Syntax Reference](./syntax-reference.md) — full `.tw` / `.tss` language guide
- Run `tw doctor` any time to check your project for common issues
