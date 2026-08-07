# Internationalization (i18n)

TW Framework doesn't have built-in i18n, but you can implement it with JSON data files.

## Translation Files

```json
// [home]/data/translations/en.json
{ "hello": "Hello", "welcome": "Welcome to our site" }
```

```json
// [home]/data/translations/hi.json
{ "hello": "Namaste", "welcome": "Hamari site mein swagat hai" }
```

## Using Translations

```tw
page { title "Home", render server }

load "@./data/translations/{lang}.json"

body {
    h1 "{t.hello}"
    p "{t.welcome}"
}
```

## Language Switcher

```tw
div {
    class "lang-switcher"
    a "EN" { href "/?lang=en" }
    a "HI" { href "/?lang=hi" }
}
```

## URL-based Language Detection

Use route structure for language:

```
[home]/pages/
├── en/
│   ├── index.tw
│   └── about.tw
├── hi/
│   ├── index.tw
│   └── about.tw
```
