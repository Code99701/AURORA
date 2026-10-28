# AURORA — UI/UX Audit & Redesign Spec (for Antigravity)

Date: 2026-10-28 · Source: screenshots of Research Desk / Documents + CSS read from `frontend/`.
Evidence labels: [CSS] read in code · [SHOT] seen in screenshot.
Goal: a clean, credible, human-made product in a **white + blue + black** scheme with **exactly one scrollbar per area**.

---

## 0. Rules for the implementer
1. Change presentation and layout only. Do not touch API wiring, hooks' data logic or backend.
2. Use CSS Modules + the shared tokens in `app/globals.css`. No new inline `style={{}}`.
3. After each section: `npx tsc --noEmit`, `npx eslint .`, `npx next build`; then show a screenshot of each changed page (light + dark, 1440 px and 390 px wide).
4. No emojis, no gradients, no glow/glass effects, no invented numbers or placeholder text.

---

## 1. THE DOUBLE-SCROLL BUG (fix first)

**Symptom [SHOT]:** the page has a scrollbar AND the chat has its own scrollbar (plus a third on the sidebar and a horizontal one in the conversation list).

**Root cause [CSS]:**
- `app-shell.module.css`: `.shell { min-height: 100vh }` → the document itself scrolls.
- `research-desk.module.css`: `.desk { height: calc(100vh - 128px); min-height: 640px }` guesses the height of everything above it. The real header, tabs and padding exceed 128 px, so the page overflows → page scroll; and `.messageViewport { overflow-y: auto }` → chat scroll. Two nested scroll containers.
- `workspace-view.module.css`: `min-height: calc(100vh - 64px)` repeats the same guess.
- `.sidebar { height: 100vh; overflow-y: auto }` shows its own scrollbar when content is tall.

**Required layout model (app-wide):**
```
html, body { height: 100%; overflow: hidden }          /* the document never scrolls */
.shell     { height: 100dvh; display: grid; grid-template-columns: 248px minmax(0,1fr) }
.sidebar   { height: 100dvh; display: flex; flex-direction: column; overflow: hidden }
.sidebar .conversationsList { flex: 1; min-height: 0; overflow-y: auto }   /* only this part of the sidebar scrolls */
.content   { min-width: 0; min-height: 0; display: flex; flex-direction: column }
main       { flex: 1; min-height: 0; overflow-y: auto }   /* default: ONE scroll area for normal pages (dashboard, settings, documents) */
```
**Research Desk page (special: no main scroll):**
```
.workspacePage { height: 100%; display: flex; flex-direction: column; min-height: 0 }
.workspaceHeader { flex: none }                    /* slim, ~56px */
.desk { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0,1fr) [340px viewer when open] }
.chatColumn { display: flex; flex-direction: column; min-height: 0 }
.messageViewport { flex: 1; min-height: 0; overflow-y: auto }   /* THE ONLY scrollbar on this page */
.composer { flex: none }                           /* always visible at the bottom, never inside the scroll area */
.sourceViewer { min-height: 0; overflow-y: auto }  /* its own scroll only when open */
```
Delete every `calc(100vh - Npx)` and `min-height: 640px` hack. Use `100dvh`, not `100vh` (mobile browsers).

**Scroll behaviour:** auto-scroll to the newest message only if the user is already near the bottom; otherwise show a small "↓ Latest" button (the current one overlaps the sources card, see 5.9). Style scrollbars thin (`scrollbar-width: thin`, subtle thumb).

**Acceptance:** at 1440×900 and 1280×720, `document.documentElement.scrollHeight === window.innerHeight` on the Research Desk; exactly one vertical scrollbar visible in the chat area; no horizontal scrollbar anywhere in the sidebar.

---

## 2. COLOUR SYSTEM: white, blue, black

**Problem [CSS]:** `globals.css` defines a purple brand (`--accent #6C5CE7`) plus playful coral, teal, amber, pink. Everything uses them, which reads as generic AI-template styling.

**Replace tokens (light):**
| Token | Value | Use |
|---|---|---|
| `--background` | `#F7F8FA` | app canvas |
| `--surface` | `#FFFFFF` | cards, sidebar, composer |
| `--surface-raised` | `#F1F3F6` | hover, code blocks, inputs |
| `--foreground` | `#0B1220` | primary text (near-black) |
| `--foreground-soft` | `#3B4558` | secondary text |
| `--muted` | `#5B6578` | captions (must be ≥ 4.5:1 on white) |
| `--border` | `#E3E6EB` | 1px lines |
| `--border-strong` | `#CBD1DA` | inputs, focused containers |
| `--accent` | `#1D4ED8` | primary buttons, links, active nav, focus ring |
| `--accent-strong` | `#1E40AF` | hover/pressed |
| `--accent-soft` | `#EAF0FF` | active nav background, selected chip |
| `--success` | `#15803D` | status "Ready" |
| `--warning` | `#B45309` | "Evidence is limited" |
| `--danger` | `#B91C1C` | errors, delete |

**Dark mode:** `--background #0A0E16`, `--surface #111827`, `--surface-raised #1A2233`, `--foreground #F1F5F9`, `--foreground-soft #B6C0D0`, `--muted #8B97AB`, `--border #232C3D`, `--accent #5B8CFF`, `--accent-soft #16233F`. Text on accent buttons: white (light) / `#0A0E16` (dark).

**Rules:** remove coral/teal/amber/pink/violet/glow tokens and every usage (grep them). Blue appears only on: primary button, active nav, links, focus ring, selected state, citation chips. Everything else is white/grey/black. Semantic colours (green/amber/red) only for status and alerts.

---

## 3. TYPOGRAPHY & SPACING

**Problems [SHOT]:** body text in chat is ~19–20 px with huge line height; section headings inside answers ("5. Conclusion") are as large as page titles; mixed families (serif headings on some screens, sans elsewhere); uppercase letter-spaced labels everywhere ("CURRENT WORKSPACE", "CONVERSATIONS", "SYSTEM").

**Spec:**
- Fonts: **Inter** for all UI. Optional serif (Source Serif 4) only for the assistant's answer body. Mono (JetBrains Mono) for code, ids, page numbers. Load via `next/font` (this also removes the `no-page-custom-font` lint warning).
- Scale: 12 caption · 13 UI-small · 14 UI/body · 15 chat answer · 18 section title · 22 page title · 28 hero only on the landing page. Line-height 1.55–1.65 for reading text, 1.3 for UI.
- Answer column `max-width: 72ch`. User message bubble: 14–15 px, max 75% width, radius 12, solid `--accent-soft` with dark text (not a giant filled blue pill).
- Markdown inside answers: h1/h2/h3 → 17/16/15 px, bold, 16px top margin; lists 20px indent; tables with 1px borders and 13px text; code blocks `--surface-raised`, 13px mono.
- Keep uppercase micro-labels to a maximum of one style (11px, `letter-spacing .04em`, `--muted`) and only for section labels in the sidebar.
- Spacing: use the 4/8 scale already in tokens (`--space-*`). Page padding 24 px (desktop) / 16 px (mobile). Radius: **8 px (controls) and 12 px (cards/modals) only**.

---

## 4. APP SHELL & SIDEBAR

| # | Problem | Fix |
|---|---|---|
| 4.1 | Sidebar mixes global links (Workspaces, Dashboard, Settings) with workspace links (Research Desk, Documents) | Group: **top** = brand + search; **Navigate** = Workspaces, Dashboard, Settings; **Workspace** switcher block with Research Desk + Documents beneath it; **Conversations** list fills remaining space; footer = user. |
| 4.2 | Conversation title is clipped at the **left** edge ("t is present in the document attac") and a horizontal scrollbar appears [SHOT] | Title `min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; text-align:left`; list `overflow-x:hidden`. Row = title + muted date, hover reveals rename/delete icons. |
| 4.3 | "New research" appears as a filled lilac block that looks like a button but is a conversation row | Add a proper **"New chat"** button (secondary style, + icon) above the list; the list shows only real conversations; active row = `--accent-soft` with a 2 px left accent bar. |
| 4.4 | Avatar shows an unrelated "N" badge overlapping the user block [SHOT: Next.js dev indicator] | Hide the dev indicator in dev (`devIndicators: false` in `next.config.ts`) or confirm it vanishes in production build; make sure the avatar is initials only. |
| 4.5 | Two icons (theme, logout) with no labels | Add `title`/`aria-label`; keep icon-only but 32×32 hit area, consistent 16 px icons. |
| 4.6 | Sidebar search "⌘K" box does not clearly open anything | Wire it to the command palette (real workspaces/conversations) or remove it until it works. |
| 4.7 | Sidebar has its own scrollbar | Per section 1: sidebar itself never scrolls; only `.conversationsList`. |
| 4.8 | Mobile: sidebar must become a drawer | ≤ 900 px: hidden; top bar with hamburger; overlay with focus trap and Esc to close. |

Colours: sidebar `--surface`, border-right 1px, active nav item `--accent-soft` + `--accent` text, hover `--surface-raised`.

---

## 5. RESEARCH DESK (chat page)

**Page header (slim, one row, 56 px):** breadcrumb `Workspace name / Research Desk` (workspace name in normal case, not forced uppercase); Chat | Documents segmented tabs; scope selector; export button. Remove any second title block.

**5.1 Message list**
- Centered column, `max-width: 760px`, 24 px between turns, reading font per section 3.
- User turn: right-aligned compact bubble. Assistant turn: no bubble; small blue logo mark + "AURORA" label (14px, 600) + optional muted "Grounded in N sources".
- Timestamp on hover only.

**5.2 Citations / sources [SHOT: 10 identical chips "Kali_Linux_WSL_Setup_Guide…. p. 1, p. 2…"]**
- Group by document: one row per document, `Kali_Linux_WSL_Setup_Guide.pdf` + a wrap of page chips `p.1 p.2 p.4 p.6 …` (or "Slide 3" for PPTX).
- Show the first 3 sources, then "Show all 10 sources" toggle.
- Inline `[n]` markers in the answer text should be small blue superscript buttons; hover shows a 2-line snippet, click opens the source viewer at that page.
- Chip style: 28 px high, 1px border, 12 px text, blue on hover/selected only.

**5.3 Answer actions:** Copy, Regenerate, Save, Export in a single muted row (icon + label, 13px, contrast ≥ 4.5:1 — currently too faint). Show on hover for older messages; always visible on the latest.

**5.4 Follow-up chips:** currently hard-coded ("Which skills appear most often?"…) and appear even under refusals [SHOT]. Remove the hard-coded list. Render only suggestions returned by the API; none → render nothing.

**5.5 Refusal / limited-evidence state:** the banner reads "Evidence is limitedThis answer…" (missing separator) and the refusal sentence is repeated below it [SHOT].
- Single card: amber border-left, title **"Not enough evidence"**, body one sentence on what was searched, and a helpful hint: "Try naming a document, page or slide, or ask for a summary." No source list on refusals.
- Meta questions ("how many documents are present?") must be answered from workspace data (backend task), not rendered as a refusal.

**5.6 Streaming states:** a thin "Retrieving → Writing" status line with a small spinner above the answer; blinking caret while streaming; **Stop** button replaces Send during generation.

**5.7 Composer (fixed at the bottom of the chat column, never inside the scroll area)**
- One rounded (12 px) container: auto-growing textarea (1–6 rows), left: attach button + "All documents ▾" scope pill + language pill; right: Send (solid blue, 36 px, arrow icon).
- Disabled Send = grey, not washed-out lilac. Hint "Enter to send · Shift+Enter for new line" in 12px muted, hidden on mobile.
- Drag-and-drop a file onto the chat → uploads to the workspace and shows an inline status chip.

**5.8 Source viewer panel (right, 340–420 px):** opens only on citation click; header = file name + "Page 4 of 14" + close; body shows the cited chunk with the matching text highlighted (soft yellow, not blue) and 1–2 lines of context; footer = Previous/Next source, "Open document". It scrolls independently only if its content is taller than the panel.

**5.9 Floating "Latest response" button:** place bottom-centre of the message area, 8 px above the composer, only when scrolled up; must never overlap sources or cards.

**5.10 Empty state (no messages):** centred title "Ask your documents", 3 example prompts derived from actual document names (or none), and a link "Upload a document" if the workspace has none.

---

## 6. DOCUMENTS PAGE [SHOT]

| # | Problem | Fix |
|---|---|---|
| 6.1 | Header repeats a second title block ("DOCUMENTS / 1 document · 1 ready") under the page header | One header: "Documents" + count, Upload (primary) and Refresh (icon) on the right. |
| 6.2 | Giant filters (search + two big selects) with 18px text | One compact toolbar row: search (36 px high), Status select, Sort select; 14px text. |
| 6.3 | Row is a big rounded card with oversized status pills ("PROCESSED" "INDEXED" in teal uppercase) | Replace with a **table**: Name (icon + filename + meta), Status (single chip: Ready / Indexing with progress / Failed with Retry / Partial), Pages, Added, Actions (Preview, Download, Delete in a `⋯` menu). Row height 56 px, 1px dividers, hover `--surface-raised`. |
| 6.4 | "Research ready" green text floats with no meaning | Merge into the single Status chip. |
| 6.5 | Upload | Drop zone (dashed 1px border, blue on drag-over) with real per-file progress; show duplicate-file (409) as a friendly inline message. |
| 6.6 | Empty state missing | "No documents yet" + Upload button. |
| 6.7 | Document preview | Opens in the same right-panel pattern as the source viewer (consistent). |

---

## 7. OTHER PAGES

- **Workspaces list:** simple table/grid of workspaces (name, #documents, #conversations, last activity from the API) with a "New workspace" primary button. No decorative icon squares or fake descriptions.
- **Dashboard:** replace marketing cards ("Active & Ready", "English & हिन्दी") with real numbers (workspaces, documents, conversations) and "Continue where you left off" (last conversation). If nothing useful, remove the page from the nav.
- **Settings:** profile (read-only for now), theme (Light / Dark / System segmented control), language, session/sign-out. Remove any claim not implemented.
- **Login / Register:** centred 400 px card on `--background`, logo above, labelled inputs (visible labels, not only placeholders), show/hide password, inline validation, clear error text, "Continue with Google" button only if OIDC is configured. Left "story" panel with gradients (`auth-screen.module.css`) → remove or reduce to a plain brand column.
- **Landing / About / Contact:** real screenshots of the product, concrete copy (what it does, supported formats, English + Hindi), no buzzwords or invented metrics, one CTA ("Get started"). Remove emojis from nav labels.
- **404 / error pages:** simple message + link home.

---

## 8. SHARED COMPONENTS (build once, reuse everywhere)
`Button` (primary / secondary / ghost / danger, sizes 32 / 36 / 40, loading state), `IconButton`, `Input`/`Textarea`/`Select` (36 px, 8 px radius, 1px `--border-strong`, focus ring 2px `--accent`), `Badge`/`StatusChip`, `Card` (1px border, 12px radius, **no shadow**), `Table`, `Tabs` (segmented), `Modal`/`Drawer` (focus trap, Esc), `Toast`, `Skeleton`, `EmptyState`, `Tooltip`, `Spinner`. Delete duplicates; no component > 300 lines; all spacing from tokens.

---

## 9. STATES, ACCESSIBILITY, RESPONSIVE
- Every list/page needs loading (skeleton), empty (message + action) and error (message + Retry) states.
- Contrast ≥ 4.5:1 for text, ≥ 3:1 for UI borders/icons. Replace `--muted #8E93B0` (fails on white).
- Visible focus ring on all interactive elements; real `<button>`/`<a>`; `aria-label` on icon buttons; `aria-live="polite"` for streaming answers; respect `prefers-reduced-motion`.
- Breakpoints: ≥ 1200 (sidebar + chat + optional viewer), 900–1199 (viewer becomes overlay drawer), < 900 (sidebar drawer, single column, composer full width). No horizontal scroll at 360 px.
- Animations: 150 ms ease only for hover/open; no bouncing, glows or pulsing.

---

## 10. IMPLEMENTATION ORDER (one commit each, screenshots after each)
1. **Scroll model** (section 1) + remove `calc(100vh …)` hacks. *Acceptance in section 1.*
2. **Tokens**: new light/dark palette, remove playful colours, switch fonts via `next/font`.
3. **Shared components** (section 8) with the new tokens.
4. **Shell + sidebar** (section 4).
5. **Research Desk** (section 5), then **Documents** (section 6).
6. Workspaces, Dashboard, Settings, Auth, public pages (section 7).
7. States, accessibility and responsive pass (section 9); run `npx playwright test` e2e and fix any selectors changed by the redesign.

**Final checklist:** one scrollbar per area · only white/blue/black (+ semantic colours) · no emoji · no hard-coded demo text · 8/12 px radii · Inter + one optional serif · every page has loading/empty/error · lint 0 warnings · build passes · e2e passes.
