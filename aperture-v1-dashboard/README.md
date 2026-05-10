# Aperture v1 Dashboard

Three-page React app reading `/api/v3.1/...` from the Aperture observability backend.

- **Overview** — health, top meta tools by tokens, top tools by cache savings.
- **Reports** — filterable table grouping `input_tokens_contributed` by any
  supported dimension (meta_tool_slug, toolkit_slug, tool_slug, user_id,
  session_turn, model, date).
- **Schema Overlay** — accepted rewrites from the schema optimizer, original
  vs optimized side-by-side with token reduction.

## Running

```bash
# Backend (port 8002):
APERTURE_SQLITE_EVENT_LOG=./events.db \\
uvicorn aperture.observability.api_endpoints:create_api_app \\
  --factory --host 0.0.0.0 --port 8002

# Frontend (port 5180):
cd aperture-v1-dashboard
npm install
npm run dev
```

The dashboard at `http://localhost:5180` proxies `/api/v3.1/*` to
`localhost:8002`. Override the backend with `APERTURE_V1_BACKEND=...`
in the environment when running `npm run dev`.

## Why a separate directory from `frontend/`

The existing `frontend/` (14 pages) is the demo branch's UI; it's frozen
during the v1 realignment per plan decision #3. This new dashboard ships
in `aperture-v1-dashboard/` so the two never share code or build setup.
