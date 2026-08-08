# Env vars in pages (public allow-list)

Security note: .tw pages only have access to environment variables you explicitly mark as public. Every other variable -- API keys, database passwords, tokens -- stays server-side only and is never baked into the generated HTML/JS that ships to visitors.

## Usage

In tw.config:

    env:
      public: "SITE_NAME, ANALYTICS_ID"

Now {env.SITE_NAME} works inside any page. {env.DATABASE_PASSWORD} (or any var not listed) simply resolves to nothing.

## Why this matters

Before this existed, page templates had access to your entire environment with no restriction. Writing {env.SOME_SECRET} anywhere in a .tw file -- even by accident -- would render the real value directly into the static HTML sent to every visitor's browser.

Now the default is the safe one: nothing is exposed unless you say so.

## Server-side code is unaffected

API routes (.twm files under [home]/api/) and server-side hooks still see the full environment as before -- this restriction only applies to the context used for rendering page HTML.
