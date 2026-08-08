# Hydration

## What Is Hydration?

Hydration attaches event listeners to server-rendered HTML. In TW, only elements with `on:*` or `bind:*` directives get hydrated.

## How TW Hydration Works

1. Build time - TW compiles .tw to static HTML
2. Page load - HTML shown immediately (no flash)
3. Runtime JS (~2KB) scans for data-tw-* attributes
4. Event binding - Runtime attaches listeners
5. State sync - bind:* elements sync with reactive state

## Data Attributes

```tw
// Source
button "Click" { on:click "increment()" }

// Compiled HTML
<button data-tw-click="increment()">Click</button>
```

```tw
// Source
input { bind:value "name" }

// Compiled HTML
<input data-tw-bind="value:name" />
```

## TW vs React Hydration

| Aspect | React | TW Framework |
|---|---|---|
| Hydration scope | Entire page | Only interactive elements |
| JS shipped | ~90KB | ~2KB |
| Virtual DOM | Yes | No |
| Time to interactive | Slower | Instant |

## No Hydration for Static Pages

Pages with `render static` and no `on:*`/`bind:*` ship zero JS - no hydration at all.
