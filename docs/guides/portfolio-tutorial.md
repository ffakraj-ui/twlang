# Tutorial: Building a Portfolio Site

Create a stunning developer portfolio with TW Framework.

## Project Setup

```bash
tw create my-portfolio
cd my-portfolio
```

## Project Structure

```
[home]/
  pages/
    index.tw        # Hero + About
    projects.tw     # Project showcase
    blog.tw         # Blog listing
    blog/
      [slug].tw     # Blog posts
    contact.tw      # Contact form
  components/
    Header.tw
    Footer.tw
    Hero.tw
    ProjectCard.tw
    SkillBar.tw
    ContactForm.tw
  layouts/
    main.tw
  style/
    global.tss
    home.tss
    projects.tss
  assets/
    images/
      profile.jpg
      projects/
```

## Step 1: Global Styles

`[home]/style/global.tss`:

```css
:root {
    --primary: #6366f1
    --primary-dark: #4f46e5
    --bg: #0f172a
    --bg-secondary: #1e293b
    --text: #f8fafc
    --text-secondary: #94a3b8
    --border: #334155
    --radius: 12px
    --shadow: 0 4px 6px rgba(0,0,0,0.3)
}

* {
    margin: 0
    padding: 0
    box-sizing: border-box
}

body {
    font-family: 'Inter', system-ui, sans-serif
    background: var(--bg)
    color: var(--text)
    line-height: 1.6
}

.container {
    max-width: 1200px
    margin: 0 auto
    padding: 0 24px
}

.section {
    padding: 80px 0
}

.btn {
    display: inline-block
    padding: 12px 32px
    background: var(--primary)
    color: white
    text-decoration: none
    radius: var(--radius)
    font-weight: 500
    transition: background 0.2s
}

.btn:hover {
    background: var(--primary-dark)
}
```

## Step 2: Layout

`[home]/layouts/main.tw`:

```tw
page {
    title "{title} | John Doe"
    render static
}

load "@./style/global.tss"

head {
    link { rel "preconnect" href "https://fonts.googleapis.com" }
    link { rel "stylesheet" href "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" }
}

body {
    Header {}
    slot {}
    Footer {}
}
```

## Step 3: Hero Section

`[home]/components/Hero.tw`:

```tw
let name = "John Doe"
let role = "Full Stack Developer"
let tagline = "Building fast, accessible web experiences"

section {
    class "hero"
    div {
        class "container"
        div {
            class "hero-content"
            h1 {
                span { class "greeting" "Hi, I'm" }
                span { class "name" "{name}" }
            }
            h2 { class "role" "{role}" }
            p { class "tagline" "{tagline}" }
            div {
                class "hero-cta"
                a "View Projects" { href "/projects" class "btn" }
                a "Contact Me" { href "/contact" class "btn btn-outline" }
            }
        }
    }
}
```

`[home]/style/home.tss`:

```css
.hero {
    min-height: 100vh
    display: flex
    align-items: center
    padding-top: 80px
}

.hero-content {
    max-width: 600px
}

.greeting {
    display: block
    color: var(--primary)
    font-size: 1.25rem
    font-weight: 500
    margin-bottom: 8px
}

.name {
    display: block
    font-size: 4rem
    font-weight: 700
    line-height: 1.1
    margin-bottom: 16px
}

.role {
    font-size: 1.5rem
    color: var(--text-secondary)
    font-weight: 400
    margin-bottom: 24px
}

.tagline {
    font-size: 1.125rem
    color: var(--text-secondary)
    margin-bottom: 32px
}

.hero-cta {
    display: flex
    gap: 16px
}

.btn-outline {
    background: transparent
    border: 2px solid var(--primary)
}
```

## Step 4: Projects Page

`[home]/projects.tw`:

```tw
page {
    title "Projects"
    layout "main"
    render static
}

load "@./style/projects.tss"

body {
    section {
        class "section"
        div {
            class "container"
            h1 { class "section-title" "Projects" }
            div {
                class "projects-grid"
                each projects as project {
                    ProjectCard { props project }
                }
            }
        }
    }
}
```

`[home]/components/ProjectCard.tw`:

```tw
let title = ""
let description = ""
let image = ""
let tags = []
let link = ""
let github = ""

article {
    class "project-card"
    img {
        src "{image}"
        alt "{title}"
        class "project-image"
        loading "lazy"
    }
    div {
        class "project-info"
        h3 "{title}"
        p "{description}"
        div {
            class "project-tags"
            each tags as tag {
                span { class "tag" "{tag}" }
            }
        }
        div {
            class "project-links"
            a "Live Demo" { href "{link}" class "link" target "_blank" }
            a "GitHub" { href "{github}" class "link" target "_blank" }
        }
    }
}
```

## Step 5: Skills Section

`[home]/components/SkillBar.tw`:

```tw
let name = ""
let level = 0  // 0-100

div {
    class "skill-bar"
    div {
        class "skill-header"
        span "{name}"
        span "{level}%"
    }
    div {
        class "skill-track"
        div {
            class "skill-fill"
            style "width: {level}%"
        }
    }
}
```

## Step 6: Contact Form

`[home]/contact.tw`:

```tw
page {
    title "Contact"
    layout "main"
    render static
}

body {
    section {
        class "section"
        div {
            class "container"
            h1 { class "section-title" "Get In Touch" }
            p { class "section-desc" "Have a project in mind? Let's talk." }

            form {
                class "contact-form"
                action "/api/contact"
                method "POST"

                div {
                    class "form-group"
                    label "Name" { for "name" }
                    input { id "name" name "name" type "text" required "true" }
                }

                div {
                    class "form-group"
                    label "Email" { for "email" }
                    input { id "email" name "email" type "email" required "true" }
                }

                div {
                    class "form-group"
                    label "Message" { for "message" }
                    textarea { id "message" name "message" rows "5" required "true" }
                }

                button "Send Message" {
                    type "submit"
                    class "btn btn-primary"
                }
            }
        }
    }
}
```

`[home]/api/contact/route.twm`:

```twm
function post(request):
    data = request.json()

    # Validate
    if not data.get("name") or not data.get("email") or not data.get("message"):
        return json_response({"error": "All fields required"}, status=400)

    # Send email (using your email service)
    send_email(
        to="john@example.com",
        subject=f"Contact from {data['name']}",
        body=f"From: {data['email']}\n\n{data['message']}"
    )

    return json_response({"success": True})
```

## Step 7: SEO

```tw
head {
    seo {
        description "John Doe - Full Stack Developer specializing in React, Python, and modern web technologies."
        og_title "John Doe | Portfolio"
        og_image "/assets/og-image.png"
        twitter_card "summary_large_image"
    }
}
```

## Build and Deploy

```bash
tw build --prod
tw deploy
```

## Tips for a Great Portfolio

1. **Show real projects**: Deployed apps > tutorial projects
2. **Write case studies**: Explain problems you solved
3. **Keep it fast**: Optimize images, use lazy loading
4. **Mobile-first**: Test on phones and tablets
5. **Accessibility**: Keyboard nav, alt text, contrast
6. **Analytics**: Track which projects get the most clicks
