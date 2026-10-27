# Design

How the TenderFlow interface is built. It started from the team's Figma Make export ("Tender-to-Quotation
Compiler"), was rebuilt as React components wired to real data, and was adjusted for readability, accessibility
and honesty (see ADR-012, ADR-014 and ADR-024 in [DECISIONS.md](DECISIONS.md)).

Screenshots of every screen, captured by the end-to-end script: [`docs/screenshots/`](screenshots/).

## 1. Principles

1. **Show where every value came from.** Each value in the editor carries an origin marker (extracted, typed by you,
   price list, company profile or settings, calculated, AI suggestion, missing), and extracted values link to their
   source text.
2. **Never look more finished than it is.** Missing values are highlighted, not hidden. Totals stay empty until
   every line is priced. Drafts are labelled. *Ready* appears only when validation says so.
3. **The user decides.** Conflicts, mappings, material changes and warnings need an explicit click; nothing is
   auto-confirmed.
4. **Nothing fake.** No placeholder statistics, simulated progress or decorative buttons. Unavailable features are
   disabled with a reason (PDF without LibreOffice, AI without a configured provider).

## 2. Visual language (`frontend/src/styles/tokens.css`)

| Token | Value | Use |
|---|---|---|
| `--color-background` | `#F7F6F8` | page background |
| `--color-surface` | `#FFFFFF` | cards, panels, the quotation sheet |
| `--color-silver` / `--color-border` | `#E4E1E8` / `#E9E5EC` | dividers, outlines |
| `--color-lavender` / `-soft` / `-ink` | `#DDD3F1` / `#F0EAF9` / `#6E5A86` | selection, active navigation, AI-related accents |
| `--color-apricot` / `-hover` / `-ink` | `#F5C6A5` / `#EFB990` / `#573B2D` | primary action |
| `--color-text` | `#34313A` | body text (12.8:1 on white) |
| `--color-text-secondary` | `#6B6672` | secondary text (5.6:1 on white, ≥ 4.7:1 on tinted surfaces) |
| `--color-accent-dark` | `#55465F` | headings accents, focus, brand |
| success / warning / error `-soft` + `-ink` | greens, ambers, reds | status badges and notices |

- **Type:** DM Sans (UI and document) and Manrope (headings), bundled through Fontsource. Scale:
  11.5 / 12.5 / 14 / 16 / 19 / 26 px (`--text-xs` … `--text-2xl`), body 14 px.
- **Spacing:** 8-point scale (`--space-1` 4 px … `--space-7` 48 px). **Radii:** 6 / 8 / 12 px. **Shadows:** two levels.
- **Icons:** lucide-react, 14–18 px, always paired with a text label or an `aria-label`.
- **Theme:** light only.

## 3. Layout

- **App shell:** a 240 px sidebar (brand, navigation with the `N` shortcut hint, a local/external processing card,
  version and licence) and a 64 px top bar (breadcrumb, backend status pill, help `?`).
- **Project flow:** a project bar (name, sample badge, save state) and a five-step stepper: *Upload documents →
  Review extracted data → Map fields → Edit quotation → Validate & export*. Steps unlock as their inputs exist;
  completed steps stay reachable.
- **Review step:** a section outline on the left; in the middle, field cards grouped by section, line items,
  instruction-like text and requirements; on the right a sticky **evidence panel** with the verbatim source text and
  the matching block highlighted.
- **Editor:** three panels — *Document outline* with per-section issue counts and validation progress, the
  **quotation canvas** (editable draft, or *In your template*), and the **instruction panel** (instructions, previews,
  history).
- **Validate & export:** findings grouped by severity with quick fixes and acknowledgements; export card with format
  choice, draft/final state, post-export checks and previews.

## 4. Screens

| Screen | Route | What it shows (all real data) |
|---|---|---|
| Overview | `#/` | Start a quotation (tender + template upload), try the sample project, how it works, recent work |
| My work | `#/projects` | All projects with stage, status, error/warning counts, exports |
| New quotation | `#/new` | Upload slots for tender, template and optional price list |
| Project flow | `#/p/<id>/<step>` | The five steps above |
| Templates | `#/templates` | Uploaded templates with detected fields; reuse in a new project |
| Document library | `#/documents` | Every uploaded document with project, type, size, date, parse status; download the original |
| Activity history | `#/activity` | Events across projects (uploads, confirmations, edits, exports) |
| Settings | `#/settings` | Company profile · Quotation defaults · Tax · AI processing · Data & deletion · About & licences |

## 5. Components and states

- **Buttons** (primary apricot, secondary outline, quiet), **badges** (neutral, lavender, success, warning, danger),
  **notices** (info, success, warning, error) and **toasts** (at most three at a time; errors use the backend's message).
- **UploadSlot:** drag-and-drop or browse, accepted formats listed, progress from the real upload, inline errors
  with the backend's explanation, replace and remove.
- **DocField:** click-to-edit value in the quotation canvas. The button's accessible name includes the label and the
  current value. Enter saves (Ctrl/⌘ + Enter in multi-line fields); Escape cancels.
- **Origin markers:** dots in the canvas and chips in lists. AI suggestions use a dashed lavender outline; missing
  values get a red dot and a visible *Add …* button, mirroring the `[MISSING: …]` marker written into draft exports.
- **Proposal card:** interpreted instruction, before → after table, material-change checkbox gating *Apply*, warnings
  (including dropped AI operations), engine badge (*Rule-based* / *AI suggestion*).
- **States:** every data view has loading, empty (with the next action) and error states. When the backend is down,
  the status pill turns to *Backend offline* and requests fail with an explanation instead of hanging.

## 6. Responsive behaviour

| Width | Change |
|---|---|
| ≤ 1500 px | Editor and review panels narrow |
| ≤ 1200 px | Evidence and instruction panels become drawers opened from the toolbar |
| ≤ 1050 px | Sidebar collapses to icons |
| ≤ 760 px | Single-column layouts; the editor is usable but not comfortable — TenderFlow is designed for laptop and desktop |

## 7. Accessibility

- Skip link, landmarks (`aside` navigation, `main`, labelled sections), one `h1` per screen (visually hidden in
  the editor, whose visible header is a toolbar).
- Visible focus ring (`--focus-ring`). The dialog moves focus inside, closes on Escape and returns focus to the opener.
- All inputs have labels. Icon-only buttons have `aria-label`s. Stepper and segmented controls expose
  `aria-current` / `aria-pressed`.
- `aria-live` regions announce proposals, the evidence panel's content, zoom level and toasts.
- Keyboard: `N` starts a new quotation, `?` opens help (ignored while typing), Ctrl/⌘ + Enter previews an instruction.
- `prefers-reduced-motion` disables animations.
- Contrast: body and secondary text meet WCAG AA on all surfaces (see the token table).
- **Not yet done:** a full screen-reader audit and automated axe checks.

## 8. Changes from the Figma export

| Figma export | TenderFlow 0.1.0 | Why |
|---|---|---|
| Name "Tender-to-Quotation Compiler" | Name and taglines from `branding.json` | One place to rename |
| Fictional user, workspace switcher, profile menu, notification bell, global search | Removed | No accounts or notifications in scope; search had nothing to search across |
| Hard-coded projects, statistics, activity and a simulated pipeline | Real data from the backend, honest empty states | No fabricated data |
| 5–9 px text in many places; `#77727E` secondary text | Readable scale, `#6B6672` | Legibility, WCAG AA |
| Google Fonts link | Bundled fonts | No third-party requests |
| Inline SVG icon set | lucide-react | Consistency and accessibility |
| Single static editor layout | Three panels + drawers at smaller widths | Real content is longer than the mock-up |

## 9. Design debt

- About 60 colour values in `app.css` are still literal hex tints (borders of badges, the printed-quotation
  greys, origin dots) rather than tokens. They should move into `tokens.css` before a theme change.
- Light theme only; no dark mode.
- English only; no internationalisation. Dates in the UI follow the browser's locale; dates written into quotations
  use the "27 October 2026" style.
- The *In your template* preview is approximate (browser rendering of DOCX); Word/Excel remain the reference.
