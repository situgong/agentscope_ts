---
skill: project-feature
date: 2026-08-20
title: Theme Switch — Light / Dark / Auto
status: review-ready
complexity: S
---

# Theme Switch — Light / Dark / Auto

## Summary

Added a three-mode theme switcher (Light / Dark / Auto) to the Web UI sidebar,
leveraging the existing `next-themes` dependency and pre-defined `.dark` CSS variables.

## Changes

### Modified Files

| File | Change |
|------|--------|
| `src/main.tsx` | Wrapped app with `ThemeProvider` from `next-themes` (`attribute="class"`, `defaultTheme="light"`, `enableSystem`) |
| `src/components/layout/AppSidebar.tsx` | Added theme toggle button in sidebar footer with `DropdownMenu` (Light/Dark/Auto options); icon changes based on current theme (Sun/Moon/Monitor) |
| `src/index.css` | Added dark-mode overrides for custom CSS variables (`--text`, `--bg`, `--border`, `--code-bg`, `--accent`, `--shadow`, `--color-text-secondary`, etc.) to `.dark` selector |
| `src/i18n/locales/en.json` | Added `theme`, `themeLight`, `themeDark`, `themeAuto` translations |
| `src/i18n/locales/zh.json` | Added `主题`, `浅色`, `深色`, `跟随系统` translations |

### No New Files

All changes reuse existing infrastructure:
- `next-themes` (^0.4.6) — already in `package.json`
- `DropdownMenu` component — already existed
- `.dark` CSS variables — already defined (extended with custom vars)
- lucide-react `Sun`, `Moon`, `Monitor` icons

## Design Decisions

1. **`next-themes` over custom solution**: Already installed, handles localStorage persistence, system preference detection, and SSR-safe class toggling out of the box.
2. **DropdownMenu over cycle button**: Three options (Light/Dark/Auto) are clearer with an explicit menu than a cycling button.
3. **Sidebar footer placement**: Consistent with existing language toggle and settings buttons.
4. **Dark CSS variable completion**: The `.dark` selector had shadcn variables but was missing custom vars (`--text`, `--bg`, etc.) from the old commented-out media query. Added them plus `@theme inline` color overrides.

## Verification Results

- ✅ TypeScript compilation: clean (no errors)
- ✅ Light mode: `classList="light"`, `bgColor="rgb(244, 245, 6)"`
- ✅ Dark mode: `classList="dark"`, `bgColor="rgb(22, 23, 29)"`
- ✅ Persistence: `localStorage.theme` survives page reload
- ✅ Dropdown menu: Shows Light/Dark/Auto with correct active state
- ✅ Icon changes: Sun for light, Moon for dark, Monitor for auto

## Phase Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| 1 UNDERSTAND | ✅ | Light/Dark/Auto three-mode theme switch |
| 2 LOCATE & READ SOURCE | ✅ | Found next-themes installed, .dark CSS vars defined |
| 3 DESIGN | ✅ | Complexity: S (3 files, no DB/API) |
| 4 IMPLEMENT | ✅ | ThemeProvider + DropdownMenu + CSS vars + i18n |
| 5 TEST | ✅ | tsc clean, browser verified light/dark/persistence |
| 6 TEST PLAN | ⏭️ | Skipped (S complexity) |
| 7 VERIFY | ⏭️ | Skipped (S complexity) |
| 8 DOCUMENT | ✅ | This document |
| 9 EXECUTE LOG | ✅ | This document |
