# AST Structure

## Node Types

### PageNode
- title: string
- layout: string
- render_mode: "static" / "server" / "edge"
- revalidate: optional number
- redirect_to: optional string
- body: List of child nodes
- head: optional head model
- loaded_sheets: list of stylesheets
- loaded_json: list of JSON data
- on_load_inits: list of hook names

### ElementNode
- tag: "div", "h1", "p", etc.
- text: optional string content
- attrs: List of Attribute
- children: List of child nodes

### ComponentNode
- name: Component name (e.g. "Hero")
- props: List of Attribute
- children: List of child nodes

### IfNode
- condition: string expression
- children: nodes if true
- else_children: nodes if false

### ForNode
- var_name: loop variable
- iterable: expression
- children: loop body

### LetNode
- name: variable name
- value: initial value

### ScriptNode
- raw_js: JavaScript code string

## Attribute Structure
- name: "class", "href", "on:click"
- value: string, number, boolean, or expression

## View AST

```bash
tw ast [home]/index.tw
```

## View IR

```bash
tw ir [home]/index.tw
```
