# HTML Elements and Attributes

## Supported HTML Tags

### Structure

`div`, `span`, `section`, `article`, `header`, `footer`, `nav`, `aside`, `main`, `figure`, `figcaption`

### Headings

`h1`, `h2`, `h3`, `h4`, `h5`, `h6`

### Text

`p`, `b`, `strong`, `i`, `em`, `u`, `small`, `mark`, `blockquote`, `pre`, `code`, `br`, `hr`

### Links & Media

`a`, `img`, `video`, `audio`, `source`, `canvas`, `svg`, `picture`

### Lists

`ul`, `ol`, `li`, `dl`, `dt`, `dd`

### Tables

`table`, `thead`, `tbody`, `tfoot`, `tr`, `td`, `th`, `caption`, `col`, `colgroup`

### Forms

`form`, `input`, `textarea`, `button`, `select`, `option`, `label`, `fieldset`, `legend`, `optgroup`

### Head

`meta`, `link`, `script`, `style`, `title`

## Void Elements (Self-closing)

These elements don't need closing tags:

`img`, `input`, `hr`, `br`, `meta`, `link`, `col`, `embed`, `source`, `track`, `wbr`, `area`, `base`

## Supported Attributes

### Common

`id`, `class`, `href`, `src`, `alt`, `type`, `name`, `value`, `placeholder`, `title`

### Form

`action`, `method`, `target`, `checked`, `disabled`, `selected`, `required`, `readonly`, `multiple`, `autofocus`, `autocomplete`, `enctype`, `min`, `max`, `step`, `pattern`, `accept`

### Table

`colspan`, `rowspan`, `for`, `rows`, `cols`

### Media

`width`, `height`, `sizes`, `srcset`, `loading`, `decoding`, `fetchpriority`, `autoplay`, `loop`, `muted`, `controls`

### Accessibility

`aria-label`, `aria-hidden`, `aria-describedby`, `role`, `tabindex`

### Link

`rel`, `hidden`, `open`, `spellcheck`

### Data attributes

Any `data-*` attribute is supported:

```tw
div {
    class "card"
    data-id "123"
    data-category "product"
}
```

## Syntax

```tw
tagname "text content" {
    attribute "value"
    child_tag "child text"
}
```

### Element with text only

```tw
h1 "Hello World"
p "A paragraph"
```

### Element with attributes only

```tw
img { src "/image.png" alt "Description" }
```

### Element with text and attributes

```tw
a "Click here" { href "/page" class "btn" }
```

### Element with children

```tw
div {
    class "container"
    h1 "Title"
    p "Content"
}
```

### Element with text AND children

```tw
span "Label: " {
    class "label"
    b "Bold value"
}
```
