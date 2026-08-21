# A2UI Schema Sync — Change Doc

**Date**: 2026-08-20
**Complexity**: S (Simple)
**Branch**: `my-examples`

## Problem

The `_COMPONENT_SCHEMAS`, `_COMPONENT_REQUIRED`, and `_REF_FIELDS` dicts in
`examples/agent_service/a2ui_tool.py` were written from memory/guesses and did
not match the actual Zod strict-mode schemas enforced by
`@a2ui/web_core` v0_9/basic_catalog. This caused:

1. **Valid properties stripped**: e.g. `weight`, `accessibility` were listed
   per-component instead of as common properties, so the validator stripped
   them from components that didn't explicitly list them.
2. **Invalid properties allowed**: e.g. `isChecked`, `isDisabled`,
   `placeholder`, `choices`, `selectedKey`, `isOpen` — all non-existent in
   the actual Zod schemas — were listed as valid, so they passed validation
   but caused frontend render failures.
3. **Missing required fields**: CheckBox `value`, ChoicePicker `options`/`value`,
   TextField `label`, Modal `trigger`/`content`, Tabs `tabs` were not enforced.
4. **Wrong ref fields**: Modal was `["child"]` instead of `["trigger", "content"]`;
   Tabs was missing entirely from `_REF_FIELDS`.
5. **Frontend workaround**: `A2UISurface.tsx` had a `SLIDER_UNSUPPORTED_KEYS`
   hack to strip `step` from Slider components — a symptom of the backend not
   stripping unknown keys correctly.

## Solution

Synced all three dicts to match the actual Zod schemas from
`@a2ui/web_core/src/v0_9/basic_catalog/components/basic_components.d.ts`.

### Changes

#### `examples/agent_service/a2ui_tool.py`

1. **`_COMPONENT_SCHEMAS`**: Rewrote all 18 component entries to match exact
   Zod schema property sets. Removed `weight`/`accessibility` from per-component
   sets (they are common properties handled separately). Key fixes:
   - CheckBox: `isChecked`/`isDisabled` → `value`, `checks`, `isValid`, `validationErrors`
   - ChoicePicker: `choices`/`selectedKey`/`isDisabled` → `options`, `value`, `variant`, `displayStyle`, `filterable`, `checks`, `isValid`, `validationErrors`
   - TextField: removed `placeholder`/`isReadOnly`/`isDisabled`; added `variant`, `validationRegexp`
   - Modal: `child`/`isOpen` → `trigger`, `content`
   - Row: added `justify`, `align`
   - List: added `direction`, `align`, `listStyle`
   - Slider: added `label`, `checks`, `isValid`, `validationErrors`
   - DateTimeInput: `isReadOnly`/`isDisabled` → `enableDate`, `enableTime`, `min`, `max`, `label`, `checks`, `isValid`, `validationErrors`
   - Button: added `checks`, `isValid`, `validationErrors`
   - Icon: removed non-existent `variant`
   - Video: removed non-existent `description`
   - Divider: added `axis`

2. **`_COMPONENT_REQUIRED`**: Added missing required fields:
   - TextField: `label`
   - CheckBox: `label`, `value`
   - ChoicePicker: `options`, `value`
   - Modal: `trigger`, `content`
   - Tabs: `tabs`

3. **`_REF_FIELDS`**: Fixed Modal to `["trigger", "content"]`; added Tabs as
   `["tabs"]` with special handling in the ref-checking logic (tabs is an
   array of `{title, child}` where `child` is a ComponentId reference).

4. **Strict-mode stripping**: Fixed the `allowed` set to include common
   properties (`weight`, `accessibility`) for ALL components, not just those
   that explicitly listed them.

5. **Ref-checking logic**: Added special case for Tabs — iterates `tabs` array
   items and checks each `child` reference. Also added `isinstance(ref, str)`
   guard to avoid false positives on non-string values.

6. **Docstring & description**: Enriched with complete component property
   reference including: data binding (`{path: "/key"}`), actions
   (`{event: {name, context}}`), checks/validation, and correct property
   names for all 18 components with required fields marked.

#### `examples/web_ui/frontend/src/components/a2ui/A2UISurface.tsx`

- Removed `SLIDER_UNSUPPORTED_KEYS` constant and the associated Slider-specific
  key-stripping logic. The backend now correctly strips ALL unknown keys for
  ALL components, making this frontend workaround unnecessary.

## Verification

- Python syntax check: PASS
- 24 validation unit tests: ALL PASS
  - Valid messages pass
  - Old property names (isChecked, choices, selectedKey, isOpen, placeholder, isReadOnly, isDisabled, variant on Icon) are stripped
  - Missing required fields (value on CheckBox, options+value on ChoicePicker, label on TextField, trigger+content on Modal) produce errors
  - Tabs structure validated (valid passes, broken refs detected)
  - Slider `step` stripped
  - Button `action` is optional (not required)
  - Modal valid with trigger+content
- TypeScript compilation: PASS (no errors)
