# Tutorial: Building a Blog

Build a complete blog with TW Framework in under 30 minutes.

## Project Setup

```bash
tw create my-blog
cd my-blog
```

## Step 1: Blog Post Data

Create `[home]/blog/[slug].json`:

```json
[
  {
    "slug": "hello-world",
    "title": "Hello World",
    "date": "2024-01-15",
    "author": "Jane Doe",
    "excerpt": "My first post using TW Framework.",
    "tags": ["intro", "tw"],
    "body": "Welcome to my blog! This post was built with TW Framework."
  },
  {
    "slug": "why-tw",
    "title": "Why I Chose TW Framework",
    "date": "2024-01-22",
    "author": "Jane Doe",
    "excerpt": "Zero JavaScript by default is a game changer.",
    "tags": ["tw", "performance"],
    "body": "After years of React, I wanted something simpler..."
  }
]
```

## Step 2: Blog Post Page

Create `[home]/blog/[slug].tw`:

```tw
page {
    title "{post.title}"
    layout "main"
    render static
}

load "@./style/blog.tss"

body {
    article {
        class "blog-post"

        header {
            class "post-header"
            h1 "{post.title}"
            div {
                class "post-meta"
                span "By {post.author}"
                time "{post.date}"
            }
            div {
                class "post-tags"
                each post.tags as tag {
                    span {
                        class "tag"
                        "{tag}"
                    }
                }
            }
        }

        div {
            class "post-content"
            "{post.body}"
        }

        nav {
            class "post-nav"
            a "All Posts" { href "/blog" class "back-link" }
        }
    }
}
```

## Step 3: Blog Index Page

Create `[home]/blog.tw`:

```tw
page {
    title "Blog"
    layout "main"
    render static
}

load "@./style/blog.tss"

body {
    div {
        class "blog-index"
        h1 "Blog"
        p "Thoughts on web development, performance, and simplicity."

        div {
            class "posts-grid"
            each posts as post {
                article {
                    class "post-card"
                    a {
                        href "/blog/{post.slug}"
                        h2 "{post.title}"
                        p "{post.excerpt}"
                        div {
                            class "post-meta"
                            time "{post.date}"
                            span "{post.author}"
                        }
                    }
                }
            }
        }
    }
}
```

## Step 4: Styles

Create `[home]/style/blog.tss`:

```css
.blog-post {
    max-width: 720px
    margin: 0 auto
    padding: 40px 20px
}

.post-header {
    margin-bottom: 40px
    border-bottom: 1px solid var(--border)
    padding-bottom: 24px
}

.post-header h1 {
    font-size: 2.5rem
    margin-bottom: 16px
    line-height: 1.2
}

.post-meta {
    color: var(--text-secondary)
    font-size: 0.9rem
    display: flex
    gap: 16px
}

.post-tags {
    display: flex
    gap: 8px
    margin-top: 16px
}

.tag {
    background: var(--bg-secondary)
    color: var(--primary)
    padding: 4px 12px
    radius: 20px
    font-size: 0.8rem
}

.post-content {
    font-size: 1.1rem
    line-height: 1.8
    color: var(--text)
}

.post-nav {
    margin-top: 60px
    padding-top: 24px
    border-top: 1px solid var(--border)
}

.back-link {
    color: var(--primary)
    text-decoration: none
    font-weight: 500
}

.blog-index {
    max-width: 960px
    margin: 0 auto
    padding: 40px 20px
}

.blog-index h1 {
    font-size: 2.5rem
    margin-bottom: 8px
}

.blog-index > p {
    color: var(--text-secondary)
    margin-bottom: 40px
}

.posts-grid {
    display: grid
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr))
    gap: 24px
}

.post-card {
    background: var(--card-bg)
    border: 1px solid var(--border)
    radius: 12px
    padding: 24px
    transition: transform 0.2s, box-shadow 0.2s
}

.post-card:hover {
    transform: translateY(-4px)
    box-shadow: var(--shadow-lg)
}

.post-card a {
    text-decoration: none
    color: inherit
    display: block
}

.post-card h2 {
    font-size: 1.25rem
    margin-bottom: 12px
    color: var(--text)
}

.post-card > a > p {
    color: var(--text-secondary)
    font-size: 0.95rem
    margin-bottom: 16px
    line-height: 1.5
}
```

## Step 5: RSS Feed

Create `[home]/api/rss.twm`:

```twm
function get(request):
    posts = load_json("[home]/blog/[slug].json")

    items = []
    for post in posts:
        items.append(
            "<item>" +
            "<title>" + escape_xml(post['title']) + "</title>" +
            "<link>https://mysite.com/blog/" + post['slug'] + "</link>" +
            "<pubDate>" + post['date'] + "</pubDate>" +
            "<description>" + escape_xml(post['excerpt']) + "</description>" +
            "</item>"
        )

    rss = '<?xml version="1.0" encoding="UTF-8"?>'
    rss += '<rss version="2.0">'
    rss += '<channel>'
    rss += '<title>My Blog</title>'
    rss += '<link>https://mysite.com/blog</link>'
    rss += '<description>Thoughts on web development</description>'
    rss += ''.join(items)
    rss += '</channel></rss>'

    return Response(rss, content_type="application/rss+xml")
```

## Step 6: Add to Navigation

Update `[home]/components/Header.tw`:

```tw
nav {
    class "main-nav"
    ul {
        li { a "Home" { href "/" } }
        li { a "Blog" { href "/blog" } }
        li { a "About" { href "/about" } }
    }
}
```

## Build and Deploy

```bash
tw build --prod
tw deploy
```

## Next Steps

- Add pagination for many posts
- Implement a tag filter system
- Add a search page using TW's built-in search
- Create an admin panel for writing posts
- Add comments using a third-party service
