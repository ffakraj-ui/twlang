# Content Management

## JSON Data Files

Store content in JSON files for easy editing:

```json
// [home]/data/blog-posts.json
[
    {
        "slug": "getting-started",
        "title": "Getting Started",
        "date": "2024-01-15",
        "author": "Admin",
        "content": "Post content..."
    }
]
```

Load in pages:

```tw
load "@./data/blog-posts.json"

body {
    each blog_posts as post {
        a "{post.title}" { href "/blog/{post.slug}" }
    }
}
```

## Headless CMS Integration

Fetch from any CMS API:

```js
// [home]/api/posts/route.twm
export async function GET(request) {
    const response = await fetch('https://api.cms.com/posts', {
        headers: { 'Authorization': 'Bearer ' + process.env.CMS_API_KEY }
    });
    const posts = await response.json();
    return { status: 200, json: posts };
}
```

## Content in .tw Files

For simple sites, keep content directly in .tw files:

```tw
// [home]/pages/about.tw
page { title "About Us", render static }

body {
    div {
        class "about-page"
        h1 "About Our Company"
        p "We are a company that builds amazing things..."
        h2 "Our Mission"
        p "To make the web faster and simpler..."
    }
}
```

## Markdown Content

For longer content, use a .twm module to parse markdown:

```js
// [home]/lib/markdown.twm
export function renderMarkdown(text) {
    return text
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>');
}
```
