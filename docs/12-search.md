# Built-in Search

TW Framework automatically generates a search index during build.

## How It Works

During `tw build`, TW:
1. Compiles all static pages
2. Extracts text content from each page
3. Builds a JSON search index at `/_tw/search-index.json`
4. Injects a search runtime (~1KB) into pages

## Using Search

The search index is available at `/_tw/search-index.json`:

```json
[
    {
        "title": "About Us",
        "url": "/about",
        "content": "About us page content..."
    },
    {
        "title": "Contact",
        "url": "/contact",
        "content": "Contact page content..."
    }
]
```

## Client-Side Search

TW provides a built-in search runtime. To add search to your site:

```tw
script {
    // Search is available via TW's runtime
    async function search(query) {
        const response = await fetch('/_tw/search-index.json');
        const index = await response.json();
        return index.filter(page =>
            page.title.toLowerCase().includes(query.toLowerCase()) ||
            page.content.toLowerCase().includes(query.toLowerCase())
        );
    }
}
```

## Dev Mode Search

During `tw dev`, the search index is generated on-the-fly from current page content. No rebuild needed.

## Customizing Search

The search index includes:
- Page title (from `page { title "..." }`)
- Page URL (from route)
- Text content (stripped of HTML tags)

To exclude a page from search:

```tw
page {
    title "Private Page"
    render static
    // Add to robots but not search
}
```

## Search Index Location

The generated index is at:
- Build: `dist/_tw/search-index.json`
- Dev: served from memory at `/_tw/search-index.json`
