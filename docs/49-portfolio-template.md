# Portfolio Template Guide

Complete portfolio site using TW Framework.

## Project Structure

```
my-portfolio/
├── tw.config
├── [home]/
│   ├── pages/
│   │   ├── index.tw         → Hero + intro
│   │   ├── projects.tw      → Projects grid
│   │   ├── about.tw          → About page
│   │   └── contact.tw        → Contact form
│   ├── components/
│   │   ├── Header.tw
│   │   ├── Footer.tw
│   │   ├── ProjectCard.tw
│   │   └── SkillBar.tw
│   ├── layouts/
│   │   └── main.tw
│   ├── api/
│   │   └── contact/
│   │       └── route.twm
│   └── style/
│       └── portfolio.tss
```

## Homepage

```tw
// [home]/pages/index.tw
page {
    title "John Doe - Developer"
    layout "main"
    render static
}

load "@./style/portfolio.tss"

body {
    section {
        class "hero"
        div {
            class "hero-content"
            h1 "Hi, I'm John"
            p "Full-stack developer building fast, beautiful websites."
            div {
                class "hero-links"
                a "View Work" { href "/projects", class "btn btn-primary" }
                a "Contact" { href "/contact", class "btn btn-outline" }
            }
        }
    }

    section {
        class "skills"
        h2 "Skills"
        div {
            class "skills-grid"
            div { class "skill", h3 "JavaScript", p "5 years" }
            div { class "skill", h3 "Python", p "3 years" }
            div { class "skill", h3 "TW Framework", p "6 months" }
        }
    }
}
```

## Projects Page

```tw
// [home]/pages/projects.tw
page {
    title "Projects - John Doe"
    layout "main"
    render static
}

load "@./style/portfolio.tss"

body {
    section {
        class "projects"
        h1 "My Projects"

        div {
            class "project-grid"
            div {
                class "project-card"
                img { src "/images/project1.webp", alt "Project 1", loading "lazy" }
                h3 "TW Mods Site"
                p "A premium APK catalog built with TW Framework."
                a "View" { href "https://twmods.in", class "btn" }
            }
            div {
                class "project-card"
                img { src "/images/project2.webp", alt "Project 2", loading "lazy" }
                h3 "Portfolio Site"
                p "This website - built with TW Framework on mobile."
                a "View" { href "#", class "btn" }
            }
        }
    }
}
```

## Contact Form

```tw
// [home]/pages/contact.tw
page {
    title "Contact - John Doe"
    layout "main"
    render static
}

body {
    section {
        class "contact"
        h1 "Get in Touch"

        form {
            on:submit "handleSubmit(event)"
            method "POST"
            action "/api/contact"

            input { type "text", name "name", placeholder "Your name", required true }
            input { type "email", name "email", placeholder "Your email", required true }
            textarea "" { name "message", placeholder "Your message", rows 5, required true }
            button "Send Message" { type "submit", class "btn btn-primary" }
        }
    }
}
```

## Contact API

```js
// [home]/api/contact/route.twm
export function POST(request) {
    const { name, email, message } = request.body;
    // Send email or save to database
    return { status: 200, json: { success: true, message: "Thanks!" } };
}
```

## Portfolio Styles

```css
/* [home]/style/portfolio.tss */
:root {
    --primary #22c55e
    --dark #1a1a1a
    --light #f8f9fa
    --radius 12px
}

.hero {
    min-height 100vh
    display flex
    align-items center
    justify-content center
    text-align center
    bg linear-gradient(135deg, #1a1a1a, #2d2d2d)
    color white
}

.hero h1 {
    font 48px
    font-weight 700
    margin-bottom 16px
}

.hero p {
    font 20px
    color #aaa
    margin-bottom 32px
}

.btn {
    display inline-block
    padding 12px 28px
    radius var(--radius)
    font-weight 600
    text-decoration none
    transition all 0.2s
}

.btn-primary {
    bg var(--primary)
    color white

    &:hover {
        bg #16a34a
        transform translateY(-2px)
    }
}

.btn-outline {
    border 2px solid white
    color white

    &:hover {
        bg white
        color var(--dark)
    }
}

.project-grid {
    display grid
    grid-template-columns repeat(auto-fill, minmax(300px, 1fr))
    gap 24px
    padding 40px 20px
}

.project-card {
    bg white
    radius var(--radius)
    overflow hidden
    shadow 0 2px 8px rgba(0,0,0,0.1)
    transition transform 0.2s, box-shadow 0.2s

    &:hover {
        transform translateY(-4px)
        shadow 0 8px 24px rgba(0,0,0,0.15)
    }

    img {
        width 100%
        height 200px
        object-fit cover
    }
}
```
