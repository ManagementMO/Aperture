# The Ark Design Bible

> **Version 2.0 · 2026‑05‑07**
> A teaching document. Kimi reads it to learn how to design Ark surfaces.
> Claude reads it before touching any UI file. Human engineers read it on day one.
>
> This document does two jobs: it specifies the system (tokens, components, layouts), and
> it teaches the *taste* — the underlying principles that produce a coherent product.

---

## Table of Contents

1. [Philosophy — What Ark Looks Like and Why](#1-philosophy)
2. [The Stack — shadcn + M3 + Aceternity](#2-the-stack)
3. [Color — Material 3 Adapted to Neutral Monochrome](#3-color)
4. [Typography](#4-typography)
5. [Spacing, Layout, Grid, Z-index](#5-spacing-layout-grid-zindex)
6. [Motion](#6-motion)
7. [Iconography](#7-iconography)
8. [Elevation & Surfaces (M3 dark-theme overlays)](#8-elevation--surfaces)
9. [Component System — The 50 shadcn Primitives, Themed](#9-component-system)
10. [Composite Patterns — Ark-Specific UI](#10-composite-patterns)
11. [Data Visualization](#11-data-visualization)
12. [Accessibility](#12-accessibility)
13. [Responsive Behavior](#13-responsive-behavior)
14. [Implementation — Web (`hs_app`) & Desktop (`desktop/`)](#14-implementation)
15. [How to Design Like Ark — A Pedagogy for Kimi](#15-how-to-design-like-ark)
16. [PR Design Checklist](#16-pr-design-checklist)
17. [Anti‑Patterns — What Not to Do](#17-anti-patterns)
18. [Appendix A: M3 Color Roles → Ark Tokens](#appendix-a)
19. [Appendix B: Full Token Tables](#appendix-b)
20. [Appendix C: Glossary](#appendix-c)

---

# 1. Philosophy

## 1.1 What Ark Is

Ark is a **proactive behavioral prediction engine**. It does not classify videos after the fact.
It does not show post‑mortem heatmaps. It predicts the next 30 seconds of behavior in a real
camera feed, in real time, and surfaces that prediction to a human operator who must act on it.

Three things follow from that:

- **Time is the unit of work.** The most important UI element is a curve, not a frame.
- **The operator is fatigued.** They watch 8+ cameras. The UI must reduce, not produce, cognitive load.
- **False positives erode trust.** Every visual element has to earn its place. Decoration is a tax on the operator's attention.

## 1.2 The Five Principles

### 1. Trust Amplification, Not Replacement

The model produces probabilities. The UI must communicate confidence, not certainty.
A "97.3% threat" is a probability — the UI surfaces the *reasoning chain* (VLM narration,
trajectory, micro‑movement signals) so the operator can audit the call.

If you ever find yourself designing a UI that says "the model says X, do Y" with no visible
reasoning, **stop**. Ark is decision support, not autopilot.

### 2. Time Is the Primary Visual Language

Every Ark surface answers one of: *what is happening now*, *what will happen next*, *what just
happened*. Curves, timelines, countdowns, sparklines. Static cards are second‑class citizens.

### 3. Per‑Person, Not Per‑Scene

Cameras are infrastructure. **Persons are subjects.** Whenever possible, organize displays around
tracked individuals (Person A on Cam 3, threat trajectory ↑) rather than scenes (Cam 3, something
happening). This matches operator mental models and the underlying re‑id pipeline.

### 4. Monochrome with Intention

Ark is black, white, gray. **No** decorative color. This is a hard rule, not a preference.

The reasons:
- **Operators look at the screen for hours.** Color fatigues. Monochrome calms.
- **Threat must read instantly.** When everything is grayscale, an inverted (white‑on‑black) panel
  signals critical state without a single colored pixel. The eye reads emphasis through *contrast*,
  not hue.
- **It scales.** Adding a tenth threat category in a colored system requires a tenth hue. In ours,
  it requires a tenth opacity stop — which we already have.
- **It's harder to do well.** Color papers over weak hierarchy. Monochrome forces the layout,
  weight, and spacing to do the actual work. The result is a more disciplined product.

The single permitted accent is **`#888` neutral gray** (M3 tertiary slot) — and it is used
sparingly, for tertiary signals only.

### 5. Density Without Clutter

A pixel either communicates state or it doesn't. If it doesn't, remove it. Border for the sake
of border, padding for the sake of padding, icon for the sake of icon — all out.

The bar:
- A 1280×800 dashboard should fit **eight cameras + threat curves + alert feed + per‑person
  panel** without scrolling, without feeling cramped.
- The way to get there is not "more compact" — it is "fewer visual elements per data point."

---

# 2. The Stack

We layer three systems. Each does one job.

| Layer | Source | Role |
|---|---|---|
| **Primitives** | `shadcn/ui` (Radix‑based, copy/paste) | Headless, accessible building blocks: Button, Dialog, Tabs, etc. |
| **Token semantics** | Material 3 color system | The *roles* (primary, on‑primary, surface‑container, etc.). We adopt the role names; we replace the values with neutrals. |
| **Motion / hero polish** | Aceternity UI (sparingly) | Spotlight, tracing beam, text‑generate effect — for narrative moments only. Forbidden on operator surfaces. |

Why this combination:

- **shadcn/ui** gives us best‑in‑class accessibility and unstyled primitives. It compiles to
  Tailwind utility classes and is fully ownable (the source lives in *our* repo). The
  shadcn **MCP server** lets coding agents browse and install components by name — we use it.
- **Material 3** gives us a token *grammar*: `primary`, `on-primary`, `surface-container`,
  `outline-variant`. That grammar is what makes a design system survive. M3's *colors* are too
  expressive for Ark — we discard them and keep the role names.
- **Aceternity** is a polish layer. The marketing site, the loading hero, the demo trailer.
  Operator surfaces never use it.

> **Rule:** if you cannot justify a component's existence under §1's five principles, it does
> not ship.

---

# 3. Color

## 3.1 Why Material 3, Not Just shadcn Defaults

shadcn ships with a "neutral" theme that is fine. M3 gives us more vocabulary:

- `surface` vs `surface-container` vs `surface-container-high` vs `surface-container-highest`
  → four levels of elevation **without** shadows.
- `outline` vs `outline-variant` → strong vs subtle dividers.
- `inverse-surface` / `inverse-on-surface` → for snackbars, focus inversions, alerting states.
- Container semantics: `primary-container` is *not* `primary` — it's a tonal partner used for
  emphasis surfaces (selected rows, active tabs). M3 distinguishes these; vanilla shadcn does
  not.

We adopt **all 25 M3 color roles** and bind them to neutral values. See [Appendix A](#appendix-a)
for the full mapping.

## 3.2 The Ark Neutral Palette

### Dark Mode (default)

| Tonal step | Hex | Used for |
|---|---|---|
| `0` | `#000000` | Page background |
| `4` | `#0A0A0A` | Surface (cards) |
| `6` | `#111111` | Surface container |
| `8` | `#161616` | Surface container high |
| `10` | `#1A1A1A` | Surface container highest |
| `12` | `#222222` | Hovered raised surface |
| `40` | `#666666` | Outline |
| `60` | `#999999` | Disabled / placeholder |
| `80` | `#CCCCCC` | Secondary text |
| `100` | `#FFFFFF` | Primary text, primary button |

### Light Mode

| Tonal step | Hex | Used for |
|---|---|---|
| `100` | `#FFFFFF` | Page background |
| `98` | `#F8F8F8` | Surface (cards) |
| `96` | `#F0F0F0` | Surface container |
| `94` | `#E8E8E8` | Surface container high |
| `92` | `#E0E0E0` | Surface container highest |
| `90` | `#D8D8D8` | Hovered raised surface |
| `60` | `#999999` | Outline |
| `40` | `#666666` | Disabled / placeholder |
| `20` | `#333333` | Secondary text |
| `0` | `#000000` | Primary text, primary button |

### M3 Role Bindings (both modes)

The full role table lives in [Appendix A](#appendix-a). The mental model:

- **Background** = absolute (black or white).
- **Surface*** = stepped neutrals creating elevation **through tone, not shadow**.
- **Primary** = highest contrast (white in dark, black in light) — used for one element per view.
- **Outline** = mid‑gray. `outline-variant` is half its opacity.
- **On‑*** = the inverse of whatever it sits on, at the appropriate emphasis level.

## 3.3 Emphasis Through Opacity (The Threat Hierarchy)

Material 2 dark theme defines text emphasis levels: high `87%`, medium `60%`, disabled `38%`.
We extend this into the **threat hierarchy**.

| Level | Text | Border | Surface tint | When |
|---|---|---|---|---|
| `CRITICAL` | `100% white, font-weight 600` | `15%` opacity, animated pulse | `rgba(255,255,255,0.02)` | Imminent threat, p > 0.95 |
| `HIGH`     | `87%  white, font-weight 600` | `10%` opacity | transparent | p > 0.7 |
| `MEDIUM`   | `60%  white, font-weight 500` | `8%`  opacity | transparent | p > 0.4 |
| `LOW`      | `38%  white, font-weight 400` | `6%`  opacity | transparent | p > 0.1 |
| `INFO`     | `60%  white, font-weight 400` | `8%`  opacity | transparent | non‑threat status |

**Why this works without color:** the human visual system reads contrast and weight before it
reads hue. A `CRITICAL` row in an alert feed *physically pops* off the page because it is the
brightest, boldest thing in the column — the operator's saccade lands there in <100ms.

The opacities are not decorative. They are not vibes. **Don't change them.** They are calibrated
against WCAG 4.5:1 contrast minimums on a `#0A0A0A` surface.

## 3.4 State Layers (M3)

Hover, press, focus, drag — none of these change *color*. They overlay a translucent tint.

| State | Dark overlay | Light overlay |
|---|---|---|
| Hover | `rgba(255,255,255,0.04)` | `rgba(0,0,0,0.04)` |
| Focus | `rgba(255,255,255,0.06)` | `rgba(0,0,0,0.06)` |
| Pressed | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.08)` |
| Dragged | `rgba(255,255,255,0.12)` | `rgba(0,0,0,0.12)` |
| Selected | `rgba(255,255,255,0.10)` | `rgba(0,0,0,0.10)` |

These compose: a focused **and** hovered element gets `0.04 + 0.06 = 0.10`.

## 3.5 The Forbidden List

Never used in Ark UI:

- ❌ Red, green, amber, blue, cyan, purple, pink, yellow — any chromatic hue.
- ❌ Box shadows for elevation. Use surface tint.
- ❌ Gradients on flat UI surfaces. (One exception: the threat trajectory chart fill — see §11.)
- ❌ More than two simultaneous translucent overlays on one element.
- ❌ Pure `#000` text on pure `#FFF` background in any informational region (use light‑mode tokens; they are tuned for readability at typical brightness).

---

# 4. Typography

## 4.1 Stack

```
font-sans:  "Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif
font-mono:  "Geist Mono", "JetBrains Mono", "SF Mono", "Fira Code", monospace
```

Geist is the system. Geist Mono is for data. There is no third font.

## 4.2 The Type Scale (M3 token names, Ark values)

| Token | px | rem | Weight | Line | Tracking | Use |
|---|---|---|---|---|---|---|
| `display-large` | 57 | 3.5625 | 600 | 64 | -0.25 | Marketing hero only |
| `display-medium` | 45 | 2.8125 | 600 | 52 | 0 | Section heroes |
| `display-small` | 36 | 2.25 | 600 | 44 | 0 | Page titles |
| `headline-large` | 32 | 2.0 | 600 | 40 | 0 | Major headings |
| `headline-medium` | 28 | 1.75 | 600 | 36 | 0 | Sub‑headings |
| `headline-small` | 24 | 1.5 | 500 | 32 | 0 | Card titles |
| `title-large` | 22 | 1.375 | 500 | 28 | 0 | Dialog titles |
| `title-medium` | 16 | 1.0 | 500 | 24 | 0.15 | List headings |
| `title-small` | 14 | 0.875 | 500 | 20 | 0.1 | Section labels |
| `body-large` | 16 | 1.0 | 400 | 24 | 0.5 | Primary body |
| `body-medium` | 14 | 0.875 | 400 | 20 | 0.25 | Secondary body |
| `body-small` | 12 | 0.75 | 400 | 16 | 0.4 | Captions |
| `label-large` | 14 | 0.875 | 500 | 20 | 0.1 | Buttons |
| `label-medium` | 12 | 0.75 | 500 | 16 | 0.5 | Small buttons, badges |
| `label-small` | 11 | 0.6875 | 500 | 16 | 0.5 | Tags |

## 4.3 Data Typography Rules

Numerical data (FPS, threat %, latency ms, timestamps, IDs) is **always** monospace:

```css
font-family: var(--font-mono);
font-variant-numeric: tabular-nums;
letter-spacing: 0;
```

- Threat probabilities always show one decimal: `97.3%`, never `97%` or `97.30%`.
- Latency always in ms with no decimal: `42ms`, never `42.0ms` or `0.042s`.
- Timestamps in 24h: `14:32:07`, with optional ms `14:32:07.412`.
- IDs are uppercase mono with em‑dashes: `PERSON‑A3F2`.

## 4.4 The Single Voice Rule

A view has **one** display‑class element, **one** headline‑class element. Anything else is
title‑class or smaller. If you find yourself wanting two `display-large`s on the same screen,
the screen has two pages on it — split it.

---

# 5. Spacing, Layout, Grid, Z-index

## 5.1 The 4px Grid

Every margin, padding, gap, width, height is a multiple of 4. No exceptions.

| Token | Value | Where it lives |
|---|---|---|
| `space-0` | 0 | — |
| `space-1` | 4 | Icon‑text gap |
| `space-2` | 8 | Inline gap, tight padding |
| `space-3` | 12 | Default component padding |
| `space-4` | 16 | Card padding, section gap |
| `space-5` | 20 | Medium gap |
| `space-6` | 24 | Large gap |
| `space-8` | 32 | Section padding |
| `space-10` | 40 | Major section gap |
| `space-12` | 48 | Page padding |
| `space-16` | 64 | Hero spacing |
| `space-20` | 80 | Sectional break |
| `space-24` | 96 | Hero break |

If you need 14, use 12 or 16. If you need 18, use 16 or 20. **Never** introduce off‑grid values.

## 5.2 Border Radius

| Token | Value | Where |
|---|---|---|
| `radius-none` | 0 | Hard edges (rare — table cells) |
| `radius-sm` | 4 | Tags, micro‑buttons |
| `radius-md` | 8 | Buttons, inputs, badges |
| `radius-lg` | 12 | Cards, dialogs |
| `radius-xl` | 16 | Hero panels |
| `radius-2xl` | 24 | Marketing only |
| `radius-full` | 9999 | Pills, avatars, dot indicators |

Defaults: cards `lg`, inputs `md`, buttons `md`, dialogs `lg`. **Don't mix** `radius-sm` and
`radius-lg` in the same surface — pick the corner language and stick with it.

## 5.3 Layout Grid

| Breakpoint | Cols | Gutter | Margin |
|---|---|---|---|
| `xs <640`  | 4 | 16 | 16 |
| `sm 640`   | 4 | 16 | 16 |
| `md 768`   | 8 | 16 | 24 |
| `lg 1024`  | 12 | 24 | 32 |
| `xl 1280`  | 12 | 24 | 32 |
| `2xl 1536` | 12 | 24 | max-width 1600, auto margins |

Max content width: **1600px**. The product is operator software; we don't stretch endlessly.

## 5.4 Z‑index

| Token | Value | Layer |
|---|---|---|
| `z-base` | 0 | Default |
| `z-raised` | 10 | Sticky elements within a card |
| `z-dropdown` | 1000 | Dropdowns, comboboxes |
| `z-sticky` | 1020 | Sticky page headers |
| `z-overlay` | 1040 | Backdrop |
| `z-modal` | 1050 | Dialog, sheet |
| `z-popover` | 1060 | Popovers, hover cards |
| `z-tooltip` | 1070 | Tooltips |
| `z-toast` | 1080 | Toasts |
| `z-command` | 1090 | Command palette |

---

# 6. Motion

## 6.1 Principles

1. **Purposeful only.** A transition without a state change is decoration. Cut it.
2. **Fast.** 150–200 ms is the default. Anything >300 ms feels broken on a real‑time UI.
3. **One curve does most of the work:** `cubic-bezier(0.2, 0, 0, 1)` (ease‑out, M3 standard‑accelerate).
4. **No bounces. No springs. No elastic.** This is a security console, not a product page.
5. **`prefers-reduced-motion: reduce`** flips every transition to instant. Always.

## 6.2 Standard Durations

| Use | ms | Curve |
|---|---|---|
| Hover, focus | 150 | ease |
| State change (selected, disabled) | 200 | ease‑out |
| Component appear/disappear | 200 | ease‑out / ease‑in |
| Dialog open | 250 | `cubic-bezier(0.2, 0, 0, 1)` |
| Dialog close | 200 | `cubic-bezier(0.4, 0, 1, 1)` |
| Page transition | 300 | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Toast appear | 300 | ease‑out |
| Threat bar fill | 500 | ease‑out |
| Sparkline draw (first render) | 800 | ease‑out |

## 6.3 Named Animations

### Live indicator pulse
A 6 px circle that pulses to indicate a connected, streaming feed.
- Scale: `1 → 1.4 → 1`
- Opacity: `0.7 → 0 → 0.7`
- Duration: 2 s · ease‑in‑out · infinite

### Critical border pulse
On a CRITICAL alert card, the border opacity oscillates `0.10 → 0.25 → 0.10` over 1.6 s.
The card itself does not move.

### Threat trajectory growth
When a new prediction arrives, the curve extends right with a 500 ms ease‑out path animation.
The historical region does not re‑draw.

### Skeleton shimmer
A 1‑direction translate sweep (left → right) of a `1.5%` white gradient over an 8% white block.
Duration 1.6 s, infinite. Disables under reduced motion (becomes a static 8% block).

## 6.4 What Motion Is Banned

- ❌ Hover scale on cards. Causes layout shift, tires the eye, reads as marketing.
- ❌ Bounce / spring easings. Reads as playful — wrong tone.
- ❌ Anything > 400 ms on a control. The user thinks the app froze.
- ❌ Auto‑play carousels.
- ❌ Parallax.

---

# 7. Iconography

- **Library:** [Lucide](https://lucide.dev) (matches shadcn defaults).
- **Stroke:** 1.5 px default, 2 px for emphasis (e.g. CRITICAL state icons).
- **Sizes:** 16 (sm), 20 (md), 24 (lg), 32 (xl).
- **Color:** `currentColor`. Never hard‑code.
- **`aria-label`** required on any icon‑only button.

| Use | Size | Stroke |
|---|---|---|
| Inline with body text | 16 | 1.5 |
| Button affordance | 20 | 1.5 |
| Sidebar nav | 24 | 1.5 |
| Empty state illustration | 32 | 1.5 |
| Status (live, critical) | 16 | 2.0 |

If a Lucide icon doesn't exist for what you need, **don't** mix in another icon library.
File a request and use a `Lucide` placeholder + label until resolved.

---

# 8. Elevation & Surfaces

Material 2 dark‑theme research established that pure black hides elevation cues. Material 3
solved this with **tonal elevation** — overlaying progressively whiter tints on the surface as
elevation rises.

We use the same idea, but our overlays are stepped neutrals (no Primary tint).

| Elevation | Dark surface | Light surface | When |
|---|---|---|---|
| 0 | `#000` | `#FFF` | Page background |
| 1 | `#0A0A0A` | `#F8F8F8` | Cards on background |
| 2 | `#111111` | `#F0F0F0` | Sidebar, menubar, popover |
| 3 | `#161616` | `#E8E8E8` | Dialog, sheet |
| 4 | `#1A1A1A` | `#E0E0E0` | Toast, raised popover |
| 5 | `#222222` | `#D8D8D8` | Hover state on elevation 4 |

**No `box-shadow`** on these. The only place we use shadow is the dialog backdrop blur.

> M3 dark‑theme footnote: M3 advises `#121212` over pure `#000` for its base because of OLED
> smearing. We deliberately use `#000` for the **page background** (it's static), and `#0A0A0A`
> upward for surfaces — the place where text and motion actually happen, where smear matters.

---

# 9. Component System

We use shadcn/ui primitives, themed. The full list lives in
[component-recipes.md](./component-recipes.md). Below is the map of which components we use,
what we override, and what we forbid.

## 9.1 Always Used (the core 30)

| Component | Variant we ship | Notes |
|---|---|---|
| `accordion` | bordered | `outline-variant` dividers only |
| `alert` | inline + toast | Border-left 2 px, no fill |
| `alert-dialog` | center modal | for destructive confirms |
| `aspect-ratio` | wrapper | 16:9 for cameras |
| `avatar` | circle, mono fallback | initials in `label-medium` |
| `badge` | outline‑only, opacity‑coded | see §3.3 |
| `breadcrumb` | text + chevron | mono divider, body‑small |
| `button` | primary, secondary, ghost, icon | see recipes |
| `calendar` | embedded | for date filters |
| `card` | flat with border | no shadow |
| `checkbox` | square 16 px | white check on black |
| `collapsible` | text disclosure | chevron rotates 90° |
| `command` | ⌘K palette | mono accelerator |
| `context-menu` | right-click | popover at elevation 2 |
| `data-table` | mono numerics | see §10.4 |
| `dialog` | center modal | elevation 3 |
| `drawer` | mobile sheet | full-height slide |
| `dropdown-menu` | popover | elevation 2 |
| `hover-card` | trigger info | elevation 2 |
| `input` | filled | `surface-container` bg |
| `kbd` | mono | 11 px, `outline-variant` border |
| `label` | label-medium | always paired with input |
| `popover` | floating | elevation 2 |
| `progress` | linear | white fill on outline track |
| `radio-group` | circle | white dot |
| `scroll-area` | invisible track | white thumb at 30% |
| `select` | native + popover | both supported |
| `separator` | 1 px outline-variant | |
| `sheet` | side slide | for filter drawers |
| `sidebar` | persistent | 280 px, `surface-container` |
| `skeleton` | shimmer | 8% white block |
| `slider` | white track | thumb is `radius-full` |
| `sonner` | top-right | replaces deprecated `toast` |
| `switch` | white thumb | tracks `surface-container-high` |
| `table` | data | mono numerics |
| `tabs` | line + pill variants | line is default |
| `textarea` | filled | min-h 120 |
| `tooltip` | mono if data | 11 px label |

## 9.2 Conditionally Used

- `carousel` — only on the marketing site, **never** in operator UI.
- `chart` — see §11; we customize hard.
- `combobox` — for camera search, person search.
- `date-picker` — for incident replay range selection.
- `input-otp` — for 2FA only.
- `menubar` — desktop app top bar.
- `navigation-menu` — marketing only.
- `pagination` — for incident archive.
- `resizable` — desktop multi‑pane layouts.
- `sonner` — operator notifications.
- `toggle`, `toggle-group` — view-mode switchers.

## 9.3 Forbidden Components

- ❌ **Empty** — we write our own empty state with the threat‑gauge ghost. Generic "No data" is wrong.
- ❌ **Form** with default colors — must use Ark inputs.
- ❌ **Aceternity hero / lamp / gradient** in operator surfaces.
- ❌ Any third‑party component library outside shadcn.

## 9.4 The Override Pattern

When you `shadcn add button`, the source lands in `components/ui/button.tsx`. **Edit it
directly** — don't wrap it. Our overrides:

1. Replace any chromatic CVA variant with monochrome equivalents.
2. Bind colors to our CSS vars (`bg-background`, `text-foreground`, etc.).
3. Add a `data-density="compact"` attribute path for operator views.
4. Ensure `aria-*` attributes are preserved (Radix gives us these).

Example diff for `button.tsx` (the canonical change):

```diff
 const buttonVariants = cva(
   "inline-flex items-center justify-center ...",
   {
     variants: {
       variant: {
-        default: "bg-primary text-primary-foreground hover:bg-primary/90",
-        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
+        default: "bg-foreground text-background hover:bg-foreground/90",
+        destructive: "bg-foreground text-background border border-foreground/20 hover:bg-foreground/95",
         outline:
           "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
-        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
+        secondary: "bg-muted text-foreground hover:bg-muted/80",
         ghost: "hover:bg-accent hover:text-accent-foreground",
-        link: "text-primary underline-offset-4 hover:underline",
+        link: "text-foreground underline-offset-4 hover:underline",
       },
       size: {
         default: "h-10 px-6 py-2 text-sm",
         sm: "h-8 px-4 text-xs",
         lg: "h-12 px-8 text-base",
         icon: "h-10 w-10",
       },
     },
   },
 );
```

The `destructive` variant **does not turn red**. It is the same monochrome button with a heavier
border, and (in the calling code) it is gated behind an `<AlertDialog>`. Color is not the safety
net — confirmation is.

---

# 10. Composite Patterns — Ark-Specific UI

These are the patterns built *on top of* shadcn primitives. They are the components that make
Ark feel like Ark.

## 10.1 The Threat Gauge

The most important UI element. Lives in the top of every camera card and at the top of the
person panel.

**Anatomy:**
```
┌─────────────────────────────────────────────────────────┐
│  PERSON A3F2                              97.3%   t-12s │  ← title row (label-medium / mono)
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░  │  ← bar (8 px, white fill, outline track)
│  ╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴↓ threshold ╴╴╴╴╴╴╴╴╴╴╴╴   │  ← dashed threshold marker
│  −30s              now              +30s                │  ← time axis (label-small)
└─────────────────────────────────────────────────────────┘
```

**Spec:**
- Bar height: 8 px.
- Track: `outline` color.
- Fill: white. Opacity ramps from 30% at `t=0` to 100% at peak.
- Peak marker: 4 px white dot at the highest point in the visible window.
- Threshold: dashed vertical line (1 px, `outline` color, `stroke-dasharray: 4 4`).
- Updates: every frame on desktop (30 fps), every 500 ms on web.
- When p > threshold: border of the *containing card* pulses (see §6.3).

## 10.2 The Camera Card

The unit of the camera grid.

**Anatomy:**
```
┌─────────────────────────────────────┐
│ ● LIVE   Cam 03 — Lobby      14:32  │  ← header (40 px, `surface-container`)
├─────────────────────────────────────┤
│                                     │
│    [ live video, 16:9, drawn       │
│      with skeletons + boxes ]       │  ← video region
│                                     │
│  ┌───────────────────────────────┐  │
│  │ ▓▓▓▓▓▓▓▓░░░░░  62.1%     ↑   │  │  ← threat strip (overlay, last 12% of height)
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**Spec:**
- 16:9 aspect ratio (`aspect-ratio` primitive).
- Border: 1 px `outline` (or `outline` at 25% if alerting).
- No shadow.
- Header strip uses `surface-container` background, 40 px tall, label-medium.
- Live dot pulses (see §6.3) when stream is healthy.
- Threat strip overlay sits on the video, 32 px tall, with a `linear-gradient` from
  `rgba(0,0,0,0.7)` to `rgba(0,0,0,0)` for legibility.
- Click → opens the per‑person focus view.

## 10.3 The Alert Feed

A scrolling list of events, newest at top.

**Row anatomy:**
```
│ 14:32:07.412  CRITICAL  Person A3F2 / Cam 03  Predicted: AGGRESSION  97.3% ▸ │
│   └ time      └ level   └ subject              └ class                └ open │
```

**Spec:**
- Rows: `body-medium` height ≈ 48 px, hover state-layer, click expands inline.
- Time column: 92 px, mono, tabular-nums.
- Level column: 80 px, opacity-coded badge (see §3.3) — **uppercase 11 px label-small**.
- Subject column: flex-1, truncated with ellipsis.
- Probability: 56 px, right-aligned, mono.
- Open chevron: 16 px icon, fades in on row hover.
- New rows enter with the "alert entry" animation (see §6).

The feed is **virtualized** (TanStack Virtual or react-window) — there can be 5000+ rows in a
shift.

## 10.4 The Per‑Person Panel

When the operator clicks into a person, they see:

```
┌───────────────────────────────────────────────────────────────────────────┐
│ PERSON A3F2                                                    Cam 03 ▾    │
│ Tracked since 14:14:02 · Visible 87% · Re-id confidence 0.94               │
├───────────────────────────────────────────────────────────────────────────┤
│ [ ───── threat trajectory chart, 220 px tall ───── ]                       │
├───────────────────────────────────────────────────────────────────────────┤
│ MICRO-MOVEMENT     INTENT             HAND-OBJECT      GAIT                │
│ stride irregular   approach (0.71)    reaching (0.58)  asymmetric (z=2.3)  │
├───────────────────────────────────────────────────────────────────────────┤
│ VLM REASONING                                                              │
│ "Subject's right hand has been near a concealed-pocket position for 8 of   │
│ the last 10 seconds. Stride length has decreased 14%. Approach angle is    │
│ 11° toward Person B6E1 (security guard)."                                  │
└───────────────────────────────────────────────────────────────────────────┘
```

**Spec:**
- Header: title-large + body-small meta row.
- Trajectory chart: see §11.2.
- Signal grid: 4 columns desktop, 2 tablet, 1 mobile. Each cell is `label-small` title +
  `body-medium` value (mono if numeric).
- VLM reasoning block: `surface-container` bg, body-medium, max-height 96 px with scroll.
  Text appears with the **text-generate** Aceternity effect (one of the few permitted).

## 10.5 The Command Palette (⌘K)

shadcn `command` component, themed.

- Opens with `cmd+k` / `ctrl+k`.
- 600 px wide, `surface-container-high` bg, elevation 3.
- Sections: Cameras · People · Incidents · Settings · Help.
- Each row: icon (16) · label · `kbd` shortcut.
- Use the **command** primitive's `<CommandItem onSelect>` — never re-implement keyboard nav.

## 10.6 The Sidebar

shadcn `sidebar` block, themed.

- Width: 280 px desktop, full-screen drawer on mobile.
- Background: `surface-container` (elev 2).
- Top section: logo + workspace switcher.
- Middle: nav items (24 px icon + label-large).
- Bottom: user avatar + status indicator.
- Active item: `surface-container-highest` bg with 2 px left border (`foreground`).

---

# 11. Data Visualization

## 11.1 Chart Defaults

Built on shadcn `chart` (which wraps Recharts) — themed:

- Lines: `var(--foreground)`, 1.5 px stroke.
- Fill: linear gradient from `rgba(255,255,255,0.1)` to `rgba(255,255,255,0)`.
- Grid: `var(--outline-variant)`, dashed `4 4`.
- Axes: `var(--on-surface-variant)`, `body-small`, mono if numeric.
- Tooltip: `surface-container-high` bg, no border, `body-small`, mono numbers.
- No legends unless absolutely required (most Ark charts have one series).
- No animation on data updates inside live charts (jitter is harmful). Animate only on first paint.

## 11.2 The Threat Trajectory Chart

The single most important chart. Used in person panels, incident replay, and the demo trailer.

**Spec:**
- X axis: time, range `−60s` to `+30s`, with `0` marked.
- Y axis: threat probability, `0` to `1`, gridlines at `0.25`, `0.5`, `0.75`, `1.0`.
- Past region (`t < 0`): solid white line, 1.5 px.
- Future region (`t > 0`): same line, dashed `8 4`, with a 10% white fill.
- Threshold: horizontal dashed line at `0.7` (or operator-configured).
- Hover: vertical guide line + tooltip with `t`, `p`, and the dominant signal at that frame.
- VLM annotations: small white dots at frames where the VLM produced a reasoning string;
  hover reveals the text.

## 11.3 Sparklines

For at‑a‑glance per‑person history in lists.

- Width: 80 px. Height: 24 px.
- Line: 1 px white.
- No fill, no axes, no labels.
- Last point: 2 px white dot.
- Renders only the last 60 s, downsampled to 30 points.

## 11.4 Heatmaps

For incident archives only.

- Cells: `surface` → `foreground`, opacity ramp from 0% to 80%.
- No color scale; legend is opacity stops `0%, 25%, 50%, 75%`.
- Cell size: 12 px square, `radius-sm`, 2 px gap.

---

# 12. Accessibility

Non-negotiable.

## 12.1 Contrast

Every text/background pairing **must** clear WCAG 2.2 AA: 4.5:1 for body, 3:1 for ≥18 px or
bold ≥14 px. Verified pairings:

| Pair | Ratio |
|---|---|
| `#FFF` on `#000` | 21:1 |
| `#FFF` on `#0A0A0A` | 18.5:1 |
| `#FFF` on `#111` | 16.8:1 |
| `#FFF 87%` on `#0A0A0A` | 16:1 |
| `#FFF 60%` on `#0A0A0A` | 11:1 |
| `#FFF 38%` on `#0A0A0A` | 7:1 |

Anything dimmer than 38% is for *non-essential* glyphs (axis ticks, separators) and is **not**
sole carrier of meaning.

## 12.2 Focus

- Visible always. Focus ring: `2 px outline`, `2 px offset`, color `var(--ring)` which is
  `rgba(255,255,255,0.6)` in dark, `rgba(0,0,0,0.6)` in light.
- Tab order matches reading order.
- Skip links present on every page.
- Focus trapped in dialogs; `Esc` closes.

## 12.3 Keyboard

- Every interactive element reachable via Tab.
- ⌘K opens the command palette from anywhere.
- ⌘1–⌘9 switch cameras (desktop only).
- `J/K` move down/up the alert feed; `Enter` opens the focused alert; `D` dismisses.

## 12.4 Screen Readers

- Icons inside buttons: `<span class="sr-only">Action label</span>`.
- Live regions for the alert feed: `aria-live="assertive"` on CRITICAL, `aria-live="polite"`
  on lower levels.
- Threat probability changes announce as: *"Person A3F2 threat 97 percent, predicted aggression."*
- Charts: paired with a `<table>` of values with `aria-describedby`.

## 12.5 Motion

`@media (prefers-reduced-motion: reduce)` reduces every animation duration to `0.01ms` and
disables the `live indicator pulse`, `critical border pulse`, and `skeleton shimmer`. Static
fallbacks are defined.

## 12.6 Color Independence

No information is conveyed by color alone (we have no color anyway). Threat level is conveyed
by **opacity + weight + uppercase label** simultaneously.

---

# 13. Responsive Behavior

| Surface | xs | sm | md | lg | xl | 2xl |
|---|---|---|---|---|---|---|
| Camera grid | 1 col | 1 | 2 | 2 | 3 | 4 |
| Alert feed | bottom drawer | drawer | side panel 320 | side 360 | side 400 | side 400 |
| Person panel | full-screen sheet | sheet | sheet | inline 480 | inline 520 | inline 560 |
| Sidebar | drawer | drawer | drawer | fixed 240 | fixed 280 | fixed 280 |
| Top bar | 56 | 56 | 56 | 56 | 56 | 56 |

Operator workflows assume `lg` and up. Mobile is supported but not optimized for live
monitoring — a phone is for paging, not console.

---

# 14. Implementation

## 14.1 Web (`hs_app/`)

Stack: Next.js 15 (app router) · React 19 · Tailwind CSS v4 · shadcn/ui · Radix · Lucide.

Files:
- `app/globals.css` — paste [tokens.css](./tokens.css) into the `@theme inline { }` block.
- `components/ui/*` — shadcn primitives (installed via CLI, themed per §9.4).
- `components/ark/*` — composite patterns (§10).
- `lib/design.ts` — TypeScript token mirror ([tokens.ts](./tokens.ts)).
- `lib/utils.ts` — `cn()` helper from shadcn.
- `components.json` — shadcn config ([reference](./components.json)).

Install playbook on a fresh `hs_app`:

```bash
pnpm dlx shadcn@latest init --template next --css-variables --defaults
# then paste tokens.css into app/globals.css inside @theme inline { ... }
pnpm dlx shadcn@latest mcp init --client claude   # enables MCP for AI agents
pnpm dlx shadcn@latest add button card dialog input label select tabs \
  badge separator dropdown-menu popover sheet sidebar skeleton sonner \
  switch table tooltip command scroll-area progress alert
```

Then apply our overrides per §9.4.

## 14.2 Desktop (`desktop/`)

Stack: Tauri v2 · React 19 · Vite · Tailwind v4 · same shadcn primitives where they run client‑only.

Files:
- `src/lib/design.ts` — same TS tokens.
- `src/styles/tokens.css` — same CSS tokens, scoped to `:root`.
- `src/components/ui/*` — primitives (manually copied because Tauri root differs from Next).
- `src/components/ark/*` — composite patterns; some have desktop variants (e.g. native title bar
  integration).

Platform considerations:
- macOS: hide chrome title bar (`titleBarStyle: 'overlay'` in `tauri.conf.json`), draw our own
  56 px top bar with traffic-light gutter.
- Windows: custom controls drawn in our top bar.
- Linux: respect WM behavior; show controls on the right.
- System tray: white icon when healthy, pulses (per §6.3) when alerting.
- Native notifications: route through Tauri notifier; `surface-container-high` styled inside
  the app for in-app fallback.

## 14.3 Token Sync Discipline

The **CSS tokens and TS tokens MUST agree.** [tokens.css](./tokens.css) and
[tokens.ts](./tokens.ts) are kept in lockstep — when you change one, you change the other in the
same commit. There is a unit test (`tests/design-tokens.test.ts`) that diffs them and fails CI
on drift. Don't disable it.

---

# 15. How to Design Like Ark — A Pedagogy for Kimi

This section is the part that's hardest to write down. It's the *taste*. Read this when you are
designing a new surface and you don't know where to start.

## 15.1 The Order of Operations

Always design in this order. Skipping a step or changing the order produces ugly UI.

**1. The data.** What information must this surface answer? Write it as three or four user
questions. *"Where is Person A right now? What will they do in 10 s? Why does the model think
that?"* These three questions are the surface.

**2. The hierarchy.** Rank the questions by frequency and urgency. The most-asked question gets
the largest, brightest piece of real estate. The least-asked question can be a hover tooltip.

**3. The grid.** Now decide the layout. 12-column grid. Where does the dominant question go?
Probably top-left, taking 8 columns. The second question takes 4 columns on the right. The
third question is below.

**4. The type hierarchy.** Apply the type scale. The dominant element gets `headline-medium`
or `display-small`. Sub-elements get `title-medium`. Body is `body-medium`. Mono everywhere
there's a number.

**5. The tokens.** Now and only now, apply colors. **Background** for the page, **surface**
for cards, **surface-container** for the elevated surface where the dominant element lives.
The dominant element itself uses `foreground` as its primary contrast. Outlines come last.

**6. The components.** Drop in shadcn primitives (Button, Card, Tabs, etc.). If a primitive
doesn't exist for what you need, build the composite per §10. Don't reach for raw `<div>`
where a `<Card>` will do.

**7. The motion.** What state changes happen here? A new alert? A threat curve growing?
Specify the duration and curve. If nothing changes, no motion.

**8. The polish.** Round corners, add separators, check spacing. Walk away. Come back. Cut
the three least-useful elements.

The mistake everyone makes is starting at step 5 (picking colors) and working backward. That
produces dashboards that look like marketing pages.

## 15.2 The "Half" Test

After you have a draft, ask: *can I cut half the visual elements and still answer the user's
questions?*

If yes, cut them.

This is how Ark gets density without clutter. Most designers default to additive thinking ("I
should add a label here, an icon there"). Ark designs subtractively. The final UI is what's
left after you've removed everything you can.

## 15.3 The Mono Discipline

When you feel the urge to add color: **stop**. Ask:

- Is this signaling a state? Use opacity + weight (§3.3).
- Is this distinguishing categories? Use position + label, not color.
- Is this a brand moment? Use a pure white element on pure black, or vice versa. Inversion is
  Ark's brand color.

If after that exercise you *still* believe you need color, file an issue with a screenshot and
the principle you think justifies it. There are no other escapes.

## 15.4 The Rule of One

Each view has:
- One `display`-class element.
- One `headline`-class element.
- One primary action button.
- One alerting state at a time.

If a view has two of any of those, it has two pages. Split it.

## 15.5 Time First

Ask of every element: *does this show what is happening, what will happen, or what just
happened?* If none, ask whether it should.

The most-loved Ark UI elements (the threat gauge, the trajectory chart, the live pulse) all
encode time. The least-loved (settings forms, user lists) are timeless. Spend your design
budget where it matters.

## 15.6 Per-Person, Then Per-Camera

Whenever a list could be either, make it per-person. Operators ask "where is X?" 10x more often
than they ask "what's on Cam Y?". The exception is the camera grid itself — that's spatial
infrastructure, and it's the only place cameras get top billing.

## 15.7 Numbers Are Mono. Mono Numbers Are Tabular.

Every. Single. Number. If you ever see a percent in `font-sans`, it's a bug. The columns won't
align, and that's an instant tell that the system isn't being followed.

## 15.8 Density Targets (the bar)

For an operator surface at `lg` (1024 wide):

- Camera grid: 4 cameras visible in 2x2, each 16:9, with no scroll on a 768-tall viewport.
- Alert feed: 12 rows visible without scrolling.
- Per-person panel: full signal grid (4 signals × micro-movement, intent, hand-object, gait)
  + threat chart + VLM block, no scroll.

If any of those three need scrolling at `lg` × 768, the surface is too sparse.

## 15.9 Consistency Beats Cleverness

A clever new component that looks great in one view but doesn't fit anywhere else is a net
negative. Always check: *does this generalize?* If it doesn't, refactor it or push back on the
requirement.

## 15.10 Cite Your Sources

When you make a non-obvious choice, leave a comment in the code:

```tsx
// Threat strip uses 32px height (§10.2) and gradient overlay
// (rgba(0,0,0,0.7) → 0) for legibility over arbitrary video frames.
```

Six months from now, you (or Kimi, or Claude) will need to know *why*.

---

# 16. PR Design Checklist

Run this on every PR that touches UI. Block on any failure.

- [ ] No hex literals in component files. All colors come from CSS vars.
- [ ] All numbers in the UI are `font-mono` + `tabular-nums`.
- [ ] Every spacing/padding/gap value is a multiple of 4.
- [ ] No new components introduced without a recipe in [component-recipes.md](./component-recipes.md).
- [ ] No animation > 300 ms on interactive controls.
- [ ] `prefers-reduced-motion` honored (test with the browser flag).
- [ ] Focus ring visible on every interactive element (test with `Tab`).
- [ ] All icons have `aria-label` if standalone, or `aria-hidden` if decorative beside text.
- [ ] Contrast verified for any new token pair (use `bg-token-fg-token` test page).
- [ ] No `box-shadow` for elevation. (Backdrop blur on dialog backdrop is the exception.)
- [ ] No chromatic colors anywhere. Grayscale screenshot looks identical to the live UI.
- [ ] Component fits the **Half Test** (§15.2). PR description names what you cut.
- [ ] Token values in `tokens.css` and `tokens.ts` agree (CI test passes).

---

# 17. Anti‑Patterns — What Not to Do

The following are real mistakes engineers make. Each maps to a principle violated.

## 17.1 "Just a little red for errors"

**Wrong.** Errors are conveyed by inversion (white panel on black bg, or vice versa) and an
uppercase `CRITICAL` label. The moment one component goes red, every other component has to
opt in or out of the color system, and the discipline collapses.

## 17.2 "I'll add a hover scale to make it feel alive"

**Wrong.** Hover scales cause layout shift, slow down dense views, and look like marketing.
Use border-color or state-layer overlays.

## 17.3 "This number is sans because it's part of the heading"

**Wrong.** Even in headings, numerals go mono. The rule is unconditional. `Detected 47 events`
has `47` in mono.

## 17.4 "I bumped the radius to 14px because 12 felt small"

**Wrong.** 14 isn't on the scale. Choose 12 or 16. The scale exists so we don't have eight
slightly-different radii across the app.

## 17.5 "Three card variants — flat, raised, and floating"

**Wrong.** We have one card, with elevation determined by *which surface token it's on*. A card
on `background` looks raised because it's `surface`. A card on `surface-container` reads as
inset because the elevations are reversed. **Use the surface system.** Don't invent variants.

## 17.6 "I added a gradient bg for visual interest"

**Wrong.** Visual interest is a signal of design failure, not a design goal. Ark dashboards are
not interesting; they are *useful*. The interesting thing on the screen is the threat curve.

## 17.7 "Loading spinner so the user knows something's happening"

Ok — but use the `skeleton` shimmer for content placeholders. Reserve the spinner for true
indeterminate operations (model loading, file upload). Both must respect reduced-motion.

## 17.8 "I put the alert level in the icon shape"

Use the standard badge with opacity-coded label. We don't carry meaning in icon shape; the icon
is decorative.

## 17.9 "I wrote my own button because shadcn's didn't have what I needed"

Open the source in `components/ui/button.tsx` and **add** the variant. Don't fork. The CVA
config exists exactly for this.

## 17.10 "The customer wants a colored logo"

Brand assets are exempt. The product chrome is not. The logo can be wordmark + glyph; the rest
of the UI stays monochrome.

---

# Appendix A

## M3 Color Roles → Ark Token Bindings

This is the lookup table you reach for when you ask: *"shadcn's `--card-foreground` — what
should it be in Ark?"*

| M3 Role | Dark | Light | shadcn var | Use |
|---|---|---|---|---|
| `primary` | `#FFFFFF` | `#000000` | `--primary` | Primary action button |
| `on-primary` | `#000000` | `#FFFFFF` | `--primary-foreground` | Text on primary |
| `primary-container` | `#161616` | `#E8E8E8` | — | Selected row, active tab |
| `on-primary-container` | `#FFFFFF` | `#000000` | — | Text on container |
| `secondary` | `#1A1A1A` | `#E0E0E0` | `--secondary` | Secondary surfaces |
| `on-secondary` | `#FFFFFF` | `#000000` | `--secondary-foreground` | |
| `tertiary` | `#888888` | `#666666` | `--accent` | The single permitted gray |
| `on-tertiary` | `#000000` | `#FFFFFF` | `--accent-foreground` | |
| `error` | `#FFFFFF` | `#000000` | `--destructive` | Destructive (still mono — uses border + label) |
| `on-error` | `#000000` | `#FFFFFF` | `--destructive-foreground` | |
| `background` | `#000000` | `#FFFFFF` | `--background` | Page bg |
| `on-background` | `#FFFFFF` | `#000000` | `--foreground` | Page text |
| `surface` | `#0A0A0A` | `#F8F8F8` | `--card` | Cards |
| `on-surface` | `#FFFFFF` | `#000000` | `--card-foreground` | Card text |
| `surface-variant` | `#111111` | `#F0F0F0` | `--muted` | Muted surfaces |
| `on-surface-variant` | `rgba(255,255,255,0.7)` | `rgba(0,0,0,0.6)` | `--muted-foreground` | Secondary text |
| `surface-container` | `#111111` | `#F0F0F0` | — | Sidebar, popovers |
| `surface-container-high` | `#161616` | `#E8E8E8` | `--popover` | Dialogs |
| `surface-container-highest` | `#1A1A1A` | `#E0E0E0` | — | Toast, raised popover |
| `outline` | `rgba(255,255,255,0.16)` | `rgba(0,0,0,0.16)` | `--border` | Borders |
| `outline-variant` | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.08)` | `--input` | Subtle dividers, input borders |
| `inverse-surface` | `#FFFFFF` | `#000000` | — | Snackbar bg in dark mode |
| `inverse-on-surface` | `#000000` | `#FFFFFF` | — | Snackbar text in dark mode |
| `inverse-primary` | `#000000` | `#FFFFFF` | — | Action text on inverse surface |
| `scrim` | `rgba(0,0,0,0.6)` | `rgba(0,0,0,0.4)` | — | Dialog backdrop |
| `shadow` | `transparent` | `transparent` | — | We don't use shadows |

# Appendix B

## Full Token Reference — see [tokens.css](./tokens.css) and [tokens.ts](./tokens.ts)

# Appendix C

## Glossary

- **Operator** — a security/loss-prevention staffer using Ark to monitor live cameras.
- **Threat trajectory** — the model's predicted probability curve over the next 30 s.
- **Re-id** — re-identification, the pipeline that keeps a person's identity across cameras.
- **Tonal elevation** — Material 3 technique of indicating elevation by progressively lighter
  surface tones rather than shadow.
- **State layer** — a translucent overlay (hover, focus, pressed, dragged) applied over a base
  surface; M3 vocabulary.
- **Aceternity** — a marketing-grade animation/effect library; we use it for one or two narrative
  moments only.
- **VLM** — Vision-Language Model. The narrator that turns the threat signals into a readable
  reasoning chain.
- **Sparkline** — a 24 px-tall single-series chart used inline in lists.

---

*Maintained by Ark Engineering · Drafted by Claude · Reviewed by Kimi*
*v2.0 · 2026-05-07 · Supersedes `docs/ark-design-system.md` v1.0*
