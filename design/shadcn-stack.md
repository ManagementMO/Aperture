# shadcn Stack — CLI · MCP · Registry · Override Discipline

> Operational reference. How we install, theme, and extend shadcn/ui in any Ark surface.
> Read alongside [ARK_DESIGN_BIBLE.md](./ARK_DESIGN_BIBLE.md) §9 (Component System).

---

## 1. Why shadcn (and Not a Library)

shadcn/ui is **not** an npm package you import. The CLI copies source files into your repo,
and **you own them**. That is what we want:

- We can re-theme freely without forking.
- We can audit the entire UI tree (no opaque vendor code).
- We can extend variants in‑place (CVA‑based — see Bible §9.4).
- We can ship the same primitives to web (`hs_app`) and desktop (`desktop/`) without import-resolution headaches.

It is built on Radix Primitives (accessibility) and Tailwind (utility classes). Both of those
*are* dependencies — they're stable and we accept them.

---

## 2. CLI

### 2.1 Init a new surface

For Next.js (web):

```bash
pnpm dlx shadcn@latest init \
  --template next \
  --css-variables \
  --defaults
```

For Vite (desktop / Tauri):

```bash
pnpm dlx shadcn@latest init \
  --template vite \
  --css-variables \
  --defaults
```

The `--defaults` flag uses the `next + nova` preset. We override it immediately — see §4.

### 2.2 Add components

```bash
# canonical core
pnpm dlx shadcn@latest add button card dialog input label select tabs \
  badge separator dropdown-menu popover sheet sidebar skeleton sonner \
  switch table tooltip command scroll-area progress alert

# extended
pnpm dlx shadcn@latest add accordion alert-dialog avatar breadcrumb \
  calendar checkbox collapsible context-menu data-table drawer \
  hover-card menubar pagination radio-group resizable textarea \
  toggle toggle-group
```

After install, immediately apply the override per Bible §9.4 (replace chromatic CVA variants
with monochrome equivalents, bind colors to our CSS vars).

### 2.3 Other useful commands

| Command | When |
|---|---|
| `view <component>` | Inspect registry source before installing. |
| `search @shadcn -q <term>` | Find a primitive by keyword. |
| `list @shadcn` | List everything available. |
| `info --json` | Dump current project config (debug). |
| `migrate radix src/components/ui/**` | Consolidate `@radix-ui/react-*` → `radix-ui` after bumps. |
| `migrate icons` | Bulk‑switch icon library (we don't — Lucide is canonical). |
| `apply <preset>` | Apply a preset theme (we don't — we own the theme). |

### 2.4 What we never use

- `--all` on `add`. Never. We hand‑pick.
- Any preset other than the one we generate ourselves. The "neon" or "claude" presets are
  chromatic and violate Ark monochrome.
- The deprecated `toast` component — replaced by `sonner`.

---

## 3. MCP Server (for AI agents)

The shadcn MCP server lets coding agents (Claude, Cursor, Codex) browse and install
components by natural language. We use it to make sure Claude/Kimi installs from the
canonical source instead of guessing.

### 3.1 One-time install

In any Ark surface that has `components.json`:

```bash
pnpm dlx shadcn@latest mcp init --client claude
```

This writes/updates `.mcp.json` at the repo root with:

```json
{
  "mcpServers": {
    "shadcn": {
      "command": "npx",
      "args": ["shadcn@latest", "mcp"]
    }
  }
}
```

Restart Claude Code. The server exposes these tools:

| Tool | Purpose |
|---|---|
| `mcp__shadcn__list_items_in_registries` | List everything in `@shadcn` (or our private registries). |
| `mcp__shadcn__search_items_in_registries` | Fuzzy search by keyword. |
| `mcp__shadcn__view_items_in_registries` | Read the source before installing. |
| `mcp__shadcn__get_item_examples_from_registries` | See usage examples. |
| `mcp__shadcn__get_add_command_for_items` | Get the exact `shadcn add` command. |
| `mcp__shadcn__get_project_registries` | List configured registries. |
| `mcp__shadcn__get_audit_checklist` | Post-install checklist. |

### 3.2 The agent's standard flow

When Claude/Kimi needs a component:

```
1. mcp__shadcn__list_items_in_registries(['@shadcn'])      → confirm name
2. mcp__shadcn__search_items_in_registries(...)            → if name not known
3. mcp__shadcn__view_items_in_registries([...])            → read source
4. mcp__shadcn__get_item_examples_from_registries([...])   → see usage
5. Bash:  pnpm dlx shadcn@latest add <name>                → install
6. Edit components/ui/<name>.tsx                           → apply Ark monochrome override
7. mcp__shadcn__get_audit_checklist()                      → verify
```

**Do not** copy/paste shadcn source from the website. Always go through MCP or CLI.

### 3.3 Multi‑client config

We support agents running on Claude Code, Cursor, VS Code, Codex. Add per `components.json`:

| Editor | File | Format |
|---|---|---|
| Claude Code | `.mcp.json` (repo root) | JSON, key `mcpServers` |
| Cursor | `.cursor/mcp.json` | JSON, key `mcpServers` |
| VS Code | `.vscode/mcp.json` | JSON, key `servers` |
| Codex | `~/.codex/config.toml` | TOML |

`.mcp.json` is **not** checked in (the repo `.gitignore` excludes it for security). To
onboard a new contributor, they re-run `mcp init --client <theirs>` once.

---

## 4. `components.json` — Our Canonical Config

A reference copy lives at [./components.json](./components.json). When you `init` a new
surface, replace the generated file with that one. Annotated:

```jsonc
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",            // tighter spacing, smaller radii — matches our density
  "rsc": true,                    // we are on the Next.js app router (web only; false for Vite)
  "tsx": true,                    // never plain JS
  "tailwind": {
    "config": "",                 // Tailwind v4 has no config file — empty string is correct
    "css": "app/globals.css",     // hs_app: app/globals.css; desktop: src/styles/tokens.css
    "baseColor": "neutral",       // we adapt this further; neutral is the closest base
    "cssVariables": true,         // ALWAYS true — required for our token system
    "prefix": ""                  // no prefix — our utilities are global
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide",        // never override
  "registries": {
    "@shadcn": "https://ui.shadcn.com/r/{name}.json"
    // future: "@ark": "https://registry.honoursystems.io/{name}.json"
  }
}
```

When we eventually publish our own composite recipes (ThreatGauge, AlertFeed, CameraCard) as
a private registry, we add it under `registries`. Then they're installable via:

```bash
pnpm dlx shadcn@latest add @ark/threat-gauge
```

---

## 5. Override Discipline (the Most Important Section)

shadcn ships components with a chromatic palette (red destructive, blue link, etc.). We
**replace** every chromatic mention with a monochrome equivalent.

### 5.1 The `cva()` Override Pattern

Every shadcn component uses `class-variance-authority`. The variants table lives at the top of
the file. **Edit the variants in place**, do not wrap.

Diff for `components/ui/button.tsx`:

```diff
   variants: {
     variant: {
-      default: "bg-primary text-primary-foreground hover:bg-primary/90",
-      destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
+      default: "bg-foreground text-background hover:bg-foreground/90",
+      destructive:
+        "bg-foreground text-background border border-foreground/20 hover:bg-foreground/95",
       outline: "border border-input bg-background hover:bg-muted",
-      secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
+      secondary: "bg-muted text-foreground hover:bg-muted/80",
       ghost: "hover:bg-muted text-foreground",
-      link: "text-primary underline-offset-4 hover:underline",
+      link: "text-foreground underline-offset-4 hover:underline",
     },
```

Then commit with `chore(ui): mono override for button` and add a comment at the top of the
file:

```tsx
/**
 * Ark monochrome override applied (see ark/design/ARK_DESIGN_BIBLE.md §9.4).
 * - All chromatic variants replaced with foreground/background pairs.
 * - Destructive carries no color; safety provided by AlertDialog confirm in callsite.
 */
```

### 5.2 What to override per component

| Component | Replace |
|---|---|
| `button` | red `destructive`, blue `link`, colored `secondary` → all mono |
| `badge` | colored `destructive`, `secondary`, `outline` → opacity-stepped variants |
| `alert` | red `destructive` → border-only mono |
| `alert-dialog` | red destructive button → `<Button variant="destructive">` (already mono) |
| `progress` | colored fill → `bg-foreground` |
| `switch` | colored on-state → `bg-foreground` track |
| `slider` | colored range → `bg-foreground` |
| `toast` (sonner) | colored success/error icons → text-only with `CRITICAL`/`SUCCESS` labels |
| `chart` | default rainbow → `var(--chart-1)` etc. all set to `oklch(... grayscale)` |

### 5.3 Don't add new variants without a recipe

When you need a new variant (e.g. a "compact" button for the toolbar), add it to
[component-recipes.md](./component-recipes.md) **first** with anatomy, spec, and use-case.
Then implement. This prevents one-off variants from polluting the system.

---

## 6. Audit Checklist (run after every install/override)

Run `mcp__shadcn__get_audit_checklist()` and walk through each item. The MCP version covers
shadcn-specific checks; we add our own:

- [ ] Component installed via CLI (not copy/paste from website).
- [ ] `cva` chromatic variants replaced with monochrome (Bible §9.4).
- [ ] Color-bearing classes (`bg-red-500`, `text-blue-400`, etc.) — **none present**.
- [ ] All sizes/spacing on the 4px grid.
- [ ] Lucide icons only.
- [ ] `aria-*` props passed through (Radix gives us these — do not strip).
- [ ] Reduced-motion respected on any new transition.
- [ ] Dark mode + light mode both rendered correctly (both screenshotted in PR).
- [ ] Component recipe added/updated in [component-recipes.md](./component-recipes.md).

---

## 7. Useful prompts (drop into chat with Claude/Kimi)

```
"Using the shadcn MCP, install <component>. Then apply the Ark monochrome override per
ark/design/ARK_DESIGN_BIBLE.md §9.4 and add a recipe to component-recipes.md."
```

```
"Show me the shadcn registry source for <component> via mcp__shadcn__view_items_in_registries
before installing. Identify every chromatic class that will need replacement under Ark
monochrome rules."
```

```
"Audit components/ui/* against ark/design/ARK_DESIGN_BIBLE.md. Flag any chromatic Tailwind
class, off-grid spacing, or hex literal."
```

---

*See also:* [tokens.css](./tokens.css) · [tokens.ts](./tokens.ts) · [components.json](./components.json) · [component-recipes.md](./component-recipes.md)
