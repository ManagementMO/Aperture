# Repository Guidelines

## Project Structure & Module Organization

This directory is the active Aperture v1 React/Vite dashboard. It is separate
from the parent repo's Python package and from the legacy `frontend/` UI.

- `src/main.tsx` wires React, `BrowserRouter`, and the three dashboard routes.
- `src/Layout.tsx` owns shared navigation and page framing.
- `src/api.ts` is the small client for `/api/v3.1/*` endpoints.
- `src/pages/Overview.tsx`, `Reports.tsx`, and `SchemaOverlay.tsx` contain the
  page-level UI.
- `index.html`, `vite.config.ts`, `tsconfig.json`, and `eslint.config.js`
  define the app shell, dev proxy, strict TypeScript, and lint rules.

## Build, Test, and Development Commands

- `npm install` installs dependencies from `package-lock.json`.
- `npm run dev` starts Vite on port `5180`.
- `APERTURE_V1_BACKEND=http://127.0.0.1:8002 npm run dev` points the dev proxy
  at a non-default backend.
- `npm run lint` runs ESLint over the dashboard.
- `npm run build` runs `tsc -b` and produces the Vite production build.
- `npm run preview` serves the built app for local smoke testing.

The backend API normally runs from the parent repo with:

```bash
uvicorn aperture.observability.api_endpoints:create_api_app \
  --factory --host 0.0.0.0 --port 8002
```

## Coding Style & Naming Conventions

Use TypeScript React with strict compiler settings. Keep components and page
files in `PascalCase` (`SchemaOverlay.tsx`), hooks/state variables in
`camelCase`, and API response types as explicit `interface`s in `src/api.ts`
when shared. Prefer existing CSS custom properties from `index.html` and the
simple inline style pattern already used in the pages. Do not add unused locals
or parameters; `tsconfig.json` rejects them.

## Testing Guidelines

No dedicated dashboard test runner is configured yet. Treat `npm run lint` and
`npm run build` as the required local verification before opening a PR. When
adding tests, keep them close to the related source as `*.test.tsx` or under a
future `src/__tests__/` directory, and add the matching npm script in
`package.json`.

## Commit & Pull Request Guidelines

Recent history uses concise scoped messages such as `fix: close final proxy docs
and dashboard lint gaps`, `docs: rewrite README to reflect actual v1-fixes
state`, and `[deep-fix-3] ...`. Follow that style: prefix with the scope or
change type, then state the visible result.

PRs should include a short summary, verification commands run, linked issue or
task when available, and screenshots or screen recordings for UI changes. Do
not commit credentials; use local environment variables such as
`APERTURE_V1_BACKEND` for configuration.
