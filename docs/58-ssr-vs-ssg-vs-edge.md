# SSR vs SSG vs Edge Rendering

## render static (SSG)

HTML generated at build time. Zero server needed.

```tw
page { render static }
```

- When: Blogs, landing pages, docs, portfolios
- Speed: Fastest (pre-built HTML)
- JS: 0 bytes (or ~2KB with interactivity)
- Use revalidate for periodic refresh: `page { render static, revalidate 3600 }`

## render server (SSR)

HTML generated per request on the server.

```tw
page { render server }
```

- When: Dashboards, personalized pages, real-time data
- Speed: Moderate (generates per request)
- Dynamic: Yes (fresh data every request)
- Needs: Server (Vercel serverless, Netlify functions)

## render edge (Edge Rendering)

HTML generated at CDN edge closest to user.

```tw
page { render edge }
```

- When: Global audience, personalized, low latency
- Speed: Fast (edge is close to user)
- Dynamic: Yes
- Needs: Edge runtime (Vercel Edge, Cloudflare Workers)

## Comparison

| Feature | static | server | edge |
|---|---|---|---|
| Build time generation | Yes | No | No |
| Per-request generation | No | Yes | Yes |
| Speed | Fastest | Moderate | Fast |
| Needs server | No | Yes | Yes (edge) |
| Best for | Blogs, docs | Dashboards | Global apps |
| Cost | Free (static) | Server costs | Edge costs |

## Choosing a Render Mode

- Landing page: `render static`
- Blog post: `render static` with `revalidate 3600`
- User dashboard: `render server`
- Global API: `render edge`
- Product page: `render static` with `revalidate 300`
- Search results: `render server`
- Documentation: `render static`
