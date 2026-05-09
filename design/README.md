# Ark Design System — `ark/design/`

> **Purpose:** A single source of truth for how every Honour Systems surface looks, feels, and is built.
> Used by Claude, Kimi, Geon, and every future engineer/designer to keep the product visually
> synonymous across web (`hs_app`), desktop (`desktop/`), and any new Ark surface.

---

## What Lives Here

| File | What it is | Read it when… |
|---|---|---|
| **[ARK_DESIGN_BIBLE.md](./ARK_DESIGN_BIBLE.md)** | The massive authoritative design doc. Philosophy, color theory, type, motion, every component, dashboard patterns, anti‑patterns, and a teaching section ("how to design like Ark"). | You are designing **anything** — start here. |
| **[shadcn-stack.md](./shadcn-stack.md)** | How we use shadcn/ui: CLI, MCP server, registry config, components.json, install playbook, audit checklist. | You need to install, theme, or extend a shadcn component. |
| **[material3-foundations.md](./material3-foundations.md)** | M3 color system, tonal palettes, dark‑mode elevation rules, contrast — adapted to our neutral monochrome. | You are choosing a token, designing a new surface, or unsure why the palette is the way it is. |
| **[component-recipes.md](./component-recipes.md)** | Component‑by‑component spec: every shadcn primitive themed for Ark, with copy‑paste class names, anatomy diagrams, do/don't. | You are using `Button`, `Card`, `Dialog`, etc. and want the canonical Ark variant. |
| **[tokens.css](./tokens.css)** | Production CSS variables. Drop into `app/globals.css`. | You are setting up the Tailwind v4 theme on a new surface. |
| **[tokens.ts](./tokens.ts)** | TypeScript token object — same values, type‑safe. Drop into `lib/design.ts`. | You are using inline styles, JS animations, or charts. |
| **[components.json](./components.json)** | Reference shadcn CLI config matching our tokens. | You are running `shadcn init` or wiring the MCP server. |

---

## The 60‑Second Brief

1. **Aesthetic:** Black, white, gray. **No** color decoration. Color (or its absence) communicates meaning.
2. **System:** shadcn/ui primitives + Aceternity micro‑animations + Material 3 token semantics, all themed to neutral monochrome.
3. **Modes:** Dark‑first (`#000` bg, white on top), light supported (`#fff` bg, black on top). Mirrored, not re‑themed.
4. **Type:** Geist Sans for UI, Geist Mono for data. Tabular numbers for any metric.
5. **Grid:** 4px spacing scale. 8px and 16px do most of the work.
6. **Motion:** 150–200ms, ease‑out. Purposeful only. `prefers-reduced-motion` respected.
7. **Density:** Operators monitor 8+ cameras. Every pixel earns its place.
8. **Threat hierarchy:** Encoded in **opacity + weight**, never hue. (CRITICAL = 100%, HIGH = 80%, MED = 50%, LOW = 30%.)

If you violate any of these, you are not designing Ark.

---

## How to Use This Folder

### If you are Claude / an LLM coding agent

1. Before touching any UI file, **read [ARK_DESIGN_BIBLE.md](./ARK_DESIGN_BIBLE.md) §1–§6** (Philosophy → Motion).
2. For the specific component you are about to build, read its entry in **[component-recipes.md](./component-recipes.md)**.
3. Use the shadcn MCP server first (see [shadcn-stack.md](./shadcn-stack.md) §3) — `mcp__shadcn__list_items_in_registries`, then `view_items_in_registries`, then `get_add_command_for_items`. Do **not** copy raw HTML/CSS off the web.
4. After scaffolding, run the audit checklist (`mcp__shadcn__get_audit_checklist`).
5. Verify every CSS color token you introduce is one already defined in [tokens.css](./tokens.css). If you need a new one, add it there — never hard‑code hex values in components.

### If you are Kimi / a designer

1. Read **ARK_DESIGN_BIBLE.md** end‑to‑end once. It teaches the *why*.
2. When designing a new surface, work in this order: **layout grid → type hierarchy → tokens → components → motion → polish**.
3. Pull components from [component-recipes.md](./component-recipes.md). If a recipe doesn't exist, write one before designing.
4. The §15 "How to Design Like Ark" section is your instruction manual — it codifies the taste.

### If you are reviewing a PR

1. Open the **§16 PR Design Checklist** in the bible. It's the bar.
2. CRITICAL violations (color decoration, hardcoded hex, missing reduced‑motion, density bloat) block the merge.

---

## Inspirations & Sources

- **shadcn/ui** — `https://ui.shadcn.com/docs/components` — primitive library
- **shadcn MCP** — `https://ui.shadcn.com/docs/mcp` — agent integration
- **shadcn CLI** — `https://ui.shadcn.com/docs/cli` — installer
- **Material 3** — `https://m3.material.io/styles/color/system/overview` — token semantics
- **Material 3 schemes** — `https://m3.material.io/styles/color/choosing-a-scheme` — palette theory
- **Material 2 dark theme** — `https://m2.material.io/design/color/dark-theme.html` — elevation overlays, emphasis levels
- **Linear**, **Vercel dashboard**, **Aceternity UI** — taste references

---

*Maintained by:* Ark Engineering · *Owned across:* Web (`hs_app`), Desktop (`desktop/`), future surfaces.
*Last revision:* 2026‑05‑07 · *Version:* 2.0
