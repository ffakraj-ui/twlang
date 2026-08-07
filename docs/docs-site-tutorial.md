# Tutorial: Building a Docs Site

Build TW Framework's own documentation site using TW Framework.

## Why TW for Docs?

- Zero JavaScript by default = instant load
- File-based routing = easy content management
- Static generation = host anywhere
- Custom syntax highlighting = perfect for code

## Project Setup

```bash
tw create tw-docs
cd tw-docs
```

## Content Structure

```
[home]/
  pages/
    index.tw              # Landing page
    docs/
      index.tw            # Docs home
      getting-started.tw
      routing.tw
      components.tw
      styling.tw
      api/
        index.tw
        rest.tw
        graphql.tw
      [slug].tw           # Catch-all for docs
  components/
    DocsLayout.tw
    Sidebar.tw
    Search.tw
    CodeBlock.tw
    PrevNext.tw
  layouts/
    docs.tw
  style/
    docs.tss
  assets/
    js/
      search.js
```

## Step 1: Docs Layout

`[home]/layouts/docs.tw`:

```tw
page {
    title "{title} | TW Docs"
    layout "docs"
    render static
}

load "@./style/docs.tss"

head {
    link { rel "stylesheet" href "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css" }
    script { src "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js" }
}

body {
    div {
        class "docs-layout"
        Sidebar {}
        main {
            class "docs-main"
            article {
                class "docs-content"
                slot {}
            }
            PrevNext {}
        }
    }
    script { "hljs.highlightAll();" }
}
```

## Step 2: Sidebar Navigation

`[home]/components/Sidebar.tw`:

```tw
let current_path = "/"

let nav_items = [
    {"section": "Getting Started", "items": [
        {"title": "Introduction", "path": "/docs"},
        {"title": "Installation", "path": "/docs/getting-started"},
        {"title": "First Project", "path": "/docs/first-project"}
    ]},
    {"section": "Core Concepts", "items": [
        {"title": "Routing", "path": "/docs/routing"},
        {"title": "Components", "path": "/docs/components"},
        {"title": "Styling", "path": "/docs/styling"}
    ]},
    {"section": "API", "items": [
        {"title": "REST API", "path": "/docs/api/rest"},
        {"title": "GraphQL", "path": "/docs/api/graphql"}
    ]}
]

aside {
    class "sidebar"
    nav {
        each nav_items as section {
            div {
                class "nav-section"
                h3 "{section.section}"
                ul {
                    each section.items as item {
                        li {
                            a "{item.title}" {
                                href "{item.path}"
                                class "nav-link"
                                if item.path == current_path {
                                    class "nav-link active"
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
```

## Step 3: Search

`[home]/components/Search.tw`:

```tw
let placeholder = "Search documentation..."

div {
    class "search-box"
    input {
        type "text"
        placeholder "{placeholder}"
        id "docs-search"
        on:input "handleSearch(this.value)"
    }
    div {
        id "search-results"
        class "search-results"
    }
}
```

`[home]/assets/js/search.js`:

```javascript
let searchIndex = [];

async function loadSearchIndex() {
    const res = await fetch('/search-index.json');
    searchIndex = await res.json();
}

function handleSearch(query) {
    const resultsDiv = document.getElementById('search-results');
    if (!query || query.length < 2) {
        resultsDiv.innerHTML = '';
        return;
    }

    const results = searchIndex.filter(item => 
        item.title.toLowerCase().includes(query.toLowerCase()) ||
        item.content.toLowerCase().includes(query.toLowerCase())
    ).slice(0, 10);

    resultsDiv.innerHTML = results.map(r => `
        <a href="${r.path}" class="search-result">
            <strong>${r.title}</strong>
            <p>${r.excerpt}</p>
        </a>
    `).join('');
}

document.addEventListener('DOMContentLoaded', loadSearchIndex);
```

## Step 4: Code Block Component

`[home]/components/CodeBlock.tw`:

```tw
let language = "tw"
let code = ""

pre {
    class "code-block"
    code {
        class "language-{language}"
        "{code}"
    }
}
```

## Step 5: Content Pages

`[home]/pages/docs/routing.tw`:

```tw
page {
    title "Routing"
    layout "docs"
    render static
}

body {
    h1 "Routing"
    p "TW Framework uses file-based routing. Each .tw file becomes a route."

    h2 "Basic Routes"
    p "Create a file in [home]/pages/ to define a route."

    CodeBlock {
        language "tw"
        code "page {\n    title \"Home\"\n    render static\n}\n\nbody {\n    h1 \"Welcome\"\n}"
    }

    h2 "Dynamic Routes"
    p "Use square brackets for dynamic segments."

    CodeBlock {
        language "tw"
        code "// [home]/pages/blog/[slug].tw\npage {\n    title \"{post.title}\"\n}\n\nbody {\n    h1 \"{post.title}\"\n    article \"{post.body}\"\n}"
    }

    h2 "Catch-All Routes"
    p "Use three dots for catch-all routes."

    CodeBlock {
        language "tw"
        code "// [home]/pages/docs/[...slug].tw\n// Matches /docs/getting-started, /docs/api/rest, etc."
    }
}
```

## Step 6: Search Index Generation

Create a build script:

```python
# scripts/build-search-index.py
import os
import json
import re

DOCS_DIR = "[home]/pages/docs"
INDEX = []

def extract_content(filepath):
    with open(filepath) as f:
        content = f.read()

    # Extract title
    title_match = re.search(r'title "([^"]+)"', content)
    title = title_match.group(1) if title_match else "Untitled"

    # Extract body text (simplified)
    body = re.sub(r'[{}]', '', content)
    body = re.sub(r'\s+', ' ', body)
    excerpt = body[:200] + "..."

    return {"title": title, "content": body, "excerpt": excerpt}

for root, dirs, files in os.walk(DOCS_DIR):
    for file in files:
        if file.endswith('.tw'):
            path = os.path.join(root, file)
            rel_path = path.replace('[home]/pages', '').replace('.tw', '')
            item = extract_content(path)
            item["path"] = rel_path
            INDEX.append(item)

with open('[home]/assets/search-index.json', 'w') as f:
    json.dump(INDEX, f)

print(f"Indexed {len(INDEX)} pages")
```

## Step 7: Styling

`[home]/style/docs.tss`:

```css
.docs-layout {
    display: grid
    grid-template-columns: 280px 1fr
    min-height: 100vh
}

.sidebar {
    background: var(--bg-secondary)
    border-right: 1px solid var(--border)
    padding: 24px
    position: fixed
    width: 280px
    height: 100vh
    overflow-y: auto
}

.nav-section {
    margin-bottom: 24px
}

.nav-section h3 {
    font-size: 0.75rem
    text-transform: uppercase
    letter-spacing: 0.05em
    color: var(--text-secondary)
    margin-bottom: 8px
}

.nav-link {
    display: block
    padding: 8px 12px
    color: var(--text-secondary)
    text-decoration: none
    radius: 6px
    font-size: 0.9rem
}

.nav-link:hover,
.nav-link.active {
    color: var(--primary)
    background: var(--bg)
}

.docs-main {
    margin-left: 280px
    padding: 40px 48px
    max-width: 800px
}

.docs-content h1 {
    font-size: 2.5rem
    margin-bottom: 16px
}

.docs-content h2 {
    font-size: 1.5rem
    margin-top: 40px
    margin-bottom: 16px
    padding-bottom: 8px
    border-bottom: 1px solid var(--border)
}

.docs-content p {
    margin-bottom: 16px
    color: var(--text-secondary)
}

.code-block {
    background: #1e293b
    padding: 20px
    radius: 8px
    overflow-x: auto
    margin: 20px 0
}

.code-block code {
    font-family: 'Fira Code', monospace
    font-size: 0.9rem
    line-height: 1.6
}

.search-box {
    margin-bottom: 24px
}

.search-box input {
    width: 100%
    padding: 10px 16px
    background: var(--bg)
    border: 1px solid var(--border)
    radius: 6px
    color: var(--text)
    font-size: 0.9rem
}

.search-results {
    background: var(--bg)
    border: 1px solid var(--border)
    radius: 6px
    margin-top: 8px
}

.search-result {
    display: block
    padding: 12px 16px
    text-decoration: none
    color: var(--text)
    border-bottom: 1px solid var(--border)
}

.search-result:hover {
    background: var(--bg-secondary)
}

.search-result p {
    font-size: 0.85rem
    color: var(--text-secondary)
    margin: 4px 0 0
}
```

## Build

```bash
python scripts/build-search-index.py
tw build --prod
tw deploy
```

## Tips

1. **Version docs**: Keep docs for each major version
2. **Edit links**: Add "Edit on GitHub" links
3. **Last updated**: Show last modified date
4. **404 page**: Helpful docs-specific 404
5. **Print styles**: Make docs printable
