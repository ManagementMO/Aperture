# Material 3 Foundations — Adapted to Ark Neutral

> The "why" behind the colors. Read this once and you'll understand every other file.

Material 3 (M3) is Google's current design system. We don't use M3's *colors* (they're
expressive and chromatic; Ark is monochrome). We **do** use M3's:

- Color **role names** (vocabulary).
- Tonal palette concept (numerical tonal steps 0–100).
- Surface-elevation-via-tone idea.
- State layer overlays.
- Dark theme overlay rules from M2 (still canonical).

This file explains the M3 concepts we've adopted, so a designer or engineer can reason from
first principles when tokens don't cover an edge case.

---

## 1. Tonal Palettes

In M3, every key color produces a **tonal palette** — 13 stops from `0` (black) to `100`
(white), with named values at `0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99, 100`.

A scheme is built by picking specific tonal values for each role:

| Role | Light scheme tone | Dark scheme tone |
|---|---|---|
| `primary` | 40 | 80 |
| `on-primary` | 100 | 20 |
| `primary-container` | 90 | 30 |
| `on-primary-container` | 30 | 90 |

In a chromatic M3 scheme, those numbers index a hue — `primary tone 40` of a blue palette is
a saturated mid-blue. In **Ark neutral**, the entire palette is grayscale, so the tonal step
is the actual lightness.

### 1.1 Ark Neutral Tonal Palette (dark mode)

| Step | Value | Bound to |
|---|---|---|
| 0 | `#000000` | background |
| 4 | `#0A0A0A` | surface |
| 6 | `#111111` | surface-container, surface-variant, muted |
| 8 | `#161616` | surface-container-high, popover, primary-container |
| 10 | `#1A1A1A` | surface-container-highest, secondary |
| 12 | `#222222` | hovered raised |
| 16 | `rgba(255,255,255,0.16)` | outline |
| 8α | `rgba(255,255,255,0.08)` | outline-variant, input |
| 4α | `rgba(255,255,255,0.04)` | hover state layer |
| 6α | `rgba(255,255,255,0.06)` | focus state layer |
| 60 | `#999999` | muted-foreground (raw); we use `rgba(255,255,255,0.7)` (calibrated) |
| 87% | `rgba(255,255,255,0.87)` | high-emphasis text |
| 60% | `rgba(255,255,255,0.60)` | medium-emphasis text |
| 38% | `rgba(255,255,255,0.38)` | disabled text |
| 100 | `#FFFFFF` | foreground, primary |

### 1.2 Ark Neutral Tonal Palette (light mode)

Mirrored. Step `0` becomes `#FFFFFF` (background); step `100` becomes `#000000` (foreground).
Surface tones step *darker* (`#F8`, `#F0`, `#E8`, `#E0`) instead of lighter.

The mirroring is exact in semantics, not in raw RGB. We don't simply invert hex — we adjust
each step so the *contrast ratio* of every role matches in both modes.

---

## 2. The 25 Color Roles

M3's role table (we use all of these, see [Bible Appendix A](./ARK_DESIGN_BIBLE.md#appendix-a)
for the full mapping):

### Brand pair
- `primary` / `on-primary` — main action color and its text/icon color.
- `primary-container` / `on-primary-container` — softer container for primary content (selected
  rows, active tabs).

### Secondary pair
- `secondary` / `on-secondary` — for less prominent UI components.
- `secondary-container` / `on-secondary-container` — same idea.

### Tertiary pair (the "accent")
- `tertiary` / `on-tertiary` — sparingly used accent. **Ark uses this slot for the single
  permitted gray (`#888`).**
- `tertiary-container` / `on-tertiary-container`.

### Error pair
- `error` / `on-error` — error indication. **Ark expresses errors via inversion + label, not
  hue** — but we still bind these tokens for shadcn compatibility.
- `error-container` / `on-error-container`.

### Surface family (the workhorses)
- `background` / `on-background` — page-level.
- `surface` / `on-surface` — cards, panels.
- `surface-variant` / `on-surface-variant` — slightly different container tint; common for
  inputs, secondary text.
- `surface-container` / `surface-container-high` / `surface-container-highest` — three
  elevation steps used for sidebar, dialogs, popovers, raised popovers respectively.
- `surface-bright` / `surface-dim` — light/dark theme adjustments. We rarely need these.

### Outline family
- `outline` — borders, dividers (full opacity).
- `outline-variant` — softer dividers.

### Inverse family
- `inverse-surface` / `inverse-on-surface` — used for snackbars (in dark mode, a snackbar is
  *light* against the dark UI).
- `inverse-primary` — primary action on the inverse surface.

### Utility
- `scrim` — modal backdrop.
- `shadow` — we set this to transparent. Ark doesn't use shadows.

---

## 3. The Elevation System (M3 Tonal Elevation)

**M2 (old):** elevation drawn with shadows. Higher → darker, more diffused shadow.

**M3 (current):** elevation drawn with **surface tone**. Higher → progressively lighter
surface in dark mode (or progressively grayer in light mode).

Why: shadows fail in dark themes (a dark shadow on a dark surface is invisible). Tonal
elevation works in both modes.

### Ark's elevation table

| Level | Dark surface | Light surface | Examples |
|---|---|---|---|
| 0 | `#000000` | `#FFFFFF` | Page background |
| 1 | `#0A0A0A` | `#F8F8F8` | Card on background |
| 2 | `#111111` | `#F0F0F0` | Sidebar, popover, dropdown |
| 3 | `#161616` | `#E8E8E8` | Dialog, sheet |
| 4 | `#1A1A1A` | `#E0E0E0` | Toast, raised popover |
| 5 | `#222222` | `#D8D8D8` | Hover on level 4 |

In M3 these would be derived from `surface` + a Primary-tinted overlay. In Ark, we strip the
primary tint (no chroma) and step through neutrals only.

**Rule:** if you find yourself reaching for `box-shadow`, you're on the wrong level. Move the
surface up or down.

---

## 4. State Layers (M3)

When a user interacts with a component, M3 overlays a translucent tint of the **on-color** for
that component. This tint is the state layer.

| State | Opacity | Layer color in dark | Layer color in light |
|---|---|---|---|
| Hover | 8% (M3) → **4%** (Ark, calibrated) | `rgba(255,255,255,0.04)` | `rgba(0,0,0,0.04)` |
| Focus | 12% (M3) → **6%** (Ark) | `rgba(255,255,255,0.06)` | `rgba(0,0,0,0.06)` |
| Pressed | 12% (M3) → **8%** (Ark) | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.08)` |
| Dragged | 16% (M3) → **12%** (Ark) | `rgba(255,255,255,0.12)` | `rgba(0,0,0,0.12)` |
| Selected | 12% (M3) → **10%** (Ark) | `rgba(255,255,255,0.10)` | `rgba(0,0,0,0.10)` |

We trim M3's state layers down because Ark is **denser** than the average M3 product. M3 is
calibrated for consumer apps (one main thing on screen). Ark has 8 cameras + 50 alerts + a
trajectory chart on screen at once. Strong state layers wash everything out.

**Composability:** layers add. Hover + Focus = `0.04 + 0.06 = 0.10`. Implement via stacked
absolute pseudo-elements (`::before`, `::after`), not by changing background.

---

## 5. Choosing a Scheme — Ark's Choice

M3 offers several scheme strategies:

| Strategy | Description | Ark's stance |
|---|---|---|
| **Dynamic color** | Scheme derived from user's wallpaper at runtime | ❌ Never. Ark is a console — predictability beats personalization. |
| **Content-based** | Scheme derived from a hero image / brand color | ❌ No brand color. |
| **Custom monochrome** | Single grayscale tonal palette | ✅ **Ark uses this.** |
| **Fidelity** | Scheme stays close to source color | n/a |
| **Expressive** | Scheme uses contrasting accents | ❌ Banned. |
| **Standard contrast** | WCAG AA | ✅ Default |
| **Medium contrast** | Slightly stronger borders | ✅ Honored when `prefers-contrast: more` |
| **High contrast** | Maximum contrast | ✅ Honored when `prefers-contrast: more` and we step outlines from 16% → 32% opacity |

### 5.1 Algorithm for tonal value assignment

For a chromatic M3 scheme, the standard tonal mapping is:

```
LIGHT MODE                       DARK MODE
primary                  → 40    primary                  → 80
on-primary               → 100   on-primary               → 20
primary-container        → 90    primary-container        → 30
on-primary-container     → 10    on-primary-container     → 90
surface                  → 99    surface                  → 6
on-surface               → 10    on-surface               → 90
surface-container        → 94    surface-container        → 12
surface-container-high   → 92    surface-container-high   → 17
surface-container-highest→ 90    surface-container-highest→ 22
outline                  → 50    outline                  → 60
outline-variant          → 80    outline-variant          → 30
```

For Ark Neutral, since the palette is achromatic, the tonal step *is* the lightness percentage.
We then quantize to the values in §1.1/1.2 to produce stable, repeatable hex values.

The mirroring rule: every role's contrast ratio against the surface it sits on must be ≥ 4.5:1
in **both** schemes. We re-verified this when calibrating the values.

---

## 6. M2 Dark-Theme Rules We Still Honor

Material 2's dark-theme spec is older but contains rules M3 didn't replace:

### 6.1 Avoid pure black (sometimes)

M2 recommends `#121212` over `#000` because OLED displays smear at maximum-black transitions
(adjacent pixels can be slow to refresh). We:

- Use `#000` for the **page background** — it's static, no smear risk.
- Use `#0A0A0A` and up for **content surfaces** — where text and motion live.

This gives us the OLED energy savings (true black background) and the readability (slight gray
on cards).

### 6.2 Text emphasis levels

| Level | Opacity | Bound to |
|---|---|---|
| High | 87% | Primary text (used in CRITICAL/HIGH alerts) |
| Medium | 60% | Secondary text, labels |
| Disabled | 38% | Disabled, low-priority alert (LOW level) |

We extend this with our own threshold:
| Custom | Opacity | Bound to |
|---|---|---|
| Critical-emphasis | 100% | CRITICAL alert text |
| Tertiary | 30% | Sparkline guides, axis ticks |

### 6.3 Desaturation in dark mode

M2: bright accent colors should be desaturated 30–50% in dark mode to prevent retinal burn.
**N/A in Ark** — we have no chromatic accents. The only "accent" is white, which we do not
desaturate (a desaturated white is gray, which we use for `tertiary`).

### 6.4 Surface elevation overlays

M2 used a Primary-tinted overlay at increasing opacity per elevation level (1dp = 5%, 2dp = 7%,
3dp = 8%, etc.). M3 replaces this with tonal elevation. **Ark uses tonal elevation only**
(see §3).

---

## 7. Cheat Sheet — When You Don't Know Which Token

| You want… | Use |
|---|---|
| The page bg | `var(--background)` |
| A card | `bg-card` (= surface) |
| The card's main text | `text-card-foreground` (= on-surface, full opacity) |
| The card's secondary text | `text-muted-foreground` (= on-surface-variant, ~70%) |
| A divider inside a card | `border-input` (= outline-variant) |
| The card's border | `border-border` (= outline) |
| A primary CTA button | `bg-foreground text-background` |
| A secondary button | `bg-muted text-foreground` |
| A ghost button | `hover:bg-muted` |
| The dialog surface | `bg-popover` (= surface-container-high, elev 3) |
| A toast | `bg-popover` with elevation 4 surface |
| The single permitted gray | `text-accent` (= tertiary, `#888`) |
| A focus ring | `ring-ring` (= 60% foreground) |
| The dialog backdrop | `bg-black/60 backdrop-blur-sm` (= scrim) |

If the token you want doesn't exist, you're probably trying to break the system. Open the
issue.

---

## 8. References

- M3 color overview — `https://m3.material.io/styles/color/system/overview`
- M3 choosing a scheme — `https://m3.material.io/styles/color/choosing-a-scheme`
- M3 roles — `https://m3.material.io/styles/color/roles`
- M2 dark theme — `https://m2.material.io/design/color/dark-theme.html`
- shadcn theming — `https://ui.shadcn.com/docs/theming`
- Tailwind v4 `@theme` — `https://tailwindcss.com/docs/theme`
