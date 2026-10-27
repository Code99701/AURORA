# AURORA — Design Document

> **Version:** 1.0  
> **Last Updated:** 2026-09-29  
> **Status:** Active  

---

## 1. Design Philosophy

**Bright, Colorful, Playful, and Approachable.** AURORA should feel like a friendly companion that makes research fun, not intimidating. Think: Notion's clarity meets Figma's playfulness meets Stripe's polish.

### Core Principles
1. **Inviting First Impression** — Users should feel welcomed, not overwhelmed
2. **Delightful Micro-interactions** — Small animations that bring joy to every click
3. **Color as Communication** — Vibrant colors guide attention and convey meaning
4. **Breathing Room** — Generous whitespace makes content feel organized and calm
5. **Personality** — Rounded corners, playful illustrations, friendly copy

---

## 2. Color Palette

### Light Mode (Primary)

| Token | Hex | HSL | Usage |
|-------|-----|-----|-------|
| `--background` | `#FAFBFE` | `228 50% 99%` | Page background |
| `--background-deep` | `#F0F2F8` | `228 35% 95%` | Sunken areas |
| `--surface` | `#FFFFFF` | `0 0% 100%` | Cards, panels |
| `--surface-raised` | `#F5F7FC` | `228 42% 97%` | Hover states, elevated cards |
| `--surface-glass` | `rgba(255,255,255,0.82)` | — | Glassmorphism overlays |
| `--foreground` | `#1A1D2E` | `233 28% 14%` | Primary text |
| `--foreground-soft` | `#4A4F6A` | `234 18% 35%` | Secondary text |
| `--muted` | `#8E93B0` | `234 16% 62%` | Captions, placeholders |
| `--border` | `#E2E5F0` | `230 32% 91%` | Card borders, dividers |
| `--border-strong` | `#CBD0E3` | `232 28% 84%` | Active borders |

### Accent Colors (Vibrant & Playful)

| Token | Hex | HSL | Usage |
|-------|-----|-----|-------|
| `--accent` | `#6C5CE7` | `254 75% 63%` | Primary brand — buttons, links, active states |
| `--accent-strong` | `#5A4BD1` | `254 60% 55%` | Hover states |
| `--accent-soft` | `#EDE9FE` | `254 88% 96%` | Light accent backgrounds |
| `--accent-glow` | `rgba(108,92,231,0.15)` | — | Glow effects |
| `--coral` | `#FF6B6B` | `0 100% 71%` | Warm accent — alerts, highlights |
| `--coral-soft` | `#FFF0F0` | `0 100% 97%` | Light coral backgrounds |
| `--teal` | `#00D2D3` | `180 100% 41%` | Cool accent — success, progress |
| `--teal-soft` | `#E0FAFA` | `180 76% 93%` | Light teal backgrounds |
| `--amber` | `#FECA57` | `45 99% 67%` | Warm highlight — warnings, stars |
| `--amber-soft` | `#FFF9E6` | `45 100% 95%` | Light amber backgrounds |
| `--pink` | `#FF9FF3` | `308 100% 81%` | Playful accent — decorative elements |
| `--pink-soft` | `#FFF0FC` | `308 100% 97%` | Light pink backgrounds |

### Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--success` | `#00B894` | Success states, completed |
| `--warning` | `#FDCB6E` | Warning states, processing |
| `--danger` | `#E17055` | Error states, destructive actions |
| `--info` | `#74B9FF` | Informational states |

### Dark Mode

| Token | Hex | Usage |
|-------|-----|-------|
| `--background` | `#0F0F1A` | Deep dark page background |
| `--background-deep` | `#0A0A14` | Sunken areas |
| `--surface` | `#1A1A2E` | Cards, panels |
| `--surface-raised` | `#222240` | Hover states |
| `--surface-glass` | `rgba(26,26,46,0.85)` | Glassmorphism overlays |
| `--foreground` | `#F0F0F8` | Primary text |
| `--foreground-soft` | `#B8B8D0` | Secondary text |
| `--muted` | `#7E7E9A` | Captions |
| `--border` | `#2D2D4A` | Card borders |
| `--border-strong` | `#3D3D5C` | Active borders |
| `--accent` | `#A29BFE` | Lightened accent for dark mode |
| `--accent-strong` | `#C4BFFF` | Hover accent |

---

## 3. Typography

### Font Stack

| Purpose | Font | Fallbacks | Weight |
|---------|------|-----------|--------|
| **Primary (UI)** | Inter | "Segoe UI Variable", "Segoe UI", -apple-system, sans-serif | 400, 500, 600, 700 |
| **Display (Headlines)** | Outfit | "Segoe UI", sans-serif | 600, 700, 800 |
| **Editorial (Accent)** | Newsreader | "Palatino Linotype", Georgia, serif | 400, 500 (italic) |
| **Monospace (Code)** | JetBrains Mono | "Cascadia Code", "Fira Code", monospace | 400, 500 |

### Type Scale

| Name | Size | Line Height | Weight | Usage |
|------|------|-------------|--------|-------|
| `--text-xs` | `0.75rem` (12px) | 1.5 | 500 | Badges, captions |
| `--text-sm` | `0.875rem` (14px) | 1.5 | 400 | Helper text, metadata |
| `--text-base` | `1rem` (16px) | 1.6 | 400 | Body text |
| `--text-lg` | `1.125rem` (18px) | 1.55 | 500 | Emphasized body |
| `--text-xl` | `1.25rem` (20px) | 1.4 | 600 | Section titles |
| `--text-2xl` | `1.5rem` (24px) | 1.35 | 600 | Card headings |
| `--text-3xl` | `1.875rem` (30px) | 1.3 | 700 | Page titles |
| `--text-4xl` | `2.25rem` (36px) | 1.2 | 700 | Hero sub-headings |
| `--text-5xl` | `3rem` (48px) | 1.1 | 800 | Hero headlines |
| `--text-6xl` | `3.75rem` (60px) | 1.05 | 800 | Landing splash |

### Fluid Typography (Landing Page)
```css
/* Hero headline scales between 36px (mobile) and 60px (desktop) */
font-size: clamp(2.25rem, 5vw + 1rem, 3.75rem);
```

---

## 4. Spacing System

Based on 4px grid:

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | `4px` | Tight gaps |
| `--space-2` | `8px` | Icon gaps, badge padding |
| `--space-3` | `12px` | Small padding |
| `--space-4` | `16px` | Default padding, component gaps |
| `--space-5` | `20px` | Card padding |
| `--space-6` | `24px` | Section padding |
| `--space-8` | `32px` | Large section gaps |
| `--space-10` | `40px` | Page section spacing |
| `--space-12` | `48px` | Large page sections |
| `--space-16` | `64px` | Hero section padding |
| `--space-20` | `80px` | Page-level vertical rhythm |
| `--space-24` | `96px` | Landing section spacing |

---

## 5. Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | `8px` | Small buttons, badges |
| `--radius-md` | `12px` | Inputs, cards |
| `--radius-lg` | `18px` | Large cards, panels |
| `--radius-xl` | `24px` | Modals, hero sections |
| `--radius-2xl` | `32px` | Landing feature cards |
| `--radius-full` | `999px` | Pills, avatars |

---

## 6. Shadows

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-xs` | `0 1px 2px rgba(26,29,46,0.05)` | Subtle elevation |
| `--shadow-sm` | `0 2px 8px rgba(26,29,46,0.08)` | Card resting state |
| `--shadow-md` | `0 8px 24px rgba(26,29,46,0.10)` | Card hover |
| `--shadow-lg` | `0 16px 48px rgba(26,29,46,0.12)` | Floating panels |
| `--shadow-xl` | `0 24px 64px rgba(26,29,46,0.16)` | Modals, dropdowns |
| `--shadow-glow` | `0 0 40px var(--accent-glow)` | Accent glow effect |

---

## 7. Animation System

### Easing Curves
| Token | Value | Usage |
|-------|-------|-------|
| `--ease-out` | `cubic-bezier(0.16, 1, 0.3, 1)` | Exit/slide out |
| `--ease-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` | Transitions |
| `--ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Bouncy/playful entrances |
| `--ease-smooth` | `cubic-bezier(0.4, 0, 0.2, 1)` | Subtle transitions |

### Duration Scale
| Token | Value | Usage |
|-------|-------|-------|
| `--duration-fast` | `120ms` | Hover feedback |
| `--duration-normal` | `200ms` | Button/input transitions |
| `--duration-slow` | `350ms` | Panel transitions |
| `--duration-entrance` | `500ms` | Entrance animations |
| `--duration-dramatic` | `800ms` | Landing page entrances |

### Standard Animations

```css
/* Fade in from below */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Fade in with scale */
@keyframes fadeInScale {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

/* Slide in from left */
@keyframes slideInLeft {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}

/* Gentle float */
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

/* Gradient shift */
@keyframes gradientShift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

/* Pulse glow */
@keyframes pulseGlow {
  0%, 100% { box-shadow: 0 0 20px var(--accent-glow); }
  50% { box-shadow: 0 0 40px var(--accent-glow); }
}

/* Skeleton loading shimmer */
@keyframes shimmer {
  to { background-position-x: -200%; }
}

/* Bounce in */
@keyframes bounceIn {
  0% { opacity: 0; transform: scale(0.3); }
  50% { opacity: 1; transform: scale(1.05); }
  70% { transform: scale(0.9); }
  100% { transform: scale(1); }
}
```

### Scroll-Triggered Entrances
- Elements below the fold use `IntersectionObserver` to trigger `fadeInUp`
- Stagger child elements with `animation-delay: calc(var(--index) * 80ms)`
- Hero section: immediate entrance, no scroll trigger

---

## 8. Component Design Patterns

### Buttons
- **Primary:** Gradient purple background (`--accent`), white text, glow shadow on hover
- **Secondary:** White/surface background, accent border, accent text
- **Ghost:** Transparent, subtle hover background
- **Danger:** Coral tint background, coral text
- All buttons: `border-radius: --radius-md`, min-height 44px, playful scale on active

### Cards
- White/surface background with subtle border
- `--shadow-sm` resting, `--shadow-md` on hover with slight `translateY(-2px)`
- Rounded corners `--radius-lg` to `--radius-2xl`
- Optional accent gradient top border (2-3px)

### Inputs
- Surface-raised background, subtle border
- Accent border on focus with glow ring
- Smooth transition on all state changes
- Clear placeholder text with muted color

### Modals
- Centered with backdrop blur
- Entrance: `fadeInScale` with spring easing
- Exit: fade out + scale down
- Max-width 520px, generous padding

### Navigation
- **Public Navbar:** Glassmorphism, sticky, animated logo, CTA button
- **App Sidebar:** Collapsible, icon + label navigation, active state with accent background

---

## 9. Iconography

Using **Lucide React** exclusively (already installed):
- Stroke width: 1.75 (slightly thinner than default for elegance)
- Default size: 20px (UI), 24px (navigation), 32-48px (feature cards)
- Color: Inherits from parent `color` property
- Feature card icons get colorful circular backgrounds

---

## 10. Responsive Breakpoints

| Breakpoint | Width | Layout Changes |
|------------|-------|----------------|
| **Mobile** | < 640px | Single column, hamburger menu, stacked cards |
| **Tablet** | 640-1023px | 2-column grids, collapsible sidebar |
| **Desktop** | 1024-1279px | Full layout, expanded sidebar |
| **Wide** | ≥ 1280px | Max-width containers, comfortable spacing |

### Container Widths
| Context | Max-Width |
|---------|-----------|
| Marketing pages | `1200px` |
| App content area | `1120px` |
| Auth pages | `520px` (card) |
| Chat interface | `860px` (message area) |

---

## 11. Dark Mode Strategy

- Theme toggle in navbar (public) and app header (authenticated)
- Persist choice in `localStorage` as `aurora-theme`
- Respect `prefers-color-scheme` as default
- No flash on load (theme script in `<head>`)
- All colors switch via CSS variable overrides on `html[data-theme="dark"]`
- Accent colors get lightened for better contrast on dark backgrounds
- Shadows get darker and more diffused
- Gradients shift to darker, more saturated versions

---

## 12. Landing Page Visual Concept

```
┌────────────────────────────────────────────────────────────────┐
│ [NAVBAR] AURORA logo | Features | About | Contact | [Sign In] │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│     ★ HERO SECTION ★                                           │
│     Large gradient headline: "Research Made Magical"           │
│     Subtitle with typing animation                             │
│     [Get Started Free] [See How It Works]                      │
│     Floating illustration with document/AI elements            │
│     Animated gradient orbs in background                       │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│     ★ FEATURE CARDS (3-column grid) ★                          │
│     📄 Multi-Format Upload | 🔍 Smart Search | 💬 AI Chat      │
│     🌍 Multilingual      | 📎 Citations    | 🔒 Secure        │
│     Each with icon, title, description, hover lift             │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│     ★ HOW IT WORKS (horizontal stepper) ★                      │
│     1. Upload → 2. Process → 3. Ask → 4. Discover              │
│     Connected with animated lines/dots                         │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│     ★ TESTIMONIALS ★                                           │
│     Carousel of quote cards with avatars                       │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│     ★ CTA SECTION ★                                            │
│     "Ready to Transform Your Research?"                        │
│     [Start Free Now] — gradient background, floating shapes    │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ [FOOTER] Links | Social | Copyright                            │
└────────────────────────────────────────────────────────────────┘
```
