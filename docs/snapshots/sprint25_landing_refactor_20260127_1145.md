# Sprint 25 - Landing Refactor Stabilization

**Generated:** 2026-01-27T11:45:00Z

## Current State

The dev server starts without TypeScript errors, but there are routing and configuration issues to address.

## Issues Identified

### 1. Route Direction (analyze vs analyse)
- Current: `/analyze` redirects to `/analyse`
- Required: `/analyse` should redirect to `/analyze` (English canonical)
- Affected files: `App.tsx`, `Navbar.tsx`, `DemoPage.tsx`

### 2. Missing @ Alias Configuration
- `tsconfig.app.json`: Missing `baseUrl` and `paths` for `@/*`
- `vite.config.ts`: Missing `resolve.alias` for `@`
- Status: Not causing errors yet (all imports use relative paths)

### 3. Navbar Links
- Navbar links to `/analyse` instead of `/analyze`
- DashboardPage links to `/analyze` (correct)

### 4. UI Layer Structure
- HeroVisualLayer: Already has correct z-index (`-z-10 pointer-events-none`)
- No overlay/click issues detected

## Files to Modify

1. `src/App.tsx` - Fix redirect direction
2. `src/components/layout/Navbar.tsx` - Update link to `/analyze`
3. `src/pages/DemoPage.tsx` - Update link to `/analyze`
4. `vite.config.ts` - Add @ alias
5. `tsconfig.app.json` - Add baseUrl and paths

## Test Routes

- `/` - Landing page
- `/demo` - Demo page
- `/analyze` - Analyze page (canonical)
- `/analyse` - Redirect to /analyze
- `/dashboard` - Dashboard page
- `/offres` - Offers page
- `/offer/:id` - Offer detail
- `/profile` - Profile page
- `/match` - Match page
