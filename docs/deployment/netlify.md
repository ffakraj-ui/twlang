# Deploying to Netlify

## Zero‑Config Deployment

1. Push your TW project to a GitHub repository.
2. Go to [netlify.com](https://netlify.com) and click **Add new site → Import an existing project**.
3. Connect your repository.
4. Netlify automatically detects `tw.config` and uses the TW Framework preset.
5. Click **Deploy site**.

No manual configuration is required. Netlify will run `tw build` and publish the `dist/` directory.

## Manual Configuration

If you need to customize the build, create a `netlify.toml` file in your project root:

```toml
[build]
command = "tw build --prod"
publish = "dist"
```

## Environment Variables

Set environment variables in the Netlify dashboard under **Site settings → Build & deploy → Environment**. They will be available during the build and at runtime.

## API Routes

TW API routes (`.twm` files in `[home]/api/`) are automatically handled as Netlify Functions. No additional configuration is needed.

## Custom Domains

Add a custom domain in the Netlify dashboard under **Site settings → Domain management**.
