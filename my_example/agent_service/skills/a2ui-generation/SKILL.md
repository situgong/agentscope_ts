---
name: a2ui-generation
description: Guide for generating valid A2UI v0.9.1 messages. Read this skill before calling the A2UI tool to create interactive UI surfaces.
---

# A2UI Generation Skill

This skill provides the complete A2UI v0.9.1 protocol specification you need to generate valid A2UI messages. Read this before calling the `A2UI` tool.

## Protocol Overview

A2UI is a JSON-based streaming UI protocol. You emit a list of JSON messages (envelopes), each with `"version": "v0.9.1"` and exactly one top-level key.

### Four message types

| Message | Purpose | Required fields |
|---------|---------|-----------------|
| `createSurface` | Initialize a new UI surface | `surfaceId`, `catalogId` |
| `updateComponents` | Add/replace components | `surfaceId`, `components` |
| `updateDataModel` | Set data for path bindings | `surfaceId`, `value` |
| `deleteSurface` | Remove a surface | `surfaceId` |

**Order**: `createSurface` must come first. Then `updateComponents` and `updateDataModel` in any order. `deleteSurface` last.

**catalogId**: Always use `"basic"` — the frontend normalizes it to the full URL.

### Minimal example

```json
[
  {"version": "v0.9.1", "createSurface": {"surfaceId": "s1", "catalogId": "basic"}},
  {"version": "v0.9.1", "updateComponents": {"surfaceId": "s1", "components": [
    {"component": "Column", "id": "root", "children": ["t1", "b1"]},
    {"component": "Text", "id": "t1", "text": "Hello A2UI!"},
    {"component": "Button", "id": "b1", "child": "b1-label", "action": {"event": {"name": "click_me", "context": {}}}},
    {"component": "Text", "id": "b1-label", "text": "Click Me"}
  ]}}
]
```

## Component Model

Components use an **adjacency-list model**: a flat list where tree structure is built via ID references. One component MUST have `id: "root"`.

- Each component has: `id` (unique string), `component` (type name), plus type-specific properties.
- Container components reference children by their `id` strings.
- Components can be in any order — the client buffers until `root` is defined.

### Common properties (all components accept these)

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | **Yes** | Unique identifier within the surface |
| `component` | string | **Yes** | Component type name |
| `accessibility` | object | No | Accessibility metadata |
| `weight` | number | No | Layout sizing weight (flex-grow) |

## Data Binding

Any string/number/boolean property can be either a **literal value** or a **dynamic binding**:

```json
// Literal
{"text": "Hello World"}

// Path binding — resolves from the data model
{"text": {"path": "/userName"}}

// Function call
{"text": {"call": "formatString", "args": {"value": "Hello, ${/userName}!"}}}
```

### Path resolution

- **Absolute paths** start with `/`: `{"path": "/user/name"}` — always resolves from data model root.
- **Relative paths** (no leading `/`): `{"path": "name"}` — resolves within the current collection scope (inside template lists).

### Two-way binding (input components)

`TextField`, `CheckBox`, `Slider`, `ChoicePicker`, `DateTimeInput` establish two-way binding with the data model:
- **Read**: Component reads its value from the bound path.
- **Write**: User input immediately updates the local data model at that path.
- **Sync**: The updated state is sent to you only when a **Button action** is triggered.

### formatString function

String interpolation with `${...}` syntax:

```json
{
  "component": "Text",
  "id": "welcome",
  "text": {
    "call": "formatString",
    "args": {"value": "Hello, ${/user/firstName}! Today is ${formatDate(value:${/today}, format:'yyyy-MM-dd')}."}
  }
}
```

- `${/path/to/value}` — absolute path interpolation
- `${relativePath}` — relative path (inside templates)
- `${functionName(arg1:value, arg2:'string')}` — function call
- `\${` — literal `${`

## Actions

Interactive components (Button) use `action` to define what happens on user interaction:

### Server action (sends event back to you)

```json
{
  "component": "Button",
  "id": "submit-btn",
  "child": "submit-label",
  "action": {
    "event": {
      "name": "submit_form",
      "context": {
        "email": {"path": "/formData/email"}
      }
    }
  }
}
```

When clicked, you receive: `[A2UI Action] submit_form` with the context resolved from the data model.

### Local action (client-side function)

```json
{
  "action": {
    "functionCall": {
      "call": "openUrl",
      "args": {"url": "${/linkUrl}"}
    }
  }
}
```

## Checks & Validation

Checkable components (Button, TextField, CheckBox, ChoicePicker, Slider, DateTimeInput) support:

- `checks`: Array of check definitions. If any fails, the component shows an error (or button is disabled).
- `isValid`: Boolean override.
- `validationErrors`: Array of error strings.

### Check definition (CRITICAL format)

Each check is an object with **two required fields**: `condition` (a function call returning boolean) and `message` (error string).

```json
{
  "checks": [
    {
      "condition": {
        "call": "required",
        "args": {"value": {"path": "/formData/email"}},
        "returnType": "boolean"
      },
      "message": "Email is required"
    },
    {
      "condition": {
        "call": "email",
        "args": {"value": {"path": "/formData/email"}},
        "returnType": "boolean"
      },
      "message": "Please enter a valid email"
    }
  ]
}
```

**Common mistake**: Putting `call`/`args` directly in the check object. You MUST wrap them in a `condition` object.

### Available validation functions

| Function | Description |
|----------|-------------|
| `required` | Value is not null/undefined/empty |
| `regex` | Value matches a regex pattern (`"pattern": "^[0-9]{5}$"`) |
| `length` | String length constraints |
| `numeric` | Numeric range constraints |
| `email` | Valid email address |
| `and` | Logical AND of boolean values |
| `or` | Logical OR of boolean values |
| `not` | Logical NOT of a boolean |

### Button with validation

Buttons can have `checks` too — if any fails, the button is **automatically disabled**:

```json
{
  "component": "Button",
  "id": "submit",
  "child": "submit-label",
  "checks": [
    {
      "condition": {
        "call": "and",
        "args": {
          "values": [
            {"call": "required", "args": {"value": {"path": "/formData/terms"}}, "returnType": "boolean"},
            {"call": "required", "args": {"value": {"path": "/formData/email"}}, "returnType": "boolean"}
          ]
        },
        "returnType": "boolean"
      },
      "message": "You must accept terms and provide email"
    }
  ]
}
```

## Complete Component Reference

★ = required property

### Display components

**Text** — `text`★ (string or {path}), `variant` ("h1"/"h2"/"h3"/"h4"/"h5"/"caption"/"body")
- Supports simple Markdown (no HTML/images/links)

**Image** — `url`★ (string or {path}), `description`, `fit` ("contain"/"cover"/"fill"/"none"/"scaleDown"), `variant` ("icon"/"avatar"/"smallFeature"/"mediumFeature"/"largeFeature"/"header")

**Icon** — `name`★ (enum or {path})
- Valid icon names: `accountCircle`, `add`, `arrowBack`, `arrowForward`, `attachFile`, `calendarToday`, `call`, `camera`, `check`, `close`, `delete`, `download`, `edit`, `event`, `error`, `fastForward`, `favorite`, `favoriteOff`, `folder`, `help`, `home`, `info`, `locationOn`, `lock`, `lockOpen`, `mail`, `menu`, `moreVert`, `moreHoriz`, `notificationsOff`, `notifications`, `pause`, `payment`, `person`, `phone`, `photo`, `play`, `print`, `refresh`, `rewind`, `search`, `send`, `settings`, `share`, `shoppingCart`, `skipNext`, `skipPrevious`, `star`, `starHalf`, `starOff`, `stop`, `upload`, `visibility`, `visibilityOff`, `volumeDown`, `volumeMute`, `volumeOff`, `volumeUp`, `warning`

**Video** — `url`★ (string or {path})

**AudioPlayer** — `url`★ (string or {path}), `description`

**Divider** — `axis` ("horizontal"/"vertical")

### Layout components

**Row** — `children`★ (array of IDs or template), `justify`, `align`
- Horizontal layout (Flexbox row)

**Column** — `children`★ (array of IDs or template), `justify`, `align`
- Vertical layout (Flexbox column)

**List** — `children`★ (array of IDs or template), `direction`, `align`, `listStyle`
- Scrollable list

**Card** — `child`★ (single component ID)
- Container with card styling (rounded corners, shadow, padding)

**Tabs** — `tabs`★ (array of `{title, child}`)
- Each `child` is a component ID reference

**Modal** — `trigger`★ (component ID), `content`★ (component ID)
- `trigger` is the button that opens the modal; `content` is what shows inside

### ChildList template (dynamic lists)

Instead of a static array of IDs, `children` can be a template object:

```json
{
  "component": "List",
  "id": "item-list",
  "children": {
    "componentId": "item-row-template",
    "path": "/items"
  }
}
```

The client iterates over the array at `/items` and instantiates `item-row-template` for each item. Inside the template, use **relative paths** (`{"path": "name"}`) to access item fields.

### Interactive components

**Button** — `child`★ (component ID for label), `action` (server or local action), `variant` ("default"/"primary"/"borderless"), `checks`, `isValid`, `validationErrors`
- **Always include `action`** with a unique event `name` so clicks are sent back to you.

**TextField** — `label`★, `value` (string or {path}), `variant` ("shortText"/"longText"/"number"/"obscured"), `validationRegexp`, `checks`, `isValid`, `validationErrors`
- Two-way binding: user input updates the data model at the bound path.

**CheckBox** — `label`★, `value`★ (boolean or {path}), `checks`, `isValid`, `validationErrors`
- Two-way binding (boolean).

**ChoicePicker** — `options`★ (array), `value`★, `label`, `variant`, `displayStyle`, `filterable`, `checks`, `isValid`, `validationErrors`
- Multi-select component.

**Slider** — `value`★ (number or {path}), `max`★, `min`, `label`, `checks`, `isValid`, `validationErrors`
- Two-way binding (number).

**DateTimeInput** — `value`★ (ISO 8601 string or {path}), `enableDate`, `enableTime`, `min`, `max`, `label`, `checks`, `isValid`, `validationErrors`
- Two-way binding (string).

## Theme

Set in `createSurface`:

```json
{
  "createSurface": {
    "surfaceId": "s1",
    "catalogId": "basic",
    "theme": {
      "primaryColor": "#00BFFF",
      "iconUrl": "https://example.com/logo.png",
      "agentDisplayName": "My Agent"
    }
  }
}
```

| Property | Description |
|----------|-------------|
| `primaryColor` | Hex color (e.g. "#00BFFF") for highlights, primary buttons |
| `iconUrl` | URL for agent/tool avatar image |
| `agentDisplayName` | Text identifying the agent |

## Available Functions

| Function | Description |
|----------|-------------|
| `required` | Checks value is not null/undefined/empty |
| `regex` | Checks value matches regex pattern |
| `length` | Checks string length constraints |
| `numeric` | Checks numeric range constraints |
| `email` | Checks valid email address |
| `formatString` | String interpolation with `${...}` syntax |
| `formatNumber` | Formats number with grouping and precision |
| `formatCurrency` | Formats number as currency |
| `formatDate` | Formats date/time using a pattern |
| `pluralize` | Selects localized string based on count |
| `openUrl` | Opens a URL in browser |
| `and` | Logical AND on list of booleans |
| `or` | Logical OR on list of booleans |
| `not` | Logical NOT on a boolean |

## Common Patterns

### Form with validation and submit

```json
[
  {"version": "v0.9.1", "createSurface": {"surfaceId": "form", "catalogId": "basic"}},
  {"version": "v0.9.1", "updateComponents": {"surfaceId": "form", "components": [
    {"component": "Card", "id": "root", "child": "col"},
    {"component": "Column", "id": "col", "children": ["email-field", "submit-btn"]},
    {"component": "TextField", "id": "email-field", "label": "Email",
     "value": {"path": "/form/email"}, "variant": "shortText",
     "checks": [
       {"condition": {"call": "required", "args": {"value": {"path": "/form/email"}}, "returnType": "boolean"}, "message": "Email is required"},
       {"condition": {"call": "email", "args": {"value": {"path": "/form/email"}}, "returnType": "boolean"}, "message": "Invalid email"}
     ]},
    {"component": "Button", "id": "submit-btn", "child": "submit-label",
     "variant": "primary",
     "action": {"event": {"name": "submit", "context": {"email": {"path": "/form/email"}}}}},
    {"component": "Text", "id": "submit-label", "text": "Submit"}
  ]}}
]
```

### Dynamic list from data

```json
[
  {"version": "v0.9.1", "createSurface": {"surfaceId": "list-demo", "catalogId": "basic"}},
  {"version": "v0.9.1", "updateComponents": {"surfaceId": "list-demo", "components": [
    {"component": "List", "id": "root",
     "children": {"componentId": "item-template", "path": "/items"}},
    {"component": "Row", "id": "item-template", "children": ["item-name", "item-qty"]},
    {"component": "Text", "id": "item-name", "text": {"path": "name"}},
    {"component": "Text", "id": "item-qty", "text": {"call": "formatString", "args": {"value": "Qty: ${quantity}"}}}
  ]}},
  {"version": "v0.9.1", "updateDataModel": {"surfaceId": "list-demo", "value": {
    "items": [
      {"name": "Apple", "quantity": 10},
      {"name": "Banana", "quantity": 5}
    ]
  }}}
]
```

### Modal dialog

```json
[
  {"version": "v0.9.1", "createSurface": {"surfaceId": "modal-demo", "catalogId": "basic"}},
  {"version": "v0.9.1", "updateComponents": {"surfaceId": "modal-demo", "components": [
    {"component": "Column", "id": "root", "children": ["title", "modal"]},
    {"component": "Text", "id": "title", "text": "Modal Demo", "variant": "h2"},
    {"component": "Modal", "id": "modal", "trigger": "open-btn", "content": "modal-content"},
    {"component": "Button", "id": "open-btn", "child": "open-btn-label",
     "action": {"event": {"name": "open_modal", "context": {}}}},
    {"component": "Text", "id": "open-btn-label", "text": "Open Modal"},
    {"component": "Column", "id": "modal-content", "children": ["modal-text"]},
    {"component": "Text", "id": "modal-text", "text": "Content inside the modal!"}
  ]}}
]
```

### Tabs

```json
[
  {"version": "v0.9.1", "createSurface": {"surfaceId": "tabs-demo", "catalogId": "basic"}},
  {"version": "v0.9.1", "updateComponents": {"surfaceId": "tabs-demo", "components": [
    {"component": "Tabs", "id": "root", "tabs": [
      {"title": "Tab 1", "child": "tab1-content"},
      {"title": "Tab 2", "child": "tab2-content"}
    ]},
    {"component": "Text", "id": "tab1-content", "text": "First tab content"},
    {"component": "Text", "id": "tab2-content", "text": "Second tab content"}
  ]}}
]
```

## Critical Rules

1. **`createSurface` must come first** — before any `updateComponents` or `updateDataModel`.
2. **Root component required** — one component must have `id: "root"`.
3. **All ID references must exist** — if a component references `"child": "btn-label"`, a component with `id: "btn-label"` must exist.
4. **Strict mode** — unknown properties cause validation failure. Only use the properties listed above.
5. **Use `"basic"` as catalogId** — the frontend normalizes it.
6. **Always include `action` on Buttons** — with a unique event `name` so clicks reach you.
7. **Use `updateDataModel` for dynamic content** — don't hardcode data in component properties; bind via `{"path": "/key"}` and set data with `updateDataModel`.
8. **Button `child` is a component ID** — not a string. Create a separate `Text` component for the label.
