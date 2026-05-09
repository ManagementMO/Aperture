# Component Recipes — shadcn Primitives, Themed for Ark

> Per-component anatomy, spec, classes, and do/don't.
> Read alongside [ARK_DESIGN_BIBLE.md](./ARK_DESIGN_BIBLE.md) and [shadcn-stack.md](./shadcn-stack.md).
>
> Each recipe assumes you've already run `pnpm dlx shadcn@latest add <name>` and applied
> the monochrome override (Bible §9.4).

---

## Format

Every recipe has:
1. **Use** — when to reach for it.
2. **Anatomy** — ASCII diagram or class breakdown.
3. **Spec** — sizes, tokens, interactions.
4. **Variants** — only the ones we ship.
5. **Do / Don't**.

---

# 1. Button

**Use:** any clickable that performs an action. Not for navigation (use `<Link>`).

**Anatomy:**
```
[ ⎯  Action label  ⎯ ]
  └ icon (opt 20px)  └ end icon (opt 16px chevron, etc.)
```

**Spec:**
- Heights: `sm 32 / default 40 / lg 48 / icon 40×40`.
- Padding x: `sm 16 / default 24 / lg 32`.
- Border radius: `radius-md` (8 px).
- Font: `label-large`, weight 500.
- Focus: 2 px ring, 2 px offset, `--ring`.

**Variants:**
| Variant | bg | text | border | When |
|---|---|---|---|---|
| `default` | `foreground` | `background` | none | Primary action — **one per view**. |
| `secondary` | `muted` | `foreground` | none | Secondary actions. |
| `outline` | `transparent` | `foreground` | `1 px input` | Tertiary actions. |
| `ghost` | `transparent` | `foreground` | none | Tertiary in dense rows; hover fills `muted`. |
| `link` | `transparent` | `foreground` | none | Inline text actions. Underline on hover. |
| `destructive` | `foreground` | `background` | `1 px foreground/20` | Same as default + heavier border. **Always** wrapped in `<AlertDialog>`. |

**Do:**
- Use `icon` size for toolbar buttons.
- Pair `destructive` with confirmation.

**Don't:**
- Don't introduce new colors.
- Don't use `link` for navigation; use `<Link>` styled as needed.
- Don't put two `default` variants on one screen.

---

# 2. Card

**Use:** the default container. Group related information.

**Anatomy:**
```
┌──────────────────────────┐  ← border (outline)
│ Header                   │  ← CardHeader, p-4 pb-2
├──────────────────────────┤  ← optional separator
│ Content                  │  ← CardContent, p-4 pt-0
│                          │
└──────────────────────────┘
```

**Spec:**
- Background: `card` (= surface, elev 1).
- Border: `1 px outline`.
- Radius: `radius-lg` (12 px).
- Padding: `space-4` (16 px).
- **No shadow.**

**Variants:**
- **Default** — sits on `background`.
- **Inset** — sits on `surface-container`; uses `bg-card/50` to read as inset (rare).
- **Alerting** — same surface + border opacity `15%` (CRITICAL) or `10%` (HIGH); pulse on
  CRITICAL (Bible §6.3).

**Do:**
- One card = one subject (one camera, one person, one incident).
- Use `CardHeader` + `CardContent` semantics.

**Don't:**
- Don't nest cards more than one level. Use `Separator` for sub-sections.
- Don't add shadows. Use surface elevation (move to `bg-popover` for elev 2).

---

# 3. Dialog

**Use:** modal interactions: confirmations, focused tasks, settings.

**Spec:**
- Surface: `bg-popover` (elev 3, `#161616` dark).
- Border: `1 px outline`.
- Radius: `radius-lg`.
- Max width: `560 px`.
- Padding: `space-6` (24 px).
- Backdrop: `bg-black/60 backdrop-blur-sm`.
- Open: 250 ms `cubic-bezier(0.2,0,0,1)`. Close: 200 ms.

**Variants:**
- **Standard** — center modal.
- **Full-screen** — for camera-focus mode; no backdrop, takes whole viewport.

**Do:**
- Trap focus, restore on close.
- Esc to close (Radix gives this).
- Title via `DialogTitle` (sr-friendly).

**Don't:**
- Don't stack dialogs. If you need a sub-flow, use a wizard inside the dialog.
- Don't use Dialog for destructive confirms — use `AlertDialog`.

---

# 4. AlertDialog

**Use:** destructive or irreversible confirmations.

**Spec:** same as Dialog, plus:
- Title: `headline-small`.
- Description: `body-medium`, `muted-foreground`.
- Action: `<Button variant="destructive">`.
- Cancel: `<Button variant="outline">`.

**Do:**
- Always include a description.
- Title states the action ("Delete camera"), not the question ("Are you sure?").

**Don't:**
- Don't use for non-destructive choices.

---

# 5. Input

**Use:** any text input.

**Anatomy:**
```
┌────────────────────────────────┐  ← border outline-variant, focus → outline
│  placeholder text              │  ← muted-foreground when empty
└────────────────────────────────┘
```

**Spec:**
- Height: `48 px`.
- Padding x: `16 px`.
- Background: `surface-variant` (= muted).
- Border: `1 px input` (= outline-variant), focus → `1 px outline`.
- Radius: `radius-md`.
- Font: `body-medium`.
- Placeholder: `muted-foreground` at 50%.
- Disabled: opacity 38%.
- Error: border becomes `foreground/30` + uppercase `error` label below.

**Do:**
- Always pair with `<Label>`.
- Use `aria-describedby` for error / hint text.
- Numeric inputs: add `font-mono tabular-nums`.

**Don't:**
- Don't put icons inside the field unless absolutely necessary; prefer adjacent buttons.

---

# 6. Label

**Spec:**
- Font: `label-medium` (12 px, 500 weight).
- Color: `foreground` (full).
- Margin-bottom: `space-2` (8 px).
- Uppercase optional for terminal-feel sections.

---

# 7. Badge

**Use:** opacity-coded threat level, status, count.

**Spec:**
- Padding: `4 8`.
- Radius: `radius-full`.
- Font: `label-small` (11 px), uppercase, tracking 0.5.
- Border: `1 px outline` at variant opacity (see Bible §3.3).
- Background: transparent (or `rgba(255,255,255,0.02)` at CRITICAL).

**Variants (replace shadcn defaults):**
| Variant | Border opacity | Text opacity | Use |
|---|---|---|---|
| `critical` | 15% | 100% | CRITICAL alerts |
| `high` | 10% | 87% | HIGH alerts |
| `medium` | 8% | 60% | MEDIUM alerts |
| `low` | 6% | 38% | LOW alerts |
| `info` | 8% | 60% | non-threat status |
| `count` | 0% | 60% | numeric chip; bg `muted` |

---

# 8. Alert

**Use:** inline messaging within a page (not toasts).

**Spec:**
- Background: `card`.
- Border: `1 px outline-variant`.
- Border-left: `2 px foreground` (CRITICAL) or `2 px foreground/60` (default).
- Padding: `space-3 space-4`.
- Icon: 20 px, `2 px` stroke for CRITICAL.

---

# 9. Separator

**Spec:**
- Color: `outline-variant`.
- Thickness: 1 px.
- Margin: none (caller decides).

---

# 10. Tabs

**Use:** switching between alternative views of the same data.

**Spec — line variant (default):**
- TabsList: row, no background, `border-b outline-variant`.
- TabsTrigger inactive: `text-muted-foreground`, `body-medium`, padding `12 16`.
- TabsTrigger active: `text-foreground`, bottom 2 px `border-b foreground`.
- Hover: state-layer `hover`.

**Spec — pill variant:**
- TabsList: `bg-muted`, `radius-full`, padding `4`.
- TabsTrigger: `radius-full`, padding `8 16`.
- Active: `bg-card text-foreground`. Inactive: `text-muted-foreground`.

---

# 11. Sidebar (shadcn block)

**Use:** persistent app navigation. We have one.

**Spec:**
- Width: 280 px.
- Background: `bg-popover` (elev 2).
- Border-right: `1 px outline`.
- Sections: `top` (logo + workspace), `middle` (nav), `bottom` (user).
- Nav item: 44 px tall, `space-3` padding, 24 px icon.
- Active: `bg-accent/10` (= `surface-container-highest`) + `2 px left border foreground`.

---

# 12. Tooltip

**Use:** revealing the *name* of an icon-only control or a *value* in a chart.

**Spec:**
- Background: `bg-popover` (elev 3).
- Border: 1 px `outline`.
- Padding: `space-2`.
- Font: `label-small` for labels, `body-small + mono` for data.
- No arrow.
- Delay: 200 ms.

**Do:**
- Required on every icon-only button.

**Don't:**
- Don't write paragraphs in a tooltip. If you need >12 words, use `HoverCard`.

---

# 13. Popover

**Spec:**
- Background: `bg-popover` (elev 2).
- Border: `1 px outline`.
- Radius: `radius-md`.
- Padding: `space-4`.

---

# 14. DropdownMenu / ContextMenu / Menubar

**Spec:**
- Surface: `bg-popover` (elev 2).
- Item: 36 px tall, `space-2` padding, hover state-layer.
- Separator: `outline-variant`, 1 px.
- Shortcut: right-aligned `kbd` 11 px, `muted-foreground`.
- Submenu: chevron right (16 px), opens to the right.

---

# 15. Sheet

**Use:** side panels that slide in (filters, person detail on mobile).

**Spec:**
- Width: 360 (right side), 280 (left side).
- Background: `bg-popover` (elev 3).
- Border: 1 px `outline` on the inner edge.
- Backdrop: same as Dialog.

---

# 16. Drawer

**Use:** mobile bottom sheet (alert detail, settings on small viewports).

**Spec:**
- Background: `bg-popover` (elev 3).
- Top radius: `radius-xl` (16 px), bottom 0.
- Drag handle: 32 × 4 px, `outline`, top center.

---

# 17. Skeleton

**Use:** placeholder while content loads.

**Spec:**
- Background: `rgba(255,255,255,0.04)`.
- Animation: shimmer (Bible §6.3) — disabled under reduced motion.
- Radius: matches the element it replaces.

---

# 18. Sonner (Toast)

**Use:** transient notifications.

**Spec:**
- Position: top-right, 16 px from edges.
- Background: `bg-popover` (elev 4 — `#1A1A1A`).
- Border: 1 px `outline`.
- Radius: `radius-lg`.
- Padding: `space-4`.
- Width: 360.
- Auto-dismiss: 5 s (10 s for critical).

**Variants (mono):**
- `info` — default.
- `critical` — left border `2 px foreground`, bold title.
- No success/error colors. Status conveyed by uppercase label.

---

# 19. Switch

**Spec:**
- Track: 36 × 20 px, `bg-muted` off, `bg-foreground` on.
- Thumb: 16 × 16, `radius-full`, `bg-background`.
- Transition: 150 ms.

---

# 20. Slider

**Spec:**
- Track: 4 px tall, `bg-muted`.
- Range: `bg-foreground`.
- Thumb: 16 px circle, `bg-background` with `2 px foreground` border.
- Focus: ring on thumb.

---

# 21. Progress

**Spec:**
- Height: 4 px (default), 8 px (threat gauge).
- Track: `bg-muted`.
- Indicator: `bg-foreground`.
- Transition: 500 ms ease-out.

---

# 22. Checkbox / RadioGroup

**Checkbox spec:**
- 16 × 16, `radius-sm`.
- Off: `bg-transparent`, `1 px input` border.
- On: `bg-foreground`, white check (`text-background`).

**Radio spec:**
- 16 × 16, `radius-full`.
- Off: `1 px input` border.
- On: 6 px inner dot `bg-foreground`.

---

# 23. Select

**Spec:**
- Trigger: matches Input height + a chevron-down icon (16 px) right.
- Content: `bg-popover` (elev 3), max-height 320 with scroll.
- Item: 36 px tall, hover state-layer, check icon left when selected.

**Do:**
- Use shadcn `Select` (Radix-backed) for searchable, dynamic data.
- Use native `<select>` only when accessibility / form-fill demands it.

---

# 24. Combobox

**Use:** search + select. Commonly: camera search, person search.

**Built from:** `Popover` + `Command`.

**Spec:**
- Trigger: same as Select.
- Content: 320 wide, `bg-popover`.
- Search input at top, results scroll.

---

# 25. Command (⌘K palette)

**Use:** the global command palette, plus inside Combobox.

**Spec:**
- Background: `bg-popover` (elev 3).
- Width: 600 (palette), parent (combobox).
- Search: 56 px tall, no border, `body-large`, search icon left.
- Group label: `label-small`, `muted-foreground`, padding `8 16`.
- Item: 36 px, hover state-layer, `kbd` shortcut right.

---

# 26. Table / DataTable

**Use:** structured records (incident archive, person list, audit log).

**Spec:**
- Header row: `bg-muted`, `label-small`, uppercase, tabular-nums.
- Header cell padding: `12 16`.
- Body cell padding: `12 16`.
- Row border-bottom: `outline-variant`.
- Row hover: state-layer.
- Selected row: `bg-muted` + `1 px left border foreground`.
- Numeric columns: mono + tabular-nums + right-aligned.
- Sticky header: `position: sticky; top: 0; z-sticky`.

---

# 27. Pagination

**Spec:**
- Container: row, `space-2` gap.
- Page button: 36 × 36, `radius-md`, hover state-layer.
- Active: `bg-muted text-foreground`.
- Prev/Next: same size, chevron icon.

---

# 28. Breadcrumb

**Spec:**
- Font: `body-small`.
- Item color: `muted-foreground` until last (which is `foreground`).
- Separator: `›` glyph or `chevron-right` 12 px.

---

# 29. Avatar

**Spec:**
- Sizes: `24 / 32 / 40` px.
- `radius-full`.
- Fallback: `bg-muted`, initials `label-medium`, `foreground` text.
- Image: object-cover, no border.

---

# 30. HoverCard

**Use:** rich hover info (e.g. person preview from a username).

**Spec:**
- Background: `bg-popover` (elev 2).
- Border: 1 px `outline`.
- Width: 320.
- Padding: `space-4`.
- Open delay: 500 ms.

---

# 31. Accordion / Collapsible

**Spec:**
- Trigger row: 48 px tall, `body-medium`, chevron-right rotates 90° on open.
- Content: padding `space-4`, top border `outline-variant`.
- Border-bottom on item: `outline-variant`.

---

# 32. ScrollArea

**Use:** any scrolling region we want to style consistently across platforms.

**Spec:**
- Track: invisible.
- Thumb: 4 px wide, `rgba(255,255,255,0.2)`, `radius-full`.
- Hover thumb: `rgba(255,255,255,0.4)`.

---

# 33. AspectRatio

**Use:** lock video and chart containers. Camera card uses `16/9`.

---

# 34. Resizable

**Use:** desktop multi-pane. Camera grid + alert feed split.

**Spec:**
- Handle: 4 px wide, `outline-variant`.
- Hover: `outline`.
- Active drag: `foreground`.

---

# 35. ToggleGroup / Toggle

**Use:** view-mode switchers (e.g. grid / list).

**Spec:**
- Same dimensions as `Button.icon`.
- Off: `text-muted-foreground`, transparent.
- On: `bg-muted text-foreground`.

---

# 36. Calendar / DatePicker

**Use:** incident replay range.

**Spec:**
- Container: `bg-popover` (elev 3), `radius-lg`, padding `space-4`.
- Day cell: 32 × 32, `radius-md`.
- Today: `1 px outline foreground`.
- Selected: `bg-foreground text-background`.
- Range: `bg-muted` middle days, foreground endpoints.
- Disabled: opacity 38%.

---

# 37. InputOTP

**Use:** 2FA verification only.

**Spec:**
- Slot: 48 × 48, `radius-md`, `1 px input` border.
- Active slot: `1 px outline foreground`.
- Font: mono, 24 px, tabular-nums.

---

# 38. NavigationMenu

**Marketing site only.** Operator UIs use `Sidebar`.

---

# 39. Menubar

**Desktop app top bar only.** macOS native bar replaces this on Mac.

---

# 40. Carousel

**Marketing site only.** Forbidden in operator UIs.

---

# 41. Form

**Use:** any multi-field input flow. Built on `react-hook-form` + `zod`.

**Spec:**
- Field group: stacked `Label` + `Input` + `error` text.
- Spacing between fields: `space-6` (24 px).
- Submit button: full width on mobile, auto width on desktop.
- Error text: `body-small`, `foreground`, uppercase prefix `ERROR — `.

---

# 42. Chart (recharts wrapper)

See [ARK_DESIGN_BIBLE.md §11](./ARK_DESIGN_BIBLE.md#11-data-visualization).

---

# 43. Empty State

**Use:** no-data placeholders.

**Anatomy:**
```
       ◯◯◯
      ◯ ◯ ◯       ← 32 px line icon, opacity 38%
       ◯◯◯
   "No incidents in range"   ← body-medium, muted-foreground
   [ Adjust filters ]        ← Button outline, sm
```

**Do:**
- Always include an action.

**Don't:**
- Don't use illustrations. Icons only.

---

# 44. Kbd

**Use:** representing keyboard shortcuts in menus, tooltips, command palette.

**Spec:**
- Background: `bg-muted`.
- Border: `1 px outline-variant`.
- Radius: `radius-sm`.
- Padding: `2 6`.
- Font: mono, 11 px.
- Text: `muted-foreground`.

---

# Recipes for Composite Patterns

The Ark-specific composites (ThreatGauge, CameraCard, AlertFeed, PersonPanel, CommandPalette,
TrajectoryChart) are speced in [ARK_DESIGN_BIBLE.md §10](./ARK_DESIGN_BIBLE.md#10-composite-patterns)
and live in `components/ark/` in each surface.

When you ship a new composite, add a short recipe here and link to its source file.

---

*Maintained by Ark Engineering · One PR per recipe revision · Diff against the Bible before
adding a new variant.*
