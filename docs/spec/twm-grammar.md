## TWM Grammar

`.twm` is TW Language's scripting module format. It is designed around one rule:

Loading a module must never auto-run developer logic.

The compiler may generate JavaScript that registers exported symbols, but it must not execute user functions unless the developer explicitly triggers them (events, direct calls, lifecycle blocks).

## Loading modules

Only one keyword exists:

```tw
load @./lib/auth.twm
```

The compiler detects the file type by extension:

- `.twm` script module
- `.tw` component/page
- `.tss` stylesheet
- `.json` data

## Module behavior (MVP)

On `load`:

- Parse the module
- Compile it
- Register its functions in the TW module registry
- Do not call any of the functions automatically

## Syntax (MVP)

The MVP `.twm` parser supports only function declarations. Top-level statements are rejected so modules cannot accidentally execute code at import time.

```text
module      := (fn_decl | ws | comment)*
fn_decl     := export? ("function" | "fn") identifier params? "{" body "}"
params      := "(" ... ")"
export      := "export"
```

Notes:

- `export` is currently optional; all top-level functions are registered.
- Function bodies are emitted into the output JS as-is in the MVP implementation.
- Names are global in the registry for now. If two modules define the same function name, the last registered one wins.

## Calling functions from `.tw`

Events can reference function names directly:

```tw
button {
  onclick login
  text "Login"
}
```

Compiled output binds `onclick` to a safe dispatcher that looks up `login` in the registry and calls it.

## Local script blocks

Pages may declare a local module using a top-level `SCRIPT { ... }` block:

```tw
load @./auth.twm

SCRIPT {
  fn hello() { console.log("hello") }
}

BODY { button { onclick hello text "Hi" } }
```

`SCRIPT {}` is treated as an inline `.twm` module and compiled exactly like an external `.twm` file.

