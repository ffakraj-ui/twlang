# Blog Template Guide

Complete blog setup using TW Framework.

## Project Structure

```
my-blog/
├── tw.config
├── [home]/
│   ├── pages/
│   │   ├── index.tw          → /
│   │   ├── blog/
│   │   │   ├── index.tw       → /blog
│   │   │   └── [slug].tw      → /blog/:slug
│   │   ├── about.tw           → /about
│   │   └── 404.tw             → 404
│   ├── components/
│   │   ├── PostCard.tw
│   │   ├── Pagination.tw
│   │   └── TagList.tw
│   ├── layouts/
│   │   └── main.tw
│   ├── api/
│   │   └── posts/
│   │       └── route.twm
│   ├── data/
│   │   └── posts.json
│   └── style/
│       └── blog.tss
```

## Blog Homepage

```tw
// [home]/blog/index.tw
page {
    title "Blog - My Site"
    layout "main"
    render static
}

load "@./data/posts.json"
load "@./style/blog.tss"

body {
    div {
        class "blog-list"
        h1 "Latest Posts"

        each posts as post {
            div {
                class "post-card"
                a "{post.title}" {
                    href "/blog/{post.slug}"
                    class "post-title"
                }
                p "{post.excerpt}"
                span "{post.date}" { class "post-date" }
            }
        }
    }
}
```

## Blog Post Page

```tw
// [home]/blog/[slug].tw
page {
    title "{post.title}"
    layout "main"
    render server
}

load "@./style/blog.tss"

body {
    article {
        class "blog-post"
        h1 "{post.title}"
        div { class "post-meta", span "{post.date}", span "{post.author}" }
        div { class "post-content", text "{post.content}" }
    }

    nav {
        class "post-nav"
        a "Previous" { href "/blog/{prev.slug}" }
        a "Next" { href "/blog/{next.slug}" }
    }
}
```

## Posts JSON Data

```json
[
    {
        "slug": "getting-started-with-tw",
        "title": "Getting Started with TW Framework",
        "excerpt": "Learn how to build websites with TW Framework.",
        "date": "2024-01-15",
        "author": "Admin",
        "content": "Full post content here..."
    }
]
```

## Post Card Component

```tw
// [home]/components/PostCard.tw
div {
    class "post-card"
    a "{title}" {
        href "/blog/{slug}"
        class "post-card-title"
    }
    p "{excerpt}"
    div {
        class "post-card-meta"
        span "{date}"
        span "by {author}"
    }
}
```

## Blog Styles

```css
/* [home]/style/blog.tss */
.blog-list {
    max-width 800px
    margin 0 auto
    padding 20px
}

.post-card {
    bg #fff
    radius 8px
    padding 20px
    margin-bottom 16px
    shadow 0 1px 3px rgba(0,0,0,0.1)
    transition box-shadow 0.2s

    &:hover {
        shadow 0 4px 12px rgba(0,0,0,0.15)
    }
}

.post-title {
    font 22px
    font-weight 600
    color #1a1a1a
    text-decoration none
}

.post-date {
    color #666
    font 14px
}

.blog-post {
    max-width 800px
    margin 0 auto
    padding 40px 20px
}

.post-content {
    line-height 1.6
    font 18px
}
```

## API for Posts

```js
// [home]/api/posts/route.twm

export function GET(request) {
    const page = parseInt(request.query.page) || 1;
    const limit = 10;
    // Fetch posts from database or JSON
    return { status: 200, json: { posts: [], page, total: 0 } };
}

export function POST(request) {
    const { title, content } = request.body;
    // Save post
    return { status: 201, json: { id: 1, title, content } };
}
```

## RSS Feed

Create `[home]/rss.tw` with `render server`:

```tw
page {
    render server
    redirect "/rss.xml"
}
```

Or generate RSS in API route:

```js
// [home]/api/rss/route.twm
export function GET() {
    const xml = `<?xml version="1.0"?>
<rss version="2.0">
<channel>
<title>My Blog</title>
<link>https://example.com/blog</link>
<description>My TW Blog</description>
<item><title>Post Title</title></item>
</channel>
</rss>`;
    return { status: 200, text: xml, headers: { "Content-Type": "application/rss+xml" } };
}
```
