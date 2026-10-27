# AURORA — Rules Document

> **Version:** 1.0  
> **Last Updated:** 2026-09-29  
> **Status:** Active  

---

## 1. Technology Rules

### ✅ MUST Use
| Technology | Version | Notes |
|-----------|---------|-------|
| Next.js (App Router) | 16.3.0 | Already installed, do NOT downgrade |
| React | 19.2.8 | Use React 19 features (use, server components) |
| TypeScript | 5.9.3 | Strict mode, no `any` types unless absolutely necessary |
| CSS Modules | — | All component styles use `.module.css` files |
| CSS Variables | — | All colors, spacing, radii via `globals.css` design tokens |
| Lucide React | 1.31.0 | Only icon library, do NOT add Font Awesome or others |
| pnpm | 11.19.0 | Package manager, do NOT use npm or yarn |
| FastAPI | 0.115.8 | Backend framework, do NOT modify backend structure |

### ❌ MUST NOT Use
| Banned | Reason |
|--------|--------|
| TailwindCSS | Project uses CSS Modules + CSS Variables design system |
| styled-components / emotion | CSS Modules are the styling solution |
| Redux / Zustand / MobX | React hooks + context are sufficient |
| Axios | Native `fetch` via existing `lib/api.ts` wrapper |
| jQuery | Unnecessary with React |
| Bootstrap / Material UI / Chakra | Custom design system, no component libraries |
| Framer Motion | Use CSS animations + `@keyframes` for all animations |
| next-auth / Auth.js | Backend already handles auth with server-side sessions |

---

## 2. Coding Standards

### TypeScript
- Enable strict mode in `tsconfig.json`
- Use `interface` for object shapes, `type` for unions/intersections
- Export types alongside components that use them
- Never use `// @ts-ignore` or `// @ts-expect-error` without a comment explaining why
- Use template literal types where they improve safety

### React Components
- Use functional components only (no class components)
- Use `"use client"` directive only when the component needs client-side interactivity
- Default to server components for static/data-fetching pages
- Name components in PascalCase: `HeroSection.tsx`
- One component per file (exception: small related sub-components)
- Always provide `displayName` for components wrapped in `forwardRef` or `memo`

### File Naming
- Components: `kebab-case.tsx` (e.g., `hero-section.tsx`)
- CSS Modules: `kebab-case.module.css` (e.g., `hero-section.module.css`)
- Hooks: `use-kebab-case.ts` (e.g., `use-auth.ts`)
- Utilities: `kebab-case.ts` (e.g., `api-errors.ts`)
- Pages: `page.tsx` (Next.js convention)
- Layouts: `layout.tsx` (Next.js convention)

---

## 3. Styling Rules

### Design Tokens
- ALL colors must come from CSS variables defined in `globals.css`
- NEVER use hardcoded hex/rgb colors in component CSS
- ALL spacing uses multiples of 4px (4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64)
- ALL border-radius uses `--radius-sm/md/lg/xl` tokens
- ALL shadows use `--shadow-soft/float` tokens

### CSS Modules
- Every component with custom styles gets its own `.module.css` file
- Use `composes` for shared styles when appropriate
- Avoid deeply nested selectors (max 2 levels)
- Use BEM-like naming within modules: `.container`, `.containerActive`
- Media queries go inside the module, not in a separate file

### Animations
- All animations use CSS `@keyframes` — no JavaScript animation libraries
- Respect `prefers-reduced-motion` — disable/reduce all animations
- Keep transitions under 300ms for UI feedback, up to 600ms for entrance animations
- Use `transform` and `opacity` for GPU-accelerated animations
- Never animate `width`, `height`, `top`, `left` — use `transform` instead

### Responsive Design
- Mobile-first approach: base styles for mobile, `@media (min-width)` for larger screens
- Breakpoints: `640px` (sm), `768px` (md), `1024px` (lg), `1280px` (xl)
- Use `clamp()` for fluid typography
- Touch targets minimum 44×44px on mobile

---

## 4. API Communication Rules

### Frontend → Backend
- ALL API calls go through `lib/api.ts` wrapper
- NEVER make raw `fetch()` calls from components
- Use the existing `/api` rewrite in `next.config.ts` — never hardcode backend URLs
- Handle ALL error states: loading, error, empty, success
- Show user-friendly error messages, never raw API errors

### Error Handling
- Catch and classify errors using `lib/api-errors.ts`
- Display errors using toast notifications or inline error banners
- Log errors to console in development only
- Never expose stack traces or internal details to users

### Streaming
- Use the existing `lib/sse.ts` parser for Server-Sent Events
- Use `lib/streaming-state.ts` state machine for streaming UI states
- Always handle: `connecting`, `streaming`, `complete`, `error`, `cancelled` states

---

## 5. Security Rules

- ❌ NEVER store secrets, API keys, or tokens in frontend code
- ❌ NEVER store auth state in localStorage or sessionStorage
- ✅ Auth is managed via HttpOnly `aurora_session` cookie (set by backend)
- ✅ Use `credentials: 'include'` on all API calls (already in `lib/api.ts`)
- ❌ NEVER trust client-side data for authorization — backend enforces all access
- ✅ Sanitize all user-generated content before rendering (XSS prevention)
- ✅ Use `rel="noopener noreferrer"` on external links

---

## 6. Performance Rules

- Use Next.js `Image` component for all images (automatic optimization)
- Lazy-load components below the fold with `React.lazy()` + `Suspense`
- Use `loading.tsx` files for route-level loading states
- Use `error.tsx` files for route-level error boundaries
- Minimize client-side JavaScript — prefer server components
- Bundle split by route — each page should be independently loadable
- Keep total initial bundle under 100KB (gzipped)

---

## 7. Accessibility Rules

- All interactive elements must be keyboard navigable
- All images must have `alt` text
- All form inputs must have associated `<label>` elements
- Use semantic HTML: `<nav>`, `<main>`, `<section>`, `<article>`, `<aside>`
- Maintain color contrast ratio ≥ 4.5:1 for body text
- Include `aria-label` on icon-only buttons
- Include skip-link (already in root layout)
- Focus indicators must be visible (already styled in globals.css)

---

## 8. Git & Documentation Rules

- Commit messages: `type(scope): description` (e.g., `feat(landing): add hero section`)
- Types: `feat`, `fix`, `style`, `refactor`, `docs`, `test`, `chore`
- Keep documentation in `docs/` up to date with every significant change
- Update `Memory.md` after completing each phase
- Never commit `.env`, `node_modules/`, `.next/`, `__pycache__/`

---

## 9. Backend Rules (Do NOT Modify)

- ❌ Do NOT modify any backend Python files unless explicitly asked
- ❌ Do NOT change database models or create new migrations
- ❌ Do NOT modify API endpoint signatures or response formats
- ❌ Do NOT change authentication or authorization logic
- ✅ The backend is considered stable and complete through v1.3
- ✅ Frontend must adapt to existing API contracts, not the other way around
