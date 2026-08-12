# Deploying to Vercel

## Zero‑Config Deployment

1. Push your TW project to a GitHub repository.
2. Go to [vercel.com](https://vercel.com) and click **Add New → Project**.
3. Import your repository.
4. Vercel automatically detects `tw.config` and uses the TW Framework preset.
5. Click **Deploy**.

No manual configuration is required. Vercel will run `tw build` and serve the `dist/` directory.

## Manual Configuration

If you need to customize the build, create a `vercel.json` file in your project root:

```json
{
  "framework": "tw",
  "buildCommand": "tw build",
  "outputDirectory": "dist",
  "installCommand": "pip install tw-framework"
}
```

## Environment Variables

Set environment variables in the Vercel dashboard under **Project Settings → Environment Variables**. They will be available during the build and at runtime.

## API Routes

TW API routes (`.twm` files in `[home]/api/`) are automatically handled as serverless functions. No additional configuration is needed.

## Custom Domains

Add a custom domain in the Vercel dashboard under **Project Settings → Domains**.
